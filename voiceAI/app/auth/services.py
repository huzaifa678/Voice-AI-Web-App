import os
from tokenize import TokenError
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from app.common.jwt import generate_token
from app.common.rate_limit import rate_limit
from app.common.utils import parse_timedelta
from app.models import RefreshToken  

User = get_user_model()

class AuthService:

    REFRESH_TOKEN_LIFETIME = parse_timedelta(os.getenv("REFRESH_TOKEN_LIFETIME", "7d"))
    
    @staticmethod
    def register(username: str, email: str, password: str):
        if User.objects.filter(username=username).exists():
            raise ValueError("Username already exists")

        user = User.objects.create_user(username=username, email=email, password=password)
        return user
    
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
    def verify_token(token: str):
        """
        Verify JWT access token and return user
        """
        try:
            access = AccessToken(token)
        except TokenError:
            raise ValueError("Invalid or expired token")

        user_id = access.get("user_id")
        if not user_id:
            raise ValueError("Invalid token payload")

        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise ValueError("User not found")
        
    
class JWTAuthenticationService(BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get("Authorization")

        if not auth or not auth.startswith("Bearer "):
            return None

        token = auth.split("Bearer ")[1].strip()

        try:
            user = AuthService.verify_token(token)
        except Exception:
            raise AuthenticationFailed("Invalid or expired token")

        return (user, token)
