import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from auctions.models import Auction
from auctions.services import close_auction
from bidding.services import place_bid
from payments import wallet
from payments.models import Payment, TopUp, WalletTransaction

KEYS = dict(RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='test_secret', RAZORPAY_WEBHOOK_SECRET='whsec', PAYMENT_CURRENCY='INR', COIN_VALUE=1.0, COIN_TOPUP_MIN=10, COIN_TOPUP_MAX=100000)


def sig(secret, msg):
    return hmac.new(secret.encode(), msg.encode() if isinstance(msg, str) else msg, hashlib.sha256).hexdigest()


class WalletBase(TestCase):
    def setUp(self):
        call_command('seed_demo', verbosity=0)
        self.buyer, self.other = User.objects.get(username='demo_buyer'), User.objects.get(username='demo_buyer2')
        self.seller = User.objects.get(username='demo_seller')
        a = Auction.objects.filter(status='LIVE').first()
        place_bid(auction_id=a.id, bidder=self.buyer, amount=a.required_minimum())  # Rs 300 for the first demo item
        Auction.objects.filter(pk=a.pk).update(end_at=timezone.now() - timedelta(seconds=1))
        close_auction(a.id)
        self.payment = Payment.objects.get(auction=a)
        self.c = APIClient()
        self.c.force_authenticate(self.buyer)

    def balance(self, user):
        return wallet.wallet_for(user).balance


@override_settings(**KEYS)
class CoinPaymentTests(WalletBase):
    def test_pay_with_coins_moves_money_and_credits_the_seller(self):
        wallet.credit(self.buyer, 500, 'TOPUP', 'seed')
        r = self.c.post(f'/api/payments/{self.payment.id}/pay-coins/')
        self.assertEqual((r.status_code, r.json()['status']), (200, 'SUCCESS'))
        self.assertEqual((self.balance(self.buyer), self.balance(self.seller)), (Decimal('200'), Decimal('300')))
        self.payment.refresh_from_db()
        self.assertEqual((self.payment.provider, self.payment.status), ('coins', 'SUCCESS'))
        self.assertTrue({'PURCHASE', 'SALE'} <= {t.kind for t in WalletTransaction.objects.all()})

    def test_insufficient_coins_is_a_clear_402_and_changes_nothing(self):
        wallet.credit(self.buyer, 100, 'TOPUP', 'seed')
        r = self.c.post(f'/api/payments/{self.payment.id}/pay-coins/')
        self.assertEqual(r.status_code, 402)
        self.assertEqual((r.json()['code'], Decimal(str(r.json()['shortfall']))), ('insufficient_coins', Decimal('200')))
        self.assertEqual(self.balance(self.buyer), Decimal('100'))
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'PENDING')

    def test_cannot_pay_the_same_invoice_twice(self):
        wallet.credit(self.buyer, 900, 'TOPUP', 'seed')
        self.assertEqual(self.c.post(f'/api/payments/{self.payment.id}/pay-coins/').status_code, 200)
        self.assertEqual(self.c.post(f'/api/payments/{self.payment.id}/pay-coins/').status_code, 409)
        self.assertEqual(self.balance(self.buyer), Decimal('600'))  # charged once

    def test_another_users_invoice_is_404_and_sellers_cannot_pay(self):
        wallet.credit(self.other, 900, 'TOPUP', 'seed')
        o = APIClient()
        o.force_authenticate(self.other)
        self.assertEqual(o.post(f'/api/payments/{self.payment.id}/pay-coins/').status_code, 404)
        s = APIClient()
        s.force_authenticate(self.seller)
        self.assertEqual(s.post(f'/api/payments/{self.payment.id}/pay-coins/').status_code, 403)

    @override_settings(PLATFORM_FEE_PERCENT=10.0)
    def test_platform_fee_is_taken_from_the_sellers_credit(self):
        wallet.credit(self.buyer, 300, 'TOPUP', 'seed')
        self.c.post(f'/api/payments/{self.payment.id}/pay-coins/')
        self.assertEqual(self.balance(self.seller), Decimal('270'))

    def test_ledger_always_matches_the_balance_and_never_goes_negative(self):
        wallet.credit(self.buyer, 50, 'TOPUP', 'a')
        wallet.debit(self.buyer, 20, 'PURCHASE', 'b')
        with self.assertRaises(wallet.InsufficientCoins):
            wallet.debit(self.buyer, 31, 'PURCHASE', 'c')
        w = wallet.wallet_for(self.buyer)
        self.assertEqual(w.balance, sum(t.amount for t in w.transactions.all()))
        self.assertEqual(w.transactions.first().balance_after, w.balance)

    def test_wallet_endpoint_shows_balance_and_history(self):
        wallet.credit(self.buyer, 120, 'TOPUP', 'Top-up via fake')
        d = self.c.get('/api/payments/wallet/').json()
        self.assertEqual((Decimal(str(d['balance'])), d['transactions'][0]['kind']), (Decimal('120'), 'TOPUP'))
        self.assertEqual(APIClient().get('/api/payments/wallet/').status_code, 401)


