from django.urls import path
from .views import BidListCreateView,AuctionBidHistoryView
urlpatterns=[path('bids/',BidListCreateView.as_view()),path('auctions/<int:pk>/bids/',AuctionBidHistoryView.as_view())]
