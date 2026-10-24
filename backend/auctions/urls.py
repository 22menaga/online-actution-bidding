from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import AuctionViewSet, TimeRequestListView, TimeRequestResolveView
r=DefaultRouter(); r.register('auctions',AuctionViewSet)
urlpatterns=[path('time-requests/',TimeRequestListView.as_view()),path('time-requests/<int:pk>/resolve/',TimeRequestResolveView.as_view())]+r.urls
