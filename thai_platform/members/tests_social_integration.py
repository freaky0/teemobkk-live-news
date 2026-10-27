from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from .models import MemberProfile
from .tests_profile_image import PNG


class SocialIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', email='tester@example.com')
        MemberProfile.objects.create(user=self.user, email_key=self.user.email, nickname_key='tester', accepted_at=timezone.now(), email_verified_at=timezone.now())
        self.client.force_login(self.user)

    def test_uploaded_image_and_messaging_are_in_header(self):
        self.client.post('/accounts/profile/image/', {'image': SimpleUploadedFile('photo.png', PNG, content_type='image/png')})
        response = self.client.get('/')
        self.assertContains(response, 'src="/accounts/profile/image/"')
        self.assertContains(response, 'href="/community/messages/"')
