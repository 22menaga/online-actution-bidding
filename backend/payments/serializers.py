from rest_framework import serializers
from .models import Payment
class PaymentSerializer(serializers.ModelSerializer):
 product_name=serializers.CharField(source='auction.product.name',read_only=True)
 class Meta: model=Payment; fields=['id','auction','product_name','buyer','amount','provider','provider_payment_id','transaction_reference','status','created_at','updated_at','paid_at']; read_only_fields=['buyer','amount','provider_payment_id','transaction_reference','status','paid_at']
