"""Razorpay payment integration (Orders API + Checkout.js + signature verification).

Flow
  1. create_checkout():  server creates a Razorpay *order* for the exact invoice amount.
  2. Browser opens Razorpay Checkout with that order id (the amount can't be changed client-side).
  3. verify_payment():   browser posts back payment id + signature; the server verifies the HMAC
                         with the secret key AND re-fetches the payment from Razorpay to confirm
                         order, amount, currency and captured status before marking it paid.
  4. process_webhook():  signed server-to-server events settle payments even if the tab was closed.
Provider fields: Payment.provider_payment_id = Razorpay order id,
                 Payment.transaction_reference = Razorpay payment id.
"""
import hashlib
import hmac
import json
import logging
from decimal import ROUND_HALF_UP, Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit
from notifications.services import notify_user
from .models import Payment

logger = logging.getLogger(__name__)

API_BASE = "https://api.razorpay.com/v1"


class PaymentWebhookError(ValueError):
    pass


class PaymentVerificationError(ValueError):
    pass


class CheckoutConflictError(ValueError):
    pass


class CheckoutUnavailableError(RuntimeError):
    pass


def razorpay_configured():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def to_minor_units(amount):
    """Razorpay amounts are integers in the smallest currency unit (paise)."""
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _call(method, path, **kwargs):
    try:
        response = requests.request(
            method,
            f"{API_BASE}{path}",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            timeout=15,
            **kwargs,
        )
    except requests.RequestException as exc:
        logger.exception("Razorpay request failed: %s %s", method, path)
        raise CheckoutUnavailableError("Razorpay is temporarily unavailable. Please retry.") from exc
    if response.status_code in (401, 403):
        logger.error("Razorpay rejected the API credentials (HTTP %s). Check RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET.", response.status_code)
        raise CheckoutUnavailableError("Payments are temporarily unavailable: the payment provider rejected our credentials. Please contact support.")
    if response.status_code >= 500:
        raise CheckoutUnavailableError("Razorpay is temporarily unavailable. Please retry.")
    if response.status_code >= 400:
        logger.warning("Razorpay rejected %s %s: %s", method, path, response.text[:300])
        try:
            reason = response.json().get("error", {}).get("description", "")
        except ValueError:
            reason = ""
        raise CheckoutUnavailableError(f"Razorpay could not process the request. {reason}".strip())
    return response.json()


def _checkout_payload(payment, order_id):
    return {
        "provider": "razorpay",
        "mock": False,
        "key_id": settings.RAZORPAY_KEY_ID,
        "order_id": order_id,
        "amount": to_minor_units(payment.amount),
        "currency": settings.PAYMENT_CURRENCY,
        "name": "Auction House",
        "description": payment.auction.product.name,
    }


@transaction.atomic
def create_checkout(payment, method=None):
    """method: 'razorpay' | 'fake'. Omitted = legacy behaviour (fake only when PAYMENTS_MOCK is on)."""
    method = method or ('fake' if settings.PAYMENTS_MOCK else 'razorpay')
    payment = Payment.objects.select_for_update().select_related("auction__product", "buyer").get(pk=payment.pk)
    if payment.status not in {Payment.Status.PENDING, Payment.Status.PROCESSING}:
        raise CheckoutConflictError("Payment is not payable.")

    if method == 'fake':
        if not (settings.PAYMENTS_MOCK or settings.FAKE_PAYMENTS_ENABLED):
            raise CheckoutUnavailableError('Fake test payments are disabled on this server.')
        payment.provider = "mock"
        payment.status = Payment.Status.PROCESSING
        payment.save(update_fields=["provider", "status", "updated_at"])
        return {"provider": "mock", "mock": True, "checkout_url": f"{settings.FRONTEND_URL}/checkout/{payment.id}"}

    if not razorpay_configured():
        raise CheckoutUnavailableError("Online checkout is not configured yet.")

    # Reuse the open order so a retry or double-click never creates a second charge.
    if payment.status == Payment.Status.PROCESSING and payment.provider == "razorpay" and payment.provider_payment_id:
        order = _call("GET", f"/orders/{payment.provider_payment_id}")
        if order.get("status") != "paid":
            return _checkout_payload(payment, payment.provider_payment_id)
        raise CheckoutConflictError("This invoice has already been paid. Refresh to see the update.")

    order = _call(
        "POST",
        "/orders",
        json={
            "amount": to_minor_units(payment.amount),
            "currency": settings.PAYMENT_CURRENCY,
            "receipt": f"invoice_{payment.id}",
            "notes": {"payment_id": str(payment.id), "auction_id": str(payment.auction_id)},
        },
    )
    payment.provider = "razorpay"
    payment.provider_payment_id = order["id"]
    payment.status = Payment.Status.PROCESSING
    payment.save(update_fields=["provider", "provider_payment_id", "status", "updated_at"])
    return _checkout_payload(payment, order["id"])


def _mark_paid(payment, rzp_payment_id):
    payment.status = Payment.Status.SUCCESS
    payment.paid_at = timezone.now()
    payment.transaction_reference = rzp_payment_id or ""
    payment.save(update_fields=["status", "paid_at", "transaction_reference", "updated_at"])
    record_audit(payment.buyer, "PAYMENT_STATE_CHANGED", payment, {"status": payment.status, "provider": "razorpay"})
    notify_user(payment.buyer, "Payment update", f"Payment {payment.id} is success.")


