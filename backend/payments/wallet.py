"""In-app coin wallet.

  * 1 coin = COIN_VALUE rupees (default 1).
  * Every change is a ledger row (WalletTransaction) written in the same DB transaction as the balance change, with the
    balance locked (SELECT ... FOR UPDATE), so balances cannot drift or be double-spent.
  * Bidders top up coins with Razorpay or a fake test payment, then pay won items with coins.
    The seller is credited coins when the invoice is paid (minus an optional platform fee).
"""
import hashlib
import hmac
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit
from notifications.services import notify_user
from .models import Payment, TopUp, Wallet, WalletTransaction
from .services import (CheckoutConflictError, CheckoutUnavailableError, PaymentVerificationError, _call, razorpay_configured, to_minor_units)

logger = logging.getLogger(__name__)
CENT = Decimal('0.01')


class InsufficientCoins(ValueError):
    def __init__(self, balance, needed):
        super().__init__(f'Not enough coins: you have {balance:g} and need {needed:g}.')
        self.balance, self.needed = balance, needed


def coins_to_money(coins):
    return (Decimal(coins) * Decimal(str(settings.COIN_VALUE))).quantize(CENT, rounding=ROUND_HALF_UP)


def money_to_coins(amount):
    return (Decimal(amount) / Decimal(str(settings.COIN_VALUE))).quantize(CENT, rounding=ROUND_HALF_UP)


def wallet_for(user):
    return Wallet.objects.get_or_create(user=user)[0]


def _locked(user):
    wallet_for(user)
    return Wallet.objects.select_for_update().get(user=user)


@transaction.atomic
def credit(user, coins, kind, description, reference=''):
    coins = Decimal(coins)
    assert coins > 0
    w = _locked(user)
    w.balance += coins
    w.save(update_fields=['balance', 'updated_at'])
    return WalletTransaction.objects.create(wallet=w, kind=kind, amount=coins, balance_after=w.balance, description=description[:200], reference=reference[:100])


@transaction.atomic
def debit(user, coins, kind, description, reference=''):
    coins = Decimal(coins)
    assert coins > 0
    w = _locked(user)
    if w.balance < coins:
        raise InsufficientCoins(w.balance, coins)
    w.balance -= coins
    w.save(update_fields=['balance', 'updated_at'])
    return WalletTransaction.objects.create(wallet=w, kind=kind, amount=-coins, balance_after=w.balance, description=description[:200], reference=reference[:100])


