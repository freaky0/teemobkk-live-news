import base64
import io
from PIL import Image, PngImagePlugin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.utils import timezone
from .models import MemberProfile

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aXcAAAAASUVORK5CYII=')

class ProfileImageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='imageuser', email='image@example.com')
        self.member = MemberProfile.objects.create(user=self.user, email_key=self.user.email, nickname_key='imageuser', accepted_at=timezone.now(), email_verified_at=timezone.now())
        self.client.force_login(self.user)

    def test_upload_and_private_readback(self):
        response = self.client.post('/accounts/profile/image/', {'image': SimpleUploadedFile('photo.png', PNG, content_type='image/png')})
        self.assertEqual(response.status_code, 302)
        image = self.client.get('/accounts/profile/image/')
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image['Content-Type'], 'image/png')
        self.assertEqual(Client().get('/accounts/profile/image/').status_code, 302)
        self.assertIn('no-store', image['Cache-Control'])
        self.assertEqual(image['X-Content-Type-Options'], 'nosniff')
        other = get_user_model().objects.create_user(username='other', email='other@example.com')
        MemberProfile.objects.create(user=other, email_key=other.email, nickname_key='other', accepted_at=timezone.now(), email_verified_at=timezone.now())
        client = Client(); client.force_login(other)
        self.assertEqual(client.get('/accounts/profile/image/').status_code, 404)

    def test_reencoding_strips_metadata_and_resizes(self):
        source = io.BytesIO(); info = PngImagePlugin.PngInfo(); info.add_text('private', 'sensitive metadata')
        Image.new('RGB', (600, 500), 'red').save(source, format='PNG', pnginfo=info)
        self.client.post('/accounts/profile/image/', {'image': SimpleUploadedFile('x.png', source.getvalue())})
        response = self.client.get('/accounts/profile/image/')
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (256, 213))
        self.assertNotIn(b'sensitive metadata', response.content)
        self.assertEqual(image.info, {})

    def test_rejects_invalid_content_size_and_dimensions_without_changing_image(self):
        self.client.post('/accounts/profile/image/', {'image': SimpleUploadedFile('ok.png', PNG)})
        self.member.refresh_from_db(); previous = bytes(self.member.avatar_image)
        big = io.BytesIO(); Image.new('RGB', (2001, 2000)).save(big, 'PNG')
        for data in [b'<svg onload="alert(1)"/>', b'x' * (1024*1024+1), big.getvalue(), PNG[:20]]:
            self.client.post('/accounts/profile/image/', {'image': SimpleUploadedFile('image.png', data, content_type='image/png')})
            self.member.refresh_from_db()
            self.assertEqual(bytes(self.member.avatar_image), previous)

    def test_removal_and_choosing_icon_clear_image(self):
        for action in ('remove', 'icon'):
            self.client.post('/accounts/profile/image/', {'image': SimpleUploadedFile('x.png', PNG)})
            if action == 'remove':
                self.client.post('/accounts/profile/image/', {'remove': '1'})
            else:
                self.client.post('/accounts/profile/avatar/', {'avatar': 'cat'})
            self.member.refresh_from_db()
            self.assertIsNone(self.member.avatar_image)
            self.assertEqual(self.client.get('/accounts/profile/image/').status_code, 404)
        self.assertEqual(self.member.avatar, 'cat')

    def test_upload_requires_login_and_csrf(self):
        self.assertEqual(Client().post('/accounts/profile/image/', {'image': SimpleUploadedFile('x.png', PNG)}).status_code, 302)
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(client.post('/accounts/profile/image/', {'image': SimpleUploadedFile('x.png', PNG)}).status_code, 403)
        self.member.refresh_from_db(); self.assertIsNone(self.member.avatar_image)
