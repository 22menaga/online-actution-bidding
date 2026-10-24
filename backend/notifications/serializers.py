from rest_framework import serializers
from .models import Notification
class NotificationSerializer(serializers.ModelSerializer):
 class Meta: model=Notification; fields=['id','title','body','read_at','created_at','metadata']; read_only_fields=['recipient']
