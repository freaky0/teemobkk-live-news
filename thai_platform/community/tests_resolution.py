"""Author-only question resolution, shared by web and API."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient
from .models import AuditEvent, Post


class ResolutionTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username='resolution-owner')
        self.other = users.objects.create_user(username='resolution-other')
        self.staff = users.objects.create_user(username='resolution-staff', is_staff=True)
        self.inactive = users.objects.create_user(username='resolution-inactive', is_active=False)
        self.post = Post.objects.create(author=self.owner, title='해결 상태를 검사하는 질문', body='개인정보 없는 테스트 질문입니다.')
        self.api = APIClient()
        self.api_url = f'/api/v1/posts/{self.post.pk}/resolution/'
        self.web_url = f'/community/{self.post.pk}/resolution/'

    def test_admin_cannot_forge_resolution(self):
        self.staff.is_superuser = True
        self.staff.save()
        self.client.force_login(self.staff)
        response = self.client.post(f'/admin/community/post/{self.post.pk}/change/', {
            'title': self.post.title, 'body': self.post.body, 'region': self.post.region,
            'category': self.post.category, 'status': self.post.status,
            'resolution': 'resolved', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.resolution, 'unresolved')

    def test_api_csrf_and_incomplete_onboarding(self):
        from members.models import MemberProfile
        csrf = APIClient(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.api_url, {'resolution': 'resolved'}, format='json').status_code, 403)
        MemberProfile.objects.create(user=self.owner, email_key='resolution@example.test')
        self.api.force_authenticate(user=self.owner)
        self.assertEqual(self.api.post(self.api_url, {'resolution': 'resolved'}, format='json').status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.web_url, {'resolution': 'resolved'}).status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.resolution, 'unresolved')

    def test_default_and_public_read(self):
        self.assertEqual(self.post.resolution, 'unresolved')
        self.assertEqual(self.api.get(f'/api/v1/posts/{self.post.pk}/').data['resolution'], 'unresolved')
        for url in ['/community/', f'/community/{self.post.pk}/']:
            self.assertContains(self.client.get(url), '미해결')

    def test_api_author_only_including_staff(self):
        for user in [None, self.other, self.staff, self.inactive]:
            self.api.force_authenticate(user=user)
            self.assertEqual(self.api.post(self.api_url, {'resolution': 'resolved'}, format='json').status_code, 403)
        self.post.refresh_from_db()
        self.assertEqual(self.post.resolution, 'unresolved')
        self.assertEqual(AuditEvent.objects.count(), 0)
        self.api.force_authenticate(user=self.owner)
        self.assertEqual(self.api.post(self.api_url, {'resolution': 'resolved'}, format='json').status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.resolution, 'resolved')
        self.assertEqual(AuditEvent.objects.get().action, 'post.resolution')
        self.assertEqual(AuditEvent.objects.get().metadata, {'previous_resolution': 'unresolved', 'resolution': 'resolved'})
        self.assertEqual(self.api.post(self.api_url, {'resolution': 'resolved'}, format='json').status_code, 200)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(self.api.post(self.api_url, {'resolution': 'unresolved'}, format='json').status_code, 200)
        self.assertEqual(AuditEvent.objects.count(), 2)

    def test_strict_validation_and_no_generic_write_bypass(self):
        self.api.force_authenticate(user=self.owner)
        for data in [{}, {'resolution': 'bogus'}, {'resolution': True}, {'resolution': 'resolved', 'author': self.other.pk}]:
            self.assertEqual(self.api.post(self.api_url, data, format='json').status_code, 400)
        self.assertEqual(self.api.patch(f'/api/v1/posts/{self.post.pk}/', {'resolution': 'resolved'}, format='json').status_code, 400)
        self.assertEqual(self.api.post('/api/v1/posts/', {'title': 'Test', 'body': 'Test', 'resolution': 'resolved'}, format='json').status_code, 400)
        self.assertEqual(self.api.get(self.api_url).status_code, 405)
        self.post.refresh_from_db()
        self.assertEqual(self.post.resolution, 'unresolved')
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_hidden_deleted_and_missing_are_not_exposed(self):
        self.api.force_authenticate(user=self.owner)
        self.client.force_login(self.owner)
        for state in ['hidden', 'deleted']:
            self.post.status = state
            self.post.save()
            self.assertEqual(self.api.post(self.api_url, {'resolution': 'resolved'}, format='json').status_code, 404)
            self.assertEqual(self.client.post(self.web_url, {'resolution': 'resolved'}).status_code, 404)
        self.assertEqual(self.api.post('/api/v1/posts/999999/resolution/', {'resolution': 'resolved'}, format='json').status_code, 404)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_web_permissions_buttons_and_csrf(self):
        self.assertEqual(self.client.post(self.web_url, {'resolution': 'resolved'}).status_code, 403)
        for user in [self.other, self.staff]:
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.web_url, {'resolution': 'resolved'}).status_code, 403)
            self.assertNotContains(self.client.get(f'/community/{self.post.pk}/'), '해결로 표시')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(f'/community/{self.post.pk}/'), '해결로 표시')
        self.assertEqual(self.client.get(self.web_url).status_code, 405)
        self.assertEqual(self.client.post(self.web_url, {'resolution': 'invalid'}).status_code, 400)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(self.web_url, {'resolution': 'resolved'}).status_code, 403)
        csrf.get(f'/community/{self.post.pk}/')
        result = csrf.post(self.web_url, {'resolution': 'resolved', 'csrfmiddlewaretoken': csrf.cookies['csrftoken'].value})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, f'/community/{self.post.pk}/')
        self.assertContains(self.client.get(f'/community/{self.post.pk}/'), '미해결로 되돌리기')

    def test_filters_keep_context_and_show_matching_states(self):
        self.post.resolution = 'resolved'
        self.post.save()
        Post.objects.create(author=self.owner, title='다른 미해결 질문', body='Test')
        response = self.client.get('/community/?resolution=resolved&region=bangkok&q=해결')
        self.assertContains(response, self.post.title)
        self.assertNotContains(response, '다른 미해결 질문')
        self.assertIn('resolution=resolved', response.context['list_query'])
        self.assertContains(response, '작성자 해결 확인')
        self.assertEqual(self.api.get('/api/v1/posts/?resolution=resolved').data['count'], 1)
        self.assertEqual(self.api.get('/api/v1/posts/?resolution=bogus').status_code, 400)
        self.assertNotContains(self.client.get('/community/?resolution=unresolved'), self.post.title)


class ResolutionMigrationTests(TransactionTestCase):
    def test_existing_posts_survive_forward_and_reverse_migration(self):
        old = [('community', '0001_initial')]
        new = [('community', '0002_post_resolution')]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = get_user_model().objects.create_user(username='migration-owner')
            post = apps.get_model('community', 'Post').objects.create(
                author_id=user.pk, title='기존 질문 보존 검사', body='보존해야 할 원문', status='hidden')
            executor = MigrationExecutor(connection)
            executor.migrate(new)
            current = executor.loader.project_state(new).apps.get_model('community', 'Post').objects.get(pk=post.pk)
            self.assertEqual(current.resolution, 'unresolved')
            self.assertEqual(current.body, '보존해야 할 원문')
            self.assertEqual(current.status, 'hidden')
            executor = MigrationExecutor(connection)
            executor.migrate(old)
            original = executor.loader.project_state(old).apps.get_model('community', 'Post').objects.get(pk=post.pk)
            self.assertEqual(original.body, '보존해야 할 원문')
            self.assertEqual(original.author_id, user.pk)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
