from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from . import services
from .models import AuditEvent, Comment, ModerationAppeal, Notification, Post


@override_settings(ROOT_URLCONF='config.urls')
class AppealReviewServiceTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.author = users.objects.create_user(username='appeal-review-author')
        self.original_moderator = users.objects.create_user(
            username='appeal-original-moderator', is_staff=True
        )
        self.reviewer = users.objects.create_user(
            username='appeal-independent-reviewer', is_staff=True
        )
        group = Group.objects.get_or_create(name='Report moderators')[0]
        self.original_moderator.groups.add(group)
        self.reviewer.groups.add(group)
        self.post = Post.objects.create(
            author=self.author,
            title='Hidden synthetic appeal post',
            body='Synthetic test content only.',
            status=Post.Status.HIDDEN,
        )
        AuditEvent.objects.create(
            actor=self.original_moderator,
            action='content.hide',
            target_type='post',
            target_id=str(self.post.pk),
        )
        self.appeal = ModerationAppeal.objects.create(
            author=self.author,
            post=self.post,
            target_type=ModerationAppeal.TargetType.POST,
            details='Please review this synthetic hidden-post decision.',
        )

    def test_independent_moderator_can_restore_and_notify_author(self):
        services.resolve_appeal(
            self.reviewer, self.appeal, ModerationAppeal.Status.RESTORED
        )

        self.appeal.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.appeal.status, ModerationAppeal.Status.RESTORED)
        self.assertEqual(self.appeal.reviewed_by, self.reviewer)
        self.assertIsNotNone(self.appeal.reviewed_at)
        self.assertEqual(self.post.status, Post.Status.PUBLISHED)
        self.assertTrue(Notification.objects.filter(
            recipient=self.author,
            kind=Notification.Kind.APPEAL_UPDATE,
            appeal=self.appeal,
        ).exists())

    def test_independent_moderator_can_uphold_and_notify_author(self):
        services.resolve_appeal(
            self.reviewer, self.appeal, ModerationAppeal.Status.UPHELD
        )

        self.appeal.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.appeal.status, ModerationAppeal.Status.UPHELD)
        self.assertEqual(self.appeal.reviewed_by, self.reviewer)
        self.assertEqual(self.post.status, Post.Status.HIDDEN)
        self.assertTrue(Notification.objects.filter(
            recipient=self.author,
            kind=Notification.Kind.APPEAL_UPDATE,
            appeal=self.appeal,
        ).exists())

    def test_original_moderator_cannot_review_own_hide_decision(self):
        with self.assertRaises(PermissionDenied):
            services.resolve_appeal(
                self.original_moderator,
                self.appeal,
                ModerationAppeal.Status.RESTORED,
            )

        self.appeal.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.appeal.status, ModerationAppeal.Status.PENDING_REVIEW)
        self.assertEqual(self.post.status, Post.Status.HIDDEN)
        self.assertFalse(Notification.objects.filter(appeal=self.appeal).exists())

    def test_missing_original_moderator_fails_closed(self):
        AuditEvent.objects.filter(action='content.hide', target_id=str(self.post.pk)).delete()
        with self.assertRaises(ValidationError):
            services.resolve_appeal(
                self.reviewer, self.appeal, ModerationAppeal.Status.RESTORED
            )
        self.assertEqual(Notification.objects.filter(appeal=self.appeal).count(), 0)

    def test_appeal_can_only_be_decided_once(self):
        services.resolve_appeal(
            self.reviewer, self.appeal, ModerationAppeal.Status.UPHELD
        )
        with self.assertRaises(ValidationError):
            services.resolve_appeal(
                self.reviewer, self.appeal, ModerationAppeal.Status.RESTORED
            )
        self.assertEqual(Notification.objects.filter(appeal=self.appeal).count(), 1)

    def test_admin_action_and_private_notifications_expose_the_decision(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('admin:community_moderationappeal_changelist'),
            {'action': 'restore_appeals', '_selected_action': [str(self.appeal.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        self.appeal.refresh_from_db()
        self.assertEqual(self.appeal.status, ModerationAppeal.Status.RESTORED)

        self.client.force_login(self.author)
        response = self.client.get('/community/notifications/')
        self.assertContains(response, '콘텐츠가 복구되었습니다.')
        api = APIClient()
        api.force_authenticate(self.author)
        notification = api.get('/api/v1/notifications/').data['results'][0]
        self.assertEqual(notification['kind'], 'appeal_update')
        self.assertEqual(notification['appeal'], self.appeal.pk)
        appeal = api.get(f'/api/v1/appeals/{self.appeal.pk}/')
        self.assertEqual(appeal.status_code, 200)
        self.assertEqual(appeal.data['status'], ModerationAppeal.Status.RESTORED)
        api.force_authenticate(self.reviewer)
        self.assertEqual(api.get('/api/v1/notifications/').data['count'], 0)
        self.assertEqual(api.get(f'/api/v1/appeals/{self.appeal.pk}/').status_code, 404)

    def test_comment_appeal_restores_only_the_comment(self):
        self.post.status = Post.Status.PUBLISHED
        self.post.save(update_fields=['status', 'updated_at'])
        comment = Comment.objects.create(
            author=self.author, post=self.post, body='Synthetic hidden reply.',
            status=Comment.Status.HIDDEN,
        )
        AuditEvent.objects.create(
            actor=self.original_moderator, action='content.hide',
            target_type='comment', target_id=str(comment.pk),
        )
        appeal = ModerationAppeal.objects.create(
            author=self.author, post=self.post, comment=comment,
            target_type=ModerationAppeal.TargetType.COMMENT,
            details='Please review this hidden reply.',
        )

        services.resolve_appeal(
            self.reviewer, appeal, ModerationAppeal.Status.RESTORED
        )
        comment.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.PUBLISHED)
        self.assertEqual(self.post.status, Post.Status.PUBLISHED)

    def test_deleted_comment_appeal_never_restores_parent_post(self):
        comment = Comment.objects.create(
            author=self.author, post=self.post, body='Synthetic deleted reply.',
            status=Comment.Status.HIDDEN,
        )
        AuditEvent.objects.create(
            actor=self.original_moderator, action='content.hide',
            target_type='comment', target_id=str(comment.pk),
        )
        appeal = ModerationAppeal.objects.create(
            author=self.author, post=self.post, comment=comment,
            target_type=ModerationAppeal.TargetType.COMMENT,
            details='Please review the deleted reply.',
        )
        comment.delete()

        with self.assertRaises(ValidationError):
            services.resolve_appeal(
                self.reviewer, appeal, ModerationAppeal.Status.RESTORED
            )
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.HIDDEN)