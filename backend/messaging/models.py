from django.db import models
from django.conf import settings
from auctions.models import Auction
class Conversation(models.Model):
    auction=models.ForeignKey(Auction,on_delete=models.CASCADE,related_name='conversations'); buyer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='buyer_conversations'); seller=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='seller_conversations'); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['auction','buyer','seller'],name='unique_auction_conversation')]
class Message(models.Model):
    class Status(models.TextChoices): SENT='SENT','Sent'; READ='READ','Read'; REPORTED='REPORTED','Reported'
    conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name='messages'); sender=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='sent_messages'); body=models.TextField(max_length=5000); status=models.CharField(max_length=10,choices=Status.choices,default=Status.SENT); created_at=models.DateTimeField(auto_now_add=True); read_at=models.DateTimeField(null=True,blank=True)
    class Meta: indexes=[models.Index(fields=['conversation','created_at'])]

class Report(models.Model):
    class Status(models.TextChoices): OPEN='OPEN','Open'; REVIEWED='REVIEWED','Reviewed'; CLOSED='CLOSED','Closed'
    reporter=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='reports'); conversation=models.ForeignKey(Conversation,on_delete=models.CASCADE,related_name='reports'); reason=models.CharField(max_length=200); details=models.TextField(blank=True); status=models.CharField(max_length=10,choices=Status.choices,default='OPEN'); reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='reviewed_reports'); created_at=models.DateTimeField(auto_now_add=True); reviewed_at=models.DateTimeField(null=True,blank=True)
