from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from .models import Conversation,Message,Report
from .serializers import ConversationSerializer,MessageSerializer,ReportSerializer
from accounts.permissions import IsAdmin
class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class=ConversationSerializer; permission_classes=[IsAuthenticated]; http_method_names=['get','post']
    def get_queryset(self): return Conversation.objects.filter(buyer=self.request.user)|Conversation.objects.filter(seller=self.request.user)
    def perform_create(self,s):
        a=s.validated_data['auction']; u=self.request.user
        if u.id not in (a.seller_id,a.winner_id): raise PermissionDenied('Conversation is limited to auction participants.')
        buyer=u if u.id!=a.seller_id else a.winner
        if not buyer: raise ValidationError('No eligible buyer.')
        s.save(buyer=buyer,seller=a.seller)
    @action(detail=True,methods=['post'])
    def message(self,request,pk=None):
        c=self.get_object(); s=MessageSerializer(data={'conversation':c.id,'body':request.data.get('body','')}); s.is_valid(raise_exception=True); obj=s.save(sender=request.user); return Response(MessageSerializer(obj).data,status=201)
class MessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class=MessageSerializer; permission_classes=[IsAuthenticated]
    def get_queryset(self): return Message.objects.filter(conversation__buyer=self.request.user)|Message.objects.filter(conversation__seller=self.request.user)
class ReportViewSet(viewsets.ModelViewSet):
    serializer_class=ReportSerializer; permission_classes=[IsAuthenticated]; http_method_names=['get','post','patch']
    def get_queryset(self):
        if self.request.user.role=='ADMIN': return Report.objects.select_related('conversation','reporter','reviewed_by')
        return Report.objects.filter(reporter=self.request.user)
    def perform_create(self,s):
        c=s.validated_data['conversation']; u=self.request.user
        if u.id not in (c.buyer_id,c.seller_id): raise PermissionDenied('Forbidden.')
        s.save(reporter=u)
    @action(detail=True,methods=['post'],permission_classes=[IsAdmin])
    def review(self,request,pk=None):
        obj=self.get_object(); status=request.data.get('status','REVIEWED')
        if status not in ('REVIEWED','CLOSED'): return Response({'detail':'Invalid status.'},status=400)
        obj.status=status; obj.reviewed_by=request.user; obj.reviewed_at=timezone.now(); obj.save(update_fields=['status','reviewed_by','reviewed_at']); return Response(self.get_serializer(obj).data)
