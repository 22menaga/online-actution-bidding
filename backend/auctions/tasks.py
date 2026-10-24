from celery import shared_task
from django.utils import timezone
from .models import Auction
from .services import close_auction
@shared_task
def process_auction_lifecycle():
 now=timezone.now()
 starting=list(Auction.objects.filter(status='SCHEDULED',start_at__lte=now,end_at__gt=now).values_list('id',flat=True))
 if starting:
  Auction.objects.filter(id__in=starting,status='SCHEDULED').update(status='LIVE')
  from bidding.services import broadcast_status
  for i in starting: broadcast_status(i,'LIVE')
 for a in Auction.objects.filter(
     status__in=['LIVE', 'SCHEDULED'], end_at__lte=now
 ).values_list('id', flat=True):
  close_auction(a)
