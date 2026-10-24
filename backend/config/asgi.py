import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import OriginValidator
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from bidding.auth import JwtAuthMiddleware
from bidding.consumers import allowed_origin_hosts
from bidding.routing import websocket_urlpatterns


class BrowserOriginValidator:
    """Cross-site WebSocket protection. Browsers always send an Origin header, so a page on another site is refused;
    non-browser clients (no Origin header) are still required to present a valid JWT."""

    def __init__(self, app):
        self.app = app
        self.checked = OriginValidator(app, allowed_origin_hosts())

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket' and not dict(scope.get('headers', [])).get(b'origin'):
            return await self.app(scope, receive, send)
        return await self.checked(scope, receive, send)


application=ProtocolTypeRouter({
    'http':django_asgi_app,
    'websocket':BrowserOriginValidator(
        AuthMiddlewareStack(JwtAuthMiddleware(URLRouter(websocket_urlpatterns)))
    ),
})
