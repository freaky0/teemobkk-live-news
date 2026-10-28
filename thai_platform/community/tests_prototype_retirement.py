from django.contrib.auth import get_user_model
from django.test import TestCase

from . import services
from .board_versions import board_data_version
from .models import FreePost, JobsPost


class PrototypeRetirementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='prototype-owner')
        self.client.force_login(self.user)
        self.post = services.create_post(self.user, {'category': 'free', 'title': 'Private old title', 'body': 'Private old body'})

    def test_retired_routes_cannot_expose_or_modify_transferred_content(self):
        services.update_post(self.user, self.post, {'category': 'jobs', 'title': 'New title'})
        urls = ['/community/independent-free/', f'/community/independent-free/{self.post.pk}/',
                f'/community/independent-free/{self.post.pk}/edit/', '/community/independent-free/new/']
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {'title': 'Forged title', 'body': 'Forged body'}).status_code, 404)
        self.assertEqual(FreePost.objects.get(pk=self.post.pk).title, 'Private old title')
        self.assertEqual(JobsPost.objects.get(pk=self.post.pk).title, 'New title')

    def test_prototype_cannot_bypass_versioned_actual_write(self):
        version = board_data_version(self.post)
        url = f'/community/independent-free/{self.post.pk}/edit/'
        self.assertEqual(self.client.post(url, {'title': 'Changed title', 'body': 'Changed body'}).status_code, 404)
        services.update_post(self.user, self.post, {'title': 'Real newer title'})
        response = self.client.patch(f'/api/v1/posts/{self.post.pk}/', {'title': 'Stale title', 'board_data_version': version}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(FreePost.objects.get(pk=self.post.pk).title, 'Real newer title')
