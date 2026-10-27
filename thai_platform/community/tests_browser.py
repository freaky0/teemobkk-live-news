import json
import os
import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright
from .models import Comment, Notification, Post

@skipUnless(os.environ.get("POST_RUN_BROWSER_TESTS") == "1", "Explicit browser test opt-in required")
class BrowserFlowTests(StaticLiveServerTestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="브라우저검증")
        if self._testMethodName == 'test_staff_notice_pin_and_unpin':
            self.member.is_staff = True
            self.member.save(update_fields=['is_staff'])
        if self._testMethodName in ('test_private_messages_mobile_send', 'test_member_menu_mobile_keyboard_and_block', 'test_detail_member_menus_in_both_themes', 'test_combined_member_menu_and_comment_likes'):
            from members.models import MemberProfile
            from django.utils import timezone
            now = timezone.now()
            MemberProfile.objects.create(user=self.member, email_key='browser-sender@example.test', nickname_key='브라우저검증', accepted_at=now, email_verified_at=now)
            recipient = get_user_model().objects.create_user(username='쪽지수신자')
            if self._testMethodName == 'test_member_menu_mobile_keyboard_and_block':
                Post.objects.create(author=recipient, title='회원 메뉴 테스트', body='browser fixture')
            MemberProfile.objects.create(user=recipient, email_key='browser-recipient@example.test', nickname_key='쪽지수신자', accepted_at=now, email_verified_at=now)
            from django.test import Client
            recipient_client = Client()
            recipient_client.force_login(recipient)
            self.recipient_session = recipient_client.cookies[settings.SESSION_COOKIE_NAME].value
        self.post = Post.objects.create(author=self.member, title="브라우저 검증용 첫 생활 질문", body="실제 개인정보를 포함하지 않은 브라우저 검증용 게시글입니다. 목록 이동과 서버 저장을 확인합니다.", region="bangkok", category="housing")
        if self._testMethodName in ('test_detail_member_menus_in_both_themes', 'test_combined_member_menu_and_comment_likes'):
            comment = Comment.objects.create(post=self.post, author=recipient, body='메뉴 답변')
            Comment.objects.create(post=self.post, author=recipient, parent=comment, body='메뉴 대댓글')
        if self._testMethodName == 'test_reply_mobile_keyboard_and_submission':
            from members.models import MemberProfile
            from django.utils import timezone
            MemberProfile.objects.create(user=self.member, email_key='browser-reply@example.test', nickname_key='브라우저검증', accepted_at=timezone.now(), email_verified_at=timezone.now())
            Comment.objects.create(post=self.post, author=self.member, body='기존 답변 내용입니다.')
        if self._testMethodName == 'test_comment_like_reply_responsive':
            answer = Comment.objects.create(post=self.post, author=self.member, body='Browser answer')
            Comment.objects.create(post=self.post, author=self.member, parent=answer, body='Browser reply')
        self.client.force_login(self.member)
        if self._testMethodName == "test_hidden_content_notification_leads_to_appeal_submission":
            self.post.status = Post.Status.HIDDEN
            self.post.save(update_fields=['status', 'updated_at'])
            Notification.objects.create(recipient=self.member, kind=Notification.Kind.CONTENT_HIDDEN, post=self.post)
        self.pw = sync_playwright().start()
        launch = {"headless": True, "args": ["--no-sandbox"]}
        if os.environ.get("POST_BROWSER_EXECUTABLE"):
            launch["executable_path"] = os.environ["POST_BROWSER_EXECUTABLE"]
        self.browser = self.pw.chromium.launch(**launch)
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        self.context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": self.client.cookies[settings.SESSION_COOKIE_NAME].value, "url": self.live_server_url}])
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        # The public origin serves /favicon.ico; the isolated Django test server does not.
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" and not (m.text.startswith("Failed to load resource: the server responded with a status of 404") and m.location.get("url") == self.live_server_url + "/favicon.ico") else None)
        self.output = Path(settings.BASE_DIR) / "var" / "browser"
        self.output.mkdir(parents=True, exist_ok=True)
    def tearDown(self):
        self.browser.close()
        self.pw.stop()
    def go(self, path):
        return self.page.goto(self.live_server_url + path, wait_until="networkidle")

    def test_market_create_edit_list_detail_responsive(self):
        self.go('/community/new/?category=market')
        self.page.get_by_label('제목').fill('브라우저 중고 자전거 판매')
        self.page.get_by_label('주제').select_option('market')
        self.page.get_by_label('상황과 질문').fill('방콕에서 사용한 자전거를 판매하며 상태가 좋습니다.')
        self.page.get_by_label('글 종류').select_option('sell')
        self.page.get_by_label('가격 (THB)').fill('1250.50')
        self.page.get_by_label('거래 지역').select_option('bangkok')
        self.page.get_by_label('거래 상태').select_option('reserved')
        self.page.get_by_label('개인정보와 타인의 비공개 정보를 넣지 않았습니다.').check()
        self.page.get_by_role('button', name='질문 등록').click()
        self.page.wait_for_url('**/community/*/')
        self.assertIn('1,250.50 THB', self.page.locator('.market-details').inner_text())
        self.assertIn('예약', self.page.locator('.market-details').inner_text())
        self.page.get_by_role('link', name='수정', exact=True).click()
        self.assertEqual(self.page.get_by_label('가격 (THB)').input_value(), '1250.50')
        self.page.get_by_label('거래 상태').select_option('active')
        self.page.get_by_label('개인정보와 타인의 비공개 정보를 넣지 않았습니다.').check()
        self.page.get_by_role('button', name='수정 저장').click()
        self.page.wait_for_load_state('networkidle')
        self.assertIn('거래 중', self.page.locator('.market-details').inner_text())
        self.go('/community/?category=market')
        self.assertIn('1,250.50 THB', self.page.locator('.market-details').inner_text())
        for width in (320, 390, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
            self.page.locator('a.title', has_text='브라우저 중고 자전거 판매').click()
            self.assertIn('거래 중', self.page.locator('.market-details').inner_text())
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
            self.page.screenshot(path=str(self.output / f'market-detail-{width}.png'), full_page=True)
            self.go('/community/?category=market')
        self.assertEqual(self.errors, [])

    def test_category_change_reveals_market_fields_on_create_and_edit(self):
        paths = ('/community/new/', f'/community/{self.post.pk}/edit/')
        for path in paths:
            with self.subTest(path=path):
                self.page.set_viewport_size({'width': 1440, 'height': 900})
                self.go(path)
                market_fields = self.page.locator('[data-market-fields]')
                self.assertEqual(market_fields.count(), 1)
                price = self.page.get_by_label('가격 (THB)')
                self.assertFalse(market_fields.evaluate('(element) => element.open'))
                self.assertTrue(price.is_disabled())
                self.page.get_by_label('주제').select_option('market')
                self.assertEqual(self.page.get_by_label('주제').input_value(), 'market')
                self.assertTrue(market_fields.evaluate('(element) => element.open'))
                self.assertTrue(price.is_visible())
                self.assertFalse(price.is_disabled())
                if path == '/community/new/':
                    self.page.set_viewport_size({'width': 320, 'height': 900})
                    self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                    self.page.screenshot(path=str(self.output / 'market-form-open-320.png'), full_page=True)
                self.page.get_by_label('주제').select_option('free')
                self.assertFalse(market_fields.evaluate('(element) => element.open'))
                self.assertTrue(price.is_disabled())
        self.assertEqual(self.errors, [])

    def test_market_draft_restores_market_fields(self):
        key = f'post-draft:{self.member.pk}:new'
        self.context.add_init_script(
            f"localStorage.setItem('{key}', JSON.stringify({{title:'Saved market draft', "
            "body:'Long enough draft body for a market post.', region:'common', category:'market'}));"
        )
        self.go('/community/new/')
        self.assertEqual(self.page.get_by_label('주제').input_value(), 'market')
        market_fields = self.page.locator('[data-market-fields]')
        self.assertTrue(market_fields.evaluate('(element) => element.open'))
        self.assertFalse(self.page.get_by_label('가격 (THB)').is_disabled())

    def test_comment_like_reply_responsive(self):
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go(f'/community/{self.post.pk}/')
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
            self.assertEqual(self.page.locator('.answer button[aria-pressed]').count(), 2)
        self.page.set_viewport_size({'width': 390, 'height': 900})
        answer_button = self.page.locator('.answer').first.locator('button[aria-pressed]').first
        answer_button.focus()
        with self.page.expect_navigation(wait_until='networkidle'):
            self.page.keyboard.press('Enter')
        self.assertEqual(self.page.locator('.answer').first.locator('button[aria-pressed]').first.get_attribute('aria-pressed'), 'true')
        reply_button = self.page.locator('.reply button[aria-pressed]')
        reply_button.click()
        self.assertEqual(self.page.locator('.reply button[aria-pressed]').get_attribute('aria-pressed'), 'true')
        self.page.reload(wait_until='networkidle')
        self.assertEqual(self.page.locator('.reply button[aria-pressed]').inner_text(), '♥ 좋아요 1')
        self.page.locator('.reply button[aria-pressed]').click()
        self.assertEqual(self.page.locator('.reply button[aria-pressed]').get_attribute('aria-pressed'), 'false')
        self.page.screenshot(path=str(self.output / 'comment-likes-mobile.png'), full_page=True)
        self.assertEqual(self.errors, [])

    def test_combined_member_menu_and_comment_likes(self):
        for width in (320, 390, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go(f'/community/{self.post.pk}/')
            for theme in ('light', 'dark'):
                if (self.page.locator('html').get_attribute('data-theme') or 'light') != theme:
                    self.page.locator('[data-theme-toggle]').click()
                self.assertEqual(self.page.locator('.member-menu').count(), 3)
                for menu in self.page.locator('.member-menu').all():
                    summary = menu.locator('summary')
                    summary.focus()
                    self.page.keyboard.press('Enter')
                    self.assertTrue(menu.locator('.member-menu-actions').is_visible())
                    self.page.keyboard.press('Escape')
                    self.assertFalse(menu.locator('.member-menu-actions').is_visible())
                    self.assertTrue(summary.evaluate('(e) => document.activeElement === e'))
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
            for selector in ('.answer button[aria-pressed]', '.reply button[aria-pressed]'):
                button = self.page.locator(selector).first
                initial = button.get_attribute('aria-pressed')
                button.click()
                button = self.page.locator(selector).first
                self.assertNotEqual(button.get_attribute('aria-pressed'), initial)
                self.assertIn('1', button.inner_text())
                button.click()
                self.assertEqual(self.page.locator(selector).first.get_attribute('aria-pressed'), initial)
                self.assertIn('0', self.page.locator(selector).first.inner_text())
        self.assertEqual(self.errors, [])

    def test_staff_notice_pin_and_unpin(self):
        self.go('/community/new/')
        self.page.get_by_label('제목').fill('브라우저 공지 고정 테스트')
        self.page.get_by_label('주제').select_option('notice')
        self.page.get_by_label('상황과 질문').fill('브라우저에서 공지 고정과 해제를 확인하는 테스트입니다.')
        self.page.get_by_label('개인정보와 타인의 비공개 정보를 넣지 않았습니다.').check()
        self.page.get_by_label('공지 상단 고정 (공지 글만 가능)').check()
        self.page.get_by_role('button', name='질문 등록').click()
        self.page.wait_for_url('**/community/*/')
        self.assertTrue(self.page.get_by_text('상단 고정', exact=True).is_visible())
        self.go('/community/')
        self.assertIn('브라우저 공지 고정 테스트', self.page.locator('.row').first.inner_text())
        self.page.get_by_role('link', name='브라우저 공지 고정 테스트').click()
        self.page.get_by_role('link', name='수정', exact=True).click()
        self.page.get_by_label('공지 상단 고정 (공지 글만 가능)').uncheck()
        self.page.get_by_label('개인정보와 타인의 비공개 정보를 넣지 않았습니다.').check()
        self.page.get_by_role('button', name='수정 저장').click()
        self.assertEqual(self.page.get_by_text('상단 고정', exact=True).count(), 0)
        response = self.page.request.get(self.live_server_url + '/api/v1/posts/?category=notice')
        self.assertFalse(response.json()['results'][0]['is_pinned'])
        self.assertEqual(self.errors, [])

    def test_member_menu_mobile_keyboard_and_block(self):
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go('/community/')
            row = self.page.locator('article.row').filter(has_text='회원 메뉴 테스트')
            summary = row.locator('summary')
            before = row.bounding_box()
            summary.focus()
            self.page.keyboard.press('Enter')
            menu = row.locator('.member-menu-actions')
            self.assertTrue(row.get_by_role('link', name='회원 정보').is_visible())
            self.assertAlmostEqual(row.bounding_box()['height'], before['height'], delta=1)
            box = menu.bounding_box()
            self.assertGreaterEqual(box['x'], 0)
            self.assertLessEqual(box['x'] + box['width'], width)
            self.page.keyboard.press('Escape')
            self.assertFalse(menu.is_visible())
            self.assertTrue(summary.evaluate('(e) => document.activeElement === e'))
            summary.click()
            self.page.locator('h1').first.click()
            self.assertFalse(menu.is_visible())
            summary.click()
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
        row.get_by_role('link', name='쪽지 보내기').click()
        self.assertEqual(self.page.get_by_label('받는 회원 닉네임').input_value(), '쪽지수신자')
        self.go('/community/')
        row = self.page.locator('article.row').filter(has_text='회원 메뉴 테스트')
        row.locator('summary').click()
        row.get_by_role('button', name='회원 차단').click()
        self.assertTrue(self.page.get_by_role('button', name='차단 해제').is_visible())
        self.page.get_by_role('button', name='차단 해제').click()
        self.assertTrue(self.page.get_by_text('차단한 회원이 없습니다.').is_visible())
        self.assertEqual(self.errors, [])

    def test_detail_member_menus_in_both_themes(self):
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go(f'/community/{self.post.pk}/')
            for theme in ('light', 'dark'):
                if (self.page.locator('html').get_attribute('data-theme') or 'light') != theme:
                    self.page.locator('[data-theme-toggle]').click()
                menus = self.page.locator('.member-menu')
                self.assertEqual(menus.count(), 3)
                for i in range(3):
                    menu = menus.nth(i)
                    menu.locator('summary').click()
                    panel = menu.locator('.member-menu-actions')
                    self.assertTrue(panel.is_visible())
                    self.assertEqual(panel.evaluate("e => getComputedStyle(e).backgroundColor"), panel.evaluate("e => getComputedStyle(document.documentElement).getPropertyValue('--color-bg-surface').trim()").replace('#fff', 'rgb(255, 255, 255)') if theme == 'light' else 'rgb(24, 42, 58)')
                    box = panel.bounding_box()
                    self.assertGreaterEqual(box['x'], 0)
                    self.assertLessEqual(box['x'] + box['width'], width)
                    if i == 2:
                        self.page.screenshot(path=str(self.output / f'member-menu-{theme}-{width}.png'))
                    self.page.keyboard.press('Escape')
                    self.assertFalse(panel.is_visible())
        self.go(f'/community/{self.post.pk}/')
        self.page.locator('.answer .member-menu summary').first.click()
        self.page.locator('.answer .member-menu').first.get_by_role('link', name='회원 정보').click()
        self.assertIn('/community/members/', self.page.url)
        self.assertTrue(self.page.locator('#member-posts').is_visible())
        self.go(f'/community/{self.post.pk}/')
        self.page.locator('.reply .member-menu summary').click()
        self.page.locator('.reply .member-menu').get_by_role('link', name='작성글 보기').click()
        self.assertTrue(self.page.url.endswith('#member-posts'))
        self.assertTrue(self.page.locator('#member-posts').is_visible())
        self.assertEqual(self.errors, [])

    def test_private_messages_mobile_send(self):
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go('/community/messages/')
            self.assertTrue(self.page.get_by_label('받는 회원 닉네임').is_visible())
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
        self.page.set_viewport_size({'width': 390, 'height': 900})
        self.page.get_by_label('받는 회원 닉네임').fill('쪽지수신자')
        self.page.get_by_label('쪽지 내용').fill('브라우저 쪽지 테스트')
        self.page.get_by_role('button', name='보내기', exact=True).click()
        self.page.wait_for_url('**/community/messages/sent/')
        self.assertTrue(self.page.get_by_text('브라우저 쪽지 테스트').is_visible())

        self.context.clear_cookies()
        self.context.add_cookies([{'name': settings.SESSION_COOKIE_NAME, 'value': self.recipient_session, 'url': self.live_server_url}])
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go('/')
            badge = self.page.locator('.message-unread-badge')
            self.assertTrue(badge.is_visible())
            self.assertEqual(badge.inner_text(), '1')
            self.assertTrue(self.page.get_by_role('link', name='쪽지, 읽지 않은 쪽지 1개').is_visible())
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
        self.go('/community/notifications/')
        self.assertTrue(self.page.get_by_text('새 쪽지가 도착했습니다.').is_visible())
        self.assertFalse(self.page.get_by_text('브라우저 쪽지 테스트').is_visible())
        self.page.get_by_role('link', name='쪽지함', exact=True).click()
        self.page.wait_for_url('**/community/messages/')
        self.assertTrue(self.page.get_by_text('브라우저 쪽지 테스트').is_visible())
        self.page.get_by_role('button', name='읽음 처리').click()
        self.assertEqual(self.page.locator('.message-unread-badge').count(), 0)
        self.assertTrue(self.page.get_by_role('link', name='쪽지', exact=True).is_visible())

        self.assertEqual(self.errors, [])

    def test_reply_mobile_keyboard_and_submission(self):
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go(f'/community/{self.post.pk}/')
            summary = self.page.get_by_text('대댓글 작성', exact=True)
            summary.focus()
            self.page.keyboard.press('Enter')
            field = self.page.get_by_label('브라우저검증님의 답변에 대댓글')
            self.assertTrue(field.is_visible())
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
        field.fill('모바일 브라우저에서 작성한 대댓글입니다.')
        self.page.get_by_role('button', name='대댓글 등록').click()
        self.page.wait_for_load_state('networkidle')
        self.assertIn('모바일 브라우저에서 작성한 대댓글입니다.', self.page.locator('.reply').inner_text())
        self.assertEqual(self.errors, [])
    def test_homepage_handles_expanded_localized_copy_without_horizontal_scroll(self):
        p = self.page
        for width in [320, 390, 768, 1440]:
            p.set_viewport_size({"width": width, "height": 900})
            self.go("/")
            for title, news_label, community_label, news_heading, news_more in [
                ("ข่าวประเทศไทยและชีวิตประจำวันสำหรับผู้พำนักและนักเดินทาง", "อ่านข่าวประเทศไทยเพิ่มเติม", "แบ่งปันคำถามและประสบการณ์", "ข่าวประเทศไทยล่าสุด", "อ่านข่าวทั้งหมด"),
                ("Thai news and everyday life for residents and travelers", "Read the latest Thailand news", "Share questions and local experience", "Latest news from Thailand", "See all news"),
            ]:
                p.locator("#home-title").evaluate("(node, text) => node.textContent = text", title)
                p.locator(".home-primary-action").evaluate("(node, text) => node.textContent = text", news_label)
                p.locator(".home-secondary-action").evaluate("(node, text) => node.textContent = text", community_label)
                p.locator("#home-news-title").evaluate("(node, text) => node.textContent = text", news_heading)
                p.locator(".home-news-more").evaluate("(node, text) => node.textContent = text", news_more)
                for selector in ["#home-title", ".home-primary-action", ".home-secondary-action", "#home-news-title", ".home-news-more"]:
                    overflow = p.locator(selector).evaluate("node => node.scrollWidth > node.clientWidth + 1 || node.getBoundingClientRect().left < -1 || node.getBoundingClientRect().right > innerWidth + 1")
                    self.assertFalse(overflow, (width, selector, title))
                self.assertTrue(p.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (width, title))
            self.assertEqual(self.errors, [])

    def test_dark_home_uses_vertical_overlay_on_mobile_and_tablet(self):
        self.go('/')
        self.page.locator('[data-theme-toggle]').click()
        self.assertEqual(self.page.locator('html').get_attribute('data-theme'), 'dark')
        for width in (320, 390, 768, 800):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                gradient = self.page.locator('.home-hero').evaluate("e => getComputedStyle(e, '::after').backgroundImage")
                self.assertTrue(gradient.startswith('linear-gradient(0deg,'), gradient)
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                if width == 800:
                    self.page.screenshot(path=str(self.output / 'home-dark-800.png'))
        self.assertEqual(self.errors, [])

    def test_home_my_activity_link_opens_private_activity(self):
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go('/')
            link = self.page.locator('.home-my-activity')
            self.assertTrue(link.is_visible())
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
            link.click()
            self.assertIn('/community/activity/', self.page.url)
            self.assertIn(self.post.title, self.page.locator('main').inner_text())
        self.assertEqual(self.errors, [])

    def test_home_helpful_question_link_across_widths(self):
        self.go(f'/community/{self.post.pk}/')
        self.page.get_by_role('button', name='도움됐어요 0', exact=True).click()
        self.page.get_by_role('button', name='도움됐어요 취소 1', exact=True).wait_for()
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go('/')
            section = self.page.locator('section[aria-labelledby="helpful-questions-title"]')
            self.assertTrue(section.is_visible())
            self.assertIn('도움 반응 1개', section.inner_text())
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
            section.get_by_role('link', name=self.post.title).click()
            self.assertIn(f'/community/{self.post.pk}/', self.page.url)
        self.assertEqual(self.errors, [])

    def test_account_navigation_visible_on_desktop_and_mobile(self):
        for width in (320, 390, 768, 1440):
            self.page.set_viewport_size({'width': width, 'height': 900})
            self.go('/')
            summary = self.page.get_by_label('계정 메뉴')
            self.assertTrue(summary.is_visible(), width)
            summary.focus()
            self.page.keyboard.press('Enter')
            link = self.page.locator('header .account-profile')
            self.assertTrue(link.is_visible(), width)
            self.assertEqual(link.get_attribute('href'), '/accounts/profile/')
            self.assertEqual(self.page.locator('header .header-icon[aria-label="알림"]').get_attribute('href'), '/community/notifications/')
            self.assertEqual(self.page.locator('header .header-icon[aria-label="쪽지"]').get_attribute('href'), '/community/messages/')
            self.page.screenshot(path=str(self.output / f'header-menu-{width}.png'))
            self.page.keyboard.press('Escape')
            self.assertFalse(link.is_visible())
            self.assertTrue(summary.evaluate('(e) => document.activeElement === e'))
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
        self.assertEqual(self.errors, [])

    def test_real_db_shared_api_and_web(self):
        p = self.page
        self.go("/community/new/")
        p.locator("#id_title").fill("웹에서 등록한 서버 저장 검증 질문")
        p.locator("#id_body").fill("개인정보 없는 테스트 문장입니다. 실제 데이터베이스 저장과 다른 브라우저의 조회를 확인하는 내용입니다.")
        p.locator("#id_region").select_option("phuket")
        p.wait_for_timeout(400)
        self.assertIn("자동 저장", p.locator("#draft-status").inner_text())
        p.once("dialog", lambda d: d.dismiss())
        p.get_by_role("link", name="나가기", exact=True).click()
        self.assertIn("/community/new/", p.url)
        p.locator("#id_privacy").check()
        p.locator("form[data-editor] button[type=submit]").click()
        p.wait_for_url("**/community/*/")
        self.assertIn("웹에서 등록한", p.locator("h1").inner_text())
        # A different browser sees the same persisted record without sharing storage.
        other = self.browser.new_context()
        other_page = other.new_page()
        other_page.goto(p.url, wait_until="networkidle")
        self.assertIn("웹에서 등록한", other_page.locator("h1").inner_text())
        response = other.request.get(self.live_server_url + "/api/v1/posts/")
        self.assertEqual(response.status, 200)
        self.assertIn("웹에서 등록한", response.text())
        other.close()
        self.assertIsNone(p.evaluate("localStorage.getItem('post-draft:' + document.body.dataset.userId + ':new')"))
        p.locator("#id_body").fill("답변도 서버에 저장되는지 확인하는 검증용 내용입니다.")
        p.get_by_role("button", name="답변 등록", exact=True).click()
        p.wait_for_load_state("networkidle")
        self.assertIn("답변도 서버", p.locator(".answer").inner_text())
        p.locator("[data-open-report]").click()
        p.locator("#id_reason").select_option("spam")
        p.locator("#id_details").fill("신고 접수를 확인하기 위한 검증용 설명입니다.")
        p.get_by_role("button", name="신고 접수").click()
        p.wait_for_load_state("networkidle")
        self.assertIn("신고를 접수", p.locator(".notice-message").inner_text())
        p.get_by_role("link", name="수정", exact=True).click()
        p.locator("#id_title").fill("수정한 서버 저장 검증 질문입니다")
        p.locator("#id_privacy").check()
        p.get_by_role("button", name="수정 저장").click()
        p.wait_for_load_state("networkidle")
        self.assertIn("수정한", p.locator("h1").inner_text())
        self.assertEqual(self.errors, [])
    def test_helpful_bookmark_activity_browser(self):
        p = self.page
        self.go(f'/community/{self.post.pk}/')
        p.get_by_role('button', name='도움됐어요 0', exact=True).click()
        p.wait_for_load_state('networkidle')
        self.assertTrue(p.get_by_role('button', name='도움됐어요 취소 1', exact=True).is_visible())
        p.get_by_role('button', name='스크랩', exact=True).click()
        p.wait_for_load_state('networkidle')
        self.assertTrue(p.get_by_role('button', name='스크랩 해제', exact=True).is_visible())
        response = self.context.request.get(self.live_server_url + f'/api/v1/posts/{self.post.pk}/')
        self.assertEqual(response.json()['helpful_count'], 1)
        self.assertTrue(response.json()['bookmarked'])
        p.get_by_role('link', name='내 활동', exact=True).click()
        p.get_by_role('link', name='비공개 스크랩', exact=True).click()
        self.assertTrue(p.locator('a.title').first.is_visible())
        for width in [320, 390, 768, 1440]:
            p.set_viewport_size({'width': width, 'height': 950})
            self.go('/community/activity/?kind=bookmarks')
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
            if width == 390:
                p.screenshot(path=str(self.output / 'activity-bookmarks-390.png'), full_page=True)
            p.locator('a.title').first.click()
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
            if width == 390:
                p.screenshot(path=str(self.output / 'engagement-detail-390.png'), full_page=True)
        p.get_by_role('button', name='스크랩 해제', exact=True).click()
        p.wait_for_load_state('networkidle')
        response = self.context.request.get(self.live_server_url + '/api/v1/activity/?kind=bookmarks')
        self.assertEqual(response.json()['count'], 0)
        self.assertEqual(self.errors, [])

    def test_author_resolution_and_filter(self):
        p = self.page
        self.go(f'/community/{self.post.pk}/')
        p.get_by_role('button', name='해결로 표시', exact=True).click()
        p.wait_for_load_state('networkidle')
        response = self.context.request.get(self.live_server_url + f'/api/v1/posts/{self.post.pk}/')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json()['resolution'], 'resolved')
        self.assertTrue(p.get_by_role('button', name='미해결로 되돌리기').is_visible())
        for width in [320, 390, 768, 1440]:
            p.set_viewport_size({'width': width, 'height': 950})
            self.go('/community/?resolution=resolved&region=bangkok')
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
            self.assertEqual(p.locator('#resolution').input_value(), 'resolved')
            p.locator('a.title').first.click()
            self.assertTrue(p.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width)
            if width == 390:
                p.screenshot(path=str(self.output / 'resolution-detail-390.png'), full_page=True)
            p.locator('a.return').click()
            self.assertEqual(p.locator('#resolution').input_value(), 'resolved')
        p.locator('a.title').first.click()
        p.get_by_role('button', name='미해결로 되돌리기').click()
        p.wait_for_load_state('networkidle')
        response = self.context.request.get(self.live_server_url + f'/api/v1/posts/{self.post.pk}/')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.json()['resolution'], 'unresolved')
        self.assertEqual(self.errors, [])

    def test_desktop_and_mobile_share_primary_navigation(self):
        p = self.page
        self.go("/")
        selectors = ('nav[aria-label="주 메뉴"] a', 'nav[aria-label="모바일 메뉴"] a')
        for width in [390, 1440]:
            p.set_viewport_size({"width": width, "height": 844 if width < 768 else 1000})
            desktop = p.locator(selectors[0]).evaluate_all("links => links.map(a => [a.getAttribute('href'), Array.from(a.childNodes).filter(n => !(n.nodeType === 1 && n.getAttribute('aria-hidden') === 'true')).map(n => n.textContent).join('').trim()])")
            mobile = p.locator(selectors[1]).evaluate_all("links => links.map(a => [a.getAttribute('href'), Array.from(a.childNodes).filter(n => !(n.nodeType === 1 && n.getAttribute('aria-hidden') === 'true')).map(n => n.textContent).join('').trim()])")
            self.assertEqual(mobile[:4], desktop)
            self.assertEqual(mobile[-1][1], "내 계정")
            nav = selectors[1] if width == 390 else selectors[0]
            expected_next = mobile[1][0] if width == 390 else desktop[1][0]
            p.locator(nav).first.focus()
            p.keyboard.press("Tab")
            self.assertEqual(p.evaluate("document.activeElement.getAttribute('href')"), expected_next)
            self.assertTrue(p.evaluate("document.activeElement.matches(':focus-visible')"))

    def test_mobile_nav_does_not_cover_focused_post_body(self):
        p = self.page
        for width in [320, 390]:
            p.set_viewport_size({"width": width, "height": 844})
            self.go("/community/new/")
            p.locator("#id_body").click()
            nav = p.locator(".bottom").bounding_box()
            body = p.locator("#id_body").bounding_box()
            self.assertIsNotNone(nav)
            self.assertIsNotNone(body)
            self.assertLessEqual(body["y"] + body["height"], nav["y"] + 1, width)
            if width == 320:
                p.screenshot(path=str(self.output / "mobile-nav-clearance-320.png"))
            if width == 390:
                p.screenshot(path=str(self.output / "mobile-nav-clearance-390.png"))

    def test_responsive_links_draft_and_back(self):
        p = self.page
        urls = ["/", "/community/", f"/community/{self.post.pk}/", "/community/new/", "/accounts/login/"]
        results = []
        for width in [320, 390, 768, 1024, 1440]:
            p.set_viewport_size({"width": width, "height": 844 if width < 768 else 1000})
            for index, url in enumerate(urls):
                self.assertEqual(self.go(url).status, 200)
                self.assertTrue(p.evaluate("document.documentElement.scrollWidth<=innerWidth+1"), (width, url))
                self.assertTrue(p.locator("img").evaluate_all("a=>a.every(i=>i.complete&&i.naturalWidth>0)"))
                if width in [390, 1440]:
                    p.screenshot(path=str(self.output / f"screen-{index}-{width}.png"), full_page=True)
                results.append({"width": width, "path": url, "status": "PASS"})
        self.go("/community/?region=bangkok&q=생활")
        before = p.url
        p.locator("a.title").first.click()
        self.assertFalse(p.locator("dialog").is_visible())
        p.reload(wait_until="networkidle")
        self.assertIn("브라우저 검증용", p.locator("h1").inner_text())
        p.go_back(wait_until="networkidle")
        self.assertEqual(p.url, before)
        self.go("/community/new/")
        p.locator("#id_title").fill("자동 복구 확인용 초안 제목")
        p.wait_for_timeout(400)
        p.once("dialog", lambda d: d.accept())
        p.get_by_role("link", name="나가기", exact=True).click()
        self.go("/community/new/")
        self.assertEqual(p.locator("#id_title").input_value(), "자동 복구 확인용 초안 제목")
        self.assertEqual(self.errors, [])
        (self.output / "responsive.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))

    def test_hidden_content_notification_leads_to_appeal_submission(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.go('/community/notifications/')
        self.assertTrue(self.page.get_by_role('link', name='이의신청', exact=True).is_visible())
        self.page.screenshot(path=str(self.output / 'moderation-notification-390.png'), full_page=True)
        self.page.get_by_role('link', name='이의신청', exact=True).click()
        self.page.wait_for_url('**/community/*/appeal/')
        self.assertTrue(self.page.locator('#id_details').is_visible())
        self.page.locator('#id_details').fill('숨김 조치에 이의가 있어 검토를 요청합니다.')
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
        self.page.screenshot(path=str(self.output / 'moderation-appeal-390.png'), full_page=True)
        self.page.get_by_role('button', name='이의신청 접수', exact=True).click()
        self.page.wait_for_url('**/community/notifications/')
        self.assertIn('이의신청을 접수했습니다.', self.page.locator('body').inner_text())
        self.assertEqual(self.context.request.get(self.live_server_url + '/api/v1/appeals/').json()['count'], 1)
        self.assertEqual(self.errors, [])

    def test_failed_news_image_removes_empty_thumbnail_column(self):
        from django.utils import timezone
        from hashlib import sha256

        link = "https://example.org/broken-image"
        with TemporaryDirectory(dir=Path(settings.BASE_DIR) / "var") as temp_dir:
            news_db = Path(temp_dir) / "news.sqlite3"
            with sqlite3.connect(news_db) as connection:
                connection.executescript("""CREATE TABLE articles(link TEXT PRIMARY KEY,title_ko TEXT,summary_ko TEXT,summary TEXT,source TEXT,original_source TEXT,region TEXT,category TEXT,post_status TEXT,published_at TEXT,image_url TEXT);
CREATE TABLE hidden_links(link TEXT);
CREATE TABLE filter_rules(id INTEGER PRIMARY KEY,enabled INTEGER);
CREATE TABLE filter_hits(link TEXT,rule_id INTEGER);
CREATE TABLE filter_keeps(link TEXT);
CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT);""")
                connection.execute(
                    "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        link,
                        "이미지 오류 뉴스",
                        "이미지 요청 실패에도 본문은 읽을 수 있습니다.",
                        "Fixture summary",
                        "Fixture",
                        "",
                        "태국",
                        "생활",
                        "ready",
                        timezone.now().isoformat(),
                        "https://images.example.test/broken.jpg",
                    ),
                )

            with override_settings(POST_NEWS_DB=str(news_db)):
                self.page.route("https://images.example.test/**", lambda route: route.abort())
                for path in ["/", "/newsroom/"]:
                    self.go(path)
                    self.page.wait_for_function("""() => {
                        const image = document.querySelector('.news-item img.news-image');
                        return !image || (image.complete && image.naturalWidth === 0);
                    }""")
                    article = self.page.locator(".news-item").filter(has_text="이미지 오류 뉴스")
                    self.assertEqual(article.locator("img.news-image").count(), 0)
                    self.assertNotIn("has-image", article.get_attribute("class"))
                    self.assertTrue(article.locator("h3").is_visible())
                    self.assertIn("이미지 요청 실패에도 본문은 읽을 수 있습니다", article.inner_text())

                self.go(f"/newsroom/{sha256(link.encode()).hexdigest()}/")
                self.page.wait_for_function("""() => {
                    const image = document.querySelector('img.news-detail-image');
                    return !image || (image.complete && image.naturalWidth === 0);
                }""")
                detail = self.page.locator(".news-detail")
                self.assertEqual(detail.locator("img.news-detail-image").count(), 0)
                self.assertEqual(detail.locator("h1").inner_text(), "이미지 오류 뉴스")
                for width in [320, 390, 768, 1440]:
                    self.page.set_viewport_size({"width": width, "height": 900})
                    self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), width)

    def test_news_detail_engagement_responsive_share_and_comments(self):
        from django.utils import timezone
        from hashlib import sha256

        link = "https://example.org/news-engagement"
        with TemporaryDirectory(dir=Path(settings.BASE_DIR) / "var") as temp_dir:
            news_db = Path(temp_dir) / "news.sqlite3"
            with sqlite3.connect(news_db) as connection:
                connection.executescript("""CREATE TABLE articles(link TEXT PRIMARY KEY,title_ko TEXT,summary_ko TEXT,summary TEXT,source TEXT,original_source TEXT,region TEXT,category TEXT,post_status TEXT,published_at TEXT,image_url TEXT);
CREATE TABLE hidden_links(link TEXT);
CREATE TABLE filter_rules(id INTEGER PRIMARY KEY,enabled INTEGER);
CREATE TABLE filter_hits(link TEXT,rule_id INTEGER);
CREATE TABLE filter_keeps(link TEXT);
CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT);""")
                connection.execute(
                    "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (link, "좋아요와 댓글 검증 기사", "검증용 요약입니다.", "Synthetic summary", "Fixture", "", "태국", "생활", "ready", timezone.now().isoformat(), ""),
                )

            with override_settings(POST_NEWS_DB=str(news_db)):
                self.context.add_init_script("window.__shareCalls=[];Object.defineProperty(navigator,'share',{configurable:true,value:async payload=>window.__shareCalls.push(payload)});")
                self.go(f"/newsroom/{sha256(link.encode()).hexdigest()}/")
                self.page.get_by_role("button", name="좋아요 0", exact=False).click()
                self.page.wait_for_load_state("networkidle")
                self.assertEqual(self.page.get_by_role("button", name="♥ 좋아요 1").get_attribute("aria-pressed"), "true")
                self.page.get_by_role("button", name="공유하기").click()
                self.assertEqual(self.page.evaluate("window.__shareCalls[0].title"), "좋아요와 댓글 검증 기사")
                self.assertEqual(self.page.evaluate("window.__shareCalls[0].url"), self.page.url)
                self.page.locator("#id_news_comment_body").fill("브라우저에서 저장하는 기사 댓글입니다.")
                self.page.get_by_role("button", name="댓글 등록").click()
                self.page.wait_for_load_state("networkidle")
                self.assertIn("브라우저에서 저장하는 기사 댓글입니다.", self.page.locator(".news-comments").inner_text())
                self.page.screenshot(path=str(self.output / "news-engagement-1440.png"), full_page=True)
                for width in [320, 390, 768, 1440]:
                    self.page.set_viewport_size({"width": width, "height": 900})
                    layout = self.page.evaluate("""() => {
                        const rect = selector => {
                            const element = document.querySelector(selector);
                            if (!element) return null;
                            const box = element.getBoundingClientRect();
                            return {x: box.x, width: box.width};
                        };
                        const controls = [...document.querySelectorAll('[data-news-actions] .btn')];
                        return {
                            article: rect('.news-detail'),
                            comments: rect('.news-comments'),
                            controls: controls.map(element => {
                                const box = element.getBoundingClientRect();
                                return {x: box.x, y: box.y, width: box.width};
                            }),
                            scrollWidth: document.documentElement.scrollWidth
                        };
                    }""")
                    self.assertTrue(layout["article"] and layout["comments"], width)
                    self.assertAlmostEqual(layout["article"]["x"], layout["comments"]["x"], delta=1, msg=f"article/comment alignment at {width}px")
                    self.assertAlmostEqual(layout["article"]["width"], layout["comments"]["width"], delta=1, msg=f"article/comment width at {width}px")
                    self.assertEqual(len(layout["controls"]), 4, f"action controls at {width}px")
                    rows = {round(control["y"]) for control in layout["controls"]}
                    self.assertLessEqual(len(rows), 2, f"action rows at {width}px")
                    self.assertLessEqual(layout["scrollWidth"], width + 1, width)
                    if width == 390:
                        self.page.screenshot(path=str(self.output / "news-engagement-390.png"), full_page=True)
                self.assertEqual(self.errors, [])

    def test_video_uses_static_poster_in_list_and_player_in_detail(self):
        from django.utils import timezone
        from hashlib import sha256

        link = "https://example.org/video-story"
        poster = "https://images.example.test/video-poster.png"
        video = "https://video.example.test/video-story.mp4"
        with TemporaryDirectory(dir=Path(settings.BASE_DIR) / "var") as temp_dir:
            news_db = Path(temp_dir) / "news.sqlite3"
            with sqlite3.connect(news_db) as connection:
                connection.executescript("""CREATE TABLE articles(link TEXT PRIMARY KEY,title_ko TEXT,summary_ko TEXT,summary TEXT,source TEXT,original_source TEXT,region TEXT,category TEXT,post_status TEXT,published_at TEXT,image_url TEXT,video_url TEXT);
CREATE TABLE hidden_links(link TEXT);
CREATE TABLE filter_rules(id INTEGER PRIMARY KEY,enabled INTEGER);
CREATE TABLE filter_hits(link TEXT,rule_id INTEGER);
CREATE TABLE filter_keeps(link TEXT);
CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT);""")
                connection.execute(
                    "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (link, "동영상 검증 기사", "검증용 요약입니다.", "Synthetic summary", "Fixture", "", "태국", "생활", "ready", timezone.now().isoformat(), poster, video),
                )

            with override_settings(POST_NEWS_DB=str(news_db)):
                self.page.route(
                    "https://images.example.test/**",
                    lambda route: route.fulfill(
                        status=200,
                        content_type="image/svg+xml",
                        body='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"><rect width="640" height="360" fill="#173c5c"/><path d="M0 280 640 80v280H0" fill="#286e7d"/><text x="32" y="330" fill="#ffffff" font-size="18" font-family="sans-serif">SYNTHETIC VIDEO POSTER</text></svg>',
                    ),
                )
                self.go("/newsroom/")
                card = self.page.locator(".news-item").filter(has_text="동영상 검증 기사")
                self.assertEqual(card.locator("img.news-image").get_attribute("src"), poster)
                self.assertEqual(card.locator("video").count(), 0)
                self.assertTrue(card.locator(".video-badge").is_visible())
                self.page.screenshot(path=str(self.output / "video-news-list-1440.png"), full_page=True)

                self.go(f"/newsroom/{sha256(link.encode()).hexdigest()}/")
                player = self.page.locator("video.news-video-player")
                self.assertEqual(player.count(), 1)
                self.assertIsNotNone(player.get_attribute("controls"))
                self.assertEqual(player.get_attribute("preload"), "none")
                self.assertEqual(player.get_attribute("poster"), poster)
                self.assertEqual(player.locator("source").get_attribute("src"), video)
                self.page.screenshot(path=str(self.output / "video-news-detail-1440.png"), full_page=True)
                for width in [320, 390, 768, 1440]:
                    self.page.set_viewport_size({"width": width, "height": 900})
                    self.assertTrue(self.page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), width)
                self.assertEqual(self.errors, [])
