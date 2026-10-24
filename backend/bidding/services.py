import logging

from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from accounts.masking import mask_username
from .models import Bid
from auctions.models import Auction
from notifications.services import notify_user
from audit.services import record_audit
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def broadcast_bid(group, event):
    try:
        async_to_sync(get_channel_layer().group_send)(group, event)
    except Exception:
        logger.exception('Unable to broadcast bid update to channel group %s.', group)


def broadcast_status(auction_id, status, winner=None, price=None):
    """Tell everyone watching that an auction went LIVE or closed (so no refresh is needed)."""
    from accounts.masking import mask_username
    broadcast_bid(f'auction_{auction_id}', {'type': 'bid.update', 'data': {'event': 'status', 'status': status, 'winner': mask_username(winner) if winner else None, 'price': str(price) if price is not None else None}})


@transaction.atomic
def place_bid(*, auction_id, bidder, amount, client_reference=None, confirm_large=False):
    a=Auction.objects.select_for_update(of=('self',)).select_related('seller','current_highest_bidder','product').get(pk=auction_id)
    now=timezone.now()
    if not bidder.can_transact(): raise PermissionDenied('Account is not eligible to bid.')
    if bidder.role!='BUYER': raise PermissionDenied('Only bidder accounts can place bids. Sign in with your bidder profile.')
    if a.status!='LIVE' or now>=a.end_at: raise ValidationError('Auction is not accepting bids.')
    if a.seller_id==bidder.id: raise PermissionDenied('Seller cannot bid on own auction.')
    if a.current_highest_bidder_id==bidder.id: raise ValidationError('You are already the highest bidder.')
    if amount < a.required_minimum(): raise ValidationError({'amount':f'Minimum acceptable bid is {a.required_minimum()}.'})
    # Typo guard: a bid far above the current price (an extra zero) must be explicitly confirmed by the client.
    base=a.current_highest_bid if a.current_highest_bid is not None else a.starting_price
    if not confirm_large and amount > base*settings.BID_LARGE_MULTIPLIER: raise ValidationError({'amount':f'This bid is more than {settings.BID_LARGE_MULTIPLIER}x the current price. Please confirm it.','code':'confirm_large_bid'})
    if client_reference and Bid.objects.filter(auction=a,client_reference=client_reference).exists(): raise ValidationError('Duplicate bid reference.')
    previous=a.current_highest_bidder
    bid=Bid.objects.create(auction=a,bidder=bidder,amount=amount,client_reference=client_reference)
    a.current_highest_bid=amount; a.current_highest_bidder=bidder; a.bid_count=a.bid_count+1
    # Anti-sniping: a bid inside the closing window pushes the end time out so others can respond.
    extended=False
    window=timedelta(seconds=settings.ANTI_SNIPE_WINDOW_SECONDS)
    if a.end_at-now<=window:
        a.end_at=now+timedelta(seconds=settings.ANTI_SNIPE_EXTENSION_SECONDS); extended=True
    a.save(update_fields=['current_highest_bid','current_highest_bidder','bid_count','end_at','updated_at'])
    if previous and previous.id!=bidder.id: notify_user(previous,'You have been outbid',f'You were outbid on {a.product.name}.')
    notify_user(a.seller,'New bid received',f'A new bid was placed on {a.product.name}.')
    record_audit(bidder,'BID_CREATED',bid,{'auction_id':a.id,'amount':str(amount)})
    event = {
        'type': 'bid.update',
        'data': {
            'event': 'bid',
            'bid_id': bid.id,
            'amount': str(amount),
            'bidder': mask_username(bidder.username),
            'bidder_id': bidder.id,
            'bid_count': a.bid_count,
            'end_at': a.end_at.isoformat(),
            'extended': extended,
        },
    }
    transaction.on_commit(lambda: broadcast_bid(f'auction_{a.id}', event))
    return bid
