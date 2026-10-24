from rest_framework.routers import DefaultRouter
from django.urls import path,include
from .views import RegisterView,ResendVerificationView,ProfileView,MeView,SellerVerificationViewSet,AdminUserViewSet,VerifyEmailView,PasswordResetRequestView,PasswordResetConfirmView
r=DefaultRouter(); r.register('seller-verifications',SellerVerificationViewSet,basename='seller-verification'); r.register('admin/users',AdminUserViewSet,basename='admin-user')
urlpatterns=[path('register/',RegisterView.as_view()),path('resend-verification/',ResendVerificationView.as_view()),path('verify/<uidb64>/<token>/',VerifyEmailView.as_view()),path('password-reset/',PasswordResetRequestView.as_view()),path('password-reset/<uidb64>/<token>/',PasswordResetConfirmView.as_view()),path('me/',MeView.as_view()),path('profile/',ProfileView.as_view()),path('',include(r.urls))]
