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
        self.post = Post.objects.create(author=self.member, title="브라우저 검증용 첫 생활 질문", body="실제 개인정보를 포함하지 않은 브라우저 검증용 게시글입니다. 목록 이동과 서버 저장을 확인합니다.", region="bangkok", category="housing")
        if self._testMethodName == 'test_reply_mobile_keyboard_and_submission':
            Comment.objects.create(post=self.post, author=self.member, body='기존 답변 내용입니다.')
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
            self.assertEqual(self.page.locator('header .header-icon').get_attribute('href'), '/community/notifications/')
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
