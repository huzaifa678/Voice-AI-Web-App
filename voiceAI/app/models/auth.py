from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class RefreshToken(models.Model):
    """
    Store refresh tokens for JWT auth.
    Each token is tied to a user and can be revoked.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="refresh_tokens"
    )
    token = models.CharField(max_length=512, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    def is_valid(self):
        """
        Check if the token is not revoked and not expired
        """
        return not self.revoked and timezone.now() < self.expires_at

    def revoke(self):
        self.revoked = True
        self.save()

    def __str__(self):
        return f"RefreshToken(user={self.user.username}, revoked={self.revoked})"