@override_settings(**KEYS)
class TopUpTests(WalletBase):
    @override_settings(FAKE_PAYMENTS_ENABLED=True)
    def test_fake_topup_credits_coins_once(self):
        r = self.c.post('/api/payments/wallet/topup/', {'coins': 500, 'method': 'fake'}, format='json')
        self.assertEqual((r.status_code, r.json()['provider']), (201, 'fake'))
        tid = r.json()['topup_id']
        self.assertEqual(self.c.post(f'/api/payments/wallet/topup/{tid}/fake-pay/', {}, format='json').json()['balance'], 500)
        self.assertEqual(self.c.post(f'/api/payments/wallet/topup/{tid}/fake-pay/', {}, format='json').status_code, 409)  # not twice
        self.assertEqual(self.balance(self.buyer), Decimal('500'))

    def test_fake_payments_are_off_unless_enabled(self):
        r = self.c.post('/api/payments/wallet/topup/', {'coins': 100, 'method': 'fake'}, format='json')
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.balance(self.buyer), 0)

    def test_amount_limits(self):
        for coins in (0, 5, 100001, 12.5, 'abc'):
            self.assertEqual(self.c.post('/api/payments/wallet/topup/', {'coins': coins, 'method': 'razorpay'}, format='json').status_code, 400, coins)

    @patch('payments.services.requests.request')
    def test_razorpay_topup_creates_an_order_in_paise_and_verifies_the_signature(self, req):
        req.return_value.status_code = 200
        req.return_value.json.return_value = {'id': 'order_T1'}
        r = self.c.post('/api/payments/wallet/topup/', {'coins': 1000, 'method': 'razorpay'}, format='json')
        d = r.json()
        self.assertEqual((r.status_code, d['order_id'], d['amount']), (201, 'order_T1', 100000))
        good = {'razorpay_order_id': 'order_T1', 'razorpay_payment_id': 'pay_T1', 'razorpay_signature': sig('test_secret', 'order_T1|pay_T1')}
        bad = self.c.post(f"/api/payments/wallet/topup/{d['topup_id']}/verify/", {**good, 'razorpay_signature': 'forged'}, format='json')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.balance(self.buyer), 0)
        req.return_value.json.return_value = {'id': 'pay_T1', 'order_id': 'order_T1', 'amount': 100000, 'currency': 'INR', 'status': 'captured'}
        ok = self.c.post(f"/api/payments/wallet/topup/{d['topup_id']}/verify/", good, format='json')
        self.assertEqual((ok.status_code, ok.json()['balance']), (200, 1000))
        self.c.post(f"/api/payments/wallet/topup/{d['topup_id']}/verify/", good, format='json')  # a repeat must not credit again
        self.assertEqual(self.balance(self.buyer), Decimal('1000'))

    @patch('payments.services.requests.request')
    def test_webhook_credits_a_topup_once_even_if_delivered_twice(self, req):
        req.return_value.status_code = 200
        req.return_value.json.return_value = {'id': 'order_W1'}
        d = self.c.post('/api/payments/wallet/topup/', {'coins': 200, 'method': 'razorpay'}, format='json').json()
        body = json.dumps({'event': 'payment.captured', 'payload': {'payment': {'entity': {'id': 'pay_W1', 'order_id': 'order_W1', 'amount': 20000, 'currency': 'INR', 'status': 'captured'}}}}).encode()
        for _ in range(2):  # Razorpay may deliver the same event repeatedly
            r = self.client.post('/api/payments/webhook/razorpay/', body, content_type='application/json', HTTP_X_RAZORPAY_SIGNATURE=sig('whsec', body))
            self.assertEqual(r.status_code, 200)
        self.assertEqual(self.balance(self.buyer), Decimal('200'))
        self.assertEqual(TopUp.objects.get(pk=d['topup_id']).status, 'SUCCESS')
        unknown = json.dumps({'event': 'payment.captured', 'payload': {'payment': {'entity': {'id': 'p', 'order_id': 'order_NOPE', 'amount': 1, 'currency': 'INR'}}}}).encode()
        self.assertEqual(self.client.post('/api/payments/webhook/razorpay/', unknown, content_type='application/json', HTTP_X_RAZORPAY_SIGNATURE=sig('whsec', unknown)).status_code, 400)

    def test_only_bidders_can_top_up(self):
        s = APIClient()
        s.force_authenticate(self.seller)
        self.assertEqual(s.post('/api/payments/wallet/topup/', {'coins': 100, 'method': 'razorpay'}, format='json').status_code, 403)


@override_settings(**KEYS)
class RoutingTests(WalletBase):
    def methods(self):
        return {m['id']: m for m in self.c.get('/api/payments/methods/').json()['methods']}

    @override_settings(FAKE_PAYMENTS_ENABLED=True)
    def test_chooser_lists_coins_razorpay_and_fake(self):
        m = self.methods()
        self.assertTrue(m['coins']['available'] and m['razorpay']['available'] and m['fake']['available'])
        self.assertTrue(m['razorpay']['test_mode'])

    def test_fake_is_hidden_when_disabled_and_razorpay_hidden_without_keys(self):
        self.assertFalse(self.methods()['fake']['available'])
        with override_settings(RAZORPAY_KEY_ID='', RAZORPAY_KEY_SECRET=''):
            self.assertFalse(self.methods()['razorpay']['available'])

    @override_settings(FAKE_PAYMENTS_ENABLED=True)
    @patch('payments.services.requests.request')
    def test_checkout_routes_by_method(self, req):
        req.return_value.status_code = 200
        req.return_value.json.return_value = {'id': 'order_R1', 'status': 'created'}
        r = self.c.post(f'/api/payments/{self.payment.id}/checkout/', {'method': 'razorpay'}, format='json').json()
        self.assertEqual((r['provider'], r['order_id']), ('razorpay', 'order_R1'))
        f = self.c.post(f'/api/payments/{self.payment.id}/checkout/', {'method': 'fake'}, format='json').json()
        self.assertTrue(f['mock'])
        done = self.c.post(f'/api/payments/{self.payment.id}/mock-pay/', {'outcome': 'success'}, format='json')
        self.assertEqual(done.json()['status'], 'SUCCESS')

    def test_fake_checkout_refused_when_disabled(self):
        self.assertEqual(self.c.post(f'/api/payments/{self.payment.id}/checkout/', {'method': 'fake'}, format='json').status_code, 503)
