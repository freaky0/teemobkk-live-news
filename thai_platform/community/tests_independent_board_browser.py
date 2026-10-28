"""Browser acceptance checks against Django's disposable live-server database."""
import os
import re
from unittest import skipUnless
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright

from .models import Post

BOARDS = ('notice', 'free', 'market', 'jobs', 'living')


@skipUnless(os.environ.get('POST_RUN_BROWSER_TESTS') == '1', 'Explicit browser opt-in required')
class IndependentBoardBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username='e2e-owner')
        self.other = get_user_model().objects.create_user(username='e2e-other')
        self.staff = get_user_model().objects.create_user(username='e2e-staff', is_staff=True)
        self.pw = sync_playwright().start()
        options = {'headless': True, 'args': ['--no-sandbox']}
        if os.environ.get('POST_BROWSER_EXECUTABLE'):
            options['executable_path'] = os.environ['POST_BROWSER_EXECUTABLE']
        self.browser = self.pw.chromium.launch(**options)
        self.context = self.browser.new_context(viewport={'width': 390, 'height': 844})
        # Explicitly deny every request outside the disposable local server.
        origin = urlsplit(self.live_server_url).netloc
        self.context.route('**/*', lambda route: route.continue_() if urlsplit(route.request.url).netloc == origin else route.abort())
        self.page = self.context.new_page()
        self.page.set_default_timeout(4000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self.pw.stop()
        self.assertEqual(self.errors, [])

    def login(self, user):
        self.client.force_login(user)
        self.context.clear_cookies()
        self.context.add_cookies([{'name': settings.SESSION_COOKIE_NAME,
                                   'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                                   'url': self.live_server_url}])

    def goto(self, path):
        return self.page.goto(self.live_server_url + path, wait_until='domcontentloaded')

    def create_post(self, board):
        self.login(self.staff if board == 'notice' else self.member)
        self.goto('/community/new/')
        self.page.locator('#id_category').select_option(board)
        self.page.locator('#id_title').fill(f'Browser marker {board}')
        self.page.locator('#id_body').fill('A sufficiently long independent board browser test body.')
        self.page.locator('#id_privacy').check()
        self.page.locator('form[data-editor] button[type=submit]').click()
        self.page.wait_for_url(re.compile(r'/community/\d+/$'))
        self.assertIn(f'Browser marker {board}', self.page.locator('h1').inner_text())
        return urlsplit(self.page.url).path

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_create_edit_and_category_filter(self):
        for board in BOARDS:
            with self.subTest(board=board):
                self.create_post(board)
                self.page.get_by_role('link', name='수정', exact=True).click()
                self.page.locator('#id_title').fill(f'Edited browser marker {board}')
                self.page.locator('#id_privacy').check()
                self.page.get_by_role('button', name='수정 저장').click()
                self.assertIn(f'Edited browser marker {board}', self.page.locator('h1').inner_text())
        self.context.clear_cookies()
        for board in BOARDS:
            with self.subTest(filter=board):
                self.goto('/community/')
                self.page.locator('select#category').select_option(board)
                self.page.get_by_role('button', name='적용', exact=True).click()
                self.assertEqual(self.page.locator('select#category').input_value(), board)
                content = self.page.locator('body').inner_text()
                self.assertIn(f'Edited browser marker {board}', content)
                for other in BOARDS:
                    if other != board:
                        self.assertNotIn(f'Edited browser marker {other}', content)

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_permissions_for_notice_and_other_author(self):
        paths = [self.create_post('notice'), self.create_post('free')]
        self.login(self.other)
        for path in paths:
            with self.subTest(path=path):
                self.goto(path)
                self.assertEqual(self.page.get_by_role('link', name='수정', exact=True).count(), 0)
                response = self.goto(path + 'edit/')
                self.assertEqual(response.status, 403)
        self.goto('/community/new/?category=notice')
        self.page.locator('#id_category').select_option('notice')
        self.page.locator('#id_title').fill('Forbidden notice marker')
        self.page.locator('#id_body').fill('A sufficiently long unauthorized notice body.')
        self.page.locator('#id_privacy').check()
        with self.page.expect_response(lambda r: r.request.method == 'POST' and '/community/new/' in r.url) as result:
            self.page.locator('form[data-editor] button[type=submit]').click()
        self.assertIn(result.value.status, (200, 403))
        self.assertFalse(Post.objects.filter(title='Forbidden notice marker').exists())

    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_shared_interactions_on_each_board(self):
        for board in BOARDS:
            with self.subTest(board=board):
                path = self.create_post(board)
                self.login(self.other)
                self.goto(path)
                self.page.get_by_role('button', name='도움됐어요 0', exact=True).click()
                self.assertEqual(self.page.get_by_role('button', name='도움됐어요 취소 1').get_attribute('aria-pressed'), 'true')
                self.page.get_by_role('button', name='스크랩', exact=True).click()
                self.assertEqual(self.page.get_by_role('button', name='스크랩 해제').get_attribute('aria-pressed'), 'true')
                self.page.locator('form[action$="/comments/"] textarea[name="body"]').fill(f'Browser answer for {board}')
                self.page.get_by_role('button', name='답변 등록').click()
                self.assertIn(f'Browser answer for {board}', self.page.locator('body').inner_text())
                self.page.reload()
                self.assertIn(f'Browser answer for {board}', self.page.locator('body').inner_text())
