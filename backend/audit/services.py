from .models import AuditLog
def record_audit(actor,action,obj=None,metadata=None,request=None):
 return AuditLog.objects.create(actor=actor,action=action,object_type=obj.__class__.__name__ if obj else '',object_id=str(getattr(obj,'pk','')) if obj else '',metadata=metadata or {},ip_address=(request.META.get('REMOTE_ADDR') if request else None),user_agent=(request.META.get('HTTP_USER_AGENT','') if request else ''))
