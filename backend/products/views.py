from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from . import ai_valuation
from .models import AIEstimate, Category, Product
from .serializers import CategorySerializer, ProductSerializer, ProductImageCreateSerializer
from accounts.permissions import IsAdmin, IsSeller, IsSellerOrAdmin
from audit.services import record_audit

class CategoryViewSet(viewsets.ModelViewSet):
    queryset=Category.objects.filter(active=True); serializer_class=CategorySerializer; permission_classes=[IsAuthenticated]
    def get_permissions(self): return [IsAdmin()] if self.action in ('create','update','partial_update','destroy') else [AllowAny()]

class ProductViewSet(viewsets.ModelViewSet):
    filterset_fields=['category','status','condition']
    search_fields=['name','description','condition']
    ordering_fields=['starting_price','created_at','name']
    queryset=Product.objects.select_related('seller','category','auction').prefetch_related('images').all(); serializer_class=ProductSerializer
    def get_permissions(self):
        if self.action in ('list','retrieve'):
            permission_classes=(AllowAny,)
        elif self.action in ('create','image'):
            permission_classes=(IsSeller,)
        elif self.action=='review':
            permission_classes=(IsAdmin,)
        else:
            permission_classes=(IsSellerOrAdmin,)
        return [permission() for permission in permission_classes]
    def get_queryset(self):
        qs=super().get_queryset(); u=self.request.user
        if u.is_authenticated and u.role=='SELLER': return qs.filter(seller=u)
        if u.is_authenticated and u.role=='ADMIN': return qs
        return qs.filter(status__in=['APPROVED','AUCTION','SOLD'])
    def perform_create(self,serializer):
        if self.request.user.role!='SELLER': raise PermissionDenied('Seller required.')
        est=AIEstimate.objects.filter(pk=self.request.data.get('ai_estimate_id') or 0,user=self.request.user).first()  # only the seller's own analysis can be attached
        serializer.save(seller=self.request.user,status='DRAFT',ai_estimate=est)
    def perform_update(self,serializer):
        product=serializer.instance
        if self.request.user.role!='ADMIN' and product.status not in ('DRAFT','REJECTED'):
            raise PermissionDenied('Only draft or rejected products can be edited.')
        if hasattr(product,'auction'):
            raise PermissionDenied('Products attached to an auction cannot be edited.')
        serializer.save()
    def perform_destroy(self,instance):
        if self.request.user.role!='ADMIN' and instance.status not in ('DRAFT','REJECTED'):
            raise PermissionDenied('Only draft or rejected products can be deleted.')
        if hasattr(instance,'auction'):
            raise PermissionDenied('Products attached to an auction cannot be deleted.')
        super().perform_destroy(instance)
    @action(detail=True,methods=['post'])
    def submit(self,request,pk=None):
        p=self.get_object()
        if request.user.role=='SELLER' and p.seller_id!=request.user.id: return Response({'detail':'Forbidden'},status=403)
        if p.status not in ('DRAFT','REJECTED'): return Response({'detail':'Only draft or rejected products can be submitted.'},status=409)
        p.status='PENDING_APPROVAL'; p.save(update_fields=['status','updated_at']); record_audit(request.user,'PRODUCT_SUBMITTED',p); return Response(self.get_serializer(p).data)
    @action(detail=True,methods=['post'])
    def review(self,request,pk=None):
        p=self.get_object()
        if p.status!='PENDING_APPROVAL': return Response({'detail':'Only pending products can be reviewed.'},status=409)
        decision=request.data.get('decision')
        if decision not in ('APPROVED','REJECTED'): return Response({'detail':'Invalid decision'},status=400)
        p.status='APPROVED' if decision=='APPROVED' else 'REJECTED'; p.rejection_reason=request.data.get('reason',''); p.save(update_fields=['status','rejection_reason','updated_at']); record_audit(request.user,f'PRODUCT_{decision}',p); return Response(self.get_serializer(p).data)
    @action(detail=True,methods=['post'])
    def image(self,request,pk=None):
        p=self.get_object()
        if p.seller_id!=request.user.id: return Response({'detail':'Forbidden'},status=403)
        s=ProductImageCreateSerializer(data=request.data); s.is_valid(raise_exception=True); obj=s.save(product=p); return Response(ProductImageCreateSerializer(obj).data,status=201)


class AIEstimateView(APIView):
    """POST photos (multipart field "images", 1-4 files; optional "hint") -> AI market-value estimate. Seller-only, rate-limited."""
    permission_classes=[IsSeller]; parser_classes=[MultiPartParser,FormParser]
    throttle_classes=[ScopedRateThrottle]; throttle_scope='ai_estimate'
    def post(self,request):
        files=request.FILES.getlist('images')
        if not files: return Response({'detail':'Add at least one photo.'},status=400)
        if len(files)>ai_valuation.MAX_IMAGES: return Response({'detail':f'You can analyse up to {ai_valuation.MAX_IMAGES} photos at a time.'},status=400)
        if not ai_valuation.configured(): return Response({'detail':'AI price estimates are not set up yet. The site owner needs to add ANTHROPIC_API_KEY.','code':'not_configured'},status=503)
        try: images=[ai_valuation.prepare_image(f)[0] for f in files]
        except ai_valuation.ImageProblem as exc: return Response({'detail':str(exc)},status=400)
        categories=list(Category.objects.filter(active=True).values_list('name',flat=True))
        try: result=ai_valuation.estimate_from_images(images,request.data.get('hint',''),categories)
        except ai_valuation.AIUnavailable as exc: return Response({'detail':str(exc),'code':'unavailable'},status=503)
        except ai_valuation.AIRefused as exc: return Response({'detail':str(exc),'code':'refused'},status=422)
        from django.conf import settings
        est=AIEstimate.objects.create(user=request.user,data=result,model=settings.AI_VALUATION_MODEL)
        record_audit(request.user,'AI_ESTIMATE_CREATED',est,{'sellable':result.get('sellable'),'low':result.get('estimated_low'),'high':result.get('estimated_high')},request=request)
        return Response({'id':est.id,**result},status=201)


class AIEstimateStatusView(APIView):
    """Lets the UI know whether to offer the AI button."""
    permission_classes=[IsAuthenticated]
    def get(self,request): return Response({'enabled':ai_valuation.configured()})
