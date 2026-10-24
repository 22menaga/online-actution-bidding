from django.db import models
from django.conf import settings
from auctions.models import Auction
class Payment(models.Model):
 class Status(models.TextChoices): PENDING='PENDING','Pending'; PROCESSING='PROCESSING','Processing'; SUCCESS='SUCCESS','Success'; FAILED='FAILED','Failed'; REFUNDED='REFUNDED','Refunded'
 auction=models.OneToOneField(Auction,on_delete=models.PROTECT,related_name='payment'); buyer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='payments'); amount=models.DecimalField(max_digits=14,decimal_places=2); provider=models.CharField(max_length=30,default='razorpay'); provider_payment_id=models.CharField(max_length=255,blank=True); transaction_reference=models.CharField(max_length=255,blank=True); status=models.CharField(max_length=15,choices=Status.choices,default=Status.PENDING); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True); paid_at=models.DateTimeField(null=True,blank=True)
 class Meta: indexes=[models.Index(fields=['buyer','status']),models.Index(fields=['status','-created_at'])]


class Wallet(models.Model):
 """A user's coin balance. Only changed through payments.wallet (which also writes the ledger)."""
 user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='wallet'); balance=models.DecimalField(max_digits=14,decimal_places=2,default=0); updated_at=models.DateTimeField(auto_now=True)
 class Meta: constraints=[models.CheckConstraint(condition=models.Q(balance__gte=0),name='wallet_balance_non_negative')]

class WalletTransaction(models.Model):
 class Kind(models.TextChoices): TOPUP='TOPUP','Top-up'; PURCHASE='PURCHASE','Purchase'; SALE='SALE','Sale'; REFUND='REFUND','Refund'; ADJUSTMENT='ADJUSTMENT','Adjustment'
 wallet=models.ForeignKey(Wallet,on_delete=models.CASCADE,related_name='transactions'); kind=models.CharField(max_length=12,choices=Kind.choices); amount=models.DecimalField(max_digits=14,decimal_places=2); balance_after=models.DecimalField(max_digits=14,decimal_places=2); description=models.CharField(max_length=200,blank=True); reference=models.CharField(max_length=100,blank=True); created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=['-created_at','-id']; indexes=[models.Index(fields=['wallet','-created_at'])]

class TopUp(models.Model):
 """A purchase of coins with money (Razorpay or fake test payment)."""
 class Status(models.TextChoices): PENDING='PENDING','Pending'; SUCCESS='SUCCESS','Success'; FAILED='FAILED','Failed'
 user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='topups'); coins=models.DecimalField(max_digits=14,decimal_places=2); amount=models.DecimalField(max_digits=14,decimal_places=2)
 provider=models.CharField(max_length=20); provider_order_id=models.CharField(max_length=100,blank=True); provider_payment_id=models.CharField(max_length=100,blank=True)
 status=models.CharField(max_length=10,choices=Status.choices,default=Status.PENDING); created_at=models.DateTimeField(auto_now_add=True); completed_at=models.DateTimeField(null=True,blank=True)
 class Meta: ordering=['-created_at']; indexes=[models.Index(fields=['provider','provider_order_id'])]
