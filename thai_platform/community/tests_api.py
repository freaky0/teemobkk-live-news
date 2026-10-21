from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase, override_settings
from django.middleware.csrf import _get_new_csrf_string
from rest_framework.test import APIClient

from .models import AuditEvent, Comment, Post, Report
from .admin import CommentAdmin
from . import services
from rest_framework.exceptions import PermissionDenied, ValidationError


@override_settings(ROOT_URLCONF='community.tests_api')
class CommunityAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username='owner', email='private@example.test')
        cls.other = User.objects.create_user(username='other')
        cls.staff = User.objects.create_user(username='staff', is_staff=True)
        cls.staff.groups.add(Group.objects.get_or_create(name='Report moderators')[0])
        cls.inactive = User.objects.create_user(username='inactive', is_active=False)
        cls.post = Post.objects.create(author=cls.owner, title='Bangkok guide', body='Useful content', region='bangkok', category='living')

    def setUp(self):
        self.client = APIClient()
        self.url = f'/api/v1/posts/{self.post.pk}/'

    def test_anonymous_read_and_write_denied(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('private@example.test', str(response.data))
        self.assertNotIn('reports', response.data)
        self.assertEqual(self.client.post('/api/v1/posts/', {'title': 'New', 'body': 'Text'}, format='json').status_code, 403)
        self.assertEqual(self.client.patch(self.url, {'title': 'x'}).status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url + 'comments/', {'body': 'x'}).status_code, 403)
        self.assertEqual(self.client.post(self.url + 'reports/', {'reason': 'spam'}).status_code, 403)

    def test_owner_and_staff_mutations(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.patch(self.url, {'title': 'Other'}).status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.patch(self.url, {'title': 'Staff'}).status_code, 403)
        self.assertEqual(self.client.delete(self.url).status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(self.url, {'title': 'Owner'}).status_code, 200)
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'deleted')
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_create_and_immutable_payload(self):
        self.client.force_authenticate(self.owner)
        data = {'title': 'New', 'body': 'Text', 'region': 'common', 'category': 'visa'}
        self.assertEqual(self.client.post('/api/v1/posts/', data, format='json').status_code, 201)
        for field, value in [('author', self.other.pk), ('id', 900), ('status', 'hidden')]:
            self.assertEqual(self.client.post('/api/v1/posts/', {**data, field: value}, format='json').status_code, 400)
            self.assertEqual(self.client.patch(self.url, {field: value}, format='json').status_code, 400)
        self.post.refresh_from_db()
        self.assertEqual(self.post.author_id, self.owner.pk)
        self.assertEqual(self.post.status, 'published')

    def test_hidden_posts_never_public(self):
        self.post.status = 'hidden'
        self.post.save()
        for user in [None, self.owner, self.staff]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.client.get('/api/v1/posts/').data['count'], 0)
            self.assertEqual(self.client.get(self.url + 'comments/').status_code, 404)
        with self.assertRaises(PermissionDenied):
            services.create_comment(self.owner, self.post, {'body': 'hidden'})

    def test_comments_exclude_deleted_and_hidden(self):
        for status in ['published', 'hidden', 'deleted']:
            Comment.objects.create(post=self.post, author=self.owner, body=status, status=status)
        response = self.client.get(self.url + 'comments/')
        self.assertEqual([c['body'] for c in response.data['results']], ['published'])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(self.url + 'comments/', {'body': 'Comment'}, format='json').status_code, 201)
        self.assertEqual(self.client.post(self.url + 'comments/', {'body': 'Comment', 'author': self.owner.pk}, format='json').status_code, 400)

    def test_tenth_unique_comment_report_temporarily_hides_comment(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, body='Potentially harmful comment')
        User = get_user_model()
        for index in range(9):
            reporter = User.objects.create_user(username=f'reporter-{index}')
            services.create_report(reporter, self.post, {
                'reason': 'abuse', 'details': 'Please review', 'comment': comment.pk,
            })
        comment.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.PUBLISHED)

        tenth_reporter = User.objects.create_user(username='reporter-9')
        services.create_report(tenth_reporter, self.post, {
            'reason': 'abuse', 'details': 'Please review', 'comment': comment.pk,
        })
        comment.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.HIDDEN)

    def test_repeated_reports_by_one_account_do_not_reach_unique_reporter_threshold(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, body='Repeated reports')
        for _ in range(10):
            services.create_report(self.other, self.post, {
                'reason': 'spam', 'details': 'Please review', 'comment': comment.pk,
            })
        comment.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.PUBLISHED)

    def test_staff_review_can_restore_temporarily_hidden_comment_with_audit(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, body='Hidden for review', status=Comment.Status.HIDDEN)
        with self.assertRaises(PermissionDenied):
            services.moderate_comment(self.other, comment, Comment.Status.PUBLISHED)

        reviewed = services.moderate_comment(self.staff, comment, Comment.Status.PUBLISHED)
        self.assertEqual(reviewed.status, Comment.Status.PUBLISHED)
        event = AuditEvent.objects.get(action='comment.moderate', target_id=str(comment.pk))
        self.assertEqual(event.actor_id, self.staff.pk)
        self.assertEqual(event.metadata, {'previous_status': 'hidden', 'status': 'published'})

    def test_staff_admin_restore_action_restores_comment(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, body='Review complete', status=Comment.Status.HIDDEN)
        request = RequestFactory().post('/admin/community/comment/')
        request.user = self.staff
        comment_admin = CommentAdmin(Comment, admin.site)
        comment_admin.restore_selected(request, Comment.objects.filter(pk=comment.pk))
        comment.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.PUBLISHED)
        self.assertTrue(AuditEvent.objects.filter(action='comment.moderate', actor=self.staff).exists())

    def test_report_private_and_cross_post_mismatch(self):
        other_post = Post.objects.create(author=self.owner, title='Other', body='Body')
        comment = Comment.objects.create(post=other_post, author=self.owner, body='Comment')
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.post(self.url + 'reports/', {'reason': 'privacy', 'details': 'Private information', 'comment': comment.pk}, format='json').status_code, 400)
        response = self.client.post(self.url + 'reports/', {'reason': 'spam', 'details': 'Private detail'}, format='json')
        self.assertEqual(response.status_code, 201)
        report_url = f'/api/v1/reports/{response.data["id"]}/'
        for user in [None, self.owner, self.other]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/v1/reports/').status_code, 403)
            self.assertEqual(self.client.get(report_url).status_code, 403)
            self.assertEqual(self.client.patch(report_url, {'status': 'resolved'}).status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get(report_url).status_code, 200)
        self.assertEqual(self.client.get('/api/v1/reports/').data['count'], 1)
        self.assertEqual(self.client.patch(report_url, {'status': 'open'}).status_code, 400)
        self.assertEqual(self.client.patch(report_url, {'status': 'resolved'}).status_code, 200)
        report = Report.objects.get(pk=response.data['id'])
        self.assertEqual(report.status, 'resolved')
        event = AuditEvent.objects.get(action='report.resolve')
        self.assertEqual(event.actor_id, self.staff.pk)
        self.assertEqual(event.target_id, str(report.pk))
        self.assertEqual(event.metadata, {'previous_status': 'open', 'status': 'resolved'})

    def test_filters_include_common_and_search(self):
        Post.objects.create(author=self.owner, title='Common guide', body='Useful', region='common', category='living')
        Post.objects.create(author=self.owner, title='Phuket', body='Useful', region='phuket', category='travel')
        data = self.client.get('/api/v1/posts/?region=bangkok&category=living&q=guide').data
        self.assertEqual(data['count'], 2)
        self.assertEqual(self.client.get('/api/v1/posts/?region=invalid').status_code, 400)

    def test_service_permissions_and_validation(self):
        for user in [None, self.inactive]:
            with self.assertRaises(PermissionDenied):
                services.create_post(user, {'title': 'Title', 'body': 'Body'})
        with self.assertRaises(PermissionDenied):
            services.update_post(self.other, self.post, {'title': 'Bad'})
        with self.assertRaises(ValidationError):
            services.create_post(self.owner, {'title': 'Title', 'body': 'x' * 6001})
        with self.assertRaises(ValidationError):
            services.create_comment(self.owner, self.post, {'body': 'x' * 3001})
        with self.assertRaises(ValidationError):
            services.create_report(self.owner, self.post, {'reason': 'spam', 'details': 'x' * 2001})
        self.client.force_authenticate(self.inactive)
        self.assertEqual(self.client.post('/api/v1/posts/', {'title': 'x', 'body': 'x'}).status_code, 403)

    def test_pagination_default_and_maximum(self):
        Post.objects.bulk_create([Post(author=self.owner, title=f'Post {i}', body='Body') for i in range(125)])
        response = self.client.get('/api/v1/posts/')
        self.assertEqual(response.data['count'], 126)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(len(self.client.get('/api/v1/posts/?page_size=999').data['results']), 100)

    def test_shared_services_reject_forged_fields(self):
        for data in [{'author': self.other.pk}, {'status': 'hidden'}, {'id': 99}]:
            with self.subTest(data=data):
                with self.assertRaises(ValidationError):
                    services.update_post(self.owner, self.post, data)
        with self.assertRaises(ValidationError):
            services.create_comment(self.owner, self.post, {'body': 'Body', 'status': 'deleted'})
        with self.assertRaises(ValidationError):
            services.create_report(self.owner, self.post, {'reason': 'spam', 'reporter': self.other.pk})
        with self.assertRaises(PermissionDenied):
            services.delete_post(self.other, self.post)

    def test_report_dismissal_and_resolution_payload(self):
        report = services.create_report(self.owner, self.post, {'reason': 'outdated', 'details': 'Outdated information'})
        with self.assertRaises(PermissionDenied):
            services.resolve_report(self.owner, report, {'status': 'dismissed'})
        self.client.force_authenticate(self.staff)
        url = f'/api/v1/reports/{report.pk}/'
        self.assertEqual(self.client.patch(url, {}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'status': 'dismissed', 'reporter': self.other.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {'status': 'dismissed'}, format='json').status_code, 200)
        report.refresh_from_db()
        self.assertEqual(report.status, 'dismissed')
        self.assertEqual(AuditEvent.objects.get(action='report.resolve').metadata['status'], 'dismissed')

    def test_resolved_report_cannot_be_resolved_again(self):
        report = services.create_report(self.owner, self.post, {'reason': 'spam', 'details': 'Repeated review'})
        services.resolve_report(self.staff, report, {'status': Report.Status.RESOLVED})
        with self.assertRaises(ValidationError):
            services.resolve_report(self.staff, report, {'status': Report.Status.DISMISSED})

    def test_report_details_minimum(self):
        self.client.force_authenticate(self.owner)
        for details in [None, '', 'four']:
            data = {'reason': 'spam'}
            if details is not None:
                data['details'] = details
            with self.subTest(details=details):
                self.assertEqual(self.client.post(self.url + 'reports/', data, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.url + 'reports/', {'reason': 'spam', 'details': '12345'}, format='json').status_code, 201)

    def test_report_rejects_hidden_comment(self):
        comment = Comment.objects.create(post=self.post, author=self.owner, body='Hidden', status='hidden')
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(self.url + 'reports/', {'reason': 'spam', 'details': 'Hidden comment', 'comment': comment.pk}).status_code, 400)

    def test_csrf_enforced_for_every_mutation_route(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.staff)
        report = Report.objects.create(reporter=self.owner, post=self.post, reason='spam')
        hidden_post = Post.objects.create(author=self.staff, title='Hidden staff appeal', body='Hidden post for CSRF checks.', status=Post.Status.HIDDEN)
        requests = [
            ('patch', self.url, {'title': 'Changed'}),
            ('delete', self.url, {}),
            ('post', self.url + 'comments/', {'body': 'Comment'}),
            ('post', self.url + 'reports/', {'reason': 'spam'}),
            ('patch', f'/api/v1/reports/{report.pk}/', {'status': 'resolved'}),
            ('post', f'/api/v1/reports/{report.pk}/hide/', {}),
            ('post', '/api/v1/appeals/', {'post': hidden_post.pk, 'details': 'Appeal test detail.'}),
        ]
        for method, url, data in requests:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(client, method)(url, data, format='json').status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, 'published')
        report.refresh_from_db()
        self.assertEqual(report.status, 'open')

    def test_session_csrf_enforced(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post('/api/v1/posts/', {'title': 'X', 'body': 'Y'}).status_code, 403)
        token = _get_new_csrf_string()
        client.cookies['csrftoken'] = token
        self.assertEqual(client.post('/api/v1/posts/', {'title': 'X', 'body': 'Y'}, HTTP_X_CSRFTOKEN=token).status_code, 201)


from django.urls import include, path
urlpatterns = [path('api/v1/', include('community.api'))]
