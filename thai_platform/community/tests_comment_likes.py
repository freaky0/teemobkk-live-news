from django.contrib.auth import get_user_model
from django.test import TestCase, Client, TransactionTestCase
from django.db import IntegrityError, transaction, connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from .models import Comment, CommentLike, Post


class CommentLikeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='likes-user')
        self.post = Post.objects.create(author=self.user, title='Question', body='Body')
        self.comment = Comment.objects.create(post=self.post, author=self.user, body='Answer')
        self.client.force_login(self.user)

    def test_member_can_like_and_unlike_comment(self):
        url = reverse('comment-like', args=[self.post.pk, self.comment.pk])
        response = self.client.post(url, {'active': 'true'})
        self.assertEqual(response.status_code, 302)
        page = self.client.get(reverse('post-detail', args=[self.post.pk]))
        self.assertContains(page, '좋아요 1')
        self.assertContains(page, 'aria-pressed="true"')
        self.assertEqual(self.client.post(url, {'active': 'false'}).status_code, 302)
        self.assertContains(self.client.get(reverse('post-detail', args=[self.post.pk])), '좋아요 0')

    def test_reply_independent_users_repeated_requests_and_forgery(self):
        reply = Comment.objects.create(post=self.post, parent=self.comment, author=self.user, body='Reply')
        other = get_user_model().objects.create_user(username='other-like-user')
        url = reverse('comment-like', args=[self.post.pk, reply.pk])
        for _ in range(2):
            self.assertEqual(self.client.post(url, {'active': 'true'}).status_code, 302)
        self.client.force_login(other)
        self.assertEqual(self.client.post(url, {'active': 'true'}).status_code, 302)
        self.assertContains(self.client.get(reverse('post-detail', args=[self.post.pk])), '좋아요 2')
        self.assertEqual(self.client.post(url, {'active': 'false', 'user': self.user.pk}).status_code, 400)
        self.assertEqual(self.client.post(url, {'active': 'false'}).status_code, 302)
        self.assertTrue(CommentLike.objects.filter(comment=reply, user=self.user).exists())
        self.assertEqual(CommentLike.objects.filter(comment=reply).count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CommentLike.objects.create(comment=reply, user=self.user)

    def test_visibility_membership_and_csrf(self):
        url = reverse('comment-like', args=[self.post.pk, self.comment.pk])
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(url, {'active': 'true'}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(url, {'active': 'true'}).status_code, 403)
        self.client.force_login(self.user)
        other_post = Post.objects.create(author=self.user, title='Other', body='Body')
        self.assertEqual(self.client.post(reverse('comment-like', args=[other_post.pk, self.comment.pk]), {'active': 'true'}).status_code, 404)
        reply = Comment.objects.create(post=self.post, parent=self.comment, author=self.user, body='Reply')
        reply_url = reverse('comment-like', args=[self.post.pk, reply.pk])
        for state in ('hidden', 'deleted'):
            self.comment.status = state
            self.comment.save()
            self.assertEqual(self.client.post(url, {'active': 'true'}).status_code, 404)
            self.assertEqual(self.client.post(reply_url, {'active': 'true'}).status_code, 404)
        self.comment.status = 'published'
        self.comment.save()
        for state in ('hidden', 'deleted'):
            self.post.status = state
            self.post.save()
            self.assertEqual(self.client.post(url, {'active': 'true'}).status_code, 404)
        self.assertFalse(CommentLike.objects.exists())

    def test_detail_query_count_does_not_grow_per_comment(self):
        path = reverse('post-detail', args=[self.post.pk])
        with CaptureQueriesContext(connection) as before:
            self.client.get(path)
        for index in range(10):
            parent = Comment.objects.create(post=self.post, author=self.user, body=f'Answer {index}')
            Comment.objects.create(post=self.post, author=self.user, parent=parent, body='Reply')
        with CaptureQueriesContext(connection) as after:
            response = self.client.get(path)
        self.assertEqual(len(before), len(after))
        self.assertIn('no-store', response['Cache-Control'])

    def test_anonymous_login_link_retains_subpath(self):
        from django.urls import set_script_prefix, clear_script_prefix
        self.client.logout()
        try:
            set_script_prefix('/post/')
            response = self.client.get(f'/community/{self.post.pk}/', SCRIPT_NAME='/post')
            self.assertContains(response, f'/post/accounts/login/?next=/post/community/{self.post.pk}/')
        finally:
            clear_script_prefix()


class CommentLikeMigrationTests(TransactionTestCase):
    def test_existing_comments_survive_migration(self):
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('community', '0020_post_is_pinned_db_default')])
            old = executor.loader.project_state([('community', '0020_post_is_pinned_db_default')]).apps
            user = old.get_model('auth', 'User').objects.create(username='legacy-like')
            post = old.get_model('community', 'Post').objects.create(author_id=user.pk, title='Old', body='Body')
            comment = old.get_model('community', 'Comment').objects.create(post_id=post.pk, author_id=user.pk, body='Existing')
            MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(Comment.objects.get(pk=comment.pk).body, 'Existing')
            self.assertFalse(CommentLike.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
