from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import Post, PostImage


class PostMediaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="media-writer")
        self.client.force_login(self.user)

    def post_payload(self, **overrides):
        return {
            "title": "방콕 사진이 있는 맛집 소개",
            "body": "직접 방문한 장소와 사진을 이웃에게 충분히 소개합니다.",
            "region": "bangkok",
            "category": "foodtravel",
            "privacy": "on",
            **overrides,
        }

    def png_upload(self):
        image = BytesIO()
        Image.new("RGB", (12, 8), (20, 120, 220)).save(image, format="PNG")
        return SimpleUploadedFile("food.png", image.getvalue(), content_type="image/png")

    def test_uploaded_image_is_sanitized_saved_and_served_for_public_post(self):
        response = self.client.post(
            reverse("post-create"),
            self.post_payload(image_uploads=self.png_upload()),
        )
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get(title="방콕 사진이 있는 맛집 소개")
        image = post.images.get()
        self.assertEqual(image.content_type, "image/jpeg")
        self.assertTrue(bytes(image.image_data).startswith(b"\xff\xd8"))

        detail = self.client.get(reverse("post-detail", args=[post.pk]))
        self.assertContains(detail, reverse("post-image", args=[image.pk]))
        served = self.client.get(reverse("post-image", args=[image.pk]))
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served["Content-Type"], "image/jpeg")
        self.assertEqual(served["X-Content-Type-Options"], "nosniff")

    def test_https_image_links_are_saved_without_server_fetch(self):
        response = self.client.post(
            reverse("post-create"),
            self.post_payload(image_urls="https://images.example.test/food.jpg"),
        )
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get(title="방콕 사진이 있는 맛집 소개")
        self.assertEqual(post.images.get().image_url, "https://images.example.test/food.jpg")

    def test_non_https_image_link_is_rejected(self):
        response = self.client.post(
            reverse("post-create"),
            self.post_payload(image_urls="http://images.example.test/food.jpg"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Post.objects.filter(title="방콕 사진이 있는 맛집 소개").exists())
        self.assertFalse(PostImage.objects.exists())

    def test_hidden_post_image_is_not_publicly_served(self):
        post = Post.objects.create(
            author=self.user,
            title="숨겨진 게시글",
            body="운영자 숨김 게시글의 사진입니다.",
            category=Post.Category.FOODTRAVEL,
            status=Post.Status.HIDDEN,
        )
        image = PostImage.objects.create(
            post=post,
            image_data=b"\xff\xd8private",
            content_type="image/jpeg",
        )
        self.client.logout()
        self.assertEqual(self.client.get(reverse("post-image", args=[image.pk])).status_code, 404)
