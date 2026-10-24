from django.utils import timezone
from rest_framework import generics, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from .models import User, SellerVerification
from .serializers import UserSerializer, RegisterSerializer, SellerVerificationSerializer
from .permissions import IsAdmin
from audit.services import record_audit
from notifications.services import notify_user

class RegisterView(generics.CreateAPIView):
    queryset=User.objects.all(); serializer_class=RegisterSerializer; permission_classes=[AllowAny]
    def create(self,request,*args,**kwargs):
        response=super().create(request,*args,**kwargs)
        response.data['auto_verified']=settings.AUTO_VERIFY_EMAIL  # lets the UI say "you can log in now" instead of "check your inbox"
        return response
    @transaction.atomic
    def perform_create(self, serializer):
        user=serializer.save()
        if settings.AUTO_VERIFY_EMAIL:
            user.email_verified=True; user.save(update_fields=['email_verified']); return user
        token=default_token_generator.make_token(user); uid=urlsafe_base64_encode(force_bytes(user.pk))
        verification_url = (
            f"{settings.FRONTEND_URL}/verify/{uid}/{token}"
        )
        send_mail(
            "Verify your AuctionHub account",
            f"Verify your email address: {verification_url}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        return user

class ResendVerificationView(generics.GenericAPIView):
    """Signed-in user asks for a fresh verification email."""
    permission_classes=[IsAuthenticated]; throttle_scope='resend_verification'
    def get_throttles(self):
        from rest_framework.throttling import ScopedRateThrottle
        return [ScopedRateThrottle()]
    def post(self,request):
        user=request.user
        if user.email_verified: return Response({'detail':'Your email is already verified.','verified':True})
        token=default_token_generator.make_token(user); uid=urlsafe_base64_encode(force_bytes(user.pk))
        send_mail("Verify your AuctionHub account",f"Verify your email address: {settings.FRONTEND_URL}/verify/{uid}/{token}",settings.DEFAULT_FROM_EMAIL,[user.email])
        return Response({'detail':f'Verification email sent to {user.email}.','verified':False})

class VerifyEmailView(generics.GenericAPIView):
    permission_classes=[AllowAny]
    def get(self,request,uidb64,token):
        try: user=User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
        except (User.DoesNotExist,ValueError,TypeError): return Response({'detail':'Invalid verification link.'},status=400)
        if not default_token_generator.check_token(user,token): return Response({'detail':'Invalid or expired token.'},status=400)
        user.email_verified=True; user.save(update_fields=['email_verified']); return Response({'verified':True})

class PasswordResetRequestView(generics.GenericAPIView):
    permission_classes=[AllowAny]
    def post(self,request):
        email=request.data.get('email',''); user=User.objects.filter(email=email,is_active=True).first()
        if user:
            token=default_token_generator.make_token(user)
            uid=urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}"
            send_mail(
                "AuctionHub password reset",
                f"Reset your password: {reset_url}",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
        return Response({'detail':'If the account exists, reset instructions were sent.'})

class PasswordResetConfirmView(generics.GenericAPIView):
    permission_classes=[AllowAny]
    def post(self,request,uidb64,token):
        try: user=User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
        except (User.DoesNotExist,ValueError,TypeError): return Response({'detail':'Invalid reset link.'},status=400)
        if not default_token_generator.check_token(user,token): return Response({'detail':'Invalid or expired token.'},status=400)
        password=request.data.get('password','')
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        try: validate_password(password,user)
        except DjangoValidationError as exc: return Response({'password':list(exc.messages)},status=400)
        user.set_password(password); user.save(update_fields=['password']); return Response({'reset':True})

class MeView(generics.RetrieveUpdateAPIView):
    serializer_class=UserSerializer; permission_classes=[IsAuthenticated]
    def get_object(self): return self.request.user

class ProfileView(generics.GenericAPIView):
    """Role-specific profile: sellers have a business profile, bidders have contact details."""
    permission_classes=[IsAuthenticated]
    SELLER_FIELDS=('business_name','phone','address'); BUYER_FIELDS=('phone','address')
    def _profile(self,user):
        from .models import SellerProfile,BuyerProfile
        if user.role=='SELLER': return SellerProfile.objects.get_or_create(user=user)[0]
        if user.role=='BUYER': return BuyerProfile.objects.get_or_create(user=user)[0]
        return None
    def _data(self,user,p):
        d={'id':user.id,'username':user.username,'email':user.email,'role':user.role,'email_verified':user.email_verified}
        if user.role=='SELLER': d.update({f:getattr(p,f) for f in self.SELLER_FIELDS}|{'approved':p.approved,'verified':p.verified,'rejection_reason':p.rejection_reason})
        elif user.role=='BUYER': d.update({f:getattr(p,f) for f in self.BUYER_FIELDS})
        return d
    def get(self,request): return Response(self._data(request.user,self._profile(request.user)))
    def patch(self,request):
        p=self._profile(request.user)
        if p is None: return Response({'detail':'Admin accounts have no profile to edit.'},status=400)
        allowed=self.SELLER_FIELDS if request.user.role=='SELLER' else self.BUYER_FIELDS
        limits={'business_name':200,'phone':30,'address':1000}
        for f in allowed:
            if f in request.data:
                v=str(request.data[f]).strip()
                if len(v)>limits[f]: return Response({f:[f'Must be at most {limits[f]} characters.']},status=400)
                setattr(p,f,v)
        p.save(); record_audit(request.user,'PROFILE_UPDATED',p)
        return Response(self._data(request.user,p))

class SellerVerificationViewSet(viewsets.ModelViewSet):
    serializer_class=SellerVerificationSerializer; permission_classes=[IsAuthenticated]
    def get_queryset(self):
        if self.request.user.role=='ADMIN': return SellerVerification.objects.select_related('seller__user','reviewer').all()
        if self.request.user.role=='SELLER': return SellerVerification.objects.filter(seller__user=self.request.user)
        return SellerVerification.objects.none()
    def perform_create(self, serializer):
        if self.request.user.role!='SELLER': raise serializers.ValidationError('Only sellers can submit verification.')
        serializer.save(seller=self.request.user.seller_profile)
        record_audit(self.request.user,'SELLER_VERIFICATION_SUBMITTED',serializer.instance)
    @action(detail=True,methods=['post'],permission_classes=[IsAdmin])
    def review(self, request, pk=None):
        obj=self.get_object(); decision=request.data.get('decision')
        if decision not in ('APPROVED','REJECTED'): return Response({'detail':'Invalid decision'},status=400)
        obj.status=decision; obj.reviewer=request.user; obj.reviewed_at=timezone.now(); obj.notes=request.data.get('notes',''); obj.save()
        sp=obj.seller; sp.approved=decision=='APPROVED'; sp.verified=sp.approved; sp.rejection_reason='' if sp.approved else obj.notes; sp.save()
        record_audit(request.user,f'SELLER_{decision}',obj); notify_user(sp.user,'Seller verification updated',f'Your seller verification is {decision.lower()}.')
        return Response(self.get_serializer(obj).data)

class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=User.objects.all().order_by('-created_at'); serializer_class=UserSerializer; permission_classes=[IsAdmin]
    @action(detail=True,methods=['post'])
    def suspend(self,request,pk=None):
        u=self.get_object(); u.is_suspended=True; u.save(update_fields=['is_suspended']); record_audit(request.user,'USER_SUSPENDED',u); return Response({'status':'suspended'})
