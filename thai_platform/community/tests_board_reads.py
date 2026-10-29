from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import FreePost, JobsPost, LivingPost, MarketPost, NoticePost, Post, Comment


class BoardReadTests(TestCase):
    def test_web_api_search_and_related_content_use_board_rows(self):
        user = get_user_model().objects.create_user(username='reader')
        for category, model in [('notice', NoticePost), ('free', FreePost), ('market', MarketPost), ('jobs', JobsPost), ('living', LivingPost)]:
            post = Post.objects.create(author=user, category=category, title='stale legacy', body='old legacy body')
            model.objects.create(post=post, title=f'Fresh {category}', body='distinctive body')
            Comment.objects.create(post=post, author=user, body='comment')
            self.assertEqual(Comment.objects.get(post=post).post.display_title, f'Fresh {category}')
            response = self.client.get(f'/api/v1/posts/{post.pk}/')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['title'], f'Fresh {category}')
            self.assertContains(self.client.get(f'/community/{post.pk}/'), f'Fresh {category}')
        found = self.client.get('/api/v1/posts/', {'q': 'distinctive', 'page_size': 2}).json()
        self.assertEqual(found['count'], 5)
        self.assertEqual(len(found['results']), 2)
        self.assertEqual(self.client.get('/api/v1/posts/', {'q': 'stale legacy'}).json()['count'], 0)
        self.assertContains(self.client.get('/community/', {'q': 'distinctive'}), 'Fresh free')
