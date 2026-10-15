import json
import os
from pathlib import Path
from unittest import skipUnless
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import sync_playwright
from .models import Post

@skipUnless(os.environ.get("POST_RUN_BROWSER_TESTS") == "1", "Explicit browser test opt-in required")
class BrowserFlowTests(StaticLiveServerTestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="브라우저검증")
        self.post = Post.objects.create(author=self.member, title="브라우저 검증용 첫 생활 질문", body="실제 개인정보를 포함하지 않은 브라우저 검증용 게시글입니다. 목록 이동과 서버 저장을 확인합니다.", region="bangkok", category="housing")
        self.client.force_login(self.member)
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
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.output = Path(settings.BASE_DIR) / "var" / "browser"
        self.output.mkdir(parents=True, exist_ok=True)
    def tearDown(self):
        self.browser.close()
        self.pw.stop()
    def go(self, path):
        return self.page.goto(self.live_server_url + path, wait_until="networkidle")
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
