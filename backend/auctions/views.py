from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework import generics
from .models import Auction, ScheduleRequest, Watch
from .serializers import AllocationSerializer, AuctionSerializer, ScheduleRequestSerializer
from . import scheduling
from .review import build_report
from accounts.permissions import IsAdmin,IsSeller,IsSellerOrAdmin
from products.models import Product
from audit.services import record_audit
class AuctionViewSet(viewsets.ModelViewSet):
 queryset=Auction.objects.select_related('product','product__category','product__ai_estimate','seller','current_highest_bidder','winner').prefetch_related('product__images').all(); serializer_class=AuctionSerializer
 filterset_fields=['status','product__category']; search_fields=['product__name','product__description']; ordering_fields=['end_at','current_highest_bid','created_at','bid_count']; ordering=['end_at']
 def get_permissions(self):
  if self.action in ('list','retrieve'): permission_classes=(AllowAny,)
  elif self.action in ('watch','watchlist'): permission_classes=(IsAuthenticated,)
  elif self.action=='create': permission_classes=(IsSeller,)
  elif self.action in ('approve','reschedule','reject','review'): permission_classes=(IsAdmin,)
  elif self.action=='suggest_time': permission_classes=(IsAuthenticated,)
  else: permission_classes=(IsSellerOrAdmin,)
  return [permission() for permission in permission_classes]
 PUBLIC=['SCHEDULED','LIVE','CLOSED','SOLD','UNSOLD']
 def get_queryset(self):
  qs=super().get_queryset(); u=self.request.user
  if not u.is_authenticated: return qs.filter(status__in=self.PUBLIC)
  if u.role=='ADMIN': return qs
  if self.action in ('list','retrieve','watch','watchlist','suggest_time'):
   # Browsing is open to every role; a seller additionally sees their own unpublished auctions.
   qs=qs.filter(Q(status__in=self.PUBLIC)|Q(seller=u)) if u.role=='SELLER' else qs.filter(status__in=self.PUBLIC)
   if self.action=='list' and self.request.query_params.get('mine'): qs=qs.filter(seller=u)
   return qs
  if u.role=='SELLER': return qs.filter(seller=u)
  return qs.filter(status__in=self.PUBLIC)
 @action(detail=False,methods=['get'])
 def watchlist(self,request):
  qs=self.filter_queryset(self.get_queryset()).filter(watchers__user=request.user)
  page=self.paginate_queryset(qs); ser=self.get_serializer(page if page is not None else qs,many=True)
  return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)
 @action(detail=True,methods=['post','delete'])
 def watch(self,request,pk=None):
  a=self.get_object()
  if request.method=='POST': Watch.objects.get_or_create(user=request.user,auction=a); return Response({'watching':True})
  Watch.objects.filter(user=request.user,auction=a).delete(); return Response({'watching':False})
 def perform_create(self,serializer):
  u=self.request.user
  if u.role!='SELLER' or not getattr(getattr(u,'seller_profile',None),'approved',False): raise PermissionDenied('Approved seller required.')
  p=Product.objects.filter(pk=self.request.data.get('product')).first()
  if p is None: raise ValidationError({'product':'Product not found.'})
  if p.seller_id!=u.id or p.status not in ('APPROVED','UNSOLD'): raise ValidationError('Product must be yours and approved.')
  old=Auction.objects.filter(product=p).first()
  if old and (old.status in ('CANCELLED','UNSOLD') and old.bid_count==0): old.delete(); p.status='APPROVED'; p.save(update_fields=['status','updated_at'])  # re-listing: the old, bid-less auction is replaced
  elif old: raise ValidationError({'product':'This product already has an active auction request.'})
  a=serializer.save(seller=u,status='PENDING_APPROVAL'); record_audit(u,'AUCTION_CREATED',a,{'is_24_7':a.is_24_7})
  from accounts.models import User
  from notifications.services import notify_user
  for admin in User.objects.filter(role='ADMIN',is_active=True): notify_user(admin,'Auction awaiting scheduling',f'{u.username} submitted {p.name} and is waiting for a time slot.')
 @action(detail=True,methods=['post'])
 def approve(self,request,pk=None):
  """Admin approves a pending auction AND allocates its time. Body: start_at, end_at, note?"""
  a=self.get_object()
  if a.status!='PENDING_APPROVAL': return Response({'detail':'Only pending auctions can be approved.'},status=409)
  d=AllocationSerializer(data=request.data); d.is_valid(raise_exception=True)
  a=scheduling.allocate(a.pk,request.user,d.validated_data['start_at'],d.validated_data['end_at'],d.validated_data.get('note',''))
  return Response(self.get_serializer(a).data)
 @action(detail=True,methods=['post'])
 def reschedule(self,request,pk=None):
  """Admin moves a scheduled auction (only while it has no bids)."""
  a=self.get_object()
  if a.status!='SCHEDULED': return Response({'detail':'Only scheduled auctions can be rescheduled.'},status=409)
  d=AllocationSerializer(data=request.data); d.is_valid(raise_exception=True)
  a=scheduling.allocate(a.pk,request.user,d.validated_data['start_at'],d.validated_data['end_at'],d.validated_data.get('note',''))
  return Response(self.get_serializer(a).data)
 @action(detail=True,methods=['post'])
 def reject(self,request,pk=None):
  a=scheduling.reject(self.get_object().pk,request.user,request.data.get('reason',''))
  return Response(self.get_serializer(a).data)
 @action(detail=True,methods=['get'])
 def review(self,request,pk=None):
  """Security / data / capacity report for an admin deciding whether and when to run this auction."""
  a=self.get_object(); s=request.query_params.get('start_at'); e=request.query_params.get('end_at')
  from django.utils.dateparse import parse_datetime
  return Response(build_report(a,parse_datetime(s) if s else None,parse_datetime(e) if e else None))
 @action(detail=True,methods=['post'],url_path='suggest-time')
 def suggest_time(self,request,pk=None):
  """Any signed-in user can suggest when an upcoming auction should run. Advisory; only an admin decides."""
  a=self.get_object()
  if a.seller_id==request.user.id: return Response({'detail':'Use your auction request to set your own preferred time.'},status=403)
  if a.status!='SCHEDULED' or a.bid_count: return Response({'detail':'Time suggestions are only accepted for upcoming auctions without bids.'},status=409)
  s=ScheduleRequestSerializer(data=request.data); s.is_valid(raise_exception=True)
  obj,_=ScheduleRequest.objects.update_or_create(auction=a,requester=request.user,status='OPEN',defaults=s.validated_data)
  record_audit(request.user,'SCHEDULE_SUGGESTED',a)
  from accounts.models import User
  from notifications.services import notify_user
  for admin in User.objects.filter(role='ADMIN',is_active=True): notify_user(admin,'Time suggestion',f'{request.user.username} suggested a time for {a.product.name}.')
  return Response(ScheduleRequestSerializer(obj).data,status=201)
 @action(detail=True,methods=['post'])
 def cancel(self,request,pk=None):
  a=self.get_object();
  if request.user.role=='SELLER' and a.seller_id!=request.user.id: return Response({'detail':'Forbidden'},status=403)
  if a.bid_count or a.status in ('LIVE','CLOSED','SOLD','CANCELLED'): return Response({'detail':'Cannot cancel this auction.'},status=409)
  a.status='CANCELLED'; a.save(update_fields=['status','updated_at']); record_audit(request.user,'AUCTION_CANCELLED',a); return Response(self.get_serializer(a).data)
 def perform_update(self,serializer):
  auction=serializer.instance
  if auction.bid_count or auction.status not in ('PENDING_APPROVAL','SCHEDULED'):
   from rest_framework.exceptions import PermissionDenied
   raise PermissionDenied('Auction terms cannot be changed after bidding starts.')
  serializer.save()
 def perform_destroy(self,instance):
  if instance.bid_count or instance.status not in ('PENDING_APPROVAL','SCHEDULED'):
   from rest_framework.exceptions import PermissionDenied
   raise PermissionDenied('Only auctions without bids that have not started can be deleted.')
  if instance.status=='SCHEDULED':
   instance.product.status='APPROVED'
   instance.product.save(update_fields=['status','updated_at'])
  super().perform_destroy(instance)


