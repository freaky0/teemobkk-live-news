from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient
from .models import Comment, Notification, Post


class ReplyTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reply-user')
        self.post = Post.objects.create(author=self.user, title='Question', body='Question body')
        self.answer = Comment.objects.create(post=self.post, author=self.user, body='Existing answer')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_deleting_answer_cannot_delete_another_members_reply(self):
        from django.db.models import RestrictedError
        other = get_user_model().objects.create_user(username='other-reply-author')
        reply = Comment.objects.create(post=self.post, author=other, parent=self.answer, body='Preserve my reply')
        with self.assertRaises(RestrictedError):
            self.answer.delete()
        self.assertTrue(Comment.objects.filter(pk=reply.pk).exists())

    def test_create_reply_to_existing_answer(self):
        response = self.api.post(f'/api/v1/posts/{self.post.pk}/comments/', {'body': 'Reply to answer', 'parent': self.answer.pk}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['parent'], self.answer.pk)
        self.assertEqual(Comment.objects.get(pk=response.data['id']).parent_id, self.answer.pk)
        self.assertContains(self.client.get(f'/community/{self.post.pk}/'), 'Reply to answer')

    def test_rejects_other_post_hidden_deleted_nested_and_missing_parent(self):
        other = Post.objects.create(author=self.user, title='Other', body='Other body')
        cross = Comment.objects.create(post=other, author=self.user, body='Foreign answer')
        hidden = Comment.objects.create(post=self.post, author=self.user, body='Hidden answer', status='hidden')
        deleted = Comment.objects.create(post=self.post, author=self.user, body='Deleted answer', status='deleted')
        nested = Comment.objects.create(post=self.post, author=self.user, body='Existing reply', parent=self.answer)
        for parent in (cross.pk, hidden.pk, deleted.pk, nested.pk, 999999):
            with self.subTest(parent=parent):
                response = self.api.post(f'/api/v1/posts/{self.post.pk}/comments/', {'body': 'Invalid reply', 'parent': parent}, format='json')
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Comment.objects.count(), 5)

    def test_guest_and_incomplete_member_cannot_reply(self):
        url = f'/api/v1/posts/{self.post.pk}/comments/'
        self.api.force_authenticate(None)
        self.assertEqual(self.api.post(url, {'body': 'Guest reply', 'parent': self.answer.pk}, format='json').status_code, 403)
        from members.models import MemberProfile
        MemberProfile.objects.create(user=self.user, email_key='reply@example.invalid')
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.post(url, {'body': 'Member reply', 'parent': self.answer.pk}, format='json').status_code, 403)

    def test_inactive_user_and_nonpublic_post_cannot_accept_replies(self):
        url = f'/api/v1/posts/{self.post.pk}/comments/'
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.api.post(url, {'body': 'Inactive reply', 'parent': self.answer.pk}, format='json').status_code, 403)
        self.user.is_active = True
        self.user.save()
        for state in ('hidden', 'deleted'):
            self.post.status = state
            self.post.save()
            self.assertIn(self.api.post(url, {'body': 'Unavailable reply', 'parent': self.answer.pk}, format='json').status_code, (403, 404))

    def test_web_rejects_foreign_post_parent(self):
        from django.urls import reverse
        other = Post.objects.create(author=self.user, title='Other', body='Other body')
        foreign = Comment.objects.create(post=other, author=self.user, body='Foreign answer')
        self.client.force_login(self.user)
        response = self.client.post(reverse('comment-create', args=[self.post.pk]), {'body': 'Forged reply', 'parent': foreign.pk})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Comment.objects.filter(body='Forged reply').exists())

    def test_hidden_parent_hides_replies_and_cannot_accept_new_ones(self):
        reply = Comment.objects.create(post=self.post, author=self.user, parent=self.answer, body='Private hidden thread')
        self.answer.status = 'hidden'
        self.answer.save()
        self.assertNotContains(self.client.get(f'/community/{self.post.pk}/'), reply.body)
        response = self.api.get(f'/api/v1/posts/{self.post.pk}/comments/')
        self.assertNotIn(reply.pk, [item['id'] for item in response.data['results']])
        self.assertEqual(self.api.post(f'/api/v1/posts/{self.post.pk}/comments/', {'body': 'Another reply', 'parent': self.answer.pk}, format='json').status_code, 400)

    def test_web_reply_csrf_and_notification_preserved(self):
        other = get_user_model().objects.create_user(username='reply-other')
        client = Client(enforce_csrf_checks=True)
        client.force_login(other)
        from django.urls import reverse
        url = reverse('comment-create', args=[self.post.pk])
        self.assertEqual(client.post(url, {'body': 'Web reply body', 'parent': self.answer.pk}).status_code, 403)
        page = client.get(f'/community/{self.post.pk}/')
        self.assertContains(page, f'for="reply-{self.answer.pk}"')
        response = client.post(url, {'body': 'Web reply body', 'parent': self.answer.pk, 'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        reply = Comment.objects.get(body='Web reply body')
        self.assertEqual(reply.parent_id, self.answer.pk)
        self.assertTrue(Notification.objects.filter(recipient=self.user, comment=reply, kind=Notification.Kind.REPLY).exists())


class ReplyMigrationTests(TransactionTestCase):
    def test_existing_answers_and_notifications_survive_nullable_migration(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('community', '0012_report_closed_at')])
            old = executor.loader.project_state([('community', '0012_report_closed_at')]).apps
            user = old.get_model('auth', 'User').objects.create(username='migration-reply')
            post = old.get_model('community', 'Post').objects.create(author_id=user.pk, title='Legacy', body='Body')
            answer = old.get_model('community', 'Comment').objects.create(post_id=post.pk, author_id=user.pk, body='Old answer')
            note = old.get_model('community', 'Notification').objects.create(recipient_id=user.pk, post_id=post.pk, comment_id=answer.pk, kind='reply')
            executor = MigrationExecutor(connection)
            executor.migrate(leaves)
            self.assertIsNone(Comment.objects.get(pk=answer.pk).parent_id)
            self.assertEqual(Notification.objects.get(pk=note.pk).comment_id, answer.pk)
        finally:
            MigrationExecutor(connection).migrate(leaves)
