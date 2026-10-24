"""All identities/emails in this module are synthetic. No provider requests."""
import logging
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from community.models import Post
from config.adapters import GoogleOnlyAdapter
from .models import EmailChallenge, MemberProfile
from .middleware import AuthLogFilter

@override_settings(POST_AUTH_EMAIL_ENABLED=True,POST_SIGNUP_ENABLED=True,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='auth@example.com',POST_PUBLIC_ORIGIN='https://preview.example.com')
class MemberTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox=[]
    def issue(self,email='member@example.com'):
        result=self.client.post('/accounts/email/',{'email':email})
        self.assertEqual(result.status_code,302)
        self.assertTrue(bool(mail.outbox))
        link=next(line for line in mail.outbox[-1].body.splitlines() if line.startswith('https://'))
        url=urlsplit(link)
        self.assertEqual(url.netloc,'preview.example.com')
        self.assertFalse(bool(url.query))
        values=parse_qs(url.fragment)
        return {'challenge':values['id'][0],'token':values['token'][0]}
    def verify(self,email='member@example.com'):
        payload=self.issue(email)
        response=self.client.post('/accounts/email/confirm/',payload)
        self.assertEqual(response.status_code,302)
        return payload,get_user_model().objects.get(email=email.casefold())
    def onboard(self,nickname='테스트이웃'):
        return self.client.post('/accounts/onboarding/',{'nickname':nickname,'terms':'on','privacy':'on'})
    def social(self,email='google@example.com',verified=True):
        return SocialLogin(user=get_user_model()(username='google_fixture',email=email),account=SocialAccount(provider='google',uid='fixture-google-sub'),email_addresses=[EmailAddress(email=email,verified=verified,primary=True)])
    def test_login_route_shows_email_password_form_and_method_options(self):
        response=self.client.get('/accounts/login/')
        self.assertContains(response,'name="login"')
        self.assertContains(response,'name="password"')
        self.assertContains(response,'이메일 인증 링크로 로그인')
        self.assertEqual(self.client.post('/accounts/login/',{'login':'a@example.com','password':'invalid'}).status_code,200)
        options=self.client.get('/accounts/login/options/')
        self.assertContains(options,'이메일 인증 링크로 가입·로그인')
        self.assertContains(options,'Google로 계속하기')
        self.assertEqual(self.client.get('/accounts/password/reset/').status_code,403)
    def test_email_member_can_set_password_after_magic_link_then_login(self):
        _,user=self.verify()
        self.onboard()
        self.assertFalse(user.has_usable_password())
        self.assertContains(self.client.get('/accounts/profile/'),'비밀번호 설정')
        response=self.client.get('/accounts/password/set/')
        self.assertEqual(response.status_code,200)
        response=self.client.post('/accounts/password/set/',{'password1':'Valid-new-passphrase-742!','password2':'Valid-new-passphrase-742!'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,'/accounts/profile/')
        user.refresh_from_db()
        self.assertTrue(user.check_password('Valid-new-passphrase-742!'))
        self.client.logout()
        response=self.client.post('/accounts/login/',{'login':'member@example.com','password':'Valid-new-passphrase-742!'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,'/accounts/profile/')
        self.assertIn('_auth_user_id',self.client.session)
    def test_email_verify_onboard_real_write_logout_login(self):
        payload,user=self.verify()
        self.assertFalse(user.has_usable_password())
        self.assertTrue(EmailAddress.objects.get(user=user).verified)
        self.assertFalse(user.membership.is_complete)
        post={'title':'인증된 회원이 작성하는 테스트 질문','body':'실제 개인정보가 없는 테스트 질문입니다. 가입 절차와 권한 연결을 검증하는 내용입니다.','region':'bangkok','category':'living','privacy':'on'}
        self.assertEqual(self.client.post('/community/new/',post).status_code,403)
        self.assertEqual(Post.objects.count(),0)
        self.assertEqual(self.onboard().status_code,302)
        user.refresh_from_db()
        profile=MemberProfile.objects.get(user=user)
        self.assertTrue(profile.is_complete)
        self.assertEqual(user.username,'테스트이웃')
        self.assertEqual(profile.terms_version,settings.POST_TERMS_VERSION)
        self.assertEqual(profile.privacy_version,settings.POST_PRIVACY_VERSION)
        self.assertEqual(self.client.post('/community/new/',post).status_code,302)
        self.assertEqual(Post.objects.get().author_id,user.pk)
        self.assertEqual(self.client.post('/accounts/logout/').status_code,302)
        cache.clear()
        self.verify()
        self.assertEqual(get_user_model().objects.count(),1)
        self.assertEqual(self.client.get('/accounts/profile/').status_code,200)
    def test_expiry_replay_modified_and_cross_browser_rejected(self):
        payload=self.issue()
        other=Client()
        self.assertEqual(other.post('/accounts/email/confirm/',payload).status_code,400)
        self.assertEqual(self.client.post('/accounts/email/confirm/',{**payload,'token':payload['token']+'x'}).status_code,400)
        self.assertEqual(self.client.post('/accounts/email/confirm/',payload).status_code,302)
        self.assertEqual(self.client.post('/accounts/email/confirm/',payload).status_code,400)
        self.client.logout()
        cache.clear()
        payload=self.issue()
        EmailChallenge.objects.filter(pk=payload['challenge']).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.post('/accounts/email/confirm/',payload).status_code,400)
    def test_get_does_not_consume_token_or_login(self):
        payload=self.issue()
        self.assertEqual(self.client.get('/accounts/email/confirm/').status_code,200)
        self.assertIsNone(EmailChallenge.objects.get().used_at)
        self.assertNotIn('_auth_user_id',self.client.session)
        self.assertEqual(self.client.post('/accounts/email/confirm/',payload).status_code,302)
    def test_rate_limit_uniform_response_and_old_link_still_works(self):
        payload=self.issue()
        before=len(mail.outbox)
        response=self.client.post('/accounts/email/',{'email':'member@example.com'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(len(mail.outbox),before)
        self.assertEqual(self.client.post('/accounts/email/confirm/',payload).status_code,302)
    def test_google_only_account_never_gains_email_login_implicitly(self):
        user=get_user_model().objects.create_user(username='google',email='member@example.com')
        profile=MemberProfile.objects.create(user=user,email_key=user.email,email_login_enabled=False,email_verified_at=timezone.now())
        SocialAccount.objects.create(user=user,provider='google',uid='fixture-sub')
        result=self.client.post('/accounts/email/',{'email':'member@example.com'})
        self.assertEqual(result.status_code,302)
        self.assertEqual(len(mail.outbox),0)
        self.assertEqual(EmailChallenge.objects.count(),0)
        profile.refresh_from_db()
        self.assertFalse(profile.email_login_enabled)
    def test_google_only_account_cannot_set_or_use_email_password(self):
        user=get_user_model().objects.create_user(username='google',email='google@example.com')
        user.set_password('Valid-new-passphrase-742!')
        user.save(update_fields=['password'])
        MemberProfile.objects.create(user=user,email_key=user.email,email_login_enabled=False,email_verified_at=timezone.now())
        SocialAccount.objects.create(user=user,provider='google',uid='fixture-sub')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/accounts/password/set/').status_code,403)
        self.client.logout()
        response=self.client.post('/accounts/password/login/',{'login':'google@example.com','password':'Valid-new-passphrase-742!'})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('_auth_user_id',self.client.session)
    def test_google_does_not_link_existing_email_account(self):
        self.verify()
        adapter=GoogleOnlyAdapter()
        request=self.client.get('/accounts/email/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse) as error:
            adapter.pre_social_login(request,self.social('member@example.com'))
        self.assertEqual(error.exception.response.status_code,409)
        self.assertEqual(SocialAccount.objects.count(),0)
    @override_settings(GOOGLE_CONFIGURED=True)
    def test_new_google_account_has_private_email_and_needs_onboarding(self):
        adapter=GoogleOnlyAdapter()
        social=self.social()
        request=self.client.get('/accounts/email/').wsgi_request
        adapter.pre_social_login(request,social)
        self.assertTrue(adapter.is_open_for_signup(request,social))
        user=adapter.save_user(request,social)
        self.assertEqual(user.membership.email_key,'google@example.com')
        self.assertFalse(user.membership.email_login_enabled)
        self.assertFalse(user.membership.is_complete)
        self.assertIsNotNone(user.membership.email_verified_at)
    def test_unverified_google_email_and_connect_are_denied(self):
        adapter=GoogleOnlyAdapter()
        request=self.client.get('/accounts/email/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse):adapter.pre_social_login(request,self.social(verified=False))
        social=self.social()
        social.state['process']='connect'
        with self.assertRaises(ImmediateHttpResponse):adapter.pre_social_login(request,social)
    def test_consent_and_nickname_are_required_and_unique(self):
        _,user=self.verify()
        response=self.client.post('/accounts/onboarding/',{'nickname':'이웃하나','terms':'on'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(MemberProfile.objects.get(user=user).is_complete)
        self.assertEqual(self.onboard('이웃하나').status_code,302)
        self.client.logout()
        cache.clear()
        _,other=self.verify('other@example.com')
        self.assertEqual(self.onboard('이웃하나').status_code,200)
        self.assertFalse(MemberProfile.objects.get(user=other).is_complete)
        self.assertEqual(self.onboard('다른이웃').status_code,302)
    def test_csrf_and_account_pages_are_private(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/accounts/email/',{'email':'a@example.com'}).status_code,403)
        self.assertEqual(client.post('/accounts/email/confirm/',{}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/me/').status_code,403)
        _,user=self.verify()
        self.onboard()
        response=self.client.get('/api/v1/me/')
        self.assertEqual(response.json()['email'],'member@example.com')
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertNotContains(Client().get('/community/'),'member@example.com')
        self.assertNotContains(Client().get('/accounts/login/'),'member@example.com')
    def test_email_disabled_and_policy_unapproved_are_not_fake_success(self):
        with override_settings(POST_AUTH_EMAIL_ENABLED=False):
            self.assertEqual(self.client.post('/accounts/email/',{'email':'a@example.com'}).status_code,503)
        self.assertEqual(get_user_model().objects.count(),0)
        self.verify()
        with override_settings(POST_SIGNUP_ENABLED=False):
            self.assertEqual(self.onboard().status_code,200)
        self.assertFalse(MemberProfile.objects.get().is_complete)
        self.assertContains(self.client.get('/accounts/policy/privacy/'),'개발 검토용 초안')
    def test_delivery_error_invalidates_challenge_without_leaking_account(self):
        with patch('members.services.send_mail',side_effect=SMTPException('fixture failure')):
            response=self.client.post('/accounts/email/',{'email':'member@example.com'})
        self.assertEqual(response.status_code,302)
        self.assertIsNotNone(EmailChallenge.objects.get().used_at)
    def test_source_email_change_or_inactive_user_invalidates_link(self):
        payload=self.issue()
        user=get_user_model().objects.get()
        user.email='changed@example.com'
        user.save()
        self.assertEqual(self.client.post('/accounts/email/confirm/',payload).status_code,400)
        user.email='member@example.com'
        user.is_active=False
        user.save()
        self.assertEqual(self.client.post('/accounts/email/confirm/',payload).status_code,400)
    def test_no_raw_token_in_challenge_storage_or_access_log(self):
        payload=self.issue()
        challenge=EmailChallenge.objects.get()
        self.assertNotEqual(challenge.digest,payload['token'])
        record=logging.LogRecord('django.server',logging.INFO,'',1,'GET /accounts/google/login/callback/?code=fixture-code&state=fixture-state HTTP/1.1',(),None)
        AuthLogFilter().filter(record)
        self.assertNotIn('fixture-code',record.getMessage())
        self.assertIn('[REDACTED]',record.getMessage())
