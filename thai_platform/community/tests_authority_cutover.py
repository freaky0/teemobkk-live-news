from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from . import services
from .models import Post, FreePost, JobsPost, Comment


class AuthorityCutoverTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='authority', is_staff=True)

    def test_missing_board_never_exposes_or_searches_legacy_content_and_cannot_be_updated(self):
        post = Post.objects.create(author=self.user, category='free', title='Secret stale title', body='Secret stale body')
        self.assertNotIn('Secret stale', post.display_title + post.display_body)
        self.assertFalse(services.search_posts(Post.objects.all(), 'Secret stale').exists())
        self.assertNotContains(self.client.get(f'/community/{post.pk}/'), 'Secret stale')
        self.assertNotIn('Secret stale', str(self.client.get(f'/api/v1/posts/{post.pk}/').content))
        with self.assertRaises(ValidationError):
            services.update_post(self.user, post, {'body': 'New content'})
        self.assertFalse(FreePost.objects.filter(pk=post.pk).exists())

    def test_board_writes_are_not_mirrored_and_transfer_keeps_identity(self):
        post = services.create_post(self.user, {'category': 'free', 'title': 'First title', 'body': 'First body long enough'})
        post.refresh_from_db()
        self.assertNotEqual(post.title, 'First title')
        Comment.objects.create(post=post, author=self.user, body='A comment')
        FreePost.objects.filter(pk=post.pk).update(title='Fresh title', body='Fresh body')
        post = services.update_post(self.user, post, {'category': 'jobs', 'body': 'Updated body long enough'})
        self.assertEqual((JobsPost.objects.get(pk=post.pk).title, JobsPost.objects.get(pk=post.pk).body), ('Fresh title', 'Updated body long enough'))
        self.assertEqual(Comment.objects.get(post_id=post.pk).post_id, post.pk)
        self.assertNotEqual(Post.objects.get(pk=post.pk).title, 'Fresh title')

    def test_legacy_board_remains_searchable_and_can_move_to_independent_board(self):
        post = Post.objects.create(author=self.user, category='questions', title='Legacy title', body='Legacy body')
        self.assertTrue(services.search_posts(Post.objects.all(), 'Legacy title').filter(pk=post.pk).exists())
        post = services.update_post(self.user, post, {'category': 'free'})
        self.assertEqual(FreePost.objects.get(pk=post.pk).title, 'Legacy title')
