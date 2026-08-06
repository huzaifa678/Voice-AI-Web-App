import uuid
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class AudioSession(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audio_sessions",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.STARTED,
    )

    transcript = models.TextField(blank=True)
    audio_duration_ms = models.IntegerField(null=True, blank=True)
    sample_rate = models.IntegerField(default=16000)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(blank=True)

    def mark_completed(self, transcript: str):
        self.status = self.Status.COMPLETED
        self.transcript = transcript
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "transcript", "completed_at"])

    def mark_failed(self, error: str):
        self.status = self.Status.FAILED
        self.error_message = error
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "error_message", "completed_at"])

    def __str__(self):
        return f"AudioSession({self.id}, user={self.user}, status={self.status})"
