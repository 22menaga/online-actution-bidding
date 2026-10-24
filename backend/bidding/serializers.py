from rest_framework import serializers
from .models import Bid
class BidSerializer(serializers.ModelSerializer):
 bidder_name=serializers.CharField(source='bidder.username',read_only=True)
 product_name=serializers.CharField(source='auction.product.name',read_only=True); auction_status=serializers.CharField(source='auction.status',read_only=True); auction_end_at=serializers.DateTimeField(source='auction.end_at',read_only=True); current_highest_bid=serializers.DecimalField(source='auction.current_highest_bid',max_digits=14,decimal_places=2,read_only=True); is_leading=serializers.SerializerMethodField()
 def get_is_leading(self,obj): return obj.auction.current_highest_bidder_id==obj.bidder_id
 class Meta: model=Bid; fields=['id','auction','bidder','bidder_name','amount','client_reference','created_at','product_name','auction_status','auction_end_at','current_highest_bid','is_leading']; read_only_fields=['bidder']
