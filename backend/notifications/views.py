from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Notification
from .serializers import NotificationSerializer
class NotificationListView(generics.ListAPIView):
    serializer_class=NotificationSerializer; permission_classes=[IsAuthenticated]
    def get_queryset(self): return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')
class NotificationReadView(generics.UpdateAPIView):
    serializer_class=NotificationSerializer; permission_classes=[IsAuthenticated]; http_method_names=['patch']
    def get_queryset(self): return Notification.objects.filter(recipient=self.request.user)
    def perform_update(self,s): s.instance.read_at=timezone.now(); s.save(update_fields=['read_at'])
