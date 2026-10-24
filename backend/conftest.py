import pytest


@pytest.fixture(autouse=True)
def _real_payment_provider_by_default(settings):
    # Local .env enables test-mode checkout; tests exercise the real Razorpay path unless they opt in.
    from django.core.cache import cache
    cache.clear()  # throttles and lockouts live in the cache; keep tests independent
    settings.PAYMENTS_MOCK = False
    settings.FAKE_PAYMENTS_ENABLED = False
    settings.AUTO_VERIFY_EMAIL = False  # tests exercise the real email-verification path unless they opt in
