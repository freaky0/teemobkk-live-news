from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from .models import AuditEvent, Comment, Post


from .test_board_fixtures import fixture_post

class OperatorPostTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user(username='author')
        self.other = User.objects.create_user(username='other')
        self.staff = User.objects.create_user(username='staff', is_staff=True)
        self.moderator = User.objects.create_user(username='moderator')
        self.moderator.groups.add(Group.objects.get_or_create(name='Report moderators')[0])
        self.inactive = User.objects.create_user(username='inactive', is_staff=True, is_active=False)
        self.operator = User.objects.create_superuser(username='operator', email='op@example.test', password='test-only')
        self.post = fixture_post(author=self.author, title='Old unique post', body='legacy body')
        self.comment = Comment.objects.create(author=self.other, post=self.post, body='preserved answer')
        self.url = f'/community/{self.post.pk}/operator/'

    def test_ordinary_staff_can_see_and_use_operator_controls(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(f'/community/{self.post.pk}/'), '운영자 숨김')
        self.assertContains(self.client.get('/community/'), '숨긴 게시글 관리')
        self.assertEqual(self.client.post(self.url, {'action': 'hide'}).status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.HIDDEN)
        self.assertTrue(AuditEvent.objects.filter(actor=self.staff, action='content.hide', target_id=str(self.post.pk)).exists())
        self.assertContains(self.client.get('/community/operator/hidden/'), self.post.title)
        self.assertEqual(self.client.post(self.url, {'action': 'restore'}).status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(actor=self.staff, action='content.restore', target_id=str(self.post.pk)).exists())
        self.assertEqual(self.client.get(f'/community/{self.post.pk}/operator/delete/').status_code, 200)
        self.assertEqual(self.client.post(self.url, {'action': 'delete', 'confirm': 'yes'}).status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.DELETED)
        self.assertTrue(AuditEvent.objects.filter(actor=self.staff, action='post.delete', target_id=str(self.post.pk)).exists())

    def test_operator_hide_restore_and_public_visibility(self):
        self.client.force_login(self.operator)
        self.assertContains(self.client.get(f'/community/{self.post.pk}/'), '운영자 숨김')
        self.assertContains(self.client.get('/community/'), '숨긴 게시글 관리')
        self.assertEqual(self.client.post(self.url, {'action': 'hide'}).status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.HIDDEN)
        self.assertTrue(AuditEvent.objects.filter(actor=self.operator, action='content.hide', target_id=str(self.post.pk)).exists())
        self.assertContains(self.client.get('/community/operator/hidden/'), self.post.title)
        self.assertNotContains(self.client.get('/community/?q=Old'), self.post.title)
        self.assertNotContains(self.client.get('/api/v1/posts/?q=Old'), self.post.title)
        self.assertEqual(self.client.get(f'/api/v1/posts/{self.post.pk}/').status_code, 404)
        self.assertEqual(self.client.post(self.url, {'action': 'restore'}).status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.PUBLISHED)
        self.assertEqual(self.comment.body, 'preserved answer')
        self.assertTrue(AuditEvent.objects.filter(actor=self.operator, action='content.restore', target_id=str(self.post.pk)).exists())

    def test_forged_requests_and_csrf(self):
        for user in (None, self.author, self.other, self.moderator, self.inactive):
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            self.assertNotContains(self.client.get(f'/community/{self.post.pk}/'), '운영자 숨김')
            self.assertNotContains(self.client.get('/community/'), '숨긴 게시글 관리')
            self.assertIn(self.client.get(f'/community/{self.post.pk}/operator/delete/').status_code, (403, 404))
            for action in ('hide', 'restore', 'delete'):
                self.assertIn(self.client.post(self.url, {'action': action, 'confirm': 'yes'}).status_code, (403, 404))
            self.assertIn(self.client.get('/community/operator/hidden/').status_code, (403, 404))
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.PUBLISHED)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.staff)
        self.assertEqual(csrf.post(self.url, {'action': 'hide'}).status_code, 403)
        self.assertEqual(csrf.get(self.url).status_code, 405)

    def test_delete_is_confirmed_soft_delete_and_cannot_restore(self):
        self.client.force_login(self.operator)
        self.assertEqual(self.client.post(self.url, {'action': 'delete'}).status_code, 400)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.PUBLISHED)
        self.assertEqual(self.client.post(self.url, {'action': 'delete', 'confirm': 'yes'}).status_code, 302)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.DELETED)
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(actor=self.operator, action='post.delete', target_id=str(self.post.pk)).exists())
        self.assertIn(self.client.post(self.url, {'action': 'restore'}).status_code, (400, 404))
