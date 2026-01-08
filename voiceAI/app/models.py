from django.contrib.auth.models import AbstractUser, Group, Permission
from time import timezone
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model

User = get_user_model()

class RefreshToken(models.Model):
    """
    Store refresh tokens for JWT auth.
    Each token is tied to a user and can be revoked.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
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
    
    
class CustomUser(AbstractUser):
    groups = models.ManyToManyField(
        Group,
        related_name="user3553",  
        blank=True,
        help_text="The groups this user belongs to.",
        verbose_name="groups",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="user3553", 
        blank=True,
        help_text="Specific permissions for this user.",
        verbose_name="user permissions",
    )

class UserProfile(models.Model):
    """
    Stores additional info like voice phrase, STT data, etc.
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="profile")
    voice_phrase = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile"


