"""Pre-approval report an admin reads before allocating a time: security, data quality and capacity."""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import Auction
from .scheduling import concurrent_count

OK, WARN, FAIL = 'ok', 'warn', 'fail'


def _check(key, label, status, detail):
    return {'key': key, 'label': label, 'status': status, 'detail': detail}


def build_report(a, start=None, end=None):
    seller, product, now = a.seller, a.product, timezone.now()
    profile = getattr(seller, 'seller_profile', None)
    checks = []

    checks.append(_check('seller_verified', 'Seller identity verified',
                         OK if profile and profile.approved and profile.verified else FAIL,
                         'Verified and approved seller.' if profile and profile.approved and profile.verified else 'Seller has not completed admin verification.'))
    checks.append(_check('seller_email', 'Seller email verified', OK if seller.email_verified else FAIL,
                         'Email verified.' if seller.email_verified else 'Seller email is not verified.'))
    checks.append(_check('seller_status', 'Seller account standing', FAIL if seller.is_suspended or not seller.is_active else OK,
                         'Account is suspended or inactive.' if seller.is_suspended or not seller.is_active else 'Account in good standing.'))

    age_days = (now - seller.created_at).days
    checks.append(_check('seller_age', 'Account age', WARN if age_days < 7 else OK, f'Account is {age_days} day(s) old.' + (' New accounts carry higher risk.' if age_days < 7 else '')))

    history = Auction.objects.filter(seller=seller).exclude(pk=a.pk)
    cancelled = history.filter(status='CANCELLED', created_at__gte=now - timedelta(days=30)).count()
    sold = history.filter(status='SOLD').count()
    checks.append(_check('seller_history', 'Seller track record', WARN if cancelled >= 3 else OK,
                         f'{sold} sold, {cancelled} cancelled/rejected in the last 30 days.'))

    images = product.images.count()
    desc_ok = len((product.description or '').strip()) >= 30
    checks.append(_check('listing_quality', 'Listing completeness', OK if images and desc_ok else WARN,
                         f'{images} photo(s); description {"is detailed" if desc_ok else "is very short"}.'))

    ref = Decimal(product.starting_price or 0)
    ratio = (Decimal(a.starting_price) / ref) if ref else None
    price_bad = ratio is not None and (ratio < Decimal('0.5') or ratio > Decimal('3'))
    checks.append(_check('price_sanity', 'Starting price vs reference price', WARN if price_bad else OK,
                         f'Starting price {a.starting_price} against reference {ref}.' + (' Unusually far apart.' if price_bad else '')))
    inc_bad = Decimal(a.min_increment) > Decimal(a.starting_price) / 2
    checks.append(_check('increment_sanity', 'Bid increment', WARN if inc_bad else OK,
                         f'Increment {a.min_increment} on a {a.starting_price} start.' + (' Very large; may deter bidders.' if inc_bad else '')))

    est = getattr(product, 'ai_estimate', None)
    if est and est.data.get('sellable'):
        lo, hi, cur = Decimal(str(est.data['estimated_low'])), Decimal(str(est.data['estimated_high'])), est.data.get('currency', '')
        start = Decimal(a.starting_price)
        if start > hi:
            st, msg = WARN, f'Starting price {start} is ABOVE the AI market estimate ({lo}-{hi} {cur}); it may not attract bids.'
        elif start < lo * Decimal('0.2'):
            st, msg = WARN, f'Starting price {start} is far below the AI market estimate ({lo}-{hi} {cur}). Check this is intended.'
        else:
            st, msg = OK, f'Starting price {start} is within a sensible range of the AI market estimate ({lo}-{hi} {cur}, {est.data.get("confidence")} confidence).'
        checks.append(_check('ai_estimate', 'AI market estimate', st, msg))
    dup = Auction.objects.filter(seller=seller, product__name__iexact=product.name, status__in=['PENDING_APPROVAL', 'SCHEDULED', 'LIVE']).exclude(pk=a.pk).exists()
    checks.append(_check('duplicate', 'Duplicate listing', WARN if dup else OK, 'Seller already has an active auction with the same title.' if dup else 'No duplicates found.'))

    s = start or a.requested_start_at or a.start_at
    e = end or a.requested_end_at or a.end_at
    if s and e and e > s:
        n = concurrent_count(s, e, exclude_pk=a.pk)
        cap = settings.AUCTION_MAX_CONCURRENT
        checks.append(_check('capacity', 'Capacity in that window', FAIL if n >= cap else WARN if n >= cap * 0.8 else OK,
                             f'{n} of {cap} concurrent auctions already booked in the window.'))
    else:
        checks.append(_check('capacity', 'Capacity in that window', OK, 'No window to check yet.'))

    overall = FAIL if any(c['status'] == FAIL for c in checks) else WARN if any(c['status'] == WARN for c in checks) else OK
    return {
        'overall': overall,
        'checks': checks,
        'seller': {'username': seller.username, 'email': seller.email, 'joined': seller.created_at, 'business_name': getattr(profile, 'business_name', '')},
        'request': {'is_24_7': a.is_24_7, 'requested_start_at': a.requested_start_at, 'requested_end_at': a.requested_end_at, 'seller_note': a.seller_note},
        'limits': {'min_minutes': settings.AUCTION_MIN_DURATION_MINUTES, 'max_days': settings.AUCTION_MAX_DURATION_DAYS, 'max_concurrent': settings.AUCTION_MAX_CONCURRENT},
    }
