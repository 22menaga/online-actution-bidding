from rest_framework import serializers
from .models import Category,Product,ProductImage
class CategorySerializer(serializers.ModelSerializer):
 class Meta: model=Category; fields='__all__'
class ProductImageSerializer(serializers.ModelSerializer):
 class Meta: model=ProductImage; fields=['id','image','alt_text','sort_order']
class ProductSerializer(serializers.ModelSerializer):
 images=ProductImageSerializer(many=True,read_only=True); seller_name=serializers.CharField(source='seller.username',read_only=True); category_name=serializers.CharField(source='category.name',read_only=True); auction_status=serializers.SerializerMethodField(); auction_id=serializers.SerializerMethodField(); ai_estimate=serializers.SerializerMethodField()
 def get_ai_estimate(self,obj):
  e=obj.ai_estimate
  if not e or not e.data.get('sellable'): return None
  d=e.data; return {k:d.get(k) for k in ('estimated_low','estimated_high','estimated_mid','suggested_start_price','currency','confidence','item_name','condition')}|{'created_at':e.created_at}
 def get_auction_status(self,obj): a=getattr(obj,'auction',None); return a.status if a else None
 def get_auction_id(self,obj): a=getattr(obj,'auction',None); return a.id if a else None
 class Meta: model=Product; fields=['ai_estimate','auction_status','auction_id','id','seller','seller_name','category','category_name','name','description','starting_price','condition','status','rejection_reason','images','created_at','updated_at']; read_only_fields=['seller','status','rejection_reason']
class ProductImageCreateSerializer(serializers.ModelSerializer):
 def validate_image(self,value):
  from .images import sanitize_upload
  return sanitize_upload(value)
 class Meta: model=ProductImage; fields=['image','alt_text','sort_order']
