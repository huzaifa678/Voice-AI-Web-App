from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from app.common.jwt import generate_token
from app.common.rate_limit import rate_limit
from app.audio.services import AudioService


class AuthService:

    @staticmethod
    def login(ip: str, username: str, password: str):
        rate_limit(
            key=f"login:{ip}",
            limit=5,
            window_seconds=60,
        )

        user = authenticate(username=username, password=password)
        if not user:
            raise ValueError("Invalid credentials")

        return generate_token(user)

    @staticmethod
    def refresh(refresh_token: str):
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken(refresh_token)
        return {"access": str(token.access_token)}