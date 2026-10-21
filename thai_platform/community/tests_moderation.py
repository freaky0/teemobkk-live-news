from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from . import services
from .admin import NewsCommentAdmin
from .models import AuditEvent, Comment, NewsComment, Notification, Post, Report


@override_settings(ROOT_URLCONF='config.urls')
class ModeratorRoleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username="ordinary-staff", is_staff=True)
        self.moderator = User.objects.create_user(username="report-moderator", is_staff=True)
        group = Group.objects.get_or_create(name="Report moderators")[0]
        self.moderator.groups.add(group)

    def test_moderation_role_is_separate_from_staff_and_superuser(self):
        self.assertFalse(services.is_report_moderator(self.staff))
        self.assertTrue(services.is_report_moderator(self.moderator))
        self.staff.is_superuser = True
        self.staff.save(update_fields=["is_superuser"])
        self.assertFalse(services.is_report_moderator(self.staff))

    def test_require_report_moderator_rejects_ordinary_staff(self):
        with self.assertRaises(PermissionDenied):
            services.require_report_moderator(self.staff)

    def test_hiding_reported_comment_does_not_hide_parent_post(self):
        owner = get_user_model().objects.create_user(username="content-author")
        reporter = get_user_model().objects.create_user(username="reporter")
        post = Post.objects.create(author=owner, title="Question", body="Question body")
        comment = Comment.objects.create(post=post, author=owner, body="Answer body")
        report = Report.objects.create(reporter=reporter, post=post, comment=comment, target_type=Report.TargetType.COMMENT, reason="spam")

        services.hide_reported_content(self.moderator, report)

        post.refresh_from_db()
        comment.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertEqual(comment.status, Comment.Status.HIDDEN)
        self.assertEqual(report.status, Report.Status.RESOLVED)
        self.assertEqual(Notification.objects.filter(recipient=owner, kind=Notification.Kind.CONTENT_HIDDEN).count(), 1)
        self.assertTrue(owner.is_active)
        self.assertEqual(AuditEvent.objects.get(action="content.hide").target_id, str(comment.pk))

    def test_hiding_reported_post_does_not_hide_its_comments_or_restrict_author(self):
        owner = get_user_model().objects.create_user(username="post-content-author")
        reporter = get_user_model().objects.create_user(username="post-content-reporter")
        post = Post.objects.create(author=owner, title="Question", body="Question body")
        comment = Comment.objects.create(post=post, author=owner, body="Answer body")
        report = Report.objects.create(reporter=reporter, post=post, reason="spam")

        services.hide_reported_content(self.moderator, report)

        post.refresh_from_db()
        comment.refresh_from_db()
        owner.refresh_from_db()
        self.assertEqual(post.status, Post.Status.HIDDEN)
        self.assertEqual(comment.status, Comment.Status.PUBLISHED)
        self.assertTrue(owner.is_active)

    def test_staff_cannot_hide_or_resolve_report(self):
        owner = get_user_model().objects.create_user(username="author-two")
        reporter = get_user_model().objects.create_user(username="reporter-two")
        post = Post.objects.create(author=owner, title="Question", body="Question body")
        report = Report.objects.create(reporter=reporter, post=post, reason="spam")

        with self.assertRaises(PermissionDenied):
            services.hide_reported_content(self.staff, report)
        with self.assertRaises(PermissionDenied):
            services.resolve_report(self.staff, report, {"status": Report.Status.DISMISSED})

    def test_report_api_hides_only_reported_content_for_moderators(self):
        owner = get_user_model().objects.create_user(username="api-content-author")
        reporter = get_user_model().objects.create_user(username="api-reporter")
        post = Post.objects.create(author=owner, title="Question", body="Question body")
        comment = Comment.objects.create(post=post, author=owner, body="Answer body")
        report = Report.objects.create(reporter=reporter, post=post, comment=comment, target_type=Report.TargetType.COMMENT, reason="spam")
        api = APIClient()

        api.force_authenticate(self.staff)
        self.assertEqual(api.get('/api/v1/reports/').status_code, 403)
        api.force_authenticate(self.moderator)
        response = api.get('/api/v1/reports/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(api.post('/api/v1/reports/', {}, format='json').status_code, 405)
        response = api.post(f'/api/v1/reports/{report.pk}/hide/')
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        post.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.HIDDEN)
        self.assertEqual(post.status, Post.Status.PUBLISHED)

    def test_appeal_is_limited_to_author_of_hidden_content_and_private(self):
        owner = get_user_model().objects.create_user(username="appeal-author")
        other = get_user_model().objects.create_user(username="appeal-other")
        post = Post.objects.create(author=owner, title="Question", body="Question body", status=Post.Status.HIDDEN)
        api = APIClient()

        api.force_authenticate(other)
        self.assertEqual(api.post('/api/v1/appeals/', {'post': post.pk, 'details': 'I disagree with hiding.'}, format='json').status_code, 403)
        api.force_authenticate(owner)
        response = api.post('/api/v1/appeals/', {'post': post.pk, 'details': 'I disagree with hiding.'}, format='json')
        self.assertEqual(response.status_code, 201)
        response = api.get('/api/v1/appeals/')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        api.force_authenticate(other)
        self.assertEqual(api.get('/api/v1/appeals/').data['count'], 0)

    def test_appeal_web_form_only_renders_for_hidden_content_author(self):
        owner = get_user_model().objects.create_user(username="web-appeal-author")
        other = get_user_model().objects.create_user(username="web-appeal-other")
        post = Post.objects.create(author=owner, title="Question", body="Question body", status=Post.Status.HIDDEN)
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/community/{post.pk}/appeal/').status_code, 404)
        self.client.force_login(owner)
        response = self.client.get(f'/community/{post.pk}/appeal/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '이의신청 접수')
        self.assertTrue(response['Cache-Control'].startswith('no-store, private'))
        response = self.client.post(f'/community/{post.pk}/appeal/', {'details': '조치에 이의가 있습니다.'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(owner.community_appeals.count(), 1)

    def test_admin_report_and_audit_pages_are_moderator_only(self):
        self.client.force_login(self.staff)
        self.assertNotEqual(self.client.get('/admin/community/report/').status_code, 200)
        self.assertNotEqual(self.client.get('/admin/community/auditevent/').status_code, 200)
        self.client.force_login(self.moderator)
        self.assertEqual(self.client.get('/admin/community/report/').status_code, 200)
        self.assertEqual(self.client.get('/admin/community/auditevent/').status_code, 200)

    def test_news_comment_moderation_is_restricted_audited_and_reversible(self):
        author = get_user_model().objects.create_user(username='news-comment-author')
        comment = NewsComment.objects.create(
            article_id='a' * 64,
            author=author,
            body='A public article comment that needs moderation.',
        )

        with self.assertRaises(PermissionDenied):
            services.moderate_news_comment(self.staff, comment, NewsComment.Status.HIDDEN)

        services.moderate_news_comment(self.moderator, comment, NewsComment.Status.HIDDEN)
        comment.refresh_from_db()
        self.assertEqual(comment.status, NewsComment.Status.HIDDEN)
        self.assertEqual(
            AuditEvent.objects.filter(
                actor=self.moderator,
                action='content.hide',
                target_type='newscomment',
                target_id=str(comment.pk),
            ).count(),
            1,
        )

        services.moderate_news_comment(self.moderator, comment, NewsComment.Status.HIDDEN)
        self.assertEqual(AuditEvent.objects.filter(target_id=str(comment.pk)).count(), 1)
        services.moderate_news_comment(self.moderator, comment, NewsComment.Status.PUBLISHED)
        comment.refresh_from_db()
        self.assertEqual(comment.status, NewsComment.Status.PUBLISHED)
        self.assertEqual(
            AuditEvent.objects.filter(
                actor=self.moderator,
                action='content.restore',
                target_type='newscomment',
                target_id=str(comment.pk),
            ).count(),
            1,
        )

    def test_news_comment_admin_actions_hide_and_restore(self):
        author = get_user_model().objects.create_user(username='news-comment-admin-author')
        comment = NewsComment.objects.create(
            article_id='b' * 64,
            author=author,
            body='A comment moderated through the admin action.',
        )
        url = reverse('admin:community_newscomment_changelist')

        self.client.force_login(self.staff)
        self.assertNotEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.moderator)
        hidden = self.client.post(url, {'action': 'hide_selected', '_selected_action': str(comment.pk)})
        self.assertEqual(hidden.status_code, 302)
        comment.refresh_from_db()
        self.assertEqual(comment.status, NewsComment.Status.HIDDEN)
        self.assertTrue(AuditEvent.objects.filter(action='content.hide', target_id=str(comment.pk)).exists())

        restored = self.client.post(url, {'action': 'restore_selected', '_selected_action': str(comment.pk)})
        self.assertEqual(restored.status_code, 302)
        comment.refresh_from_db()
        self.assertEqual(comment.status, NewsComment.Status.PUBLISHED)
        self.assertTrue(AuditEvent.objects.filter(action='content.restore', target_id=str(comment.pk)).exists())

    def test_news_comment_admin_is_visible_only_to_moderators(self):
        model_admin = NewsCommentAdmin(NewsComment, admin.site)
        request = RequestFactory().get('/admin/community/newscomment/')
        request.user = self.staff
        self.assertFalse(model_admin.has_module_permission(request))
        self.assertFalse(model_admin.has_view_permission(request))
        request.user = self.moderator
        self.assertTrue(model_admin.has_module_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))

    def test_hide_rejects_comment_from_a_different_post(self):
        owner = get_user_model().objects.create_user(username="mismatched-content-author")
        reporter = get_user_model().objects.create_user(username="mismatched-content-reporter")
        reported_post = Post.objects.create(author=owner, title="Reported post", body="Reported body")
        other_post = Post.objects.create(author=owner, title="Other post", body="Other body")
        comment = Comment.objects.create(post=other_post, author=owner, body="Other answer")
        report = Report.objects.create(
            reporter=reporter, post=reported_post, comment=comment,
            target_type=Report.TargetType.COMMENT, reason="spam",
        )

        with self.assertRaises(ValidationError):
            services.hide_reported_content(self.moderator, report)

        reported_post.refresh_from_db()
        other_post.refresh_from_db()
        comment.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(reported_post.status, Post.Status.PUBLISHED)
        self.assertEqual(other_post.status, Post.Status.PUBLISHED)
        self.assertEqual(comment.status, Comment.Status.PUBLISHED)
        self.assertEqual(report.status, Report.Status.OPEN)

    def test_deleted_reported_comment_is_never_misinterpreted_as_post_report(self):
        owner = get_user_model().objects.create_user(username="deleted-comment-author")
        reporter = get_user_model().objects.create_user(username="deleted-comment-reporter")
        post = Post.objects.create(author=owner, title="Question", body="Question body")
        comment = Comment.objects.create(post=post, author=owner, body="Answer body")
        report = Report.objects.create(reporter=reporter, post=post, comment=comment, target_type=Report.TargetType.COMMENT, reason="spam")
        comment.delete()

        with self.assertRaises(ValidationError):
            services.hide_reported_content(self.moderator, report)
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
