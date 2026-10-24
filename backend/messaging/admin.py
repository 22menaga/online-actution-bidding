from django.contrib import admin
from .models import Conversation,Message,Report
admin.site.register([Conversation,Message,Report])
