from django.db import models
from django.conf import settings
from auctions.models import Auction
class Bid(models.Model):
 auction=models.ForeignKey(Auction,on_delete=models.PROTECT,related_name='bids'); bidder=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='bids'); amount=models.DecimalField(max_digits=14,decimal_places=2); client_reference=models.UUIDField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True)
 class Meta: indexes=[models.Index(fields=['auction','-created_at']),models.Index(fields=['bidder','-created_at'])]; constraints=[models.CheckConstraint(condition=models.Q(amount__gt=0),name='bid_amount_positive'),models.UniqueConstraint(fields=['auction','client_reference'],condition=models.Q(client_reference__isnull=False),name='uniq_bid_client_reference')]
