from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from app.auth.services import AuthService
from types import SimpleNamespace
from channels.db import database_sync_to_async

class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send): 
        query_string = scope.get("query_string", b"").decode()
        qs = parse_qs(query_string)
        token = qs.get("token", [None])[0]
        
        print(token)
        print(qs)
        print(query_string)

        scope["user"] = await self.get_user(token)

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user(self, token):
        if not token:
            return AnonymousUser()
        try:
            user_data = AuthService.verify_token(token)
            user_data = {
                "id": user_data.id,
                "username": user_data.username,
                "email": user_data.email,
            }
            user = SimpleNamespace(**user_data)
            return user
        except Exception as e:
            print("Token verification failed:", e)
            return AnonymousUser()
