"""Shared web/API mutations. All failures are DRF PermissionDenied (403),
ValidationError (400), or NotFound (404). Inputs are mappings, never trusted
model kwargs. Mutations return model instances; delete_post returns the deleted
Post. Requests are not idempotency-key protected; do not blindly retry creates.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from allauth.account.models import EmailAddress
from members.models import MemberProfile
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import (AuditEvent, Bookmark, Comment, FreePost, Helpful, JobsPost, LivingPost,
                     MarketPost, MemberBlock, ModerationAppeal, NewsComment, NoticePost,
                     Notification, Post, Report)
from .board_versions import board_data_version
from django.db.models import Count, Exists, OuterRef, Q
from .serializers import (CommentInputSerializer, PostInputSerializer, PostResolutionSerializer, EngagementInputSerializer,
                          ReportInputSerializer, ReportResolutionSerializer, AppealInputSerializer)

logger = logging.getLogger(__name__)

LIFE_BOARD_CATEGORIES = (
    Post.Category.LIVING,
    Post.Category.HOUSING,
    Post.Category.BANKING,
)


def canonical_life_category(category):
    return Post.Category.LIVING if category in LIFE_BOARD_CATEGORIES else category


def category_filter_values(category):
    return LIFE_BOARD_CATEGORIES if category in LIFE_BOARD_CATEGORIES else (category,)


BOARD_CONTENT_MODELS = {
    Post.Category.NOTICE: NoticePost,
    Post.Category.FREE: FreePost,
    Post.Category.MARKET: MarketPost,
    Post.Category.JOBS: JobsPost,
    Post.Category.LIVING: LivingPost,
}


def _sync_board_content(post, old_category=None):
    """Maintain non-authoritative board copies while legacy reads use Post."""
    old_model = BOARD_CONTENT_MODELS.get(canonical_life_category(old_category))
    new_model = BOARD_CONTENT_MODELS.get(canonical_life_category(post.category))
    if old_model is not None and old_model is not new_model:
        old_model.objects.filter(post_id=post.pk).delete()
    if new_model is not None:
        new_model.objects.update_or_create(
            post_id=post.pk, defaults={'title': post.title, 'body': post.body},
        )


def validate_board_category(category, board_category):
    if board_category and board_category.board != canonical_life_category(category):
        raise ValidationError({'board_category': 'Category does not belong to this board.'})


def require_active(user):
    if not user or not user.is_authenticated or not user.is_active:
        raise PermissionDenied('An active signed-in account is required.')
    profile = getattr(user, 'membership', None)
    if profile is not None and not profile.is_complete:
        raise PermissionDenied('Complete nickname and consent onboarding first.')


def is_report_moderator(user):
    return bool(
        user and user.is_authenticated and user.is_active and user.is_staff
        and user.groups.filter(name='Report moderators').exists()
    )


def require_report_moderator(user):
    require_active(user)
    if not is_report_moderator(user):
        raise PermissionDenied('Report moderator access required.')


def require_owner(user, post):
    require_active(user)
    if post.category == Post.Category.NOTICE:
        if not user.is_staff:
            raise PermissionDenied('Staff access required for notices.')
    elif post.author_id != user.pk:
        raise PermissionDenied('Only the author may change this post.')


def _published(post):
    if post.status != Post.Status.PUBLISHED:
        raise PermissionDenied('This post is not available for interaction.')


def _validate(serializer_class, data, **kwargs):
    serializer = serializer_class(data=data, **kwargs)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _audit(user, action, obj, metadata=None):
    AuditEvent.objects.create(actor=user, action=action, target_type=obj._meta.model_name,
                              target_id=str(obj.pk), metadata=metadata or {})


def require_post_operator(user):
    require_active(user)
    # Post operators are active staff, as for notice management; report
    # moderation remains a separate group-based permission.
    if not user.is_staff:
        raise PermissionDenied('Operator access required.')


@transaction.atomic
def operator_post_action(user, post, action):
    require_post_operator(user)
    if action not in ('hide', 'restore', 'delete'):
        raise ValidationError({'action': 'Invalid action.'})
    post = Post.objects.select_for_update().select_related('author').get(pk=post.pk)
    if post.status == Post.Status.DELETED:
        raise NotFound('Post not found.')
    previous = post.status
    if action == 'hide' and previous != Post.Status.PUBLISHED:
        raise ValidationError({'action': 'Only published posts can be hidden.'})
    if action == 'restore' and previous != Post.Status.HIDDEN:
        raise ValidationError({'action': 'Only hidden posts can be restored.'})
    post.status = {'hide': Post.Status.HIDDEN, 'restore': Post.Status.PUBLISHED, 'delete': Post.Status.DELETED}[action]
    post.save(update_fields=['status', 'updated_at'])
    _audit(user, {'hide': 'content.hide', 'restore': 'content.restore', 'delete': 'post.delete'}[action], post,
           {'previous_status': previous, 'status': post.status, 'source': 'operator'})
    if action == 'hide' and post.author.is_active:
        Notification.objects.create(recipient=post.author, kind=Notification.Kind.CONTENT_HIDDEN, post=post)
    return post


@transaction.atomic
def create_post(user, data):
    require_active(user)
    values = _validate(PostInputSerializer, data)
    values.pop('confirm_board_data_removal', None)
    values.pop('board_data_version', None)
    if 'category' in values:
        values['category'] = canonical_life_category(values['category'])
    validate_board_category(values.get('category', Post.Category.LIVING), values.get('board_category'))
    if values.get('category') != Post.Category.MARKET:
        for key in ('market_kind', 'market_price', 'market_region', 'market_status'):
            values.pop(key, None)
    if values.get('category') != Post.Category.JOBS:
        for key in ('job_kind', 'job_region', 'job_compensation', 'job_status'):
            values.pop(key, None)
    if values.get('category') != Post.Category.FOODTRAVEL:
        for key in ('place_name', 'place_region', 'place_note', 'place_url'):
            values.pop(key, None)
    if values.get('category') == Post.Category.NOTICE and not user.is_staff:
        raise PermissionDenied('Staff access required for notices.')
    if 'is_pinned' in data and not user.is_staff:
        raise PermissionDenied('Staff access required for pinning.')
    if values.get('is_pinned') and values.get('category') != Post.Category.NOTICE:
        raise ValidationError({'is_pinned': 'Only notices can be pinned.'})
    post = Post.objects.create(author=user, **values)
    _sync_board_content(post)
    _audit(user, 'post.create', post)
    return post


@transaction.atomic
def update_post(user, post, data):
    require_owner(user, post)
    post = Post.objects.select_for_update().get(pk=post.pk)
    require_owner(user, post)
    old_category = post.category
    # Partial edits and board transfers must start from the board row, not
    # potentially stale legacy fields on the shared identity record.
    content = post.board_content
    if content is not None:
        post.title, post.body = content.title, content.body
    if post.status == Post.Status.DELETED:
        raise NotFound('Post not found.')
    values = _validate(PostInputSerializer, data, partial=True)
    confirmed = values.pop('confirm_board_data_removal', False)
    version = values.pop('board_data_version', None)
    if version and version != board_data_version(post):
        raise ValidationError({'board_data_version': '게시글이 변경되었습니다. 최신 정보를 확인해 주세요.'})
    if 'category' in values:
        values['category'] = canonical_life_category(values['category'])
    validate_board_category(values.get('category', post.category), values.get('board_category', post.board_category))
    board_fields = {
        Post.Category.MARKET: ('market_kind', 'market_price', 'market_region', 'market_status'),
        Post.Category.JOBS: ('job_kind', 'job_region', 'job_compensation', 'job_status'),
        Post.Category.FOODTRAVEL: ('place_name', 'place_region', 'place_note', 'place_url'),
    }
    if (values.get('category', post.category) != post.category and
            any(getattr(post, field) is not None and getattr(post, field) != '' for field in board_fields.get(post.category, ())) and
            (not confirmed or version != board_data_version(post))):
        raise ValidationError({'confirm_board_data_removal': '게시판 정보가 변경되었거나 삭제 동의가 없습니다. 최신 정보를 확인하고 다시 동의해 주세요.'})
    if values.get('category', post.category) != Post.Category.MARKET:
        for key in ('market_kind', 'market_price', 'market_region', 'market_status'):
            values.pop(key, None)
        if post.category == Post.Category.MARKET:
            values.update(market_kind='', market_price=None, market_region='', market_status='')
    if values.get('category', post.category) != Post.Category.JOBS:
        for key in ('job_kind', 'job_region', 'job_compensation', 'job_status'):
            values.pop(key, None)
        if post.category == Post.Category.JOBS:
            values.update(job_kind='', job_region='', job_compensation='', job_status='')
    if values.get('category', post.category) != Post.Category.FOODTRAVEL:
        for key in ('place_name', 'place_region', 'place_note', 'place_url'):
            values.pop(key, None)
        if post.category == Post.Category.FOODTRAVEL:
            values.update(place_name='', place_region='', place_note='', place_url='')
    if values.get('category') == Post.Category.NOTICE and not user.is_staff:
        raise PermissionDenied('Staff access required for notices.')
    if 'is_pinned' in data and not user.is_staff:
        raise PermissionDenied('Staff access required for pinning.')
    if values.get('is_pinned', post.is_pinned) and values.get('category', post.category) != Post.Category.NOTICE:
        raise ValidationError({'is_pinned': 'Only notices can be pinned.'})
    for key, value in values.items():
        setattr(post, key, value)
    post.save()
    _sync_board_content(post, old_category)
    _audit(user, 'post.update', post)
    return post


@transaction.atomic
def delete_post(user, post):
    require_owner(user, post)
    post = Post.objects.select_for_update().get(pk=post.pk)
    require_owner(user, post)
    if post.status != Post.Status.DELETED:
        post.status = Post.Status.DELETED
        post.save(update_fields=['status', 'updated_at'])
        _audit(user, 'post.delete', post)
    return post


def blocked_member_ids(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    return MemberBlock.objects.filter(blocker_id=user.pk).values_list('blocked_id', flat=True)


def visible_posts(user=None):
    blocked_ids = blocked_member_ids(user)
    qs = Post.objects.filter(status=Post.Status.PUBLISHED)
    qs = qs.select_related('noticepost', 'freepost', 'marketpost', 'jobspost', 'livingpost')
    if blocked_ids is not None:
        qs = qs.exclude(author_id__in=blocked_ids)
    qs = qs.select_related('author', 'author__membership').annotate(
        helpful_count=Count('helpful_votes', distinct=True),
    ).order_by('-is_pinned', '-created_at', '-pk')
    if user and getattr(user, 'is_authenticated', False):
        qs = qs.annotate(
            helpful_active=Exists(Helpful.objects.filter(user=user, post_id=OuterRef('pk'))),
            bookmarked=Exists(Bookmark.objects.filter(user=user, post_id=OuterRef('pk'))),
        )
    return qs


def search_posts(qs, query):
    from django.db.models import Case, CharField, F, When
    from django.db.models.functions import Coalesce
    boards = [('notice', 'noticepost'), ('free', 'freepost'), ('market', 'marketpost'),
              ('jobs', 'jobspost'), ('living', 'livingpost'), ('housing', 'livingpost'),
              ('banking', 'livingpost')]
    def content(field):
        return Case(*(When(category=category, then=Coalesce(F(f'{relation}__{field}'), F(field)))
                      for category, relation in boards), default=F(field), output_field=CharField())
    return qs.alias(search_title=content('title'), search_body=content('body')).filter(
        Q(search_title__icontains=query) | Q(search_body__icontains=query))


def public_posts(user=None):
    return visible_posts(user)


def visible_comments(user=None, post=None):
    qs = Comment.objects.filter(
        status=Comment.Status.PUBLISHED,
        post__status=Post.Status.PUBLISHED,
    ).filter(Q(parent__isnull=True) | Q(parent__status=Comment.Status.PUBLISHED))
    if post is not None:
        qs = qs.filter(post_id=post.pk)
    blocked_ids = blocked_member_ids(user)
    if blocked_ids is not None:
        qs = qs.exclude(author_id__in=blocked_ids).exclude(post__author_id__in=blocked_ids)
        qs = qs.filter(Q(parent__isnull=True) | ~Q(parent__author_id__in=blocked_ids))
    return qs


def visible_notifications(user):
    qs = Notification.objects.filter(recipient=user)
    invalid_reply = Q(kind=Notification.Kind.REPLY, comment__isnull=False) & (
        ~Q(comment__status=Comment.Status.PUBLISHED)
        | Q(post__isnull=True)
        | ~Q(post__status=Post.Status.PUBLISHED)
        | Q(comment__post__isnull=True)
        | ~Q(comment__post__status=Post.Status.PUBLISHED)
        | (Q(comment__parent__isnull=False) & ~Q(comment__parent__status=Comment.Status.PUBLISHED))
    )
    qs = qs.exclude(invalid_reply)
    blocked_ids = blocked_member_ids(user)
    if blocked_ids is not None:
        qs = qs.exclude(
            Q(kind=Notification.Kind.REPLY, comment__author_id__in=blocked_ids)
            | Q(kind=Notification.Kind.REPLY, post__author_id__in=blocked_ids)
            | Q(kind=Notification.Kind.REPLY, comment__post__author_id__in=blocked_ids)
            | Q(kind=Notification.Kind.REPLY, comment__parent__author_id__in=blocked_ids)
        )
    return qs


def activity(user, kind):
    require_active(user)
    qs = public_posts(user)
    if kind == 'posts':
        return qs.filter(author=user)
    if kind == 'comments':
        return visible_comments(user).filter(author=user).order_by('-created_at', '-pk')
    if kind == 'helpful':
        return qs.filter(helpful_votes__user=user)
    if kind == 'bookmarks':
        return qs.filter(bookmarks__user=user)
    raise ValidationError({'kind': 'Invalid activity kind.'})


@transaction.atomic
def set_bookmark(user, post, data):
    require_active(user)
    post = Post.objects.select_for_update().get(pk=post.pk)
    _published(post)
    active = _validate(EngagementInputSerializer, data)['active']
    if active:
        Bookmark.objects.get_or_create(user=user, post=post)
    else:
        Bookmark.objects.filter(user=user, post=post).delete()
    # Private interests are not copied into the general moderation audit log.
    return {'active': active}


@transaction.atomic
def set_helpful(user, post, data):
    require_active(user)
    post = Post.objects.select_for_update().get(pk=post.pk)
    _published(post)
    active = _validate(EngagementInputSerializer, data)['active']
    if active:
        _, changed = Helpful.objects.get_or_create(user=user, post=post)
    else:
        changed, _ = Helpful.objects.filter(user=user, post=post).delete()
    if changed:
        _audit(user, 'post.helpful', post, {'active': active})
    return {'active': active, 'helpful_count': Helpful.objects.filter(post=post).count()}


@transaction.atomic
def set_resolution(user, post, data):
    require_active(user)
    post = Post.objects.select_for_update().get(pk=post.pk)
    if post.status != Post.Status.PUBLISHED:
        raise NotFound('Post not found.')
    if post.author_id != user.pk:
        raise PermissionDenied('Only the author may confirm resolution.')
    value = _validate(PostResolutionSerializer, data)['resolution']
    previous = post.resolution
    if previous != value:
        post.resolution = value
        post.save(update_fields=['resolution', 'updated_at'])
        _audit(user, 'post.resolution', post, {'previous_resolution': previous, 'resolution': value})
    return post


@transaction.atomic
def create_comment(user, post, data):
    require_active(user)
    post = Post.objects.select_for_update().get(pk=post.pk)
    _published(post)
    values = _validate(CommentInputSerializer, data)
    parent_id = values.pop('parent', None)
    if parent_id is not None:
        parent = visible_comments(user, post).select_for_update().filter(pk=parent_id, parent__isnull=True).first()
        if parent is None:
            raise ValidationError({'parent': 'Invalid answer.'})
        values['parent'] = parent
    comment = Comment.objects.create(author=user, post=post, **values)
    if post.author_id != user.pk and post.author.is_active:
        Notification.objects.create(recipient=post.author, kind=Notification.Kind.REPLY, post=post, comment=comment)
        if parent_id is None:
            transaction.on_commit(
                lambda user_id=post.author_id, post_id=post.pk: _send_answer_notification_email(user_id, post_id)
            )
    _audit(user, 'comment.create', comment)
    return comment


def _send_answer_notification_email(user_id, post_id):
    if not settings.POST_MAIL_ENABLED or not settings.DEFAULT_FROM_EMAIL or not settings.POST_PUBLIC_ORIGIN:
        return
    try:
        profile = MemberProfile.objects.select_related('user').filter(
            user_id=user_id,
            email_answer_notifications=True,
            email_verified_at__isnull=False,
            user__is_active=True,
        ).first()
        if profile is None:
            return
        email = profile.email_key.strip().casefold()
        if not email or profile.user.email.strip().casefold() != email:
            return
        if not EmailAddress.objects.filter(user_id=user_id, email__iexact=email, verified=True).exists():
            return
        post = Post.objects.filter(pk=post_id, author_id=user_id, status=Post.Status.PUBLISHED).first()
        if post is None:
            return
        link = settings.POST_PUBLIC_ORIGIN + reverse('post-detail', kwargs={'pk': post.pk})
        send_mail(
            '새 답변이 등록되었습니다',
            f'작성하신 질문에 새 답변이 등록되었습니다.\n\n아래 링크에서 확인할 수 있습니다.\n{link}\n',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
    except Exception:
        logger.error('Could not send an opted-in answer notification email.')


@transaction.atomic
def create_report(user, post, data):
    require_active(user)
    post = Post.objects.select_for_update().get(pk=post.pk)
    _published(post)
    values = _validate(ReportInputSerializer, data)
    comment = values.get('comment')
    if comment:
        comment = Comment.objects.select_for_update().get(pk=comment.pk)
        if comment.post_id != post.pk:
            raise ValidationError({'comment': 'Comment must belong to this post.'})
        values['comment'] = comment
    report = Report.objects.create(
        reporter=user, post=post,
        target_type=Report.TargetType.COMMENT if comment else Report.TargetType.POST,
        **values,
    )
    from django.contrib.auth import get_user_model
    for moderator in get_user_model().objects.filter(is_active=True, is_staff=True, groups__name='Report moderators').distinct().only('pk'):
        Notification.objects.create(recipient=moderator, kind=Notification.Kind.MODERATION_REPORT, post=post, report=report)
    _audit(user, 'report.create', report)
    if comment and comment.status == Comment.Status.PUBLISHED:
        reporter_count = comment.reports.filter(status=Report.Status.OPEN).values('reporter_id').distinct().count()
        if reporter_count >= 10:
            comment.status = Comment.Status.HIDDEN
            comment.save(update_fields=['status', 'updated_at'])
            _audit(user, 'comment.auto_hide', comment, {
                'reason': 'report_threshold', 'distinct_open_reporters': reporter_count,
            })
    return report


@transaction.atomic
def moderate_news_comment(user, comment, status):
    require_report_moderator(user)
    if status not in (NewsComment.Status.HIDDEN, NewsComment.Status.PUBLISHED):
        raise ValidationError({'status': 'Choose hide or restore.'})

    comment = NewsComment.objects.select_for_update().get(pk=comment.pk)
    if comment.status == NewsComment.Status.DELETED:
        raise ValidationError({'status': 'Deleted comments cannot be moderated.'})
    if comment.status == status:
        return comment
    if comment.status not in (NewsComment.Status.PUBLISHED, NewsComment.Status.HIDDEN):
        raise ValidationError({'status': 'This comment cannot be moderated from its current state.'})

    previous = comment.status
    comment.status = status
    comment.save(update_fields=['status', 'updated_at'])
    action = 'content.hide' if status == NewsComment.Status.HIDDEN else 'content.restore'
    _audit(user, action, comment, {
        'previous_status': previous,
        'status': status,
        'article_id': comment.article_id,
    })
    return comment


@transaction.atomic
def moderate_comment(user, comment, status):
    require_report_moderator(user)
    if status not in (Comment.Status.PUBLISHED, Comment.Status.HIDDEN):
        raise ValidationError({'status': 'Comment moderation supports published or hidden status.'})
    comment = Comment.objects.select_for_update().get(pk=comment.pk)
    if comment.status == Comment.Status.DELETED:
        raise ValidationError({'status': 'Deleted comments cannot be moderated.'})
    previous = comment.status
    if previous != status:
        comment.status = status
        comment.save(update_fields=['status', 'updated_at'])
        _audit(user, 'comment.moderate', comment, {'previous_status': previous, 'status': status})
    return comment


@transaction.atomic
def resolve_report(user, report, data):
    require_report_moderator(user)
    values = _validate(ReportResolutionSerializer, data)
    report = Report.objects.select_for_update().select_related('post', 'comment', 'reporter').get(pk=report.pk)
    if report.status != Report.Status.OPEN:
        raise ValidationError({'status': 'Only open reports can be resolved.'})
    previous = report.status
    report.status = values['status']
    report.closed_at = timezone.now()
    report.save(update_fields=['status', 'closed_at', 'updated_at'])
    if previous != report.status and report.reporter.is_active:
        Notification.objects.create(recipient=report.reporter, kind=Notification.Kind.REPORT_UPDATE, post=report.post, report=report)
    _audit(user, 'report.resolve', report, {'previous_status': previous, 'status': report.status})
    return report


@transaction.atomic
def hide_reported_content(user, report):
    require_report_moderator(user)
    report = Report.objects.select_for_update().select_related('post', 'comment', 'reporter').get(pk=report.pk)
    if report.status != Report.Status.OPEN:
        raise ValidationError({'status': 'Only open reports can hide content.'})
    if report.target_type == Report.TargetType.COMMENT:
        if report.comment_id is None:
            raise ValidationError({'target': 'The reported comment is no longer available.'})
        content = Comment.objects.select_for_update().select_related('author').filter(
            pk=report.comment_id, post_id=report.post_id
        ).first()
        if content is None:
            raise ValidationError({'target': 'The reported comment cannot be verified for this post.'})
    else:
        content = Post.objects.select_for_update().select_related('author').get(pk=report.post_id)
    if content.status != Post.Status.PUBLISHED:
        raise ValidationError({'status': 'Reported content is no longer published.'})
    content.status = Post.Status.HIDDEN
    content.save(update_fields=['status', 'updated_at'])
    report.status = Report.Status.RESOLVED
    report.save(update_fields=['status', 'updated_at'])
    if content.author.is_active:
        Notification.objects.create(
            recipient=content.author, kind=Notification.Kind.CONTENT_HIDDEN,
            post=report.post, comment=report.comment, report=report,
        )
    _audit(user, 'content.hide', content, {'report_id': report.pk, 'content_type': content._meta.model_name})
    _audit(user, 'report.resolve', report, {'previous_status': Report.Status.OPEN, 'status': Report.Status.RESOLVED, 'action': 'content_hidden'})
    if report.reporter.is_active:
        Notification.objects.create(recipient=report.reporter, kind=Notification.Kind.REPORT_UPDATE, post=report.post, report=report)
    return report


@transaction.atomic
def create_appeal(user, data):
    require_active(user)
    values = _validate(AppealInputSerializer, data)
    post = Post.objects.select_for_update().get(pk=values['post'].pk)
    comment = values.get('comment')
    if comment:
        comment = Comment.objects.select_for_update().get(pk=comment.pk)
        if comment.post_id != post.pk or comment.author_id != user.pk or comment.status != Comment.Status.HIDDEN:
            raise PermissionDenied('Only the author of a hidden comment may appeal it.')
    elif post.author_id != user.pk or post.status != Post.Status.HIDDEN:
        raise PermissionDenied('Only the author of a hidden post may appeal it.')
    appeal = ModerationAppeal.objects.create(
        author=user, post=post, comment=comment,
        target_type=ModerationAppeal.TargetType.COMMENT if comment else ModerationAppeal.TargetType.POST,
        details=values['details'],
    )
    _audit(user, 'appeal.create', appeal, {'content_type': 'comment' if comment else 'post'})
    return appeal


@transaction.atomic
def resolve_appeal(user, appeal, outcome):
    require_report_moderator(user)
    if outcome not in (ModerationAppeal.Status.UPHELD, ModerationAppeal.Status.RESTORED):
        raise ValidationError({'status': 'Choose uphold or restore.'})

    appeal = ModerationAppeal.objects.select_for_update().select_related('author', 'post', 'comment').get(pk=appeal.pk)
    if appeal.status != ModerationAppeal.Status.PENDING_REVIEW:
        raise ValidationError({'status': 'Only pending appeals can be reviewed.'})
    if appeal.target_type == ModerationAppeal.TargetType.COMMENT:
        if not appeal.comment_id:
            raise ValidationError({'target': 'The appealed comment is no longer available.'})
        content = Comment.objects.select_for_update().filter(pk=appeal.comment_id, post_id=appeal.post_id).first()
        if content is None:
            raise ValidationError({'target': 'The appealed comment is no longer available.'})
    elif appeal.target_type == ModerationAppeal.TargetType.POST:
        content = Post.objects.select_for_update().get(pk=appeal.post_id)
    else:
        raise ValidationError({'target': 'The appeal target cannot be verified; manual review is required.'})
    if content.status != Post.Status.HIDDEN:
        raise ValidationError({'status': 'The appealed content is no longer hidden.'})

    hide_event = AuditEvent.objects.filter(
        action='content.hide', target_type=appeal.target_type, target_id=str(content.pk)
    ).order_by('-created_at', '-pk').first()
    if hide_event is None or hide_event.actor_id is None:
        raise ValidationError({'reviewer': 'The original moderator cannot be verified; manual review is required.'})
    if hide_event.actor_id == user.pk:
        raise PermissionDenied('The moderator who hid this content cannot review its appeal.')

    now = timezone.now()
    claimed = ModerationAppeal.objects.filter(
        pk=appeal.pk, status=ModerationAppeal.Status.PENDING_REVIEW
    ).update(status=outcome, reviewed_by=user, reviewed_at=now)
    if claimed != 1:
        raise ValidationError({'status': 'This appeal has already been reviewed.'})

    if outcome == ModerationAppeal.Status.RESTORED:
        content.status = Post.Status.PUBLISHED
        content.save(update_fields=['status', 'updated_at'])
        _audit(user, 'content.restore', content, {'appeal_id': appeal.pk})
    _audit(user, 'appeal.review', appeal, {'decision': outcome, 'target_type': appeal.target_type})
    Notification.objects.create(
        recipient=appeal.author,
        kind=Notification.Kind.APPEAL_UPDATE,
        post=appeal.post,
        comment=appeal.comment,
        appeal=appeal,
    )
    return ModerationAppeal.objects.select_related('author', 'post', 'comment', 'reviewed_by').get(pk=appeal.pk)
