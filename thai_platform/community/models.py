from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models


class ContentStatus(models.TextChoices):
    PUBLISHED = 'published', 'Published'
    HIDDEN = 'hidden', 'Hidden'
    DELETED = 'deleted', 'Deleted'


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Post(Timestamped):
    class Resolution(models.TextChoices):
        UNRESOLVED = "unresolved", "미해결"
        RESOLVED = "resolved", "작성자 해결 확인"

    class Region(models.TextChoices):
        BANGKOK = 'bangkok', 'Bangkok'
        CHIANGMAI = 'chiangmai', 'Chiang Mai'
        PHUKET = 'phuket', 'Phuket'
        COMMON = 'common', 'Common'

    class Category(models.TextChoices):
        LIVING = 'living', 'Living'
        HOUSING = 'housing', 'Housing'
        VISA = 'visa', 'Visa'
        TRAVEL = 'travel', 'Travel'
        BANKING = 'banking', 'Banking'

    Status = ContentStatus
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='community_posts')
    title = models.CharField(max_length=100)
    body = models.TextField(validators=[MaxLengthValidator(6000)])
    region = models.CharField(max_length=10, choices=Region.choices, default=Region.COMMON)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.LIVING)
    resolution = models.CharField(max_length=10, choices=Resolution.choices, default=Resolution.UNRESOLVED, db_index=True)
    status = models.CharField(max_length=10, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.title


class Comment(Timestamped):
    Status = ContentStatus
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='community_comments')
    body = models.TextField(validators=[MaxLengthValidator(3000)])
    status = models.CharField(max_length=10, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED, db_index=True)

    class Meta:
        ordering = ['created_at', 'pk']


class Report(Timestamped):
    class Reason(models.TextChoices):
        OUTDATED = 'outdated', 'Outdated'
        PRIVACY = 'privacy', 'Privacy'
        SPAM = 'spam', 'Spam'
        ABUSE = 'abuse', 'Abuse'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved'
        DISMISSED = 'dismissed', 'Dismissed'

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='community_reports')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reports')
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    reason = models.CharField(max_length=10, choices=Reason.choices)
    details = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.comment_id and self.comment.post_id != self.post_id:
            raise ValidationError({'comment': 'Comment must belong to this post.'})


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
