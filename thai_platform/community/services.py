"""Shared web/API mutations. All failures are DRF PermissionDenied (403),
ValidationError (400), or NotFound (404). Inputs are mappings, never trusted
model kwargs. Mutations return model instances; delete_post returns the deleted
Post. Requests are not idempotency-key protected; do not blindly retry creates.
"""
from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import AuditEvent, Comment, Post, Report, Helpful, Bookmark
from django.db.models import Count, Exists, OuterRef
from .serializers import (CommentInputSerializer, PostInputSerializer, PostResolutionSerializer, EngagementInputSerializer,
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


def public_posts(user=None):
    qs = Post.objects.filter(status=Post.Status.PUBLISHED).select_related('author').annotate(helpful_count=Count('helpful_votes', distinct=True)).order_by('-created_at', '-pk')
    if user and user.is_authenticated:
        qs = qs.annotate(
            helpful_active=Exists(Helpful.objects.filter(user=user, post_id=OuterRef('pk'))),
            bookmarked=Exists(Bookmark.objects.filter(user=user, post_id=OuterRef('pk'))),
        )
    return qs


def activity(user, kind):
    require_active(user)
    qs = public_posts(user)
    if kind == 'posts':
        return qs.filter(author=user)
    if kind == 'comments':
        return Comment.objects.filter(author=user, status=Post.Status.PUBLISHED, post__status=Post.Status.PUBLISHED).order_by('-created_at', '-pk')
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
    if comment and comment.post_id != post.pk:
        raise ValidationError({'comment': 'Comment must belong to this post.'})
    report = Report.objects.create(reporter=user, post=post, **values)
    _audit(user, 'report.create', report)
    return report


@transaction.atomic
def resolve_report(user, report, data):
    require_staff(user)
    values = _validate(ReportResolutionSerializer, data)
    report = Report.objects.select_for_update().get(pk=report.pk)
    previous = report.status
    report.status = values['status']
    report.save(update_fields=['status', 'updated_at'])
    _audit(user, 'report.resolve', report, {'previous_status': previous, 'status': report.status})
    return report
