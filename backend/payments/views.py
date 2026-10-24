from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Payment
from .serializers import PaymentSerializer
from .services import (
    CheckoutConflictError,
    CheckoutUnavailableError,
    PaymentVerificationError,
    PaymentWebhookError,
    create_checkout,
    mock_pay,
    process_webhook,
    sync_payment,
    verify_payment,
)


class MyPaymentsView(generics.ListAPIView):
    serializer_class=PaymentSerializer; permission_classes=[IsAuthenticated]
    def get_queryset(self): return Payment.objects.filter(buyer=self.request.user).select_related('auction__product').order_by('-created_at')


class _OwnPaymentView(generics.GenericAPIView):
    serializer_class=PaymentSerializer; permission_classes=[IsAuthenticated]
    def own_payment(self,pk): return Payment.objects.filter(pk=pk,buyer=self.request.user).select_related('auction__product').first()


class CheckoutView(_OwnPaymentView):
    """Creates (or reuses) the Razorpay order for an invoice and returns what Checkout.js needs."""
    def post(self,request,pk):
        p=self.own_payment(pk)
        if not p: return Response({'detail':'Payment not found.'},status=404)
        try: data=create_checkout(p,request.data.get('method'))
        except CheckoutConflictError as exc: return Response({'detail':str(exc)},status=409)
        except CheckoutUnavailableError as exc: return Response({'detail':str(exc)},status=503)
        bp=getattr(request.user,'buyer_profile',None)
        return Response({**data,'prefill':{'name':request.user.username,'email':request.user.email,'contact':getattr(bp,'phone','') or ''}})


class VerifyPaymentView(_OwnPaymentView):
    """Browser posts Razorpay's success response here; the signature is verified server-side."""
    def post(self,request,pk):
        p=self.own_payment(pk)
        if not p: return Response({'detail':'Payment not found.'},status=404)
        d=request.data
        try: p=verify_payment(p,d.get('razorpay_payment_id',''),d.get('razorpay_order_id',''),d.get('razorpay_signature',''))
        except PaymentVerificationError as exc: return Response({'detail':str(exc)},status=400)
        except CheckoutUnavailableError as exc: return Response({'detail':str(exc)},status=503)
        return Response(self.get_serializer(p).data)


class SyncPaymentView(_OwnPaymentView):
    def post(self,request,pk):
        p=self.own_payment(pk)
        if not p: return Response({'detail':'Payment not found.'},status=404)
        try: p=sync_payment(p)
        except CheckoutUnavailableError as exc: return Response({'detail':str(exc)},status=503)
        return Response(self.get_serializer(p).data)


class MockPayView(_OwnPaymentView):
    def post(self,request,pk):
        p=self.own_payment(pk)
        if not p: return Response({'detail':'Payment not found.'},status=404)
        try: p=mock_pay(p,success=request.data.get('outcome','success')=='success')
        except CheckoutConflictError as exc: return Response({'detail':str(exc)},status=409)
        except CheckoutUnavailableError as exc: return Response({'detail':str(exc)},status=403)
        return Response(self.get_serializer(p).data)


@method_decorator(csrf_exempt,name='dispatch')
class RazorpayWebhookView(generics.GenericAPIView):
    permission_classes=[AllowAny]; authentication_classes=[]; throttle_classes=[]
    def post(self,request):
        try: payment=process_webhook(request.body,request.META.get('HTTP_X_RAZORPAY_SIGNATURE',''))
        except PaymentWebhookError: return Response({'detail':'Invalid webhook.'},status=400)
        return Response({'received':True,'payment_id':getattr(payment,'id',None)})
