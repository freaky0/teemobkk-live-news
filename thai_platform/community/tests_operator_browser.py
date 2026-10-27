import os
from pathlib import Path
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright
from .models import Post


@skipUnless(os.environ.get('POST_RUN_BROWSER_TESTS') == '1', 'Explicit browser test opt-in required')
class OperatorMobileTests(StaticLiveServerTestCase):
    def test_mobile_hide_restore_and_confirmation(self):
        User = get_user_model()
        author = User.objects.create_user(username='legacy-author')
        operator = User.objects.create_superuser(username='operator', email='op@example.test', password='test-only')
        post = Post.objects.create(author=author, title='기존 게시글 확인', body='기존 데이터 보존 테스트입니다.')
        self.client.force_login(operator)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(self.live_server_url + f'/community/{post.pk}/', wait_until='networkidle')
            self.assertTrue(page.get_by_role('button', name='운영자 숨김').is_visible())
            page.get_by_role('button', name='운영자 숨김').click()
            self.assertTrue(page.get_by_role('button', name='게시글 복원').is_visible())
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
            output = Path(settings.BASE_DIR) / 'var' / 'browser'
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / 'operator-hidden-mobile.png'), full_page=True)
            page.get_by_role('link', name='운영자 삭제').click()
            self.assertTrue(page.get_by_label('이 게시글을 삭제하겠습니다.').is_visible())
            page.go_back()
            page.get_by_role('button', name='게시글 복원').click()
            self.assertEqual(errors, [])
            browser.close()
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
