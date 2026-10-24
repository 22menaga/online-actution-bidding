from django.db import models
from accounts.models import User
class Category(models.Model): name=models.CharField(max_length=120,unique=True); slug=models.SlugField(max_length=140,unique=True); active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True)
class AIEstimate(models.Model):
    """One AI photo analysis, stored so the seller, and later the admin reviewing the listing, see the same numbers."""
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='ai_estimates'); data=models.JSONField(); model=models.CharField(max_length=60,blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=['-created_at']; indexes=[models.Index(fields=['user','-created_at'])]
class Product(models.Model):
 class Status(models.TextChoices): DRAFT='DRAFT','Draft'; PENDING='PENDING_APPROVAL','Pending approval'; APPROVED='APPROVED','Approved'; AUCTION='AUCTION','Auction'; SOLD='SOLD','Sold'; UNSOLD='UNSOLD','Unsold'; REJECTED='REJECTED','Rejected'
 seller=models.ForeignKey(User,on_delete=models.PROTECT,related_name='products'); category=models.ForeignKey(Category,on_delete=models.PROTECT,related_name='products'); name=models.CharField(max_length=240); description=models.TextField(); starting_price=models.DecimalField(max_digits=14,decimal_places=2); condition=models.CharField(max_length=80); status=models.CharField(max_length=20,choices=Status.choices,default=Status.DRAFT); rejection_reason=models.TextField(blank=True); ai_estimate=models.ForeignKey('AIEstimate',null=True,blank=True,on_delete=models.SET_NULL,related_name='products'); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 class Meta: indexes=[models.Index(fields=['status','category']),models.Index(fields=['seller','status']),models.Index(fields=['created_at'])]
class ProductImage(models.Model): product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name='images'); image=models.ImageField(upload_to='products/%Y/%m/'); alt_text=models.CharField(max_length=200,blank=True); sort_order=models.PositiveIntegerField(default=0); created_at=models.DateTimeField(auto_now_add=True)
