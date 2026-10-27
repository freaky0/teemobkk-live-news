"""Real browser + Django test DB + in-memory mail. Never sends external email."""
import json
import os
from pathlib import Path
from unittest import skipUnless
from urllib.parse import urlsplit
from django.core import mail
from django.core.cache import cache
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright
from members.tests_google_preview import GOOGLE_FIXTURE

@skipUnless(os.environ.get('POST_RUN_BROWSER_TESTS')=='1','Browser opt-in required')
@override_settings(POST_AUTH_EMAIL_ENABLED=True,POST_SIGNUP_ENABLED=True,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='auth@example.com',POST_PUBLIC_ORIGIN='https://preview.example.com')
class MembershipBrowserTests(StaticLiveServerTestCase):
    @override_settings(GOOGLE_CONFIGURED=True,SOCIALACCOUNT_PROVIDERS=GOOGLE_FIXTURE)
    def test_passwordless_signup_consent_profile_and_write(self):
        cache.clear()
        mail.outbox=[]
        output=Path(__file__).resolve().parent.parent/'var'/'auth-browser'
        output.mkdir(parents=True,exist_ok=True)
        views=[]
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
            for width in [320,390,768,1024,1440]:
                page.set_viewport_size({'width':width,'height':950})
                for name,path in [('choices','/accounts/login/options/'),('password-login','/accounts/login/'),('email','/accounts/email/')]:
                    self.assertEqual(page.goto(self.live_server_url+path,wait_until='networkidle').status,200)
                    self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    if width in [390,1440]:
                        page.screenshot(path=str(output/f'{name}-{width}.png'),full_page=True)
                    views.append({'width':width,'state':name})
            page.set_viewport_size({'width':1440,'height':950})
            page.goto(self.live_server_url+'/community/?category=housing',wait_until='networkidle')
            page.locator('header a').get_by_text('로그인',exact=True).click()
            page.get_by_role('link',name='이메일 인증 링크로 로그인').click()
            page.locator('#id_email').fill('browser-check@example.com')
            with page.expect_response(lambda response: response.request.method=='POST') as submitted:
                page.get_by_role('button',name='인증 메일 받기',exact=True).click()
            self.assertEqual(submitted.value.status,302,page.locator('body').inner_text()[:600])
            page.wait_for_url('**/accounts/email/sent/')
            self.assertTrue(bool(mail.outbox))
            link=next(line for line in mail.outbox[-1].body.splitlines() if line.startswith('https://'))
            fragment=urlsplit(link).fragment
            # Keep fixture token inside this test server and browser session.
            page.goto(self.live_server_url+'/accounts/email/confirm/#'+fragment,wait_until='networkidle')
            self.assertNotIn('#',page.url)
            self.assertTrue(page.get_by_role('button',name='이메일 인증하고 계속하기').is_enabled())
            page.get_by_role('button',name='이메일 인증하고 계속하기').click()
            page.wait_for_url('**/accounts/onboarding/')
            self.assertIn('browser-check@example.com',page.locator('.auth-verified').inner_text())
            for width in [320,390,768,1024,1440]:
                page.set_viewport_size({'width':width,'height':950})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                if width in [390,1440]:page.screenshot(path=str(output/f'onboarding-{width}.png'),full_page=True)
                views.append({'width':width,'state':'onboarding'})
            page.set_viewport_size({'width':390,'height':950})
            page.locator('#id_nickname').fill('가입검증이웃')
            page.locator('#id_terms').check()
            page.locator('#id_privacy').check()
            page.get_by_role('button',name='가입 마치기').click()
            page.wait_for_url('**/community/?category=housing')
            page.goto(self.live_server_url+'/accounts/profile/',wait_until='networkidle')
            self.assertIn('가입검증이웃',page.locator('h1').inner_text())
            from members.tests_profile_image import PNG
            page.locator('#profile-image').set_input_files({'name': 'photo.png', 'mimeType': 'image/png', 'buffer': PNG})
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/accounts/profile/image/')) as upload:
                page.get_by_role('button', name='사진 저장', exact=True).click()
            self.assertEqual(upload.value.status, 302)
            page.wait_for_load_state('networkidle')
            self.assertTrue(page.get_by_alt_text('내 프로필 사진').is_visible())
            self.assertTrue(page.get_by_alt_text('내 프로필 사진').evaluate('(img) => img.complete && img.naturalWidth > 0'))
            page.screenshot(path=str(output/'profile-photo-390.png'), full_page=True)
            page.get_by_role('button', name='사진 삭제', exact=True).click()
            page.wait_for_load_state('networkidle')
            self.assertEqual(page.get_by_alt_text('내 프로필 사진').count(), 0)
            page.locator('#id_avatar').select_option('cat')
            page.get_by_role('button', name='아이콘 저장', exact=True).click()
            page.wait_for_load_state('networkidle')
            self.assertIn('🐱', page.locator('h1').inner_text())
            answer_email_toggle=page.get_by_label('답변 알림 이메일 받기')
            self.assertFalse(answer_email_toggle.is_checked())
            self.assertIn('답변 내용은 이메일에 포함하지 않습니다.',page.get_by_role('region',name='질문 답변 알림').inner_text())
            mail_count=len(mail.outbox)
            answer_email_toggle.check()
            with page.expect_response(lambda response: response.request.method=='POST' and '/accounts/profile/' in response.url):
                page.get_by_role('button',name='알림 설정 저장',exact=True).click()
            page.wait_for_load_state('networkidle')
            self.assertTrue(page.get_by_label('답변 알림 이메일 받기').is_checked())
            page.get_by_label('답변 알림 이메일 받기').uncheck()
            with page.expect_response(lambda response: response.request.method=='POST' and '/accounts/profile/' in response.url):
                page.get_by_role('button',name='알림 설정 저장',exact=True).click()
            page.wait_for_load_state('networkidle')
            self.assertFalse(page.get_by_label('답변 알림 이메일 받기').is_checked())
            self.assertEqual(len(mail.outbox),mail_count)
            for width in [320,390,768,1440]:
                page.set_viewport_size({'width':width,'height':950})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),f'profile overflow at {width}px')
            page.set_viewport_size({'width':390,'height':950})
            self.assertTrue(page.get_by_role('button',name='Google 계정 연결',exact=True).is_visible())
            page.get_by_role('link',name='비밀번호 설정',exact=True).click()
            page.wait_for_url('**/accounts/password/set/')
            page.locator('#id_password1').fill('Browser-test-passphrase-817!')
            page.locator('#id_password2').fill('Browser-test-passphrase-817!')
            with page.expect_response(lambda response: response.request.method=='POST' and '/accounts/password/set/' in response.url) as password_submit:
                page.get_by_role('button',name='비밀번호 저장',exact=True).click()
            self.assertEqual(password_submit.value.status,302,page.locator('body').inner_text()[:600])
            page.wait_for_url('**/accounts/profile/')
            self.assertNotIn('비밀번호 설정',page.locator('body').inner_text())
            page.screenshot(path=str(output/'profile-390.png'),full_page=True)
            response=context.request.get(self.live_server_url+'/api/v1/me/')
            self.assertTrue(response.json()['onboarding_complete'])
            self.assertEqual(response.json()['email'],'browser-check@example.com')
            page.get_by_role('link',name='질문 쓰기',exact=True).first.click()
            page.wait_for_url('**/community/new/')
            page.locator('#id_title').fill('이메일 가입 후 작성하는 브라우저 검증 질문')
            page.locator('#id_body').fill('실제 회원정보가 아닌 테스트 회원으로 가입과 글쓰기를 검증하는 내용입니다. 외부 메일을 발송하지 않습니다.')
            page.locator('#id_privacy').check()
            page.get_by_role('button',name='질문 등록').click()
            page.wait_for_url('**/community/*/')
            self.assertIn('이메일 가입 후 작성',page.locator('h1').inner_text())
            anonymous=browser.new_context()
            another=anonymous.new_page()
            another.goto(page.url,wait_until='networkidle')
            self.assertNotIn('browser-check@example.com',another.locator('body').inner_text())
            self.assertEqual(anonymous.request.get(self.live_server_url+'/api/v1/me/').status,403)
            anonymous.close()
            page.get_by_role('link',name='로그아웃',exact=True).first.click()
            page.get_by_role('button',name='로그아웃',exact=True).click()
            page.wait_for_url(self.live_server_url+'/')
            self.assertEqual(context.request.get(self.live_server_url+'/api/v1/me/').status,403)
            page.goto(self.live_server_url+'/accounts/login/',wait_until='networkidle')
            page.locator('#id_login').fill('browser-check@example.com')
            page.locator('#id_password').fill('Browser-test-passphrase-817!')
            page.get_by_role('button',name='로그인',exact=True).click()
            page.wait_for_url(self.live_server_url+'/')
            page.goto(self.live_server_url+'/accounts/profile/',wait_until='networkidle')
            self.assertIn('가입검증이웃',page.locator('h1').inner_text())
            page.locator('#id_nickname').fill('브라우저새이름')
            page.get_by_role('button',name='닉네임 저장').click()
            self.assertIn('브라우저새이름',page.locator('h1').inner_text())
            page.locator('#id_nickname').fill('변경차단검증')
            page.get_by_role('button',name='닉네임 저장').click()
            self.assertIn('브라우저새이름',page.locator('h1').inner_text())
            page.locator('#id_avatar').select_option('cat')
            page.get_by_role('button',name='아이콘 저장').click()
            self.assertIn('🐱',page.locator('h1').inner_text())
            page.get_by_role('link',name='로그아웃',exact=True).first.click()
            page.get_by_role('button',name='로그아웃',exact=True).click()
            page.wait_for_url(self.live_server_url+'/')
            self.assertEqual(context.request.get(self.live_server_url+'/api/v1/me/').status,403)
            self.assertEqual(errors,[])
            browser.close()
        (output/'results.json').write_text(json.dumps({'mail_backend':'in-memory test only','external_google_login':'NOT_TESTED','external_email_delivery':'NOT_TESTED','views':views,'signup_consent_write_logout':'PASS','console_errors':errors},ensure_ascii=False,indent=2))

    def test_header_theme_toggle_persists_across_reload(self):
        errors=[]
        output=Path(os.environ.get('POST_BROWSER_CAPTURE_DIR',Path(__file__).resolve().parent.parent/'var'/'theme-browser'))
        output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            launch={'headless':True,'args':['--no-sandbox']}
            if os.environ.get('POST_BROWSER_EXECUTABLE'):
                launch['executable_path']=os.environ['POST_BROWSER_EXECUTABLE']
            browser=pw.chromium.launch(**launch)
            page=browser.new_page(color_scheme='light')
            page.on('pageerror',lambda err:errors.append(str(err)))
            self.assertEqual(page.goto(self.live_server_url+'/',wait_until='networkidle').status,200)
            for width in [320,390,768,1024,1440]:
                page.set_viewport_size({'width':width,'height':900})
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),f'horizontal overflow at {width}px')
                if width==320:page.screenshot(path=str(output/'header-mobile-light.png'),clip={'x':0,'y':0,'width':320,'height':120})
            self.assertTrue(page.locator('[data-theme-icon="moon"]').is_visible())
            page.screenshot(path=str(output/'header-light.png'),clip={'x':0,'y':0,'width':1440,'height':120})
            page.screenshot(path=str(output/'theme-light.png'),full_page=True)
            page.get_by_role('button',name='다크 모드로 전환').click()
            page.wait_for_function("document.documentElement.dataset.theme === 'dark'")
            self.assertEqual(page.get_by_role('button',name='라이트 모드로 전환').get_attribute('aria-pressed'),'true')
            self.assertTrue(page.locator('[data-theme-icon="sun"]').is_visible())
            self.assertEqual(page.locator('.header .notice').count(),0)
            dark_bg=page.locator('body').evaluate('(e)=>getComputedStyle(e).backgroundColor')
            page.screenshot(path=str(output/'header-dark.png'),clip={'x':0,'y':0,'width':1440,'height':120})
            page.screenshot(path=str(output/'theme-dark.png'),full_page=True)
            page.reload(wait_until='networkidle')
            page.wait_for_function("document.documentElement.dataset.theme === 'dark'")
            self.assertEqual(page.get_by_role('button',name='라이트 모드로 전환').count(),1)
            page.get_by_role('button',name='라이트 모드로 전환').click()
            page.wait_for_function("document.documentElement.dataset.theme === 'light'")
            light_bg=page.locator('body').evaluate('(e)=>getComputedStyle(e).backgroundColor')
            self.assertNotEqual(dark_bg,light_bg)
            self.assertEqual(errors,[])
            browser.close()
