from django.contrib.auth import get_user_model
from django.test import TestCase

from . import services
from .models import BoardCategory, Post


class WebBoardCategoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='category-web', is_staff=True)
        self.client.force_login(self.user)
        self.categories = {board: BoardCategory.objects.create(board=board, slug='general', name=f'{board} category') for board in ('notice', 'free', 'market', 'jobs', 'living')}

    def test_create_edit_and_filter_each_board(self):
        for board, subcategory in self.categories.items():
            with self.subTest(board=board):
                response = self.client.get('/community/new/', {'category': board})
                self.assertContains(response, subcategory.name)
                payload = {'title': f'Title for {board}', 'body': 'A sufficiently long community post body.', 'region': 'common', 'category': board, 'board_category': subcategory.pk, 'privacy': 'on'}
                response = self.client.post('/community/new/', payload)
                self.assertEqual(response.status_code, 302, response.content)
                post = services.search_posts(Post.objects.all(), payload['title']).get(category=board)
                self.assertEqual(post.board_category_id, subcategory.pk)
                response = self.client.get(f'/community/{post.pk}/edit/')
                self.assertEqual(str(response.context['form']['board_category'].value()), str(subcategory.pk))
                payload['title'] = f'Edited title for {board}'
                response = self.client.post(f'/community/{post.pk}/edit/', payload)
                self.assertEqual(response.status_code, 302, response.content)
                post.refresh_from_db()
                self.assertEqual(post.board_category_id, subcategory.pk)
                response = self.client.get('/community/', {'category': board, 'board_category': subcategory.pk})
                self.assertContains(response, payload['title'])
                self.assertContains(response, subcategory.name)

    def test_wrong_board_category_rejected_and_filter_is_scoped(self):
        payload = {'title': 'Wrong board category', 'body': 'A sufficiently long community post body.', 'region': 'common', 'category': 'free', 'board_category': self.categories['market'].pk, 'privacy': 'on'}
        response = self.client.post('/community/new/', payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(Post.objects.filter(title=payload['title']).exists())
        services.create_post(self.user, {k: v for k, v in {**payload, 'board_category': self.categories['free'].pk}.items() if k != 'privacy'})
        response = self.client.get('/community/', {'category': 'free', 'board_category': self.categories['market'].pk})
        self.assertNotContains(response, payload['title'])
        self.assertEqual(self.client.get('/community/', {'category': 'free', 'board_category': '9' * 100}).status_code, 200)