def _matches_invoice(payment, rzp_payment):
    return (
        rzp_payment.get("order_id") == payment.provider_payment_id
        and rzp_payment.get("amount") == to_minor_units(payment.amount)
        and (rzp_payment.get("currency") or "").upper() == settings.PAYMENT_CURRENCY
    )


@transaction.atomic
def verify_payment(payment, rzp_payment_id, rzp_order_id, signature):
    """Called by the browser after Checkout succeeds. Never trusts the client: verifies the HMAC signature
    and then confirms the payment details directly with Razorpay."""
    if not settings.RAZORPAY_KEY_SECRET:
        raise CheckoutUnavailableError("Online checkout is not configured yet.")
    payment = Payment.objects.select_for_update().select_related("buyer", "auction").get(pk=payment.pk)
    if payment.status in {Payment.Status.SUCCESS, Payment.Status.REFUNDED}:
        return payment
    if not payment.provider_payment_id or rzp_order_id != payment.provider_payment_id:
        raise PaymentVerificationError("Order does not belong to this invoice.")

    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(), f"{rzp_order_id}|{rzp_payment_id}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, str(signature or "")):
        raise PaymentVerificationError("Invalid payment signature.")

    rzp_payment = _call("GET", f"/payments/{rzp_payment_id}")
    if not _matches_invoice(payment, rzp_payment):
        raise PaymentVerificationError("Payment details do not match the invoice.")
    if rzp_payment.get("status") == "authorized":  # accounts without auto-capture
        rzp_payment = _call("POST", f"/payments/{rzp_payment_id}/capture", json={"amount": rzp_payment["amount"], "currency": rzp_payment["currency"]})
    if rzp_payment.get("status") != "captured":
        raise PaymentVerificationError("Payment has not been captured.")
    _mark_paid(payment, rzp_payment_id)
    return payment


@transaction.atomic
def sync_payment(payment):
    """Ask Razorpay whether the open order has been paid (used if the browser never posted back)."""
    if not razorpay_configured() or payment.provider != "razorpay" or not payment.provider_payment_id:
        return payment
    payment = Payment.objects.select_for_update().select_related("buyer", "auction").get(pk=payment.pk)
    if payment.status != Payment.Status.PROCESSING:
        return payment
    items = _call("GET", f"/orders/{payment.provider_payment_id}/payments").get("items", [])
    for item in items:
        if item.get("status") == "captured" and _matches_invoice(payment, item):
            _mark_paid(payment, item["id"])
            break
    return payment


@transaction.atomic
def process_webhook(payload, signature):
    """Razorpay webhook (Dashboard -> Webhooks). Verified with RAZORPAY_WEBHOOK_SECRET."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise PaymentWebhookError("Razorpay webhook verification is not configured.")
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        raise PaymentWebhookError("Invalid Razorpay webhook signature.")
    try:
        event = json.loads(payload)
    except ValueError as exc:
        raise PaymentWebhookError("Invalid webhook payload.") from exc

    event_type = event.get("event")
    if event_type not in {"payment.captured", "order.paid", "payment.failed"}:
        return None
    entity = (event.get("payload", {}).get("payment", {}) or {}).get("entity") or {}
    order_id = entity.get("order_id")
    payment = Payment.objects.select_for_update().select_related("buyer", "auction").filter(provider="razorpay", provider_payment_id=order_id).first() if order_id else None
    if payment is None:
        from . import wallet  # the order may belong to a coin top-up instead of an invoice
        if event_type in {"payment.captured", "order.paid"} and order_id:
            try:
                topup = wallet.settle_topup_from_webhook(order_id, entity)
            except PaymentVerificationError as exc:
                raise PaymentWebhookError(str(exc)) from exc
            if topup is not None:
                return topup
        raise PaymentWebhookError("Webhook references an unknown order.")
    if not _matches_invoice(payment, entity):
        raise PaymentWebhookError("Webhook payment details do not match the invoice.")
    if payment.status in {Payment.Status.SUCCESS, Payment.Status.REFUNDED}:
        return payment

    if event_type == "payment.failed":
        # The customer may retry on the same order, so the invoice stays payable.
        record_audit(payment.buyer, "PAYMENT_ATTEMPT_FAILED", payment, {"reason": entity.get("error_description", "")})
        notify_user(payment.buyer, "Payment failed", f"A payment attempt for invoice {payment.id} failed. You can retry.")
        return payment
    _mark_paid(payment, entity.get("id"))
    return payment


@transaction.atomic
def mock_pay(payment, success=True):
    """Test-mode settlement used by the demo checkout page. Disabled unless PAYMENTS_MOCK is on."""
    if not (settings.PAYMENTS_MOCK or settings.FAKE_PAYMENTS_ENABLED):
        raise CheckoutUnavailableError("Test-mode payments are disabled.")
    payment = Payment.objects.select_for_update().select_related("buyer").get(pk=payment.pk)
    if payment.status not in {Payment.Status.PENDING, Payment.Status.PROCESSING}:
        raise CheckoutConflictError("Payment is not payable.")
    if success:
        payment.status = Payment.Status.SUCCESS
        payment.paid_at = timezone.now()
        payment.transaction_reference = f"mock_{payment.id}_{int(payment.paid_at.timestamp())}"
    else:
        payment.status = Payment.Status.FAILED
    payment.save(update_fields=["status", "paid_at", "transaction_reference", "updated_at"])
    record_audit(payment.buyer, "PAYMENT_STATE_CHANGED", payment, {"status": payment.status, "mock": True})
    notify_user(payment.buyer, "Payment update", f"Payment {payment.id} is {payment.status.lower()}.")
    return payment
