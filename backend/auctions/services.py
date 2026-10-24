from django.db import transaction
from django.utils import timezone
from .models import Auction
from payments.models import Payment
from notifications.services import notify_user
from audit.services import record_audit
@transaction.atomic
def close_auction(auction_id, actor=None):
 a=Auction.objects.select_for_update(of=('self',)).select_related('product','seller','current_highest_bidder').get(pk=auction_id)
 if a.status in [Auction.Status.CLOSED,Auction.Status.SOLD,Auction.Status.UNSOLD,Auction.Status.CANCELLED]: return a
 now=timezone.now()
 if a.end_at>now and a.status!=Auction.Status.LIVE: return a
 a.status=Auction.Status.SOLD if a.current_highest_bidder_id else Auction.Status.UNSOLD; a.winner=a.current_highest_bidder; a.closed_at=now; a.save(update_fields=['status','winner','closed_at','updated_at'])
 a.product.status='SOLD' if a.winner_id else 'UNSOLD'; a.product.save(update_fields=['status','updated_at'])
 if a.winner_id:
  p=Payment.objects.create(auction=a,buyer=a.winner,amount=a.current_highest_bid,status=Payment.Status.PENDING); notify_user(a.winner,'Auction won',f'You won {a.product.name}. Payment {p.id} is pending.'); notify_user(a.seller,'Auction sold',f'{a.product.name} sold successfully.')
 else: notify_user(a.seller,'Auction closed',f'{a.product.name} closed without a winning bid.')
 if actor: record_audit(actor,'AUCTION_CLOSED',a)
 from bidding.services import broadcast_status
 transaction.on_commit(lambda: broadcast_status(a.id,a.status,a.winner.username if a.winner_id else None,a.current_highest_bid))
 return a
