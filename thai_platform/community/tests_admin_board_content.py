from django.contrib.auth import get_user_model
from django.test import TestCase

from .admin import PostAdmin
from . import services
from .models import Post


class AdminBoardContentTests(TestCase):
    def test_admin_displays_and_searches_authoritative_content_only(self):
        admin = get_user_model().objects.create_superuser('admin', 'admin@example.com', 'password')
        post = services.create_post(admin, {'category': 'free', 'title': 'Fresh board title', 'body': 'Fresh board body'})
        Post.objects.filter(pk=post.pk).update(title='stale secret title', body='stale secret body')
        self.client.force_login(admin)
        for url in ('/admin/community/post/', f'/admin/community/post/{post.pk}/change/'):
            response = self.client.get(url)
            self.assertContains(response, 'Fresh board title')
            self.assertNotContains(response, 'stale secret title')
        self.assertContains(self.client.get(f'/admin/community/post/{post.pk}/change/'), 'Fresh board body')
        self.assertContains(self.client.get('/admin/community/post/', {'q': 'Fresh board body'}), 'Fresh board title')
        self.assertNotContains(self.client.get('/admin/community/post/', {'q': 'stale secret'}), 'Fresh board title')
        self.assertEqual(self.client.post(f'/admin/community/post/{post.pk}/change/', {}).status_code, 403)
        self.assertFalse(PostAdmin.search_fields)
