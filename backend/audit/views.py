from rest_framework import generics
from accounts.permissions import IsAdmin
from .models import AuditLog
from .serializers import AuditLogSerializer
class AuditLogListView(generics.ListAPIView): queryset=AuditLog.objects.select_related('actor').all(); serializer_class=AuditLogSerializer; permission_classes=[IsAdmin]