class TimeRequestListView(generics.ListAPIView):
 """Admin inbox of suggested times (from buyers and sellers)."""
 serializer_class=ScheduleRequestSerializer; permission_classes=[IsAdmin]; filterset_fields=['status']
 def get_queryset(self): return ScheduleRequest.objects.select_related('auction__product','requester').order_by('-created_at')


class TimeRequestResolveView(generics.GenericAPIView):
 serializer_class=ScheduleRequestSerializer; permission_classes=[IsAdmin]
 def post(self,request,pk):
  obj=ScheduleRequest.objects.select_related('auction__product','requester').filter(pk=pk).first()
  if not obj: return Response({'detail':'Not found.'},status=404)
  decision=request.data.get('status')
  if decision not in ('ACCEPTED','DISMISSED'): return Response({'detail':'status must be ACCEPTED or DISMISSED.'},status=400)
  obj.status=decision; obj.resolved_by=request.user; obj.resolved_at=timezone.now(); obj.save(update_fields=['status','resolved_by','resolved_at'])
  record_audit(request.user,f'SCHEDULE_REQUEST_{decision}',obj)
  from notifications.services import notify_user
  notify_user(obj.requester,'Time suggestion reviewed',f'Your suggestion for {obj.auction.product.name} was {decision.lower()}.')
  return Response(self.get_serializer(obj).data)
