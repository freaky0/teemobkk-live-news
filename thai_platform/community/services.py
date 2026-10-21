"""Shared web/API mutations. All failures are DRF PermissionDenied (403),
ValidationError (400), or NotFound (404). Inputs are mappings, never trusted
model kwargs. Mutations return model instances; delete_post returns the deleted
Post. Requests are not idempotency-key protected; do not blindly retry creates.
"""
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import AuditEvent, Comment, Post, Report
from .serializers import (CommentInputSerializer, PostInputSerializer,
                          ReportInputSerializer, ReportResolutionSerializer)


def require_active(user):
    if not user or not user.is_authenticated or not user.is_active:
        raise PermissionDenied('An active signed-in account is required.')
    profile = getattr(user, 'membership', None)
    if profile is not None and not profile.is_complete:
        raise PermissionDenied('Complete nickname and consent onboarding first.')


def require_staff(user):
    require_active(user)
    if not user.is_staff:
        raise PermissionDenied('Staff access required.')


def require_owner(user, post):
    require_active(user)
    if post.author_id != user.pk and not user.is_staff:
        raise PermissionDenied('Only the author or staff may change this post.')


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


@transaction.atomic
def create_post(user, data):
    require_active(user)
    post = Post.objects.create(author=user, **_validate(PostInputSerializer, data))
    _audit(user, 'post.create', post)
    return post


@transaction.atomic
def update_post(user, post, data):
    require_owner(user, post)
    post = Post.objects.select_for_update().get(pk=post.pk)
    require_owner(user, post)
    if post.status == Post.Status.DELETED:
        raise NotFound('Post not found.')
    for key, value in _validate(PostInputSerializer, data, partial=True).items():
        setattr(post, key, value)
    post.save()
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


@transaction.atomic
def create_comment(user, post, data):
    require_active(user)
    post = Post.objects.select_for_update().get(pk=post.pk)
    _published(post)
    comment = Comment.objects.create(author=user, post=post, **_validate(CommentInputSerializer, data))
    _audit(user, 'comment.create', comment)
    return comment


@transaction.atomic
def create_report(user, post, data):
    require_active(user)
    post = Post.objects.select_for_update().get(pk=post.pk)
    _published(post)
    values = _validate(ReportInputSerializer, data)
    comment = values.get('comment')
    if comment:
        comment_id = comment.pk if isinstance(comment, Comment) else comment
        comment = Comment.objects.select_for_update().get(pk=comment_id)
        if comment.post_id != post.pk:
            raise ValidationError({'comment': 'Comment must belong to this post.'})
    report = Report.objects.create(reporter=user, post=post, comment=comment, **{k: v for k, v in values.items() if k != 'comment'})
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
def moderate_comment(user, comment, status):
    require_staff(user)
    if status not in (Comment.Status.PUBLISHED, Comment.Status.HIDDEN):
        raise ValidationError({'status': 'Comment moderation supports published or hidden status.'})
    comment = Comment.objects.select_for_update().get(pk=comment.pk)
    previous = comment.status
    if previous != status:
        comment.status = status
        comment.save(update_fields=['status', 'updated_at'])
        _audit(user, 'comment.moderate', comment, {'previous_status': previous, 'status': status})
    return comment


@transaction.atomic
def resolve_report(user, report, data):
    require_staff(user)
    values = _validate(ReportResolutionSerializer, data)
    report = Report.objects.select_for_update().get(pk=report.pk)
    if report.status != Report.Status.OPEN:
        raise ValidationError({'status': 'Only open reports can be reviewed.'})
    previous = report.status
    report.status = values['status']
    report.save(update_fields=['status', 'updated_at'])
    _audit(user, 'report.resolve', report, {'previous_status': previous, 'status': report.status})
    return report
