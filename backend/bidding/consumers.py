"""Live auction WebSocket: read-only feed (bids, status changes, viewer count). Bids are only accepted over REST.

Hardening: JWT in the subprotocol (never the URL), suspended users refused, a per-user connection cap, only existing
SCHEDULED/LIVE auctions, size-limited frames, and the page's Origin is checked in config/asgi.py.
"""
from urllib.parse import urlparse

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.core.cache import cache

from auctions.models import Auction

TTL = 6 * 3600  # counters expire on their own so a crashed worker cannot leave them stuck


def _bump(key, delta):
    cache.add(key, 0, TTL)
    try:
        n = cache.incr(key, delta)
    except ValueError:
        n = max(delta, 0)
        cache.set(key, n, TTL)
    if n < 0:
        n = 0
        cache.set(key, 0, TTL)
    return n


class AuctionConsumer(AsyncJsonWebsocketConsumer):
    max_size = 4096  # clients only ever send tiny ping frames

    async def connect(self):
        self.counted_conn = self.counted_view = False
        self.auction_id = self.scope['url_route']['kwargs']['auction_id']
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        if getattr(user, 'is_suspended', False) or not user.is_active:
            await self.close(code=4403)
            return
        if not await self.allowed():
            await self.close(code=4403)
            return
        self.user_key = f'ws-conn:{user.pk}'
        if await database_sync_to_async(_bump)(self.user_key, 1) > settings.WS_MAX_CONNECTIONS_PER_USER:
            await database_sync_to_async(_bump)(self.user_key, -1)
            await self.close(code=4429)  # too many connections for this account
            return
        self.counted_conn = True
        self.group = f'auction_{self.auction_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept('jwt' if 'jwt' in self.scope.get('subprotocols', []) else None)
        self.view_key = f'viewers:{self.auction_id}'
        count = await database_sync_to_async(_bump)(self.view_key, 1)
        self.counted_view = True
        await self.channel_layer.group_send(self.group, {'type': 'bid.update', 'data': {'event': 'viewers', 'count': count}})

    async def disconnect(self, code):
        if getattr(self, 'group', None):
            await self.channel_layer.group_discard(self.group, self.channel_name)
        if getattr(self, 'counted_conn', False):
            await database_sync_to_async(_bump)(self.user_key, -1)
        if getattr(self, 'counted_view', False):
            count = await database_sync_to_async(_bump)(self.view_key, -1)
            await self.channel_layer.group_send(self.group, {'type': 'bid.update', 'data': {'event': 'viewers', 'count': count}})

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict) and content.get('type') == 'ping':
            await self.send_json({'event': 'pong'})
            return
        await self.send_json({'type': 'error', 'detail': 'Bids must be submitted through the authenticated REST endpoint.'})

    async def bid_update(self, event):
        await self.send_json(event['data'])

    async def allowed(self):
        @database_sync_to_async
        def check():
            return Auction.objects.filter(pk=self.auction_id, status__in=['SCHEDULED', 'LIVE']).exists()
        return await check()


def allowed_origin_hosts():
    """Hostnames the browser page may connect from: ALLOWED_HOSTS plus the CORS origins (and localhost in development)."""
    hosts = {h for h in settings.ALLOWED_HOSTS if h and h != '*'}
    hosts |= {urlparse(o).hostname for o in settings.CORS_ALLOWED_ORIGINS if urlparse(o).hostname}
    if settings.DEBUG:
        hosts |= {'localhost', '127.0.0.1'}
    return sorted(hosts)
