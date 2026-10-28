from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from . import services
from .models import Comment, FreePost, JobsPost, LivingPost, MarketPost, NoticePost, Post


MODELS = {'notice': NoticePost, 'free': FreePost, 'market': MarketPost,
          'jobs': JobsPost, 'living': LivingPost}


class BoardContentCutoverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='cutover', is_staff=True)

    def test_create_and_partial_update_write_content_for_each_board(self):
        for board, model in MODELS.items():
            with self.subTest(board=board):
                post = services.create_post(self.user, {'category': board, 'title': 'Original title', 'body': 'Original content'})
                self.assertEqual((model.objects.get(pk=post.pk).title, model.objects.get(pk=post.pk).body), ('Original title', 'Original content'))
                services.update_post(self.user, post, {'body': 'Updated content'})
                content = model.objects.get(pk=post.pk)
                self.assertEqual((content.title, content.body), ('Original title', 'Updated content'))
                self.assertTrue(services.visible_posts().filter(pk=post.pk).exists())

    def test_partial_update_and_transfer_preserve_authoritative_content(self):
        for board, model in MODELS.items():
            with self.subTest(board=board):
                post = services.create_post(self.user, {'category': board, 'title': 'Original title', 'body': 'Original content'})
                model.objects.filter(pk=post.pk).update(title='Board title', body='Board body')
                services.update_post(self.user, post, {'body': 'Changed body'})
                row = model.objects.get(pk=post.pk)
                self.assertEqual((row.title, row.body), ('Board title', 'Changed body'))
                target = 'free' if board != 'free' else 'jobs'
                services.update_post(self.user, post, {'category': target})
                row = MODELS[target].objects.get(pk=post.pk)
                self.assertEqual((row.title, row.body), ('Board title', 'Changed body'))

    def test_transfer_preserves_identity_comment_and_old_content(self):
        post = services.create_post(self.user, {'category': 'free', 'title': 'Original title', 'body': 'Original content'})
        comment = Comment.objects.create(post=post, author=self.user, body='Existing comment')
        services.update_post(self.user, post, {'category': 'jobs', 'title': 'New title'})
        self.assertTrue(FreePost.objects.filter(pk=post.pk).exists())
        self.assertEqual(JobsPost.objects.get(pk=post.pk).title, 'New title')
        self.assertEqual(Comment.objects.get(pk=comment.pk).post_id, post.pk)

    def test_content_write_failure_rolls_back_create_and_transfer(self):
        with patch.object(FreePost.objects, 'update_or_create', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                services.create_post(self.user, {'category': 'free', 'title': 'Failure title', 'body': 'Failure content'})
        self.assertFalse(Post.objects.filter(title='Failure title').exists())
        post = services.create_post(self.user, {'category': 'free', 'title': 'Original title', 'body': 'Original content'})
        with patch.object(JobsPost.objects, 'update_or_create', side_effect=RuntimeError('write failed')):
            with self.assertRaises(RuntimeError):
                services.update_post(self.user, post, {'category': 'jobs'})
        post.refresh_from_db()
        self.assertEqual(post.category, 'free')
        self.assertTrue(FreePost.objects.filter(pk=post.pk).exists())
        self.assertFalse(JobsPost.objects.filter(pk=post.pk).exists())
