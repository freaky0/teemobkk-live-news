import uuid
from django.conf import settings
from django.db import models

class MemberProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="membership")
    email_key = models.EmailField(unique=True)
    email_login_enabled = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    email_answer_notifications = models.BooleanField(default=False)
    nickname_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    nickname_changed_at = models.DateTimeField(null=True, blank=True)
    avatar = models.CharField(max_length=12, default='person')
    avatar_image = models.BinaryField(null=True, blank=True, editable=False)
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


class AccountClosureRequest(models.Model):
    class Status(models.TextChoices):
        PENDING_REVIEW = 'pending_review', 'Pending review'
        REVIEWED = 'reviewed', 'Reviewed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='closure_requests')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_REVIEW, db_index=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_closure_requests')

    class Meta:
        ordering = ['status', 'requested_at', 'pk']
