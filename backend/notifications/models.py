from django.db import models
from django.conf import settings
class Notification(models.Model):
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='notifications'); title=models.CharField(max_length=200); body=models.TextField(); read_at=models.DateTimeField(null=True,blank=True); created_at=models.DateTimeField(auto_now_add=True); metadata=models.JSONField(default=dict,blank=True)
    class Meta: indexes=[models.Index(fields=['recipient','read_at','-created_at'])]
