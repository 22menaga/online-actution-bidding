from django.contrib import admin
from .models import AuditLog
@admin.register(AuditLog)
class AuditAdmin(admin.ModelAdmin): readonly_fields=[f.name for f in AuditLog._meta.fields]
