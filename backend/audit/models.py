from django.db import models
from django.conf import settings
class AuditLog(models.Model):
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='audit_events'); action=models.CharField(max_length=100); object_type=models.CharField(max_length=100,blank=True); object_id=models.CharField(max_length=100,blank=True); metadata=models.JSONField(default=dict,blank=True); ip_address=models.GenericIPAddressField(null=True,blank=True); user_agent=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at']; indexes=[models.Index(fields=['action','-created_at']),models.Index(fields=['object_type','object_id'])]
