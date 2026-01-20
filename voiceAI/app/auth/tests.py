import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestAuthViews:

    @patch("app.auth.views.AuthService.register")
    @patch("app.auth.views.publish_email_task")
    def test_register_success(self, mock_publish_email, mock_register, api_client):
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_register.return_value = mock_user

        url = reverse("register")  
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "strongpassword123"
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["detail"] == "User created successfully"
        mock_publish_email.assert_called_once_with({
            "to_email": mock_user.email,
            "subject": "Welcome to VoiceAI!",
            "template": "welcome_email",
            "context": {"username": mock_user.username}
        })

    @patch("app.auth.views.AuthService.register")
    def test_register_failure_invalid_data(self, mock_register, api_client):
        url = reverse("register")
        data = {"username": "", "email": "not-an-email", "password": "123"}
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_register.assert_not_called()

    @patch("app.auth.views.AuthService.login")
    def test_login_success(self, mock_login, api_client):
        mock_login.return_value = ("access_token_mock", "refresh_token_mock")

        url = reverse("login")
        data = {"username": "testuser", "password": "password123"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "access": "access_token_mock",
            "refresh": "refresh_token_mock"
        }

    @patch("app.auth.views.AuthService.login")
    def test_login_failure_invalid_credentials(self, mock_login, api_client):
        mock_login.side_effect = ValueError("Invalid credentials")
        url = reverse("login")
        data = {"username": "testuser", "password": "wrongpassword"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["detail"] == "Invalid credentials"

    @patch("app.auth.views.AuthService.refresh")
    def test_refresh_success(self, mock_refresh, api_client):
        mock_refresh.return_value = {"access": "new_access_token"}
        url = reverse("refresh")
        data = {"refresh": "valid_refresh_token"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"access": "new_access_token"}

    @patch("app.auth.views.AuthService.refresh")
    def test_refresh_failure_invalid_token(self, mock_refresh, api_client):
        mock_refresh.side_effect = ValueError("Invalid refresh token")
        url = reverse("refresh")
        data = {"refresh": "invalid_token"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["detail"] == "Invalid refresh token"
