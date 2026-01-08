from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status

from .services import AuthService


class LoginView(APIView):

    def post(self, request):
        ip = request.META.get("REMOTE_ADDR", "unknown")

        try:
            tokens = AuthService.login(
                ip=ip,
                username=request.data.get("username"),
                password=request.data.get("password"),
            )
            return Response(tokens, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class RefreshView(APIView):

    def post(self, request):
        token = AuthService.refresh(request.data.get("refresh"))
        return Response(token, status=status.HTTP_200_OK)
