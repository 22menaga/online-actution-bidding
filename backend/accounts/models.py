from django.contrib.auth.models import AbstractUser
from django.db import models
class User(AbstractUser):
    class Roles(models.TextChoices): ADMIN='ADMIN','Admin'; SELLER='SELLER','Seller'; BUYER='BUYER','Buyer'
    email=models.EmailField(unique=True); role=models.CharField(max_length=10,choices=Roles.choices,default=Roles.BUYER)
    email_verified=models.BooleanField(default=False); is_suspended=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    def can_transact(self): return self.is_active and not self.is_suspended and self.email_verified
class SellerProfile(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='seller_profile'); business_name=models.CharField(max_length=200,blank=True); phone=models.CharField(max_length=30,blank=True); address=models.TextField(blank=True); approved=models.BooleanField(default=False); verified=models.BooleanField(default=False); rejection_reason=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
class BuyerProfile(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name='buyer_profile'); phone=models.CharField(max_length=30,blank=True); address=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
class SellerVerification(models.Model):
    class Status(models.TextChoices): PENDING='PENDING','Pending'; APPROVED='APPROVED','Approved'; REJECTED='REJECTED','Rejected'
    seller=models.ForeignKey(SellerProfile,on_delete=models.CASCADE,related_name='verifications'); legal_name=models.CharField(max_length=200); document_type=models.CharField(max_length=100); document_reference=models.CharField(max_length=200); status=models.CharField(max_length=10,choices=Status.choices,default=Status.PENDING); reviewer=models.ForeignKey(User,null=True,blank=True,on_delete=models.SET_NULL,related_name='seller_reviews'); notes=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True); reviewed_at=models.DateTimeField(null=True,blank=True)
