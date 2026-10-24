from .models import Notification
def notify_user(user,title,body,metadata=None): return Notification.objects.create(recipient=user,title=title,body=body,metadata=metadata or {})
