from django.db import models
class SystemSetting(models.Model):
    key=models.CharField(max_length=120,unique=True); value=models.TextField(blank=True); description=models.TextField(blank=True); updated_at=models.DateTimeField(auto_now=True)
