import uuid
from django.conf import settings
from django.db import models

class MemberProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership")
    email_key = models.EmailField(unique=True)
    email_login_enabled = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    nickname_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    terms_version = models.CharField(max_length=40, blank=True)
    privacy_version = models.CharField(max_length=40, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_complete(self):
        return bool(self.accepted_at and self.nickname_key and self.email_verified_at)

class EmailChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64)
    session_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
