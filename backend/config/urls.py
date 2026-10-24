from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from config.security import LogoutView, SecureTokenObtainPairView
from config.health import readiness
urlpatterns=[path('admin/',admin.site.urls),path('api/auth/token/',SecureTokenObtainPairView.as_view(),name='token'),path('api/auth/logout/',LogoutView.as_view(),name='logout'),path('api/auth/token/refresh/',TokenRefreshView.as_view(),name='token_refresh'),path('api/accounts/',include('accounts.urls')),path('api/products/',include('products.urls')),path('api/auctions/',include('auctions.urls')),path('api/bidding/',include('bidding.urls')),path('api/payments/',include('payments.urls')),path('api/notifications/',include('notifications.urls')),path('api/messaging/',include('messaging.urls')),path('api/dashboard/',include('dashboard.urls')),path('api/audit/',include('audit.urls')),path('',include('dashboard.web_urls'))]
urlpatterns.insert(0, path('health/', readiness, name='health'))
if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
