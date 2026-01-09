import os
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

from app.common.jwt import generate_token
from app.common.rate_limit import rate_limit
from app.common.utils import parse_timedelta
from app.models import RefreshToken  

User = get_user_model()

class AuthService:

    REFRESH_TOKEN_LIFETIME = parse_timedelta(os.getenv("REFRESH_TOKEN_LIFETIME", "7d"))
    
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

        access_token = generate_token(user)

        refresh_token = str(uuid.uuid4())
        expires_at = timezone.now() + AuthService.REFRESH_TOKEN_LIFETIME
        RefreshToken.objects.create(
            user=user,
            token=refresh_token,
            expires_at=expires_at
        )

        return {
            "access": access_token,
            "refresh": refresh_token
        }

    @staticmethod
    def refresh(refresh_token_str: str):
        """
        Validate the DB-backed refresh token and issue a new access token.
        """
        try:
            db_token = RefreshToken.objects.get(token=refresh_token_str)
        except RefreshToken.DoesNotExist:
            raise ValueError("Invalid refresh token")

        if not db_token.is_valid():
            raise ValueError("Refresh token expired or revoked")

        access_token = generate_token(db_token.user)

        return {
            "access": access_token,
        }
        
    @staticmethod
    def register(username: str, email: str, password: str):
        if User.objects.filter(username=username).exists():
            raise ValueError("Username already exists")

        user = User.objects.create_user(username=username, email=email, password=password)
        return user
