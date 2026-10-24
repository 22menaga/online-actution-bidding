"""Security layer: hardened login (brute-force lockout), token revocation, bid throttles and response headers."""
import logging

from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from audit.services import record_audit
from django.conf import settings

logger = logging.getLogger(__name__)


def client_ip(request):
    """Best-effort client address. Behind a proxy, configure it to set X-Forwarded-For and keep SECURE_PROXY_SSL_HEADER."""
    fwd = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (fwd.split(',')[0].strip() if fwd and not settings.DEBUG else request.META.get('REMOTE_ADDR', '')) or 'unknown'


# ------------------------------------------------------------------ login with lockout
def _keys(username, ip):
    u = (username or '').strip().lower()[:150]
    return f'login-fail:user-ip:{u}:{ip}', f'login-fail:user:{u}'


class LoginRequest(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256)


class SecureTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/token/ - rate limited per IP, plus a lockout after repeated failures for the same account.

    * 5 failures for a username from one IP (LOGIN_LOCK_THRESHOLD) locks that pair for LOGIN_LOCK_MINUTES.
    * 30 failures for a username from anywhere locks the account's logins for the same period (credential stuffing).
    * Wrong password and unknown user give the same answer, so usernames cannot be probed.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request, *args, **kwargs):
        s = LoginRequest(data=request.data)
        if not s.is_valid():
            return Response({'detail': 'Enter a username and password.'}, status=400)
        username, ip = s.validated_data['username'], client_ip(request)
        pair_key, user_key = _keys(username, ip)
        window = settings.LOGIN_LOCK_MINUTES * 60
        if cache.get(pair_key, 0) >= settings.LOGIN_LOCK_THRESHOLD or cache.get(user_key, 0) >= settings.LOGIN_LOCK_THRESHOLD * 6:
            record_audit(None, 'LOGIN_BLOCKED', None, {'username': username[:80]}, request=request)
            r = Response({'detail': f'Too many failed attempts. Try again in about {settings.LOGIN_LOCK_MINUTES} minutes.', 'code': 'locked'}, status=429)
            r['Retry-After'] = str(window)
            return r
        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:  # SimpleJWT signals bad credentials by raising, not by returning a 401
            response = None
        if response is not None and response.status_code == 200:
            cache.delete(pair_key)
            return response
        if response is None:
            for k in (pair_key, user_key):
                cache.add(k, 0, window)
                try:
                    cache.incr(k)
                except ValueError:
                    cache.set(k, 1, window)
            fails = cache.get(pair_key, 0)
            record_audit(None, 'LOGIN_FAILED', None, {'username': username[:80], 'attempt': fails}, request=request)
            if fails >= settings.LOGIN_LOCK_THRESHOLD:
                record_audit(None, 'ACCOUNT_LOCKED', None, {'username': username[:80], 'minutes': settings.LOGIN_LOCK_MINUTES}, request=request)
            left = max(settings.LOGIN_LOCK_THRESHOLD - fails, 0)
            return Response({'detail': 'Invalid username or password.' + (f' {left} attempt{"s" if left != 1 else ""} left before a temporary lock.' if 0 < left <= 2 else '')}, status=401)
        return response


class LogoutView(APIView):
    """POST /api/auth/logout/ {refresh} - revokes the refresh token so a stolen copy stops working. Always answers 204."""
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        try:
            RefreshToken(str(request.data.get('refresh', ''))).blacklist()
        except (TokenError, Exception):  # already expired / invalid / blacklisted: nothing to revoke
            pass
        return Response(status=204)


# ------------------------------------------------------------------ bid throttles
class BidUserThrottle(SimpleRateThrottle):
    """Caps a user's total bids per minute across all auctions (bots, runaway scripts)."""
    scope = 'bid'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': f'u{request.user.pk}'} if request.user.is_authenticated else None


class BidAuctionThrottle(SimpleRateThrottle):
    """Caps one user's bids on a single auction per minute (blocks hammering one lot)."""
    scope = 'bid_auction'

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': f'u{request.user.pk}:a{str(request.data.get("auction", ""))[:12]}'}


# ------------------------------------------------------------------ response headers
class SecurityHeadersMiddleware:
    """Adds the headers Django's SecurityMiddleware does not: CSP, Permissions-Policy, COOP/CORP and no-store for API data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        r = self.get_response(request)
        r.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(self), usb=()')
        r.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        path = request.path
        if path.startswith(('/api/', '/health')):
            r['Cache-Control'] = 'no-store'  # private data must never sit in a shared/browser cache
            r.setdefault('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'")
            r.setdefault('Cross-Origin-Resource-Policy', 'same-site')
        elif path.startswith('/admin/'):
            r.setdefault('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'")
        return r
