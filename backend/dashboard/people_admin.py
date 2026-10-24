"""Admin-only views of the people on the platform: every seller and bidder with their full selling / bidding history."""
from django.db.models import Count, Q, Sum
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import SellerVerification, User
from accounts.permissions import IsAdmin
from audit.models import AuditLog
from audit.services import record_audit
from auctions.models import Auction, Watch
from bidding.models import Bid
from notifications.services import notify_user
from payments import wallet
from payments.models import Payment
from products.models import Product


class PeoplePage(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _profile(u):
    p = getattr(u, 'seller_profile', None) if u.role == 'SELLER' else getattr(u, 'buyer_profile', None) if u.role == 'BUYER' else None
    if p is None:
        return {}
    d = {'phone': p.phone, 'address': p.address}
    if u.role == 'SELLER':
        d.update({'business_name': p.business_name, 'approved': p.approved, 'verified': p.verified, 'rejection_reason': p.rejection_reason})
    return d


class AdminPeopleListView(APIView):
    """GET /api/dashboard/people/?role=SELLER|BUYER&state=suspended|unverified&q=&page="""
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = (User.objects.exclude(role='ADMIN').select_related('seller_profile', 'buyer_profile')
              .annotate(bids_n=Count('bids', distinct=True), listings_n=Count('auctions', distinct=True),
                        sold_n=Count('auctions', filter=Q(auctions__status='SOLD'), distinct=True), wins_n=Count('won_auctions', distinct=True)))
        role = request.query_params.get('role')
        if role in ('SELLER', 'BUYER'):
            qs = qs.filter(role=role)
        state = request.query_params.get('state')
        if state == 'suspended':
            qs = qs.filter(is_suspended=True)
        elif state == 'unverified':
            qs = qs.filter(Q(email_verified=False) | Q(role='SELLER', seller_profile__approved=False))
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
        page = PeoplePage()
        rows = page.paginate_queryset(qs.order_by('-created_at', '-id'), request)
        return page.get_paginated_response([{
            'id': u.id, 'username': u.username, 'email': u.email, 'role': u.role, 'joined': u.created_at, 'last_login': u.last_login,
            'email_verified': u.email_verified, 'is_suspended': u.is_suspended,
            'seller_verified': bool(getattr(getattr(u, 'seller_profile', None), 'approved', False)) if u.role == 'SELLER' else None,
            'listings': u.listings_n if u.role == 'SELLER' else None, 'sold': u.sold_n if u.role == 'SELLER' else None,
            'bids': u.bids_n if u.role == 'BUYER' else None, 'wins': u.wins_n if u.role == 'BUYER' else None,
        } for u in rows])


class AdminPersonDetailView(APIView):
    """GET /api/dashboard/people/<id>/ - everything about one seller or bidder."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        u = User.objects.select_related('seller_profile', 'buyer_profile').filter(pk=pk).exclude(role='ADMIN').first()
        if u is None:
            return Response({'detail': 'Not found.'}, status=404)
        data = {
            'id': u.id, 'username': u.username, 'email': u.email, 'role': u.role, 'joined': u.created_at, 'last_login': u.last_login,
            'email_verified': u.email_verified, 'is_suspended': u.is_suspended, 'profile': _profile(u),
            'watchlist': Watch.objects.filter(user=u).count(),
            'wallet': {'balance': wallet.wallet_for(u).balance, 'transactions': [{'kind': t.kind, 'amount': t.amount, 'balance_after': t.balance_after, 'description': t.description, 'at': t.created_at} for t in wallet.wallet_for(u).transactions.all()[:15]]},
            'security': [{'action': e.action, 'at': e.created_at, 'object': f'{e.object_type} {e.object_id}'.strip(), 'ip': e.ip_address}
                         for e in AuditLog.objects.filter(actor=u).order_by('-created_at')[:15]],
        }
        pay_by_auction = {p.auction_id: p for p in Payment.objects.filter(auction__seller=u)} if u.role == 'SELLER' else {}
        if u.role == 'SELLER':
            auctions = list(Auction.objects.filter(seller=u).select_related('product', 'winner').order_by('-created_at'))
            sold = [a for a in auctions if a.status == 'SOLD']
            verifs = SellerVerification.objects.filter(seller__user=u).order_by('-created_at')
            data['selling'] = {
                'totals': {'listed': len(auctions), 'live': sum(a.status == 'LIVE' for a in auctions), 'pending': sum(a.status == 'PENDING_APPROVAL' for a in auctions),
                           'sold': len(sold), 'unsold': sum(a.status == 'UNSOLD' for a in auctions), 'cancelled': sum(a.status == 'CANCELLED' for a in auctions),
                           'sales_value': sum((a.current_highest_bid or 0) for a in sold),
                           'paid_value': sum((p.amount for p in pay_by_auction.values() if p.status == 'SUCCESS'), 0), 'total_bids_received': sum(a.bid_count for a in auctions)},
                'verifications': [{'legal_name': v.legal_name, 'document_type': v.document_type, 'document_reference': v.document_reference, 'status': v.status, 'notes': v.notes, 'submitted': v.created_at, 'reviewed': v.reviewed_at} for v in verifs],
                'products': [{'id': p.id, 'name': p.name, 'status': p.status, 'reference_price': p.starting_price, 'category': p.category.name,
                              'ai_low': (p.ai_estimate.data.get('estimated_low') if p.ai_estimate_id else None), 'ai_high': (p.ai_estimate.data.get('estimated_high') if p.ai_estimate_id else None)}
                             for p in Product.objects.filter(seller=u).select_related('category', 'ai_estimate').order_by('-created_at')],
                'auctions': [{'id': a.id, 'name': a.product.name, 'status': a.status, 'starting_price': a.starting_price, 'current_bid': a.current_highest_bid, 'bids': a.bid_count,
                              'winner': a.winner.username if a.winner_id else None, 'payment_status': pay_by_auction[a.id].status if a.id in pay_by_auction else None, 'end_at': a.end_at} for a in auctions],
            }
        if u.role == 'BUYER':
            bids = list(Bid.objects.filter(bidder=u).select_related('auction', 'auction__product').order_by('-created_at'))
            won = list(Auction.objects.filter(winner=u).select_related('product').order_by('-closed_at'))
            leading = Auction.objects.filter(current_highest_bidder=u, status='LIVE').select_related('product')
            pays = list(Payment.objects.filter(buyer=u).select_related('auction__product').order_by('-created_at'))
            sums = lambda st: sum((p.amount for p in pays if p.status in st), 0)
            data['bidding'] = {
                'totals': {'bids': len(bids), 'auctions_bid_on': len({b.auction_id for b in bids}), 'wins': len(won), 'leading_now': leading.count(),
                           'paid': sums(('SUCCESS',)), 'unpaid': sums(('PENDING', 'PROCESSING')), 'failed_payments': sum(p.status == 'FAILED' for p in pays)},
                'leading_now': [{'id': a.id, 'name': a.product.name, 'bid': a.current_highest_bid, 'end_at': a.end_at} for a in leading],
                'wins': [{'id': a.id, 'name': a.product.name, 'price': a.current_highest_bid, 'closed_at': a.closed_at} for a in won],
                'payments': [{'id': p.id, 'auction': p.auction_id, 'name': p.auction.product.name, 'amount': p.amount, 'status': p.status, 'provider': p.provider, 'reference': p.transaction_reference, 'created': p.created_at, 'paid_at': p.paid_at} for p in pays],
                'recent_bids': [{'auction': b.auction_id, 'name': b.auction.product.name, 'amount': b.amount, 'at': b.created_at, 'auction_status': b.auction.status} for b in bids[:25]],
            }
        return Response(data)


class AdminPersonSuspendView(APIView):
    """POST /api/dashboard/people/<id>/suspend/  {suspended: true|false, reason?}. Suspended users cannot bid, list or pay."""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        u = User.objects.filter(pk=pk).exclude(role='ADMIN').first()
        if u is None:
            return Response({'detail': 'Not found.'}, status=404)
        suspend = bool(request.data.get('suspended', True))
        reason = str(request.data.get('reason', '')).strip()[:300]
        if suspend and not reason:
            return Response({'detail': 'Please give a reason (it is kept in the audit log).'}, status=400)
        u.is_suspended = suspend
        u.save(update_fields=['is_suspended'])
        record_audit(request.user, 'USER_SUSPENDED' if suspend else 'USER_RESTORED', u, {'reason': reason})
        notify_user(u, 'Account suspended' if suspend else 'Account restored', reason if suspend else 'Your account has been restored. You can use the marketplace again.')
        return Response({'id': u.id, 'is_suspended': u.is_suspended})
