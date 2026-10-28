from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from . import services
from .models import BoardCategory, Post
from .serializers import PostSerializer


class BoardCategoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='board-category-writer')
        self.free = BoardCategory.objects.create(board='free', slug='general', name='Free general')
        self.market = BoardCategory.objects.create(board='market', slug='general', name='Market general')

    def test_post_category_is_scoped_and_returned_by_api_serializer(self):
        post = services.create_post(self.user, {'title': 'Free category post', 'body': 'A sufficiently long post body.', 'category': 'free', 'board_category': self.free.pk})
        self.assertEqual(Post.objects.get(pk=post.pk).board_category, self.free)
        self.assertEqual(PostSerializer(post).data['board_category'], self.free.pk)
        with self.assertRaises(ValidationError):
            services.create_post(self.user, {'title': 'Wrong category post', 'body': 'A sufficiently long post body.', 'category': 'free', 'board_category': self.market.pk})

    def test_board_change_cannot_leave_a_mismatched_category(self):
        post = services.create_post(self.user, {'title': 'Changing board post', 'body': 'A sufficiently long post body.', 'category': 'free', 'board_category': self.free.pk})
        with self.assertRaises(ValidationError):
            services.update_post(self.user, post, {'category': 'market'})
        post.refresh_from_db()
        self.assertEqual((post.category, post.board_category), ('free', self.free))
        post = services.update_post(self.user, post, {'category': 'market', 'board_category': self.market.pk})
        self.assertEqual((post.category, post.board_category), ('market', self.market))

    def test_api_create_detail_and_update_enforce_category_board(self):
        self.client.force_login(self.user)
        payload = {'title': 'API board category', 'body': 'A sufficiently long post body.', 'category': 'free', 'board_category': self.free.pk}
        response = self.client.post('/api/v1/posts/', payload, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        pk = response.json()['id']
        self.assertEqual(self.client.get(f'/api/v1/posts/{pk}/').json()['board_category'], self.free.pk)
        response = self.client.patch(f'/api/v1/posts/{pk}/', {'category': 'market'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Post.objects.get(pk=pk).board_category_id, self.free.pk)

    def test_staff_can_manage_categories_but_not_move_existing_ones(self):
        staff = get_user_model().objects.create_superuser(username='category-admin', email='admin@example.test', password='test-password')
        self.client.force_login(staff)
        response = self.client.get('/admin/community/boardcategory/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f'/admin/community/boardcategory/{self.free.pk}/change/', {'board': 'market', 'slug': self.free.slug, 'name': self.free.name})
        self.free.refresh_from_db()
        self.assertEqual(self.free.board, 'free')

    def test_api_discovers_board_categories_and_filters_posts(self):
        free_post = services.create_post(self.user, {'title': 'Free filtered post', 'body': 'A sufficiently long post body.', 'category': 'free', 'board_category': self.free.pk})
        services.create_post(self.user, {'title': 'Market filtered post', 'body': 'A sufficiently long post body.', 'category': 'market', 'board_category': self.market.pk})
        response = self.client.get('/api/v1/board-categories/?board=free')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()['results']], [self.free.pk])
        response = self.client.get(f'/api/v1/posts/?board_category={self.free.pk}')
        self.assertEqual([item['id'] for item in response.json()['results']], [free_post.pk])
        self.assertEqual(self.client.get('/api/v1/posts/?board_category=bad').status_code, 400)
