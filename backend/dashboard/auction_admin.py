"""Admin-only views: every auction with everything an admin needs to understand what happened (selling + bidding)."""
from django.db.models import Count, Q, Sum
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin
from audit.models import AuditLog
from auctions.models import Auction, ScheduleRequest, Watch
from bidding.models import Bid
from payments.models import Payment


class AuctionPage(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


ORDERING = {'created_at', '-created_at', 'end_at', '-end_at', 'current_highest_bid', '-current_highest_bid', 'bid_count', '-bid_count'}


def _row(a, payments):
    p = payments.get(a.id)
    return {
        'id': a.id, 'product_name': a.product.name, 'category': a.product.category.name, 'image': next((i.image.url for i in a.product.images.all()), None),
        'seller': a.seller.username, 'status': a.status, 'start_at': a.start_at, 'end_at': a.end_at, 'created_at': a.created_at,
        'starting_price': a.starting_price, 'current_highest_bid': a.current_highest_bid, 'bid_count': a.bid_count, 'unique_bidders': a.unique_bidders,
        'leader': a.current_highest_bidder.username if a.current_highest_bidder_id else None,
        'winner': a.winner.username if a.winner_id else None,
        'payment_status': p.status if p else None, 'is_24_7': a.is_24_7,
    }


class AdminAuctionListView(APIView):
    """GET /api/dashboard/auctions/?status=&q=&ordering=&page="""
    permission_classes = [IsAdmin]

    def get(self, request):
        qs = (Auction.objects.select_related('product', 'product__category', 'seller', 'current_highest_bidder', 'winner')
              .prefetch_related('product__images').annotate(unique_bidders=Count('bids__bidder', distinct=True)))
        status = request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(product__name__icontains=q) | Q(seller__username__icontains=q))
        ordering = request.query_params.get('ordering', '-created_at')
        qs = qs.order_by(ordering if ordering in ORDERING else '-created_at', '-id')
        page = AuctionPage()
        rows = page.paginate_queryset(qs, request)
        payments = {p.auction_id: p for p in Payment.objects.filter(auction_id__in=[a.id for a in rows])}
        return page.get_paginated_response([_row(a, payments) for a in rows])


class AdminAuctionSummaryView(APIView):
    """Counts and money across all auctions, for the header of the All-auctions tab."""
    permission_classes = [IsAdmin]

    def get(self, request):
        by_status = dict(Auction.objects.values_list('status').annotate(n=Count('id')))
        sold_value = Auction.objects.filter(status='SOLD').aggregate(t=Sum('current_highest_bid'))['t'] or 0
        paid = Payment.objects.filter(status='SUCCESS').aggregate(t=Sum('amount'))['t'] or 0
        return Response({
            'by_status': by_status, 'total': sum(by_status.values()), 'total_bids': Bid.objects.count(),
            'sold_value': sold_value, 'paid_value': paid,
            'unpaid_sold': Payment.objects.filter(status__in=['PENDING', 'PROCESSING']).count(),
        })


class AdminAuctionDetailView(APIView):
    """GET /api/dashboard/auctions/<id>/ - the whole story of one auction. Real usernames are shown (admin only)."""
    permission_classes = [IsAdmin]

    def get(self, request, pk):
        a = (Auction.objects.select_related('product', 'product__category', 'product__ai_estimate', 'seller', 'seller__seller_profile', 'current_highest_bidder', 'winner', 'scheduled_by')
             .prefetch_related('product__images').filter(pk=pk).first())
        if a is None:
            return Response({'detail': 'Not found.'}, status=404)
        product, seller = a.product, a.seller
        profile = getattr(seller, 'seller_profile', None)

        bids = list(Bid.objects.filter(auction=a).select_related('bidder').order_by('created_at'))
        history, prev = [], None
        for b in bids:
            history.append({'id': b.id, 'bidder_id': b.bidder_id, 'bidder': b.bidder.username, 'amount': b.amount, 'increase': (b.amount - prev) if prev is not None else None, 'at': b.created_at,
                            'is_leader': b.bidder_id == a.current_highest_bidder_id and b.amount == a.current_highest_bid})
            prev = b.amount
        per_bidder = {}
        for b in bids:
            d = per_bidder.setdefault(b.bidder.username, {'id': b.bidder_id, 'bidder': b.bidder.username, 'email': b.bidder.email, 'bids': 0, 'highest': b.amount, 'first_bid_at': b.created_at})
            d['bids'] += 1
            d['highest'] = max(d['highest'], b.amount)
        bidders = sorted(per_bidder.values(), key=lambda d: -d['highest'])

        pay = Payment.objects.filter(auction=a).select_related('buyer').first()
        est = product.ai_estimate.data if product.ai_estimate_id and product.ai_estimate.data.get('sellable') else None
        timeline = [{'action': e.action, 'actor': e.actor.username if e.actor else None, 'at': e.created_at, 'meta': e.metadata}
                    for e in AuditLog.objects.filter(object_type='Auction', object_id=str(a.pk)).select_related('actor').order_by('created_at')]
        suggestions = [{'by': s.requester.username, 'role': s.requester.role, 'preferred_start': s.preferred_start, 'preferred_end': s.preferred_end, 'note': s.note, 'status': s.status, 'at': s.created_at}
                       for s in ScheduleRequest.objects.filter(auction=a).select_related('requester')]
        seller_history = Auction.objects.filter(seller=seller).exclude(pk=a.pk)

        return Response({
            'id': a.id, 'status': a.status, 'is_24_7': a.is_24_7, 'created_at': a.created_at, 'closed_at': a.closed_at,
            'product': {'name': product.name, 'category': product.category.name, 'condition': product.condition, 'description': product.description,
                        'reference_price': product.starting_price, 'images': [i.image.url for i in product.images.all()], 'status': product.status},
            'pricing': {'starting_price': a.starting_price, 'min_increment': a.min_increment, 'current_highest_bid': a.current_highest_bid, 'required_minimum': a.required_minimum(),
                        'bid_count': a.bid_count, 'unique_bidders': len(bidders), 'watchers': Watch.objects.filter(auction=a).count()},
            'ai_estimate': ({k: est.get(k) for k in ('item_name', 'estimated_low', 'estimated_high', 'estimated_mid', 'suggested_start_price', 'currency', 'confidence', 'risks', 'value_drivers')} if est else None),
            'schedule': {'requested_start_at': a.requested_start_at, 'requested_end_at': a.requested_end_at, 'seller_note': a.seller_note, 'start_at': a.start_at, 'end_at': a.end_at,
                         'admin_note': a.admin_note, 'scheduled_by': a.scheduled_by.username if a.scheduled_by_id else None, 'scheduled_at': a.scheduled_at},
            'seller': {'id': seller.id, 'username': seller.username, 'email': seller.email, 'joined': seller.created_at, 'business_name': getattr(profile, 'business_name', ''),
                       'verified': bool(profile and profile.approved), 'other_auctions': seller_history.count(), 'other_sold': seller_history.filter(status='SOLD').count()},
            'leader': a.current_highest_bidder.username if a.current_highest_bidder_id else None, 'leader_id': a.current_highest_bidder_id,
            'winner': a.winner.username if a.winner_id else None, 'winner_id': a.winner_id,
            'bids': history, 'bidders': bidders,
            'payment': ({'id': pay.id, 'status': pay.status, 'amount': pay.amount, 'provider': pay.provider, 'reference': pay.transaction_reference, 'buyer': pay.buyer.username,
                         'created_at': pay.created_at, 'paid_at': pay.paid_at} if pay else None),
            'time_suggestions': suggestions, 'timeline': timeline,
        })
