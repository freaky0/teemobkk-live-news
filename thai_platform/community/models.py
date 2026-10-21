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


class Helpful(Timestamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='helpful_votes')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'post'], name='unique_helpful_user_post')]


class NewsLike(Timestamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='news_likes')
    article_id = models.CharField(max_length=64, db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'article_id'], name='unique_news_like_user_article')]


class NewsComment(Timestamped):
    Status = ContentStatus
    article_id = models.CharField(max_length=64, db_index=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='news_comments')
    body = models.TextField(validators=[MaxLengthValidator(3000)])
    status = models.CharField(max_length=10, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED, db_index=True)

    class Meta:
        ordering = ['created_at', 'pk']


class Bookmark(Timestamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='bookmarks')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'post'], name='unique_bookmark_user_post')]


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

    class TargetType(models.TextChoices):
        POST = 'post', 'Post'
        COMMENT = 'comment', 'Comment'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved'
        DISMISSED = 'dismissed', 'Dismissed'

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='community_reports')
    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name='reports')
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    target_type = models.CharField(max_length=10, choices=TargetType.choices, default=TargetType.POST, db_index=True)
    reason = models.CharField(max_length=10, choices=Reason.choices)
    details = models.TextField(blank=True, validators=[MaxLengthValidator(2000)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.comment_id and self.comment.post_id != self.post_id:
            raise ValidationError({'comment': 'Comment must belong to this post.'})

class ModerationAppeal(Timestamped):
    class TargetType(models.TextChoices):
        POST = 'post', 'Post'
        COMMENT = 'comment', 'Comment'

    class Status(models.TextChoices):
        PENDING_REVIEW = 'pending_review', 'Pending review'
        UPHELD = 'upheld', 'Hidden decision upheld'
        RESTORED = 'restored', 'Content restored'

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='community_appeals')
    post = models.ForeignKey(Post, on_delete=models.PROTECT, related_name='moderation_appeals')
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderation_appeals')
    target_type = models.CharField(max_length=10, choices=TargetType.choices, null=True, blank=True)
    details = models.TextField(validators=[MaxLengthValidator(2000)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_REVIEW, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_community_appeals')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class Notification(Timestamped):
    class Kind(models.TextChoices):
        REPLY = 'reply', 'Reply'
        MODERATION_REPORT = 'moderation_report', 'New report'
        REPORT_UPDATE = 'report_update', 'Report update'
        CONTENT_HIDDEN = 'content_hidden', 'Content hidden'
        APPEAL_UPDATE = 'appeal_update', 'Appeal update'

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_notifications')
    kind = models.CharField(max_length=24, choices=Kind.choices)
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    comment = models.ForeignKey(Comment, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    report = models.ForeignKey(Report, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    appeal = models.ForeignKey(ModerationAppeal, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
