from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Notification, Post
from . import services


class NotificationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username='notification-owner')
        self.other = users.objects.create_user(username='notification-other')
        self.staff = users.objects.create_user(username='notification-staff', is_staff=True)
        self.post = Post.objects.create(author=self.owner, title='개인정보 없는 질문', body='Test')
        self.api = APIClient()

    def test_report_notifies_active_staff_and_resolution_notifies_reporter(self):
        report = services.create_report(self.other, self.post, {'reason': 'spam', 'details': '스팸 신고 내용'})
        self.assertEqual(Notification.objects.filter(recipient=self.staff, kind=Notification.Kind.MODERATION_REPORT, report=report).count(), 1)
        services.resolve_report(self.staff, report, {'status': 'resolved'})
        self.assertEqual(Notification.objects.filter(recipient=self.other, kind=Notification.Kind.REPORT_UPDATE, report=report).count(), 1)
        self.api.force_authenticate(self.staff)
        response = self.api.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, 200)
        payload = response.data['results'][0]
        self.assertEqual(payload['kind'], 'moderation_report')
        self.assertNotIn('details', payload)
        self.assertNotIn('스팸 신고 내용', str(response.data))

    def test_web_notifications_page_marks_only_owned_items_read(self):
        item = Notification.objects.create(recipient=self.owner, kind=Notification.Kind.REPLY, post=self.post)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'/community/notifications/{item.pk}/read/').status_code, 404)
        item.refresh_from_db()
        self.assertFalse(item.is_read)
        self.client.force_login(self.owner)
        response = self.client.get('/community/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '내 질문에 새 답변이 등록되었습니다.')
        self.assertNotContains(response, self.post.title)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        response = self.client.post(f'/community/notifications/{item.pk}/read/')
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertTrue(item.is_read)

    def test_notification_read_is_private_and_only_recipient_can_mark_it(self):
        item = Notification.objects.create(recipient=self.owner, kind=Notification.Kind.REPLY, post=self.post)
        self.api.force_authenticate(self.other)
        response = self.api.post(f'/api/v1/notifications/{item.pk}/read/')
        self.assertEqual(response.status_code, 404)
        item.refresh_from_db()
        self.assertFalse(item.is_read)
        self.api.force_authenticate(self.owner)
        response = self.api.post(f'/api/v1/notifications/{item.pk}/read/')
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.is_read)

    def test_other_reply_notifies_owner_without_content_copy(self):
        services.create_comment(self.owner, self.post, {'body': '내 답변은 알림을 만들지 않습니다.'})
        services.create_comment(self.other, self.post, {'body': '민감한 본문은 알림에 복사하지 않습니다.'})
        self.api.force_authenticate(self.owner)
        response = self.api.get('/api/v1/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['kind'], 'reply')
        self.assertNotIn('민감한 본문', str(response.data))
        self.assertNotIn(self.post.title, str(response.data))
        self.assertEqual(response['Cache-Control'], 'no-store, private')
