from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import Post


class PinningTests(TestCase):
    def test_staff_can_create_pinned_notice_and_list_it_first(self):
        staff = get_user_model().objects.create_user(username='staff', is_staff=True)
        self.client.force_login(staff)
        response = self.client.post('/api/v1/posts/', {'title': 'Pinned notice', 'body': 'Notice body', 'category': 'notice', 'is_pinned': True}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['is_pinned'])
        Post.objects.create(author=staff, title='Newer post', body='Body', category='free')
        self.assertEqual(self.client.get('/api/v1/posts/').json()['results'][0]['title'], 'Pinned notice')
