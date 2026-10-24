from datetime import timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import SellerProfile, User
from auctions.models import Auction
from auctions.services import close_auction
from auctions.tasks import process_auction_lifecycle
from bidding.services import place_bid
from config.asgi import application
from products.models import Category, Product


class LiveAuctionSocketTests(TransactionTestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='liveseller', email='ls@example.com', password='StrongPassword123!', role='SELLER', email_verified=True)
        SellerProfile.objects.create(user=self.seller, approved=True, verified=True)
        self.buyer = User.objects.create_user(username='livebuyer', email='lb@example.com', password='StrongPassword123!', role='BUYER', email_verified=True)
        p = Product.objects.create(seller=self.seller, category=Category.objects.create(name='L', slug='l-live'), name='Live lot', description='x' * 40, starting_price=100, condition='Good', status='AUCTION')
        self.a = Auction.objects.create(product=p, seller=self.seller, starting_price=100, min_increment=10, start_at=timezone.now() - timedelta(minutes=1), end_at=timezone.now() + timedelta(hours=1), status='LIVE')
        self.token = str(AccessToken.for_user(self.buyer))

    def comm(self, origin=None, token=None):
        headers = [(b'origin', origin.encode())] if origin else []
        return WebsocketCommunicator(application, f'/ws/auctions/{self.a.id}/', headers=headers, subprotocols=['jwt', token or self.token])

    def test_a_page_on_another_site_cannot_connect(self):
        ok, _ = async_to_sync(self.comm(origin='https://evil.example').connect)()
        self.assertFalse(ok)

    def test_the_real_frontend_origin_and_non_browser_clients_can_connect(self):
        async def run():
            res = []
            for origin in ('http://localhost:5173', None):
                c = self.comm(origin=origin)
                res.append((await c.connect())[0])
                await c.disconnect()
            return res
        self.assertEqual(async_to_sync(run)(), [True, True])

    def test_suspended_accounts_are_refused(self):
        User.objects.filter(pk=self.buyer.pk).update(is_suspended=True)
        ok, code = async_to_sync(self.comm().connect)()
        self.assertEqual((ok, code), (False, 4403))

    @override_settings(WS_MAX_CONNECTIONS_PER_USER=2)
    def test_connection_cap_per_account(self):
        async def run():
            a, b, c = self.comm(), self.comm(), self.comm()
            ok_a, ok_b = (await a.connect())[0], (await b.connect())[0]
            refused = await c.connect()
            await a.disconnect()  # frees a slot
            d = self.comm()
            ok_d = (await d.connect())[0]
            await b.disconnect()
            await d.disconnect()
            return ok_a, ok_b, refused, ok_d
        ok_a, ok_b, refused, ok_d = async_to_sync(run)()
        self.assertTrue(ok_a and ok_b and ok_d)
        self.assertEqual(refused, (False, 4429))

    def test_viewer_count_is_pushed_and_ping_gets_a_pong(self):
        async def run():
            a = self.comm()
            await a.connect()
            first = await a.receive_json_from()
            b = self.comm()
            await b.connect()
            second = await a.receive_json_from()
            await a.send_json_to({'type': 'ping'})
            events = [await a.receive_json_from() for _ in range(1)]
            await b.disconnect()
            gone = await a.receive_json_from()
            await a.disconnect()
            return first, second, events, gone
        first, second, events, gone = async_to_sync(run)()
        self.assertEqual((first['event'], first['count']), ('viewers', 1))
        self.assertEqual(second['count'], 2)
        self.assertEqual(events[0], {'event': 'pong'})
        self.assertEqual((gone['event'], gone['count']), ('viewers', 1))

    def test_going_live_and_closing_are_broadcast_without_a_refresh(self):
        Auction.objects.filter(pk=self.a.pk).update(status='SCHEDULED')

        async def run():
            c = self.comm()
            await c.connect()
            await c.receive_json_from()  # viewers
            from asgiref.sync import sync_to_async
            await sync_to_async(process_auction_lifecycle)()
            live = await c.receive_json_from()
            await sync_to_async(place_bid)(auction_id=self.a.id, bidder=self.buyer, amount=Decimal('100'))
            bid = await c.receive_json_from()
            await sync_to_async(lambda: Auction.objects.filter(pk=self.a.pk).update(end_at=timezone.now() - timedelta(seconds=1)))()
            await sync_to_async(close_auction)(self.a.id)
            closed = await c.receive_json_from()
            await c.disconnect()
            return live, bid, closed
        live, bid, closed = async_to_sync(run)()
        self.assertEqual((live['event'], live['status']), ('status', 'LIVE'))
        self.assertEqual((bid['event'], bid['bidder_id']), ('bid', self.buyer.id))
        self.assertEqual((closed['event'], closed['status'], closed['winner']), ('status', 'SOLD', 'li***r'))  # winner is masked on the public feed
        self.assertEqual(closed['price'], '100.00')


class ServerTimeTests(TransactionTestCase):
    def test_auction_payload_carries_server_time(self):
        from rest_framework.test import APIClient
        seller = User.objects.create_user(username='st-seller', email='st@example.com', password='StrongPassword123!', role='SELLER')
        p = Product.objects.create(seller=seller, category=Category.objects.create(name='T', slug='t-st'), name='T', description='x' * 40, starting_price=10, condition='Good', status='AUCTION')
        a = Auction.objects.create(product=p, seller=seller, starting_price=10, min_increment=1, start_at=timezone.now() - timedelta(minutes=1), end_at=timezone.now() + timedelta(hours=1), status='LIVE')
        r = APIClient().get(f'/api/auctions/auctions/{a.id}/')
        self.assertIn('server_time', r.json())
