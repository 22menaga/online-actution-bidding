from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError


class JwtAuthMiddleware:
    def __init__(self, app):
        self.app = app
        self.authentication = JWTAuthentication()

    async def __call__(self, scope, receive, send):
        protocols = scope.get("subprotocols", [])
        token = next((value for value in protocols if value not in {"jwt", ""}), None)
        if token:
            try:
                validated_token = self.authentication.get_validated_token(token.encode("ascii"))
                scope = dict(scope)
                scope["user"] = await database_sync_to_async(self.authentication.get_user)(
                    validated_token
                )
            except (AuthenticationFailed, TokenError, UnicodeEncodeError):
                scope = dict(scope)
                scope["user"] = AnonymousUser()
        await self.app(scope, receive, send)
