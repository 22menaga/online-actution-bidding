from rest_framework.routers import DefaultRouter
from .views import ConversationViewSet,MessageViewSet,ReportViewSet
r=DefaultRouter(); r.register('conversations',ConversationViewSet,basename='conversation'); r.register('messages',MessageViewSet,basename='message'); r.register('reports',ReportViewSet,basename='report'); urlpatterns=r.urls
