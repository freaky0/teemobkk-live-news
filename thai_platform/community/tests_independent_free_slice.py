from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import FreePost, Post


class IndependentFreeSliceTests(TestCase):
    def test_web_create_list_detail_use_independent_content(self):
        user = get_user_model().objects.create_user(username='slice-writer')
        self.client.force_login(user)
        response = self.client.post('/community/independent-free/new/', {
            'title': 'Independent free title', 'body': 'A sufficiently long independent body.',
        })
        self.assertEqual(response.status_code, 302)
        entry = FreePost.objects.get(title='Independent free title')
        self.assertNotEqual(entry.post.title, entry.title)
        self.assertContains(self.client.get('/community/independent-free/'), entry.title)
        self.assertContains(self.client.get(response['Location']), entry.body)
        entry.title = 'Authoritative changed title'
        entry.save()
        self.assertContains(self.client.get('/community/independent-free/'), entry.title)
        self.assertContains(self.client.get(response['Location']), entry.title)

    def test_owner_can_edit_independent_content_but_other_users_cannot(self):
        owner = get_user_model().objects.create_user(username='owner')
        other = get_user_model().objects.create_user(username='other')
        identity = Post.objects.create(author=owner, category='free', title='', body='')
        entry = FreePost.objects.create(post=identity, title='Original title', body='Original body')
        self.client.force_login(other)
        url = f'/community/independent-free/{entry.pk}/edit/'
        self.assertEqual(self.client.post(url, {'title': 'Forged', 'body': 'Forged body'}).status_code, 403)
        self.client.force_login(owner)
        self.assertEqual(self.client.post(url, {'title': 'Edited title', 'body': 'Edited body'}).status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.title, 'Edited title')
        self.assertContains(self.client.get(f'/community/independent-free/{entry.pk}/'), 'Edited body')
