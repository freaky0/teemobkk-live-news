"""Anonymous disclosures: test DB only; no email, OAuth or external requests."""
import os
from pathlib import Path
from unittest import skipUnless
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import TestCase, override_settings

# Simulate the stale preview flag; public auth screens must ignore it.
@override_settings(POST_RESTRICTED_PREVIEW=True,POST_SIGNUP_ENABLED=True,GOOGLE_CONFIGURED=False)
class AuthDisclosureTests(TestCase):
    def test_identity_and_policy_links_precede_authentication_controls(self):
        for path,control in [('/accounts/login/','class="auth-methods"'),('/accounts/email/','<form')]:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                html=response.content.decode()
                for href in ['/accounts/policy/terms/','/accounts/policy/privacy/','mailto:admin@teemobkk.io']:
                    self.assertContains(response,'href="'+href+'"')
                    self.assertLess(html.index('href="'+href+'"'),html.index(control))
                self.assertContains(response,'admin@teemobkk.io')
                self.assertNotContains(response,'freaky0@gmail.com')
                self.assertContains(response,'운영: TeemoBKK')
                self.assertContains(response,'https://teemobkk.io/about/')
        response=self.client.get('/accounts/login/')
        self.assertContains(response,'뉴스와 공개 질문은 가입 없이 읽을 수 있습니다')
        self.assertContains(response,'질문·답변·도움 반응·스크랩은 로그인 후 이용할 수 있습니다')
        self.assertContains(response,'공개 오픈 테스트')
        self.assertNotContains(response,'초대 전용')

    @override_settings(POST_POLICY_APPROVED=False,POST_SIGNUP_ENABLED=False)
    def test_email_requirements_do_not_conflict_with_sensitive_data_warning(self):
        for path in ['/accounts/login/','/accounts/email/','/accounts/email/confirm/','/accounts/policy/privacy/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                self.assertNotContains(response,'실제 개인정보나 민감한 자료를')
                self.assertContains(response,'수신 가능한 이메일 주소')
                self.assertContains(response,'신분증 번호')
                self.assertContains(response,'금융정보')
        response=self.client.get('/accounts/policy/privacy/')
        self.assertContains(response,'서비스는 이용자 편의와 안정적인 운영을 위해 쿠키 또는 브라우저 저장 기술을 사용할 수 있습니다.')
        self.assertContains(response,'개발 검토용 초안')
        self.assertContains(response,'회원가입, 로그인 및 계정 관리')

    @override_settings(POST_POLICY_APPROVED=False,POST_SIGNUP_ENABLED=False)
    def test_policy_pages_show_confirmed_responsibility_and_request_handling(self):
        for path in ['/accounts/policy/terms/','/accounts/policy/privacy/']:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'개인정보 처리 책임자: Teemobkk')
                self.assertContains(response,'문의·삭제 요청은 Teemobkk가 직접 처리')
                self.assertContains(response,'href="mailto:admin@teemobkk.io"')
                self.assertContains(response,'개발 검토용 초안')
        response=self.client.get('/accounts/policy/privacy/')
        self.assertContains(response,'Google 등 외부 계정 인증 서비스')
        self.assertContains(response,'웹사이트 호스팅 및 클라우드 서비스')
        self.assertContains(response,'외부 사이트에서 이루어지는 개인정보 처리는 해당 사이트의 개인정보처리방침에 따릅니다.')
        self.assertNotContains(response,'책임 주체')

    @override_settings(POST_POLICY_APPROVED=True,POST_SIGNUP_ENABLED=True)
    def test_approved_policy_pages_hide_draft_notice_and_use_public_documents(self):
        for path,text in [('/terms','뉴스 및 정보의 정확성'),('/privacy','태국 개인정보보호법')]:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                self.assertContains(response,text)
                self.assertNotContains(response,'개발 검토용 초안')
                self.assertNotContains(response,'[실제 사업장 또는 법령상 적절한 연락 주소 기재]')

    @override_settings(POST_POLICY_APPROVED=False,POST_SIGNUP_ENABLED=False)
    def test_unapproved_policy_pages_render_the_bundled_documents_without_opening_signup(self):
        terms=self.client.get('/accounts/policy/terms/')
        privacy=self.client.get('/accounts/policy/privacy/')
        self.assertEqual(terms.status_code,200)
        self.assertEqual(privacy.status_code,200)
        self.assertContains(terms,'서비스 이용약관')
        self.assertContains(terms,"TEEMOBKK's POST")
        self.assertContains(terms,'뉴스 및 정보의 정확성')
        self.assertContains(privacy,'개인정보처리방침')
        self.assertContains(privacy,'태국 개인정보보호법')
        self.assertContains(privacy,'개인정보의 국외 이전')
        self.assertContains(privacy,'Keith S. Jun (TeemoBKK)')
        self.assertNotContains(privacy,'[실제 사업장 또는 법령상 적절한 연락 주소 기재]')
        self.assertContains(terms,'개발 검토용 초안입니다')
        self.assertContains(privacy,'개발 검토용 초안입니다')

@skipUnless(os.environ.get('POST_RUN_BROWSER_TESTS')=='1','Browser opt-in required')
# Simulate the stale preview flag; public auth screens must ignore it.
@override_settings(POST_RESTRICTED_PREVIEW=True,POST_SIGNUP_ENABLED=True,GOOGLE_CONFIGURED=False)
class DisclosureBrowserTests(StaticLiveServerTestCase):
    def test_anonymous_can_read_notices_and_return_to_email_form(self):
        from playwright.sync_api import sync_playwright
        output=Path(__file__).resolve().parent.parent/'var'/'disclosure-browser'
        output.mkdir(parents=True,exist_ok=True)
        errors=[]
        with sync_playwright() as pw:
            launch={'headless':True,'args':['--no-sandbox']}
            if os.environ.get('POST_BROWSER_EXECUTABLE'):
                launch['executable_path']=os.environ['POST_BROWSER_EXECUTABLE']
            browser=pw.chromium.launch(**launch)
            context=browser.new_context(reduced_motion='reduce')
            page=context.new_page()
            page.on('pageerror',lambda err:errors.append(str(err)))
            # The public origin serves /favicon.ico; the isolated Django test server does not.
            page.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' and not (msg.text.startswith('Failed to load resource: the server responded with a status of 404') and msg.location.get('url')==self.live_server_url+'/favicon.ico') else None)
            for width in [320,390,1440]:
                page.set_viewport_size({'width':width,'height':950})
                for name,path in [('login','/accounts/login/'),('email','/accounts/email/')]:
                    self.assertEqual(page.goto(self.live_server_url+path,wait_until='networkidle').status,200)
                    self.assertTrue(page.locator('main .auth-disclosure').is_visible())
                    if name=='login':
                        self.assertTrue(page.get_by_text('공개 오픈 테스트',exact=True).is_visible())
                        self.assertFalse(page.get_by_text('초대 전용').count())
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    if width in [390,1440]:page.screenshot(path=str(output/f'{name}-{width}.png'),full_page=True)
                for label,heading in [('이용약관','이용약관'),('개인정보 처리방침','개인정보 처리방침')]:
                    page.locator('main .auth-disclosure').get_by_role('link',name=label,exact=True).click()
                    self.assertEqual(page.locator('h1').inner_text(),heading)
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    page.go_back(wait_until='networkidle')
                    self.assertTrue(page.locator('#id_email').is_visible())
            self.assertEqual(context.request.get(self.live_server_url+'/api/v1/posts/').status,200)
            self.assertEqual(errors,[])
            browser.close()
