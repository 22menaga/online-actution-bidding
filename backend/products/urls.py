from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import AIEstimateStatusView,AIEstimateView,CategoryViewSet,ProductViewSet
r=DefaultRouter(); r.register('categories',CategoryViewSet); r.register('products',ProductViewSet)
urlpatterns=[path('ai-estimate/',AIEstimateView.as_view()),path('ai-estimate/status/',AIEstimateStatusView.as_view())]+r.urls
