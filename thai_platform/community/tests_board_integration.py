import os
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from playwright.sync_api import sync_playwright

from .models import Post
from . import services
from .board_versions import board_data_version


class BoardPermissionIntegrationTests(TestCase):
    def test_staff_notice_and_unauthorized_controls(self):
        User = get_user_model()
        member = User.objects.create_user(username='board-member')
        staff = User.objects.create_user(username='board-staff', is_staff=True)
        staff2 = User.objects.create_user(username='board-staff2', is_staff=True)
        normal = services.create_post(member, {'category': 'free', 'title': 'Normal post', 'body': 'Normal post body'})
        self.client.force_login(staff)
        payload = {'title': 'Staff notice title', 'body': 'Sufficiently long staff notice body.', 'region': 'common', 'category': 'notice', 'privacy': 'on'}
        response = self.client.post('/community/new/', payload)
        self.assertEqual(response.status_code, 302)
        notice = Post.objects.get(pk=int(response.url.rstrip('/').split('/')[-1]))
        self.assertNotContains(self.client.get(f'/community/{normal.pk}/'), f'/community/{normal.pk}/edit/')
        self.assertEqual(self.client.get(f'/community/{normal.pk}/edit/').status_code, 403)
        self.client.force_login(staff2)
        self.assertContains(self.client.get(f'/community/{notice.pk}/'), f'/community/{notice.pk}/edit/')
        payload['title'] = 'Edited by other staff'
        payload['board_data_version'] = board_data_version(notice)
        self.assertEqual(self.client.post(f'/community/{notice.pk}/edit/', payload).status_code, 302)
        notice.refresh_from_db()
        self.assertEqual(notice.display_title, payload['title'])
        self.client.force_login(member)
        self.assertEqual(self.client.post('/api/v1/posts/', {'title': 'Forged', 'body': 'Forged content', 'category': 'notice'}).status_code, 403)
        self.assertEqual(self.client.patch(f'/api/v1/posts/{notice.pk}/', data='{"title":"forged"}', content_type='application/json').status_code, 403)
        self.assertEqual(self.client.get(f'/community/{notice.pk}/edit/').status_code, 403)
        staff.is_staff = False
        staff.save(update_fields=['is_staff'])
        self.client.force_login(staff)
        self.assertNotContains(self.client.get(f'/community/{notice.pk}/'), f'/community/{notice.pk}/edit/')
        self.assertEqual(self.client.post(f'/community/{notice.pk}/delete/').status_code, 403)


class BoardMigrationIntegrationTests(TransactionTestCase):
    def test_legacy_records_survive_and_are_visible_after_board_migrations(self):
        old = [('community', '0015_alter_notification_kind_privatemessage')]
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('auth', 'User').objects.create(username='legacy-board-owner')
            OldPost = apps.get_model('community', 'Post')
            ids = {}
            for category in ('living', 'housing', 'visa', 'travel', 'banking'):
                ids[category] = OldPost.objects.create(author_id=user.pk, title=f'Legacy {category}', body='Preserve this legacy body', category=category).pk
            executor = MigrationExecutor(connection)
            executor.migrate(leaves)
            for category, pk in ids.items():
                post = Post.objects.get(pk=pk)
                self.assertEqual((post.category, post.body, post.author_id), (category, 'Preserve this legacy body', user.pk))
                self.assertContains(self.client.get(f'/community/?category={category}'), post.title)
                self.assertContains(self.client.get(f'/community/{pk}/'), post.title)
                response = self.client.get(f'/api/v1/posts/?category={category}')
                self.assertEqual(response.status_code, 200)
                self.assertIn(post.title, response.content.decode())
        finally:
            MigrationExecutor(connection).migrate(leaves)


@skipUnless(os.environ.get('POST_RUN_BROWSER_TESTS') == '1', 'Explicit browser test opt-in required')
class BoardMobileBrowserTests(StaticLiveServerTestCase):
    @patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
    def test_authenticated_mobile_create_and_edit_all_boards(self):
        user = get_user_model().objects.create_user(username='mobile-board-member')
        staff = get_user_model().objects.create_user(username='mobile-board-staff', is_staff=True)
        with sync_playwright() as pw:
            launch = {'headless': True, 'args': ['--no-sandbox']}
            if os.environ.get('POST_BROWSER_EXECUTABLE'):
                launch['executable_path'] = os.environ['POST_BROWSER_EXECUTABLE']
            browser = pw.chromium.launch(**launch)
            context = browser.new_context(viewport={'width': 390, 'height': 844})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            try:
                for category in ('free', 'questions', 'market', 'jobs', 'foodtravel', 'notice'):
                    self.client.force_login(staff if category == 'notice' else user)
                    context.clear_cookies()
                    context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value, 'url': self.live_server_url}])
                    page.goto(self.live_server_url + f'/community/new/?category={category}', wait_until='networkidle')
                    self.assertEqual(page.locator('#id_category').input_value(), category)
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                    page.locator('#id_title').fill(f'Mobile {category} title')
                    page.locator('#id_body').fill('A sufficiently long mobile test post body.')
                    page.locator('#id_privacy').check()
                    page.locator('form[data-editor] button[type=submit]').click()
                    page.wait_for_url('**/community/*/')
                    post = Post.objects.get(title=f'Mobile {category} title')
                    self.assertEqual(post.category, category)
                    page.get_by_role('link', name='수정', exact=True).click()
                    page.locator('#id_title').fill(f'Edited mobile {category} title')
                    page.locator('#id_privacy').check()
                    page.get_by_role('button', name='수정 저장').click()
                    page.wait_for_load_state('networkidle')
                    post.refresh_from_db()
                    self.assertEqual((post.title, post.category), (f'Edited mobile {category} title', category))
                    self.assertIn(post.title, page.locator('h1').inner_text())
                self.assertEqual(errors, [])
            finally:
                browser.close()
