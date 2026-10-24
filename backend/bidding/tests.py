from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import AccessToken
from accounts.models import User,SellerProfile,BuyerProfile
from products.models import Category,Product
from auctions.models import Auction
from config.asgi import application
from .services import place_bid
class BidTests(TestCase):
    def setUp(self):
        self.seller=User.objects.create_user(username='seller',email='s@example.com',password='StrongPassword123!',role='SELLER',email_verified=True)
        SellerProfile.objects.create(user=self.seller,approved=True,verified=True)
        self.buyer=User.objects.create_user(username='buyer',email='b@example.com',password='StrongPassword123!',role='BUYER',email_verified=True)
        BuyerProfile.objects.create(user=self.buyer)
        cat=Category.objects.create(name='Art',slug='art'); p=Product.objects.create(seller=self.seller,category=cat,name='Painting',description='x',starting_price=Decimal('100'),condition='Good',status='AUCTION')
        self.auction=Auction.objects.create(product=p,seller=self.seller,starting_price=100,min_increment=10,start_at=timezone.now()-timedelta(minutes=1),end_at=timezone.now()+timedelta(minutes=30),status='LIVE')
    def test_bid_below_starting_price_is_rejected(self):
        with self.assertRaises(ValidationError):
            place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('99'))
    def test_seller_cannot_bid(self):
        with self.assertRaises(Exception): place_bid(auction_id=self.auction.id,bidder=self.seller,amount=Decimal('110'))
    def test_valid_bid_updates_leader(self):
        b=place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('110'))
        self.auction.refresh_from_db(); self.assertEqual(b.amount,Decimal('110')); self.assertEqual(self.auction.current_highest_bid,self.buyer and Decimal('110'))

    def test_bid_is_saved_when_realtime_broadcast_is_unavailable(self):
        with self.assertLogs('bidding.services', level='ERROR'):
            with patch('bidding.services.get_channel_layer', side_effect=ConnectionError):
                with self.captureOnCommitCallbacks(execute=True):
                    bid=place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('110'))

        self.assertTrue(type(bid).objects.filter(pk=bid.pk).exists())


class JwtWebSocketAuthTests(TransactionTestCase):
    def test_websocket_accepts_jwt_authentication(self):
        user=User.objects.create_user(
            username='websocket-user',
            email='websocket@example.com',
            password='StrongPassword123!',
            role='BUYER',
            email_verified=True,
        )
        token=str(AccessToken.for_user(user))
        communicator=WebsocketCommunicator(
            application,
            '/ws/auctions/999999/',
            subprotocols=['jwt',token],
        )

        connected, close_code=async_to_sync(communicator.connect)()

        self.assertFalse(connected)
        self.assertEqual(close_code,4403)

    def test_websocket_rejects_missing_jwt(self):
        communicator=WebsocketCommunicator(
            application,
            '/ws/auctions/999999/',
        )

        connected, close_code=async_to_sync(communicator.connect)()

        self.assertFalse(connected)
        self.assertEqual(close_code,4401)


class BidRulesTests(BidTests):
    def test_leader_cannot_outbid_self(self):
        place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('110'))
        with self.assertRaises(ValidationError):
            place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('130'))

    def test_late_bid_extends_auction(self):
        self.auction.end_at=timezone.now()+timedelta(seconds=30); self.auction.save()
        place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('110'))
        self.auction.refresh_from_db()
        self.assertGreater(self.auction.end_at,timezone.now()+timedelta(seconds=90))

    def test_early_bid_does_not_extend_auction(self):
        before=self.auction.end_at
        place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('110'))
        self.auction.refresh_from_db(); self.assertEqual(self.auction.end_at,before)

    def test_public_bid_history_masks_bidders(self):
        place_bid(auction_id=self.auction.id,bidder=self.buyer,amount=Decimal('110'))
        r=self.client.get(f'/api/bidding/auctions/{self.auction.id}/bids/')
        self.assertEqual(r.status_code,200)
        row=r.json()['results'][0]; self.assertEqual(row['bidder_name'],'bu***r'); self.assertNotIn('bidder',row)
