from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from members.models import AccountClosureRequest, MemberProfile
from community.models import Post


class AccountClosureTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='closure-member', email='closure@example.test'
        )
        MemberProfile.objects.create(
            user=self.user,
            email_key=self.user.email,
            nickname_key='closure-member',
            email_login_enabled=True,
            email_verified_at=timezone.now(),
            accepted_at=timezone.now(),
        )
        self.post = Post.objects.create(
            author=self.user,
            title='Keep content pending review',
            body='A community post retained while account closure is reviewed.',
        )
        self.client.force_login(self.user)

    def test_deactivation_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post('/accounts/deactivate/', {'confirm': 'on'})
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(AccountClosureRequest.objects.exists())

    def test_deactivation_requires_explicit_confirmation(self):
        page = self.client.get('/accounts/deactivate/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, '질문과 답변은 삭제하지 않고 보존합니다.')
        self.assertContains(page, '실제 삭제 여부는 운영자가 별도로 검토합니다.')
        response = self.client.post('/accounts/deactivate/', {})
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertFalse(AccountClosureRequest.objects.exists())

    def test_confirmed_request_deactivates_but_preserves_content_for_review(self):
        response = self.client.post('/accounts/deactivate/', {'confirm': 'on'})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        request = AccountClosureRequest.objects.get(user=self.user)
        self.assertEqual(request.status, AccountClosureRequest.Status.PENDING_REVIEW)
        self.assertTrue(Post.objects.filter(pk=self.post.pk, author=self.user).exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_review_action_records_operator_and_does_not_delete_account(self):
        request = AccountClosureRequest.objects.create(user=self.user)
        operator = get_user_model().objects.create_superuser(
            username='closure-operator', email='operator@example.test', password='test-only'
        )
        self.client.force_login(operator)
        response = self.client.post('/admin/members/accountclosurerequest/', {
            'action': 'mark_closure_reviewed',
            '_selected_action': str(request.pk),
        })
        self.assertEqual(response.status_code, 302)
        request.refresh_from_db()
        self.assertEqual(request.status, AccountClosureRequest.Status.REVIEWED)
        self.assertEqual(request.reviewed_by, operator)
        self.assertIsNotNone(request.reviewed_at)
        self.assertTrue(get_user_model().objects.filter(pk=self.user.pk).exists())
