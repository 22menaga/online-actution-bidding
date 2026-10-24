from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import SellerProfile, User
from products.models import Category,Product
from payments.models import Payment
from .models import Auction
from .services import close_auction
from .tasks import process_auction_lifecycle


class MarketplaceEndToEndTests(TestCase):
    @patch("payments.services.requests.request")
    @override_settings(RAZORPAY_KEY_ID="rzp_test_key", RAZORPAY_KEY_SECRET="secret", PAYMENT_CURRENCY="INR")
    def test_seller_to_auction_winner_checkout(self, mock_request):
        seller = User.objects.create_user(
            username="flow-seller",
            email="flow-seller@example.com",
            password="StrongPassword123!",
            role="SELLER",
        )
        SellerProfile.objects.create(user=seller)
        buyer = User.objects.create_user(
            username="flow-buyer",
            email="flow-buyer@example.com",
            password="StrongPassword123!",
            role="BUYER",
            email_verified=True,
        )
        admin = User.objects.create_user(
            username="flow-admin",
            email="flow-admin@example.com",
            password="StrongPassword123!",
            role="ADMIN",
        )
        seller_client = APIClient()
        seller_client.force_authenticate(seller)
        admin_client = APIClient()
        admin_client.force_authenticate(admin)
        buyer_client = APIClient()
        buyer_client.force_authenticate(buyer)

        verification = seller_client.post(
            "/api/accounts/seller-verifications/",
            {
                "legal_name": "Flow Seller",
                "document_type": "Business registration",
                "document_reference": "FLOW-001",
            },
            format="json",
        )
        self.assertEqual(verification.status_code, 201)
        response = admin_client.post(
            f"/api/accounts/seller-verifications/{verification.data['id']}/review/",
            {"decision": "APPROVED"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        seller.refresh_from_db()
        seller_client.force_authenticate(seller)

        category = Category.objects.create(name="Flow items", slug="flow-items")
        product = seller_client.post(
            "/api/products/products/",
            {
                "category": category.id,
                "name": "Flow product",
                "description": "Product through the entire marketplace",
                "starting_price": "10.00",
                "condition": "New",
            },
            format="json",
        )
        self.assertEqual(product.status_code, 201)
        submitted = seller_client.post(
            f"/api/products/products/{product.data['id']}/submit/"
        )
        self.assertEqual(submitted.status_code, 200)
        reviewed = admin_client.post(
            f"/api/products/products/{product.data['id']}/review/",
            {"decision": "APPROVED"},
            format="json",
        )
        self.assertEqual(reviewed.status_code, 200)

        start_at = timezone.now() - timedelta(minutes=1)
        end_at = timezone.now() + timedelta(hours=1)
        auction = seller_client.post(
            "/api/auctions/auctions/",
            {
                "product": product.data["id"],
                "starting_price": "10.00",
                "min_increment": "1.00",
                "is_24_7": True,
                "seller_note": "Run it around the clock please",
                # a seller may send times, but they are never the schedule
                "start_at": (timezone.now() + timedelta(days=400)).isoformat(),
                "end_at": (timezone.now() + timedelta(days=401)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(auction.status_code, 201)
        self.assertIsNone(auction.data["start_at"])  # nothing is scheduled until an admin allocates it
        approved = admin_client.post(
            f"/api/auctions/auctions/{auction.data['id']}/approve/",
            {"start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
            format="json",
        )
        self.assertEqual(approved.status_code, 200)
        process_auction_lifecycle()

        bid = buyer_client.post(
            "/api/bidding/bids/",
            {"auction": auction.data["id"], "amount": "10.00"},
            format="json",
        )
        self.assertEqual(bid.status_code, 201)
        closed = close_auction(auction.data["id"])
        self.assertEqual(closed.status, Auction.Status.SOLD)
        payment = closed.payment

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = {"id": "order_marketplace_flow", "status": "created"}
        checkout = buyer_client.post(f"/api/payments/{payment.id}/checkout/")

        self.assertEqual(checkout.status_code, 200)
        self.assertEqual(checkout.data["order_id"], "order_marketplace_flow")
        self.assertEqual(checkout.data["amount"], 1000)  # Rs 10.00 in paise
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PROCESSING)


class AuctionPermissionTests(TestCase):
    def setUp(self):
        self.seller=User.objects.create_user(username='auction-seller',email='auction-seller@example.com',password='StrongPassword123!',role='SELLER')
        self.buyer=User.objects.create_user(username='auction-buyer',email='auction-buyer@example.com',password='StrongPassword123!',role='BUYER')
        category=Category.objects.create(name='Auction items',slug='auction-items')
        product=Product.objects.create(seller=self.seller,category=category,name='Auction item',description='x',starting_price=10,condition='Good',status='AUCTION')
        self.auction=Auction.objects.create(product=product,seller=self.seller,starting_price=10,min_increment=1,start_at=timezone.now()-timedelta(hours=1),end_at=timezone.now()+timedelta(hours=1),status='LIVE',bid_count=1)
        self.client=APIClient()

    def test_buyer_cannot_cancel_or_edit_public_auction(self):
        self.client.force_authenticate(self.buyer)
        cancel=self.client.post(f'/api/auctions/auctions/{self.auction.id}/cancel/')
        update=self.client.patch(f'/api/auctions/auctions/{self.auction.id}/',{'min_increment':'5.00'},format='json')
        self.assertEqual(cancel.status_code,403)
        self.assertEqual(update.status_code,403)

    def test_seller_cannot_edit_auction_after_bidding_starts(self):
        self.client.force_authenticate(self.seller)
        response=self.client.patch(f'/api/auctions/auctions/{self.auction.id}/',{'starting_price':'12.00','min_increment':'5.00'},format='json')
        self.assertEqual(response.status_code,403)

class AuctionLifecycleTests(TestCase):
    def test_close_creates_payment_for_winner(self):
        seller=User.objects.create_user(username='s',email='s@x.com',password='StrongPassword123!',role='SELLER')
        buyer=User.objects.create_user(username='b',email='b@x.com',password='StrongPassword123!',role='BUYER',email_verified=True)
        cat=Category.objects.create(name='Books',slug='books'); p=Product.objects.create(seller=seller,category=cat,name='Book',description='x',starting_price=10,condition='Good',status='AUCTION')
        a=Auction.objects.create(product=p,seller=seller,starting_price=10,min_increment=1,start_at=timezone.now()-timedelta(hours=1),end_at=timezone.now()-timedelta(minutes=1),status='LIVE',current_highest_bid=11,current_highest_bidder=buyer,bid_count=1)
        close_auction(a.id); a.refresh_from_db(); self.assertEqual(a.status,'SOLD'); self.assertEqual(a.winner_id,buyer.id)
        from payments.models import Payment
        self.assertTrue(Payment.objects.filter(auction=a,buyer=buyer,amount=Decimal('11')).exists())

    def test_lifecycle_closes_expired_scheduled_auction(self):
        seller=User.objects.create_user(username='scheduled-seller',email='scheduled-seller@example.com',password='StrongPassword123!',role='SELLER')
        cat=Category.objects.create(name='Music',slug='music')
        product=Product.objects.create(seller=seller,category=cat,name='Guitar',description='x',starting_price=10,condition='Good',status='AUCTION')
        auction=Auction.objects.create(product=product,seller=seller,starting_price=10,min_increment=1,start_at=timezone.now()-timedelta(hours=2),end_at=timezone.now()-timedelta(hours=1),status='SCHEDULED')

        process_auction_lifecycle()

        auction.refresh_from_db()
        self.assertEqual(auction.status, Auction.Status.UNSOLD)


class SeedDemoTests(TestCase):
    def test_seed_demo_creates_live_auctions_and_is_idempotent(self):
        from django.core.management import call_command
        call_command('seed_demo', verbosity=0); call_command('seed_demo', verbosity=0)
        self.assertEqual(Auction.objects.filter(status='LIVE').count(), 5)
        self.assertEqual(Auction.objects.filter(status='SCHEDULED').count(), 1)
        self.assertEqual(Auction.objects.filter(status='PENDING_APPROVAL').count(), 1)
        self.assertTrue(all(a.product.images.exists() for a in Auction.objects.all()))


class MarketplaceRulesTests(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command('seed_demo', verbosity=0)
        self.client=APIClient(); self.buyer=User.objects.get(username='demo_buyer'); self.seller=User.objects.get(username='demo_seller')
        self.auction=Auction.objects.filter(status='LIVE').first()

    def test_seller_can_browse_other_sellers_live_auctions(self):
        other=User.objects.create_user(username='other_seller',email='o@example.com',password='StrongPassword123!',role='SELLER',email_verified=True)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get('/api/auctions/auctions/?status=LIVE').json()['count'],5)
        self.assertEqual(self.client.get('/api/auctions/auctions/?mine=1').json()['count'],0)

    def test_leader_identity_is_masked_and_flagged(self):
        from bidding.services import place_bid
        place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=self.auction.required_minimum())
        anon=self.client.get(f'/api/auctions/auctions/{self.auction.id}/').json()
        self.assertEqual(anon['leader_name'],'de***r'); self.assertFalse(anon['is_leading'])
        self.client.force_authenticate(self.buyer)
        self.assertTrue(self.client.get(f'/api/auctions/auctions/{self.auction.id}/').json()['is_leading'])

    def test_watchlist_persists_and_toggles(self):
        self.client.force_authenticate(self.buyer)
        url=f'/api/auctions/auctions/{self.auction.id}/watch/'
        self.assertTrue(self.client.post(url).json()['watching']); self.client.post(url)  # idempotent
        self.assertEqual(self.client.get('/api/auctions/auctions/watchlist/').json()['count'],1)
        self.assertTrue(self.client.get(f'/api/auctions/auctions/{self.auction.id}/').json()['is_watched'])
        self.assertFalse(self.client.delete(url).json()['watching'])
        self.assertEqual(self.client.get('/api/auctions/auctions/watchlist/').json()['count'],0)

    def test_watch_requires_login(self):
        self.assertEqual(self.client.post(f'/api/auctions/auctions/{self.auction.id}/watch/').status_code,401)

    def test_create_auction_with_unknown_product_is_400_not_500(self):
        self.client.force_authenticate(self.seller)
        r=self.client.post('/api/auctions/auctions/',{'product':99999,'starting_price':'10','min_increment':'1','start_at':'2030-01-01T00:00:00Z','end_at':'2030-01-02T00:00:00Z'},format='json')
        self.assertEqual(r.status_code,400)

    def test_duplicate_client_reference_blocked_by_database(self):
        from django.db import IntegrityError, transaction
        from bidding.models import Bid
        import uuid
        ref=uuid.uuid4(); Bid.objects.create(auction=self.auction,bidder=self.buyer,amount=1,client_reference=ref)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Bid.objects.create(auction=self.auction,bidder=self.buyer,amount=2,client_reference=ref)

    @override_settings(PAYMENTS_MOCK=True)
    def test_mock_checkout_settles_payment(self):
        from bidding.services import place_bid
        place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=self.auction.required_minimum())
        Auction.objects.filter(pk=self.auction.pk).update(end_at=timezone.now()-timedelta(seconds=1)); close_auction(self.auction.id)
        pay=Payment.objects.get(buyer=self.buyer); self.client.force_authenticate(self.buyer)
        r=self.client.post(f'/api/payments/{pay.id}/checkout/').json(); self.assertTrue(r['mock']); self.assertIn(f'/checkout/{pay.id}',r['checkout_url'])
        self.assertEqual(self.client.post(f'/api/payments/{pay.id}/mock-pay/',{'outcome':'success'},format='json').json()['status'],'SUCCESS')
        self.assertEqual(self.client.post(f'/api/payments/{pay.id}/mock-pay/',{'outcome':'success'},format='json').status_code,409)

    @override_settings(PAYMENTS_MOCK=False)
    def test_mock_pay_disabled_when_mock_mode_off(self):
        self.client.force_authenticate(self.buyer)
        pay=Payment.objects.create(auction=self.auction,buyer=self.buyer,amount=10)
        self.assertEqual(self.client.post(f'/api/payments/{pay.id}/mock-pay/',{},format='json').status_code,403)

    def test_password_reset_weak_password_is_400(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        uid=urlsafe_base64_encode(force_bytes(self.buyer.pk)); tok=default_token_generator.make_token(self.buyer)
        self.assertEqual(self.client.post(f'/api/accounts/password-reset/{uid}/{tok}/',{'password':'123'},format='json').status_code,400)
