from django.urls import path
from .views import AnalyticsView, AdminOverviewView
from .people_admin import AdminPeopleListView, AdminPersonDetailView, AdminPersonSuspendView
from .auction_admin import AdminAuctionDetailView, AdminAuctionListView, AdminAuctionSummaryView
urlpatterns=[path('analytics/',AnalyticsView.as_view()),path('overview/',AdminOverviewView.as_view()),path('auctions/',AdminAuctionListView.as_view()),path('auctions/summary/',AdminAuctionSummaryView.as_view()),path('auctions/<int:pk>/',AdminAuctionDetailView.as_view()),path('people/',AdminPeopleListView.as_view()),path('people/<int:pk>/',AdminPersonDetailView.as_view()),path('people/<int:pk>/suspend/',AdminPersonSuspendView.as_view())]
