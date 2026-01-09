import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model

from app.serializers.register_serializer import RegisterSerializer
from app.serializers.login_serializer import LoginSerializer
from app.serializers.refresh_serializer import RefreshSerializer
from app.common.rabbit_mq import publish_email_task
from .services import AuthService

User = get_user_model()

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = AuthService.register(
                    username=serializer.validated_data['username'],
                    email=serializer.validated_data['email'],
                    password=serializer.validated_data['password'],
                )
                
                publish_email_task({
                    "to_email": user.email,
                    "subject": "Welcome to VoiceAI!",
                    "template": "welcome_email", 
                    "context": {
                        "username": user.username
                    }
                })
                return Response({"detail": "User created successfully"}, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            ip = request.META.get("REMOTE_ADDR", "unknown")
            try:
                tokens = AuthService.login(
                    ip=ip,
                    username=serializer.validated_data['username'],
                    password=serializer.validated_data['password'],
                )
                return Response(tokens, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class RefreshView(APIView):
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        if serializer.is_valid():
            try:
                token = AuthService.refresh(serializer.validated_data['refresh'])
                return Response(token, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)