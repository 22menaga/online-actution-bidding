from datetime import timedelta
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdmin
from auctions.models import Auction
from bidding.models import Bid
from payments.models import Payment
from products.models import Product


class AnalyticsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(
            {
                "users": User.objects.count(),
                "buyers": User.objects.filter(role="BUYER").count(),
                "sellers": User.objects.filter(role="SELLER").count(),
                "pending_seller_verifications": User.objects.filter(
                    role="SELLER", seller_profile__approved=False
                ).count(),
                "pending_products": Product.objects.filter(status="PENDING_APPROVAL").count(),
                "pending_auctions": Auction.objects.filter(status="PENDING_APPROVAL").count(),
                "live_auctions": Auction.objects.filter(status="LIVE").count(),
                "scheduled_auctions": Auction.objects.filter(status="SCHEDULED").count(),
                "bids": Bid.objects.count(),
                "completed_auctions": Auction.objects.filter(status__in=["SOLD", "UNSOLD"]).count(),
                "successful_payments": Payment.objects.filter(status="SUCCESS").count(),
                "failed_payments": Payment.objects.filter(status="FAILED").count(),
                "gross_successful_payments": Payment.objects.filter(status="SUCCESS").aggregate(
                    total=Sum("amount")
                )["total"]
                or 0,
            }
        )


class AdminOverviewView(APIView):
    """One call for the admin console: queue, security signals, money and recent activity."""
    permission_classes = [IsAdmin]

    def get(self, request):
        from audit.models import AuditLog
        from auctions.models import ScheduleRequest
        now = timezone.now()
        day, ten = now - timedelta(hours=24), now - timedelta(minutes=10)

        # Security signals an admin should look at.
        fast_bidders = (
            Bid.objects.filter(created_at__gte=ten).values("bidder__username", "bidder_id")
            .annotate(n=Count("id")).filter(n__gte=15).order_by("-n")[:10]
        )
        failed_payers = (
            Payment.objects.filter(status="FAILED", created_at__gte=now - timedelta(days=7))
            .values("buyer__username", "buyer_id").annotate(n=Count("id")).filter(n__gte=2).order_by("-n")[:10]
        )
        from payments.provider_status import provider_status
        return Response({
            "config": {"payments": provider_status()},
            "queue": {
                "pending_auctions": Auction.objects.filter(status="PENDING_APPROVAL").count(),
                "pending_products": Product.objects.filter(status="PENDING_APPROVAL").count(),
                "pending_seller_verifications": User.objects.filter(role="SELLER", seller_profile__approved=False).count(),
                "open_time_requests": ScheduleRequest.objects.filter(status="OPEN").count(),
            },
            "platform": {
                "live_now": Auction.objects.filter(status="LIVE").count(),
                "scheduled": Auction.objects.filter(status="SCHEDULED").count(),
                "ending_within_hour": Auction.objects.filter(status="LIVE", end_at__lte=now + timedelta(hours=1)).count(),
                "bids_24h": Bid.objects.filter(created_at__gte=day).count(),
                "users": User.objects.count(),
                "new_users_24h": User.objects.filter(created_at__gte=day).count(),
            },
            "security": {
                "unverified_emails": User.objects.filter(email_verified=False).count(),
                "suspended_users": User.objects.filter(is_suspended=True).count(),
                "unverified_sellers": User.objects.filter(role="SELLER", seller_profile__verified=False).count(),
                "rapid_bidders": list(fast_bidders),
                "repeat_failed_payers": list(failed_payers),
                "admin_actions_24h": AuditLog.objects.filter(created_at__gte=day, actor__role="ADMIN").count(),
            },
            "money": {
                "gross_paid": Payment.objects.filter(status="SUCCESS").aggregate(t=Sum("amount"))["t"] or 0,
                "awaiting_payment": Payment.objects.filter(status__in=["PENDING", "PROCESSING"]).aggregate(t=Sum("amount"))["t"] or 0,
                "failed_payments": Payment.objects.filter(status="FAILED").count(),
            },
            "recent_activity": [
                {"id": e.id, "action": e.action, "actor": e.actor.username if e.actor else None, "object": f"{e.object_type} {e.object_id}".strip(), "at": e.created_at}
                for e in AuditLog.objects.select_related("actor")[:20]
            ],
        })
