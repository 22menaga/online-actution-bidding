from rest_framework import serializers
from datetime import timedelta
from django.utils import timezone
from .models import Auction, ScheduleRequest, Watch
class AuctionSerializer(serializers.ModelSerializer):
 product_name=serializers.CharField(source='product.name',read_only=True); seller_name=serializers.CharField(source='seller.username',read_only=True); required_minimum=serializers.DecimalField(max_digits=14,decimal_places=2,read_only=True)
 product_description=serializers.CharField(source='product.description',read_only=True); category_name=serializers.CharField(source='product.category.name',read_only=True); product_condition=serializers.CharField(source='product.condition',read_only=True); product_images=serializers.SerializerMethodField(); leader_name=serializers.SerializerMethodField(); is_leading=serializers.SerializerMethodField(); is_watched=serializers.SerializerMethodField(); server_time=serializers.SerializerMethodField()
 def get_server_time(self,obj): return timezone.now().isoformat()
 def _user(self):
  r=self.context.get('request'); u=getattr(r,'user',None); return u if u is not None and u.is_authenticated else None
 def get_leader_name(self,obj):
  from accounts.masking import mask_username
  return mask_username(obj.current_highest_bidder.username) if obj.current_highest_bidder_id else None
 def get_is_leading(self,obj):
  u=self._user(); return bool(u and obj.current_highest_bidder_id==u.id)
 def get_is_watched(self,obj):
  u=self._user()
  if not u: return False
  if '_watched' not in self.context: self.context['_watched']=set(Watch.objects.filter(user=u).values_list('auction_id',flat=True))
  return obj.id in self.context['_watched']
 def get_product_images(self,obj):
  # Relative URLs keep images same-origin behind the dev proxy / reverse proxy (needed for WebGL textures).
  return [i.image.url for i in obj.product.images.all()]
 class Meta: model=Auction; fields=['id','product','product_name','seller','seller_name','starting_price','min_increment','start_at','end_at','requested_start_at','requested_end_at','is_24_7','seller_note','admin_note','scheduled_at','current_highest_bid','current_highest_bidder','bid_count','status','winner','required_minimum','product_description','category_name','product_condition','product_images','leader_name','is_leading','is_watched','server_time','created_at','updated_at','closed_at']; read_only_fields=['seller','start_at','end_at','admin_note','scheduled_at','current_highest_bid','current_highest_bidder','bid_count','status','winner','closed_at']; extra_kwargs={'product':{'validators':[]}}  # re-listing rules live in the view (clear message, allows re-listing)
 def validate(self,d):
  inst=self.instance
  rs=d.get('requested_start_at',inst.requested_start_at if inst else None); re_=d.get('requested_end_at',inst.requested_end_at if inst else None)
  if rs and re_ and re_<=rs: raise serializers.ValidationError({'requested_end_at':'Requested end must be after requested start.'})
  if not inst and rs and rs<timezone.now()-timedelta(minutes=5): raise serializers.ValidationError({'requested_start_at':'Requested start cannot be in the past.'})
  starting_price=d.get('starting_price',self.instance.starting_price if self.instance else None)
  min_increment=d.get('min_increment',self.instance.min_increment if self.instance else None)
  if (starting_price is not None and starting_price<=0) or (min_increment is not None and min_increment<=0): raise serializers.ValidationError('Prices must be positive.')
  if self.instance and 'product' in d and d['product'].id!=self.instance.product_id: raise serializers.ValidationError('Auction product cannot be changed after creation.')
  return d


class ScheduleRequestSerializer(serializers.ModelSerializer):
 requester_name=serializers.CharField(source='requester.username',read_only=True); requester_role=serializers.CharField(source='requester.role',read_only=True)
 product_name=serializers.CharField(source='auction.product.name',read_only=True); auction_status=serializers.CharField(source='auction.status',read_only=True)
 current_start_at=serializers.DateTimeField(source='auction.start_at',read_only=True); current_end_at=serializers.DateTimeField(source='auction.end_at',read_only=True)
 class Meta:
  model=ScheduleRequest; fields=['id','auction','product_name','auction_status','current_start_at','current_end_at','requester_name','requester_role','preferred_start','preferred_end','note','status','created_at','resolved_at']
  read_only_fields=['auction','status','created_at','resolved_at']
 def validate(self,d):
  ps,pe=d.get('preferred_start'),d.get('preferred_end')
  if ps and pe and pe<=ps: raise serializers.ValidationError({'preferred_end':'Preferred end must be after preferred start.'})
  if not (ps or pe or (d.get('note') or '').strip()): raise serializers.ValidationError('Tell us a preferred time or add a note.')
  return d


class AllocationSerializer(serializers.Serializer):
 start_at=serializers.DateTimeField(); end_at=serializers.DateTimeField(); note=serializers.CharField(required=False,allow_blank=True,max_length=500)
