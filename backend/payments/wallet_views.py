from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsBuyer
from .models import Payment, TopUp
from . import wallet
from .services import CheckoutConflictError, CheckoutUnavailableError, PaymentVerificationError, razorpay_configured


def _tx(t): return {'id': t.id, 'kind': t.kind, 'amount': t.amount, 'balance_after': t.balance_after, 'description': t.description, 'reference': t.reference, 'at': t.created_at}


class WalletView(APIView):
    """GET /api/payments/wallet/ -> balance + latest ledger rows."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        w = wallet.wallet_for(request.user)
        return Response({'balance': w.balance, 'coin_value': settings.COIN_VALUE, 'currency': settings.PAYMENT_CURRENCY,
                         'topup': {'min': settings.COIN_TOPUP_MIN, 'max': settings.COIN_TOPUP_MAX}, 'platform_fee_percent': settings.PLATFORM_FEE_PERCENT,
                         'transactions': [_tx(t) for t in w.transactions.all()[:50]]})


class PaymentMethodsView(APIView):
    """GET /api/payments/methods/ -> how can this user pay right now (drives the payment-method chooser)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        w = wallet.wallet_for(request.user)
        return Response({'methods': [
            {'id': 'coins', 'label': 'Pay with coins', 'available': True, 'balance': w.balance},
            {'id': 'razorpay', 'label': 'Razorpay (UPI, cards, netbanking)', 'available': razorpay_configured() and not settings.PAYMENTS_MOCK, 'test_mode': settings.RAZORPAY_KEY_ID.startswith('rzp_test_')},
            {'id': 'fake', 'label': 'Fake payment (test, no money)', 'available': bool(settings.FAKE_PAYMENTS_ENABLED or settings.PAYMENTS_MOCK)},
        ], 'coin_value': settings.COIN_VALUE})


class _OwnTopUp(APIView):
    permission_classes = [IsBuyer]
    def topup(self, request, pk): return TopUp.objects.filter(pk=pk, user=request.user).first()


class TopUpStartView(APIView):
    """POST {coins, method: razorpay|fake} -> what the browser needs to complete the purchase."""
    permission_classes = [IsBuyer]

    def post(self, request):
        try:
            _, payload = wallet.start_topup(request.user, request.data.get('coins', 0), str(request.data.get('method', 'razorpay')))
        except CheckoutConflictError as exc:
            return Response({'detail': str(exc)}, status=400)
        except CheckoutUnavailableError as exc:
            return Response({'detail': str(exc)}, status=503)
        p = getattr(request.user, 'buyer_profile', None)
        return Response({**payload, 'prefill': {'name': request.user.username, 'email': request.user.email, 'contact': getattr(p, 'phone', '') or ''}}, status=201)


class TopUpVerifyView(_OwnTopUp):
    def post(self, request, pk):
        t = self.topup(request, pk)
        if not t: return Response({'detail': 'Top-up not found.'}, status=404)
        d = request.data
        try: wallet.verify_topup(t, d.get('razorpay_payment_id', ''), d.get('razorpay_order_id', ''), d.get('razorpay_signature', ''))
        except PaymentVerificationError as exc: return Response({'detail': str(exc)}, status=400)
        except CheckoutUnavailableError as exc: return Response({'detail': str(exc)}, status=503)
        return Response({'balance': wallet.wallet_for(request.user).balance})


class TopUpFakeView(_OwnTopUp):
    def post(self, request, pk):
        t = self.topup(request, pk)
        if not t: return Response({'detail': 'Top-up not found.'}, status=404)
        try: wallet.fake_complete_topup(t, success=request.data.get('outcome', 'success') == 'success')
        except CheckoutConflictError as exc: return Response({'detail': str(exc)}, status=409)
        except CheckoutUnavailableError as exc: return Response({'detail': str(exc)}, status=403)
        return Response({'balance': wallet.wallet_for(request.user).balance})


class PayWithCoinsView(APIView):
    """POST /api/payments/<id>/pay-coins/"""
    permission_classes = [IsBuyer]

    def post(self, request, pk):
        p = Payment.objects.filter(pk=pk, buyer=request.user).first()
        if not p: return Response({'detail': 'Payment not found.'}, status=404)
        try: p = wallet.pay_invoice_with_coins(p)
        except wallet.InsufficientCoins as exc:
            return Response({'detail': str(exc), 'balance': exc.balance, 'needed': exc.needed, 'shortfall': exc.needed - exc.balance, 'code': 'insufficient_coins'}, status=402)
        except CheckoutConflictError as exc: return Response({'detail': str(exc)}, status=409)
        return Response({'status': p.status, 'balance': wallet.wallet_for(request.user).balance})
