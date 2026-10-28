from django.conf import settings
from django.core.validators import MaxLengthValidator, MinValueValidator
from django.db import models
from .places import build_google_maps_search_url


class ContentStatus(models.TextChoices):
    PUBLISHED = 'published', 'Published'
    HIDDEN = 'hidden', 'Hidden'
    DELETED = 'deleted', 'Deleted'


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BoardCategory(models.Model):
    board = models.CharField(max_length=10, choices=[(v, v) for v in ('notice', 'free', 'market', 'jobs', 'living')])
    slug = models.SlugField(max_length=50)
    name = models.CharField(max_length=100)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['board', 'slug'], name='unique_board_category_slug')]
        ordering = ['board', 'name', 'pk']

    def __str__(self):
        return f'{self.board}: {self.name}'


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
        NOTICE = 'notice', '공지'
        FREE = 'free', '자유게시판'
        QUESTIONS = 'questions', '질문/답변'
        MARKET = 'market', '중고게시판'
        JOBS = 'jobs', '구인구직'
        FOODTRAVEL = 'foodtravel', '맛집/여행지'
        LIVING = 'living', '생활 질문'
        HOUSING = 'housing', '생활 질문'
        VISA = 'visa', 'Visa'
        TRAVEL = 'travel', 'Travel'
        BANKING = 'banking', '생활 질문'

    class MarketKind(models.TextChoices):
        SELL = 'sell', '판매'
        BUY = 'buy', '구매'

    class MarketStatus(models.TextChoices):
        ACTIVE = 'active', '거래 중'
        RESERVED = 'reserved', '예약'
        COMPLETED = 'completed', '완료'

    class JobKind(models.TextChoices):
        HIRING = 'hiring', '구인'
        SEEKING = 'seeking', '구직'

    class JobStatus(models.TextChoices):
        OPEN = 'open', '모집 중'
        CLOSED = 'closed', '마감'

    Status = ContentStatus
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='community_posts')
    title = models.CharField(max_length=100)
    body = models.TextField(validators=[MaxLengthValidator(6000)])
    region = models.CharField(max_length=10, choices=Region.choices, default=Region.COMMON)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.LIVING)
    board_category = models.ForeignKey(BoardCategory, null=True, blank=True, on_delete=models.PROTECT, related_name='posts')
    is_pinned = models.BooleanField(default=False, db_default=False)
    resolution = models.CharField(max_length=10, choices=Resolution.choices, default=Resolution.UNRESOLVED, db_index=True)
    status = models.CharField(max_length=10, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED, db_index=True)
    market_kind = models.CharField(max_length=4, choices=MarketKind.choices, blank=True, db_default='', default='')
    market_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    market_region = models.CharField(max_length=10, choices=Region.choices, blank=True, db_default='', default='')
    market_status = models.CharField(max_length=10, choices=MarketStatus.choices, blank=True, db_default='', default='')
    job_kind = models.CharField(max_length=7, choices=JobKind.choices, blank=True, db_default='', default='')
    job_region = models.CharField(max_length=10, choices=Region.choices, blank=True, db_default='', default='')
    job_compensation = models.CharField(max_length=200, blank=True, db_default='', default='')
    job_status = models.CharField(max_length=6, choices=JobStatus.choices, blank=True, db_default='', default='')
    place_name = models.CharField(max_length=160, blank=True, db_default='', default='')
    place_region = models.CharField(max_length=10, choices=Region.choices, blank=True, db_default='', default='')
    place_note = models.CharField(max_length=500, blank=True, db_default='', default='')
    place_url = models.CharField(max_length=500, blank=True, db_default='', default='')

    @property
    def google_maps_search_url(self):
        if self.category != self.Category.FOODTRAVEL or not self.place_name:
            return ''
        region = self.get_place_region_display() if self.place_region else ''
        return build_google_maps_search_url(self.place_name, region)

    class Meta:
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return self.title


class BoardPostContent(models.Model):
    """Staging schema for the independent-board storage migration.

    These tables are deliberately not populated until reads and writes can be
    cut over atomically; the existing Post table remains authoritative for now.
    """
    post = models.OneToOneField(Post, primary_key=True, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    body = models.TextField(validators=[MaxLengthValidator(6000)])

    class Meta:
        abstract = True


class NoticePost(BoardPostContent):
    pass


class FreePost(BoardPostContent):
    pass


class MarketPost(BoardPostContent):
    pass


class JobsPost(BoardPostContent):
    pass


class LivingPost(BoardPostContent):
    pass


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
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.RESTRICT, related_name='replies')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='community_comments')
    body = models.TextField(validators=[MaxLengthValidator(3000)])
    status = models.CharField(max_length=10, choices=ContentStatus.choices, default=ContentStatus.PUBLISHED, db_index=True)

    class Meta:
        ordering = ['created_at', 'pk']


class CommentLike(Timestamped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comment_likes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'comment'], name='unique_comment_like_user_comment')]


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
    closed_at = models.DateTimeField(null=True, blank=True, db_index=True)

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
        PRIVATE_MESSAGE = 'private_message', 'Private message'
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


class MemberBlock(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='member_blocks')
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocked_by_members')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_member_block'), models.CheckConstraint(condition=~models.Q(blocker=models.F('blocked')), name='member_block_not_self')]


class PrivateMessage(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='sent_private_messages')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='received_private_messages')
    body = models.TextField(validators=[MaxLengthValidator(3000)])
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['recipient', '-created_at']), models.Index(fields=['sender', '-created_at'])]


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at', '-pk']
