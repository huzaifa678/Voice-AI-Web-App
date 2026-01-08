from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    """
    Extend Django's default User if needed
    """
    pass

class UserProfile(models.Model):
    """
    Stores additional info like voice phrase, STT data, etc.
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="profile")
    voice_phrase = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} Profile"
