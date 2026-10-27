from django.test import TestCase, override_settings


class PublicFooterTests(TestCase):
    @override_settings(POST_POLICY_APPROVED=True)
    def test_login_footer_distinguishes_password_field_and_public_content(self):
        response = self.client.get('/accounts/login/')
        footer = response.content.decode().split('<footer', 1)[1].split('</footer>', 1)[0]
        self.assertNotIn('게시글이나 댓글에 비밀번호', footer)
        self.assertIn('개인정보 처리방침', footer)
        self.assertNotIn('개인정보 수집·이용 안내', footer)

    @override_settings(POST_POLICY_APPROVED=False)
    def test_unapproved_footer_omits_development_notice(self):
        self.assertNotContains(self.client.get('/accounts/login/'), '개발 검토용 서비스입니다.')
