import uuid

from django.contrib.auth.models import User
from django.db import models


class PasswordResetSession(models.Model):
    """Stores one-time reset codes for the neon portal."""

    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_sessions')
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def mark_used(self):
        from django.utils import timezone

        self.used_at = timezone.now()
        self.save(update_fields=['used_at'])
