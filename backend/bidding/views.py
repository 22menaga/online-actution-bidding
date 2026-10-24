from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from .models import Bid
from .serializers import BidSerializer
from .services import place_bid
from config.security import BidAuctionThrottle, BidUserThrottle
class BidListCreateView(generics.ListCreateAPIView):
 serializer_class=BidSerializer; permission_classes=[IsAuthenticated]
 def get_throttles(self):
  # bid creation is rate limited per user and per lot; listing your own bids is not
  return [BidUserThrottle(),BidAuctionThrottle()] if self.request.method=='POST' else super().get_throttles()
 def get_queryset(self): return Bid.objects.filter(bidder=self.request.user).select_related('auction','auction__product').order_by('-created_at')
 def create(self,request,*args,**kwargs):
  s=self.get_serializer(data=request.data); s.is_valid(raise_exception=True); bid=place_bid(auction_id=s.validated_data['auction'].id,bidder=request.user,amount=s.validated_data['amount'],client_reference=s.validated_data.get('client_reference'),confirm_large=str(request.data.get('confirm_large','')).lower() in ('1','true','yes')); return Response(self.get_serializer(bid).data,status=201)

class AuctionBidHistoryView(generics.ListAPIView):
 """Public bid history for one auction, with bidder names partially masked."""
 permission_classes=[AllowAny]
 def get_serializer_class(self):
  from rest_framework import serializers
  class S(serializers.ModelSerializer):
   bidder_name=serializers.SerializerMethodField()
   class Meta: model=Bid; fields=['id','bidder_name','amount','created_at']
   def get_bidder_name(self,o):
    from accounts.masking import mask_username
    return mask_username(o.bidder.username)
  return S
 def get_queryset(self): return Bid.objects.filter(auction_id=self.kwargs['pk']).select_related('bidder').order_by('-created_at')
