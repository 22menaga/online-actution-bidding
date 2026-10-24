"""Admin-controlled auction scheduling.

Auctions run 24/7 for buyers once LIVE, but *when* they run is decided only by an admin.
Every allocation goes through allocate() so the same rules apply to first-time approval and rescheduling.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from audit.services import record_audit
from notifications.services import notify_user
from .models import Auction


def concurrent_count(start, end, exclude_pk=None):
    qs = Auction.objects.filter(status__in=['SCHEDULED', 'LIVE'], start_at__lt=end, end_at__gt=start)
    return qs.exclude(pk=exclude_pk).count() if exclude_pk else qs.count()


def validate_window(start, end, exclude_pk=None):
    now = timezone.now()
    if end <= start:
        raise ValidationError({'end_at': 'End time must be after start time.'})
    if start < now - timedelta(minutes=2):
        raise ValidationError({'start_at': 'Start time cannot be in the past.'})
    if end - start < timedelta(minutes=settings.AUCTION_MIN_DURATION_MINUTES):
        raise ValidationError({'end_at': f'An auction must run for at least {settings.AUCTION_MIN_DURATION_MINUTES} minutes.'})
    if end - start > timedelta(days=settings.AUCTION_MAX_DURATION_DAYS):
        raise ValidationError({'end_at': f'An auction cannot run longer than {settings.AUCTION_MAX_DURATION_DAYS} days.'})
    if concurrent_count(start, end, exclude_pk) >= settings.AUCTION_MAX_CONCURRENT:
        raise ValidationError({'start_at': f'That window is full ({settings.AUCTION_MAX_CONCURRENT} auctions already scheduled). Choose another time.'})


@transaction.atomic
def allocate(auction_id, admin, start, end, note=''):
    """Approve a pending auction OR reschedule a scheduled one (only while it has no bids)."""
    a = Auction.objects.select_for_update(of=('self',)).select_related('product', 'seller').get(pk=auction_id)
    if a.status not in (Auction.Status.PENDING, Auction.Status.SCHEDULED):
        raise ValidationError('Only pending or scheduled auctions can be allocated a time.')
    if a.bid_count:
        raise ValidationError('This auction already has bids, so its schedule can no longer be changed.')
    validate_window(start, end, exclude_pk=a.pk)
    first_time = a.status == Auction.Status.PENDING
    a.start_at, a.end_at = start, end
    a.status = Auction.Status.SCHEDULED
    a.admin_note = (note or '')[:500]
    a.scheduled_by, a.scheduled_at = admin, timezone.now()
    a.save(update_fields=['start_at', 'end_at', 'status', 'admin_note', 'scheduled_by', 'scheduled_at', 'updated_at'])
    a.product.status = 'AUCTION'
    a.product.save(update_fields=['status', 'updated_at'])
    record_audit(admin, 'AUCTION_APPROVED' if first_time else 'AUCTION_RESCHEDULED', a,
                 {'start_at': start.isoformat(), 'end_at': end.isoformat(), 'requested_24_7': a.is_24_7})
    verb = 'approved and scheduled' if first_time else 'rescheduled'
    notify_user(a.seller, 'Auction scheduled', f'{a.product.name} was {verb} by an admin: {timezone.localtime(start):%d %b %Y %H:%M} to {timezone.localtime(end):%d %b %Y %H:%M}.')
    return a


@transaction.atomic
def reject(auction_id, admin, reason):
    a = Auction.objects.select_for_update(of=('self',)).select_related('product', 'seller').get(pk=auction_id)
    if a.status != Auction.Status.PENDING:
        raise ValidationError('Only pending auctions can be rejected.')
    if not (reason or '').strip():
        raise ValidationError({'reason': 'Please give the seller a reason.'})
    a.status = Auction.Status.CANCELLED
    a.admin_note = reason.strip()[:500]
    a.save(update_fields=['status', 'admin_note', 'updated_at'])
    record_audit(admin, 'AUCTION_REJECTED', a, {'reason': a.admin_note})
    notify_user(a.seller, 'Auction not approved', f'{a.product.name}: {a.admin_note}')
    return a