# ------------------------------------------------------------------ paying an invoice with coins
@transaction.atomic
def pay_invoice_with_coins(payment):
    """Buyer pays a won-auction invoice from their coin balance; the seller's wallet is credited."""
    p = Payment.objects.select_for_update().select_related('auction__product', 'auction__seller', 'buyer').get(pk=payment.pk)
    if p.status not in (Payment.Status.PENDING, Payment.Status.PROCESSING):
        raise CheckoutConflictError('This invoice is not payable (it may already be paid).')
    coins = money_to_coins(p.amount)
    name = p.auction.product.name
    debit(p.buyer, coins, WalletTransaction.Kind.PURCHASE, f'Paid for {name}', reference=f'payment:{p.id}')
    fee_pct = Decimal(str(settings.PLATFORM_FEE_PERCENT))
    fee = (coins * fee_pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    seller_coins = coins - fee
    if seller_coins > 0:
        credit(p.auction.seller, seller_coins, WalletTransaction.Kind.SALE, f'Sale of {name}' + (f' (after {fee_pct:g}% platform fee)' if fee else ''), reference=f'payment:{p.id}')
    p.provider, p.status, p.paid_at, p.transaction_reference = 'coins', Payment.Status.SUCCESS, timezone.now(), f'coins_{p.id}'
    p.save(update_fields=['provider', 'status', 'paid_at', 'transaction_reference', 'updated_at'])
    record_audit(p.buyer, 'PAYMENT_STATE_CHANGED', p, {'status': p.status, 'provider': 'coins', 'coins': str(coins)})
    notify_user(p.buyer, 'Payment update', f'Payment {p.id} is success. You paid {coins:g} coins for {name}.')
    notify_user(p.auction.seller, 'Sale paid', f'{name} was paid for. {seller_coins:g} coins were added to your wallet.')
    return p


# ------------------------------------------------------------------ top-ups
def _check_amount(coins):
    try:
        coins = Decimal(str(coins))
    except InvalidOperation:
        raise CheckoutConflictError('Enter a whole number of coins.')
    if not coins.is_finite() or coins != coins.to_integral_value() or not (settings.COIN_TOPUP_MIN <= coins <= settings.COIN_TOPUP_MAX):
        raise CheckoutConflictError(f'Choose between {settings.COIN_TOPUP_MIN} and {settings.COIN_TOPUP_MAX} whole coins.')
    return coins


@transaction.atomic
def start_topup(user, coins, method):
    coins = _check_amount(coins)
    amount = coins_to_money(coins)
    if method == 'fake':
        if not (settings.FAKE_PAYMENTS_ENABLED or settings.PAYMENTS_MOCK):
            raise CheckoutUnavailableError('Fake test payments are disabled on this server.')
        t = TopUp.objects.create(user=user, coins=coins, amount=amount, provider='fake')
        return t, {'provider': 'fake', 'topup_id': t.id, 'coins': int(coins), 'amount': str(amount)}
    if method != 'razorpay':
        raise CheckoutConflictError('Unknown payment method.')
    if not razorpay_configured():
        raise CheckoutUnavailableError('Online payments are not configured yet.')
    t = TopUp.objects.create(user=user, coins=coins, amount=amount, provider='razorpay')
    order = _call('POST', '/orders', json={'amount': to_minor_units(amount), 'currency': settings.PAYMENT_CURRENCY, 'receipt': f'topup_{t.id}', 'notes': {'topup_id': str(t.id), 'user_id': str(user.id)}})
    t.provider_order_id = order['id']
    t.save(update_fields=['provider_order_id'])
    return t, {'provider': 'razorpay', 'mock': False, 'topup_id': t.id, 'key_id': settings.RAZORPAY_KEY_ID, 'order_id': order['id'], 'amount': to_minor_units(amount), 'currency': settings.PAYMENT_CURRENCY,
               'name': 'Auction House', 'description': f'{int(coins)} coins'}


@transaction.atomic
def _settle(topup, provider_payment_id=''):
    """Credit the coins exactly once (safe to call from the browser verify AND the webhook)."""
    t = TopUp.objects.select_for_update().get(pk=topup.pk)
    if t.status == TopUp.Status.SUCCESS:
        return t
    credit(t.user, t.coins, WalletTransaction.Kind.TOPUP, f'Top-up via {t.provider}', reference=f'topup:{t.id}')
    t.status, t.provider_payment_id, t.completed_at = TopUp.Status.SUCCESS, provider_payment_id, timezone.now()
    t.save(update_fields=['status', 'provider_payment_id', 'completed_at'])
    record_audit(t.user, 'WALLET_TOPUP', t, {'coins': str(t.coins), 'provider': t.provider})
    notify_user(t.user, 'Coins added', f'{t.coins:g} coins were added to your wallet.')
    return t


def fake_complete_topup(topup, success=True):
    if not (settings.FAKE_PAYMENTS_ENABLED or settings.PAYMENTS_MOCK):
        raise CheckoutUnavailableError('Fake test payments are disabled on this server.')
    with transaction.atomic():
        t = TopUp.objects.select_for_update().get(pk=topup.pk)
        if t.provider != 'fake' or t.status != TopUp.Status.PENDING:
            raise CheckoutConflictError('This top-up cannot be completed.')
        if not success:
            t.status = TopUp.Status.FAILED
            t.save(update_fields=['status'])
            return t
    return _settle(topup, f'fake_{topup.id}')


def verify_topup(topup, rzp_payment_id, rzp_order_id, signature):
    if not settings.RAZORPAY_KEY_SECRET:
        raise CheckoutUnavailableError('Online payments are not configured yet.')
    t = TopUp.objects.get(pk=topup.pk)
    if t.status == TopUp.Status.SUCCESS:
        return t
    if t.provider != 'razorpay' or rzp_order_id != t.provider_order_id:
        raise PaymentVerificationError('Order does not belong to this top-up.')
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f'{rzp_order_id}|{rzp_payment_id}'.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(signature or '')):
        raise PaymentVerificationError('Invalid payment signature.')
    rp = _call('GET', f'/payments/{rzp_payment_id}')
    if rp.get('order_id') != t.provider_order_id or rp.get('amount') != to_minor_units(t.amount) or (rp.get('currency') or '').upper() != settings.PAYMENT_CURRENCY:
        raise PaymentVerificationError('Payment details do not match the top-up.')
    if rp.get('status') == 'authorized':
        rp = _call('POST', f'/payments/{rzp_payment_id}/capture', json={'amount': rp['amount'], 'currency': rp['currency']})
    if rp.get('status') != 'captured':
        raise PaymentVerificationError('Payment has not been captured.')
    return _settle(t, rzp_payment_id)


def settle_topup_from_webhook(order_id, entity):
    """Called by the Razorpay webhook for orders that belong to a top-up. Returns the TopUp or None if unknown."""
    t = TopUp.objects.filter(provider='razorpay', provider_order_id=order_id).first()
    if t is None:
        return None
    if entity.get('amount') != to_minor_units(t.amount) or (entity.get('currency') or '').upper() != settings.PAYMENT_CURRENCY:
        raise PaymentVerificationError('Webhook payment details do not match the top-up.')
    return _settle(t, entity.get('id', ''))
