from django.contrib.auth import get_user_model
from django.test import TestCase


class HeaderFooterTests(TestCase):
    def test_public_header_and_footer_do_not_expose_development_copy(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '개발용 서비스 · 회원·게시판 DB 분리')
        self.assertNotContains(response, '개발 검토용 서비스입니다.')
        self.assertNotContains(response, '뉴스는 기존 DB에서 읽기 전용으로 연결합니다.')
        for text in ('운영: TeemoBKK', '운영자 소개', '문의', '이용약관', '개인정보 처리방침'):
            self.assertContains(response, text)

    def test_member_menu_has_real_destinations_and_no_message_placeholder(self):
        self.client.force_login(get_user_model().objects.create_user(username='member'))
        response = self.client.get('/')
        self.assertContains(response, 'aria-label="계정 메뉴"')
        self.assertContains(response, 'href="/community/notifications/"')
        self.assertContains(response, 'href="/accounts/profile/"')
        self.assertContains(response, 'href="/accounts/logout/"')
        self.assertNotContains(response, 'href="#messages"')
