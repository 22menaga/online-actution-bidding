import hashlib
import hmac
import json
from unittest.mock import patch

import requests
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from auctions.models import Auction
from payments.models import Payment
from products.models import Category, Product

KEYS = dict(RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='test_secret', RAZORPAY_WEBHOOK_SECRET='whsec_test', PAYMENT_CURRENCY='INR', PAYMENTS_MOCK=False)


def sign(secret, message):
    return hmac.new(secret.encode(), message.encode() if isinstance(message, str) else message, hashlib.sha256).hexdigest()


class RazorpayTests(TestCase):
    def setUp(self):
        seller = User.objects.create_user(username='seller', email='s@example.com', password='StrongPassword123!', role='SELLER')
        self.buyer = User.objects.create_user(username='buyer', email='b@example.com', password='StrongPassword123!', role='BUYER')
        cat = Category.objects.create(name='Coins', slug='coins')
        product = Product.objects.create(seller=seller, category=cat, name='Rare Coin', description='x', starting_price=10, condition='Good')
        auction = Auction.objects.create(product=product, seller=seller, starting_price=10, min_increment=1, start_at='2026-01-01T00:00:00Z', end_at='2026-01-02T00:00:00Z', status='SOLD', winner=self.buyer, current_highest_bid=1250.50)
        self.payment = Payment.objects.create(auction=auction, buyer=self.buyer, amount='1250.50')
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def checkout(self):
        return self.client.post(f'/api/payments/{self.payment.id}/checkout/')

    def rzp_payment(self, **over):
        return {'id': 'pay_1', 'order_id': 'order_1', 'amount': 125050, 'currency': 'INR', 'status': 'captured', **over}

    def open_order(self):
        Payment.objects.filter(pk=self.payment.pk).update(provider='razorpay', provider_payment_id='order_1', status='PROCESSING')
        self.payment.refresh_from_db()

    # ---- checkout
    @override_settings(**KEYS)
    @patch('payments.services.requests.request')
    def test_checkout_creates_order_in_paise(self, req):
        req.return_value.status_code = 200
        req.return_value.json.return_value = {'id': 'order_1', 'status': 'created'}
        r = self.checkout()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['order_id'], r.data['amount'], r.data['currency'], r.data['key_id']), ('order_1', 125050, 'INR', 'rzp_test_key'))
        self.assertEqual(req.call_args.kwargs['json']['amount'], 125050)
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.status, self.payment.provider, self.payment.provider_payment_id), ('PROCESSING', 'razorpay', 'order_1'))

    @override_settings(**KEYS)
    @patch('payments.services.requests.request')
    def test_repeated_checkout_reuses_the_open_order(self, req):
        req.return_value.status_code = 200
        req.return_value.json.return_value = {'id': 'order_1', 'status': 'created'}
        self.checkout(); second = self.checkout()
        self.assertEqual(second.data['order_id'], 'order_1')
        methods = [c.args[0] for c in req.call_args_list]
        self.assertEqual(methods.count('POST'), 1)  # only one order was ever created

    @override_settings(**{**KEYS, 'RAZORPAY_KEY_ID': '', 'RAZORPAY_KEY_SECRET': ''})
    def test_checkout_without_keys_is_clearly_unavailable(self):
        r = self.checkout()
        self.assertEqual((r.status_code, r.data['detail']), (503, 'Online checkout is not configured yet.'))

    @override_settings(**KEYS)
    @patch('payments.services.requests.request', side_effect=requests.ConnectionError('down'))
    def test_provider_outage_is_retryable_and_leaves_invoice_payable(self, _req):
        r = self.checkout()
        self.assertEqual(r.status_code, 503)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'PENDING')

    # ---- browser verification
    @override_settings(**KEYS)
    @patch('payments.services.requests.request')
    def test_valid_signature_marks_paid(self, req):
        self.open_order()
        req.return_value.status_code = 200
        req.return_value.json.return_value = self.rzp_payment()
        r = self.client.post(f'/api/payments/{self.payment.id}/verify/', {'razorpay_order_id': 'order_1', 'razorpay_payment_id': 'pay_1', 'razorpay_signature': sign('test_secret', 'order_1|pay_1')}, format='json')
        self.assertEqual((r.status_code, r.data['status']), (200, 'SUCCESS'))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.transaction_reference, 'pay_1')

    @override_settings(**KEYS)
    def test_forged_signature_is_rejected(self):
        self.open_order()
        r = self.client.post(f'/api/payments/{self.payment.id}/verify/', {'razorpay_order_id': 'order_1', 'razorpay_payment_id': 'pay_1', 'razorpay_signature': 'deadbeef'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'PROCESSING')

    @override_settings(**KEYS)
    def test_order_from_another_invoice_is_rejected(self):
        self.open_order()
        r = self.client.post(f'/api/payments/{self.payment.id}/verify/', {'razorpay_order_id': 'order_other', 'razorpay_payment_id': 'pay_1', 'razorpay_signature': sign('test_secret', 'order_other|pay_1')}, format='json')
        self.assertEqual(r.status_code, 400)

    @override_settings(**KEYS)
    @patch('payments.services.requests.request')
    def test_amount_mismatch_at_razorpay_is_rejected_even_with_valid_signature(self, req):
        self.open_order()
        req.return_value.status_code = 200
        req.return_value.json.return_value = self.rzp_payment(amount=100)
        r = self.client.post(f'/api/payments/{self.payment.id}/verify/', {'razorpay_order_id': 'order_1', 'razorpay_payment_id': 'pay_1', 'razorpay_signature': sign('test_secret', 'order_1|pay_1')}, format='json')
        self.assertEqual(r.status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'PROCESSING')

    @override_settings(**KEYS)
    def test_cannot_verify_someone_elses_invoice(self):
        self.open_order()
        other = User.objects.create_user(username='x', email='x@example.com', password='StrongPassword123!')
        c = APIClient(); c.force_authenticate(other)
        self.assertEqual(c.post(f'/api/payments/{self.payment.id}/verify/', {}, format='json').status_code, 404)

    # ---- webhook
    def webhook(self, event='payment.captured', secret='whsec_test', **entity_over):
        body = json.dumps({'event': event, 'payload': {'payment': {'entity': self.rzp_payment(**entity_over)}}}).encode()
        return self.client.post('/api/payments/webhook/razorpay/', body, content_type='application/json', HTTP_X_RAZORPAY_SIGNATURE=sign(secret, body))

    @override_settings(**KEYS)
    def test_signed_webhook_settles_payment(self):
        self.open_order()
        self.assertEqual(self.webhook().status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'SUCCESS')

    @override_settings(**KEYS)
    def test_webhook_with_wrong_signature_is_rejected(self):
        self.open_order()
        self.assertEqual(self.webhook(secret='wrong').status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'PROCESSING')

    @override_settings(**KEYS)
    def test_webhook_amount_mismatch_is_rejected(self):
        self.open_order()
        self.assertEqual(self.webhook(amount=1).status_code, 400)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'PROCESSING')

    @override_settings(**KEYS)
    def test_failed_payment_event_keeps_invoice_retryable(self):
        self.open_order()
        self.assertEqual(self.webhook('payment.failed', status='failed').status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'PROCESSING')


class ProviderDiagnosticsTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    @override_settings(**KEYS)
    @patch('payments.provider_status.requests.get')
    def test_invalid_keys_are_reported(self, get):
        get.return_value.status_code = 401
        from payments.provider_status import provider_status
        s = provider_status(force=True)
        self.assertEqual(s['status'], 'invalid_keys')

    @override_settings(**KEYS)
    @patch('payments.provider_status.requests.get')
    def test_valid_keys_are_reported_ok(self, get):
        get.return_value.status_code = 200
        from payments.provider_status import provider_status
        self.assertEqual(provider_status(force=True)['status'], 'ok')

    @override_settings(**{**KEYS, 'RAZORPAY_KEY_ID': '', 'RAZORPAY_KEY_SECRET': ''})
    def test_missing_keys_are_reported(self):
        from payments.provider_status import provider_status
        self.assertEqual(provider_status(force=True)['status'], 'not_configured')

    @override_settings(**KEYS)
    @patch('payments.services.requests.request')
    def test_rejected_credentials_give_a_safe_customer_message(self, req):
        req.return_value.status_code = 401
        seller = User.objects.create_user(username='s9', email='s9@example.com', password='StrongPassword123!', role='SELLER')
        buyer = User.objects.create_user(username='b9', email='b9@example.com', password='StrongPassword123!', role='BUYER')
        cat = Category.objects.create(name='C9', slug='c9')
        p = Product.objects.create(seller=seller, category=cat, name='X', description='x', starting_price=10, condition='Good')
        a = Auction.objects.create(product=p, seller=seller, starting_price=10, min_increment=1, start_at='2026-01-01T00:00:00Z', end_at='2026-01-02T00:00:00Z', status='SOLD', winner=buyer, current_highest_bid=10)
        pay = Payment.objects.create(auction=a, buyer=buyer, amount=10)
        c = APIClient(); c.force_authenticate(buyer)
        r = c.post(f'/api/payments/{pay.id}/checkout/')
        self.assertEqual(r.status_code, 503)
        self.assertNotIn('Authentication', r.data['detail'])  # never leak provider internals to customers
        self.assertIn('credentials', r.data['detail'])

    def test_health_reports_ok_when_migrated(self):
        r = self.client.get('/health/')
        self.assertEqual((r.status_code, r.content), (200, b'ok'))
