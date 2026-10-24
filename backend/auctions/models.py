from django.db import models
from django.conf import settings
from products.models import Product
class Auction(models.Model):
 class Status(models.TextChoices): DRAFT='DRAFT','Draft'; PENDING='PENDING_APPROVAL','Pending approval'; SCHEDULED='SCHEDULED','Scheduled'; LIVE='LIVE','Live'; CLOSED='CLOSED','Closed'; CANCELLED='CANCELLED','Cancelled'; SOLD='SOLD','Sold'; UNSOLD='UNSOLD','Unsold'
 product=models.OneToOneField(Product,on_delete=models.PROTECT,related_name='auction'); seller=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='auctions'); starting_price=models.DecimalField(max_digits=14,decimal_places=2); min_increment=models.DecimalField(max_digits=14,decimal_places=2); start_at=models.DateTimeField(null=True,blank=True); end_at=models.DateTimeField(null=True,blank=True); current_highest_bid=models.DecimalField(max_digits=14,decimal_places=2,null=True,blank=True); current_highest_bidder=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='leading_auctions'); bid_count=models.PositiveIntegerField(default=0); status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT); winner=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='won_auctions'); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True); closed_at=models.DateTimeField(null=True,blank=True)
 # What the seller asked for (a request only). The real start_at/end_at are allocated by an admin.
 requested_start_at=models.DateTimeField(null=True,blank=True); requested_end_at=models.DateTimeField(null=True,blank=True); is_24_7=models.BooleanField(default=False); seller_note=models.CharField(max_length=500,blank=True)
 admin_note=models.CharField(max_length=500,blank=True); scheduled_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='allocated_auctions'); scheduled_at=models.DateTimeField(null=True,blank=True)
 class Meta:
  indexes=[models.Index(fields=['status','start_at']),models.Index(fields=['status','end_at']),models.Index(fields=['seller','status'])]
  constraints=[models.CheckConstraint(condition=models.Q(end_at__gt=models.F('start_at')),name='auction_end_after_start'),models.CheckConstraint(condition=models.Q(starting_price__gt=0,min_increment__gt=0),name='auction_prices_positive')]
 def required_minimum(self): return self.starting_price if self.current_highest_bid is None else self.current_highest_bid+self.min_increment


class Watch(models.Model):
 """A user's saved (watchlisted) auction."""
 user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='watches'); auction=models.ForeignKey(Auction,on_delete=models.CASCADE,related_name='watchers'); created_at=models.DateTimeField(auto_now_add=True)
 class Meta: constraints=[models.UniqueConstraint(fields=['user','auction'],name='uniq_watch_user_auction')]; ordering=['-created_at']


class ScheduleRequest(models.Model):
 """A buyer's (or seller's) suggestion for when an auction should run. Advisory only: an admin decides."""
 class Status(models.TextChoices): OPEN='OPEN','Open'; ACCEPTED='ACCEPTED','Accepted'; DISMISSED='DISMISSED','Dismissed'
 auction=models.ForeignKey(Auction,on_delete=models.CASCADE,related_name='schedule_requests'); requester=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='schedule_requests')
 preferred_start=models.DateTimeField(null=True,blank=True); preferred_end=models.DateTimeField(null=True,blank=True); note=models.CharField(max_length=500,blank=True)
 status=models.CharField(max_length=10,choices=Status.choices,default=Status.OPEN); created_at=models.DateTimeField(auto_now_add=True); resolved_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='+'); resolved_at=models.DateTimeField(null=True,blank=True)
 class Meta: ordering=['-created_at']; indexes=[models.Index(fields=['status','-created_at'])]
