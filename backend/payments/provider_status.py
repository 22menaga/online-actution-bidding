"""Is the payment provider usable right now? Cached so admin pages never hammer Razorpay."""
import requests
from django.conf import settings
from django.core.cache import cache

CACHE_KEY = 'payments.provider_status'


def provider_status(force=False):
    """-> {'provider', 'status': ok|invalid_keys|not_configured|unreachable|mock, 'detail'}"""
    if not force:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached
    if settings.PAYMENTS_MOCK:
        result = {'provider': 'mock', 'status': 'mock', 'detail': 'Test-mode checkout is on (no real money moves).'}
    elif not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        result = {'provider': 'razorpay', 'status': 'not_configured', 'detail': 'RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set in backend/.env.'}
    else:
        try:
            r = requests.get('https://api.razorpay.com/v1/payments?count=1', auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET), timeout=10)
        except requests.RequestException:
            result = {'provider': 'razorpay', 'status': 'unreachable', 'detail': 'Could not reach Razorpay (network problem?).'}
        else:
            if r.status_code == 200:
                mode = 'test' if settings.RAZORPAY_KEY_ID.startswith('rzp_test_') else 'LIVE'
                result = {'provider': 'razorpay', 'status': 'ok', 'detail': f'Razorpay accepted the {mode} keys.'}
            elif r.status_code in (401, 403):
                result = {'provider': 'razorpay', 'status': 'invalid_keys', 'detail': 'Razorpay rejected RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET. Regenerate a key pair in the Razorpay Dashboard and update backend/.env.'}
            else:
                result = {'provider': 'razorpay', 'status': 'unreachable', 'detail': f'Razorpay answered HTTP {r.status_code}.'}
    cache.set(CACHE_KEY, result, 300 if result['status'] == 'ok' else 30)
    return result
