"""Google OAuth boundary tests; fixture credentials, no real provider traffic."""
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount,SocialLogin
from members.models import MemberProfile

GOOGLE_FIXTURE={
    'google': {
        **settings.SOCIALACCOUNT_PROVIDERS['google'],
        'APP': {'client_id':'fixture-web-client.apps.googleusercontent.com','secret':'fixture-only-not-a-real-secret','key':''},
    }
}

@override_settings(
    GOOGLE_CONFIGURED=True,
    POST_RESTRICTED_PREVIEW=True,
    POST_PREVIEW_ALLOWED_EMAILS=frozenset({'invited@example.invalid'}),
    POST_SIGNUP_ENABLED=True,
    MIDDLEWARE=[*settings.MIDDLEWARE,'members.preview.RestrictedPreviewMiddleware'],
    SOCIALACCOUNT_PROVIDERS=GOOGLE_FIXTURE,
)
class GooglePreviewFlowTests(TestCase):
    def test_csrf_protected_google_start_reaches_google_with_pkce(self):
        client=Client(enforce_csrf_checks=True)
        client.get('/accounts/login/')
        self.assertEqual(client.post('/accounts/google/login/').status_code,403)
        token=client.cookies['csrftoken'].value
        response=client.post('/accounts/google/login/',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,302)
        target=urlsplit(response['Location'])
        self.assertEqual(target.hostname,'accounts.google.com')
        params=parse_qs(target.query)
        self.assertEqual(params['code_challenge_method'],['S256'])
        self.assertTrue(params['code_challenge'][0])
        self.assertTrue(params['state'][0])
        self.assertEqual(urlsplit(params['redirect_uri'][0]).path,'/accounts/google/login/callback/')
        self.assertEqual(set(params['scope'][0].split()),{'openid','email'})
        self.assertEqual(params['access_type'],['online'])

    def test_callback_reaches_allauth_but_invalid_state_never_calls_google(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No real Google traffic permitted')):
            response=self.client.get('/accounts/google/login/callback/',{'state':'invalid-test-state','code':'fixture-not-a-real-code'})
        self.assertEqual(response.status_code,401)
        self.assertTemplateUsed(response,'socialaccount/authentication_error.html')
        self.assertNotIn('_auth_user_id',self.client.session)

    def social(self,email='invited@example.invalid',verified=True,user=None,account=None):
        from django.contrib.auth import get_user_model
        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount,SocialLogin
        user=user or get_user_model()(email=email)
        account=account or SocialAccount(provider='google',uid='fixture-google-sub',user=user)
        return SocialLogin(user=user,account=account,email_addresses=[EmailAddress(email=email,verified=verified,primary=True)])

    def test_uninvited_google_identity_cannot_sign_up(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.contrib.auth import get_user_model
        social=self.social('uninvited@example.invalid')
        adapter=GoogleOnlyAdapter()
        request=self.client.get('/accounts/login/').wsgi_request
        self.assertFalse(adapter.is_open_for_signup(request,social))
        with self.assertRaises(ImmediateHttpResponse) as error:
            adapter.pre_social_login(request,social)
        self.assertEqual(error.exception.response.status_code,403)
        self.assertEqual(get_user_model().objects.count(),0)

    def test_invited_verified_google_signup_creates_incomplete_private_profile(self):
        from config.adapters import GoogleOnlyAdapter
        adapter=GoogleOnlyAdapter()
        social=self.social()
        request=self.client.get('/accounts/login/').wsgi_request
        self.assertTrue(adapter.is_open_for_signup(request,social))
        adapter.pre_social_login(request,social)
        user=adapter.save_user(request,social)
        self.assertEqual(user.membership.email_key,'invited@example.invalid')
        self.assertIsNotNone(user.membership.email_verified_at)
        self.assertFalse(user.membership.email_login_enabled)
        self.assertFalse(user.membership.is_complete)

    def test_unverified_invited_google_email_is_not_allowed(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        adapter=GoogleOnlyAdapter()
        social=self.social(verified=False)
        request=self.client.get('/accounts/login/').wsgi_request
        self.assertFalse(adapter.is_open_for_signup(request,social))
        with self.assertRaises(ImmediateHttpResponse) as error:
            adapter.pre_social_login(request,social)
        self.assertEqual(error.exception.response.status_code,403)

    def test_existing_google_accounts_still_require_invitation(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.contrib.auth import get_user_model
        from allauth.socialaccount.models import SocialAccount
        adapter=GoogleOnlyAdapter()
        request=self.client.get('/accounts/login/').wsgi_request
        for index,email in enumerate(['invited@example.invalid','other@example.invalid']):
            user=get_user_model().objects.create_user(username='fixture'+str(index),email=email)
            account=SocialAccount.objects.create(user=user,provider='google',uid='fixture-sub-'+str(index))
            social=self.social(email,user=user,account=account)
            self.assertTrue(social.is_existing)
            if index==0:
                adapter.pre_social_login(request,social)
            else:
                with self.assertRaises(ImmediateHttpResponse) as error:
                    adapter.pre_social_login(request,social)
                self.assertEqual(error.exception.response.status_code,403)

    def test_existing_email_account_is_never_automatically_linked(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.contrib.auth import get_user_model
        from allauth.socialaccount.models import SocialAccount
        user=get_user_model().objects.create_user(username='email-member',email='invited@example.invalid')
        social=self.social()
        request=self.client.get('/accounts/login/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse) as error:
            GoogleOnlyAdapter().pre_social_login(request,social)
        self.assertEqual(error.exception.response.status_code,409)
        self.assertIn('Google 로그인을 완료하지 못했습니다.',error.exception.response.content.decode())
        self.assertIn('이메일 링크로 로그인한 뒤 내 계정에서',error.exception.response.content.decode())
        self.assertEqual(SocialAccount.objects.count(),0)
        self.assertEqual(get_user_model().objects.get().pk,user.pk)

    def email_member(self,email='invited@example.invalid',email_login_enabled=True):
        user=get_user_model().objects.create_user(username='email-member',email=email)
        MemberProfile.objects.create(user=user,email_key=email,email_login_enabled=email_login_enabled,email_verified_at=timezone.now())
        EmailAddress.objects.create(user=user,email=email,verified=True,primary=True)
        self.client.force_login(user,backend='sesame.backends.ModelBackend')
        return user

    def test_explicit_connect_accepts_authenticated_matching_verified_email_member(self):
        from config.adapters import GoogleOnlyAdapter
        from members.models import MemberProfile
        user=self.email_member()
        social=self.social(user=user)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        GoogleOnlyAdapter().pre_social_login(request,social)
        self.assertEqual(MemberProfile.objects.get(user=user).email_key,'invited@example.invalid')

    def test_explicit_connect_rejects_unverified_google_email(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        user=self.email_member()
        social=self.social(user=user,verified=False)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse) as error:
            GoogleOnlyAdapter().pre_social_login(request,social)
        self.assertEqual(error.exception.response.status_code,403)

    def test_explicit_connect_requires_a_current_verified_email_record(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        user=self.email_member()
        EmailAddress.objects.filter(user=user).delete()
        social=self.social(user=user)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse):
            GoogleOnlyAdapter().pre_social_login(request,social)

    def test_explicit_connect_rejects_mismatching_google_email(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        user=self.email_member()
        social=self.social('different@example.invalid',user=user)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse) as error:
            GoogleOnlyAdapter().pre_social_login(request,social)
        self.assertEqual(error.exception.response.status_code,403)
        self.assertIn('Google 계정을 연결하지 못했습니다.',error.exception.response.content.decode())

    def test_explicit_connect_rejects_anonymous_and_google_only_accounts(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        adapter=GoogleOnlyAdapter()
        anonymous_social=self.social()
        anonymous_social.state['process']='connect'
        anonymous_request=self.client.get('/accounts/login/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse):
            adapter.pre_social_login(anonymous_request,anonymous_social)

        user=self.email_member(email_login_enabled=False)
        social=self.social(user=user)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse):
            adapter.pre_social_login(request,social)

    def test_explicit_connect_never_moves_google_identity_from_another_user(self):
        from config.adapters import GoogleOnlyAdapter
        from allauth.core.exceptions import ImmediateHttpResponse
        from django.contrib.auth import get_user_model
        target=self.email_member()
        other=get_user_model().objects.create_user(username='other-google-owner',email='invited@example.invalid')
        account=SocialAccount.objects.create(user=other,provider='google',uid='fixture-google-sub')
        social=self.social(user=other,account=account)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        with self.assertRaises(ImmediateHttpResponse):
            GoogleOnlyAdapter().pre_social_login(request,social)
        account.refresh_from_db()
        self.assertEqual(account.user_id,other.pk)
        self.assertNotEqual(account.user_id,target.pk)

    def test_allauth_sociallogin_connect_attaches_google_identity_to_signed_in_user(self):
        from config.adapters import GoogleOnlyAdapter
        user=self.email_member()
        social=self.social(user=user)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        GoogleOnlyAdapter().pre_social_login(request,social)
        social.connect(request,user)
        account=SocialAccount.objects.get(provider='google',uid='fixture-google-sub')
        self.assertEqual(account.user_id,user.pk)
        self.assertEqual(user.email,'invited@example.invalid')
        self.assertEqual(GoogleOnlyAdapter().get_connect_redirect_url(request,account),'/accounts/profile/')

    def test_connected_google_identity_is_shown_instead_of_a_second_connect_button(self):
        from config.adapters import GoogleOnlyAdapter
        user=self.email_member()
        MemberProfile.objects.filter(user=user).update(nickname_key='email-member',accepted_at=timezone.now())
        social=self.social(user=user)
        social.state['process']='connect'
        request=self.client.get('/accounts/profile/').wsgi_request
        GoogleOnlyAdapter().pre_social_login(request,social)
        social.connect(request,user)
        response=self.client.get('/accounts/profile/')
        self.assertContains(response,'Google 계정이 연결되어 있습니다.')
        self.assertNotContains(response,'Google 계정 연결</button>')

    def test_google_disconnect_is_rejected(self):
        from config.adapters import GoogleOnlyAdapter
        from django.core.exceptions import ValidationError
        account=SocialAccount(provider='google',uid='fixture-google-sub')
        with self.assertRaises(ValidationError):
            GoogleOnlyAdapter().validate_disconnect(account,[])

    def test_profile_offers_only_post_reauthenticated_google_connect_for_email_member(self):
        user=self.email_member()
        MemberProfile.objects.filter(user=user).update(nickname_key='email-member',accepted_at=timezone.now())
        response=self.client.get('/accounts/profile/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Google 계정 연결')
        self.assertContains(response,'process=connect')
        self.assertContains(response,'action=reauthenticate')
        self.assertContains(response,'csrfmiddlewaretoken')

    def test_profile_hides_google_connect_when_local_verified_email_record_is_missing(self):
        user=self.email_member()
        MemberProfile.objects.filter(user=user).update(nickname_key='email-member',accepted_at=timezone.now())
        EmailAddress.objects.filter(user=user).delete()
        response=self.client.get('/accounts/profile/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'Google 계정 연결')

    def test_profile_google_connect_post_starts_reauthenticated_oauth(self):
        import html
        import re
        client=Client(enforce_csrf_checks=True)
        user=get_user_model().objects.create_user(username='email-member',email='invited@example.invalid')
        MemberProfile.objects.create(user=user,email_key=user.email,email_login_enabled=True,email_verified_at=timezone.now(),nickname_key='email-member',accepted_at=timezone.now())
        EmailAddress.objects.create(user=user,email=user.email,verified=True,primary=True)
        client.force_login(user,backend='sesame.backends.ModelBackend')
        profile_response=client.get('/accounts/profile/')
        self.assertIn('csrftoken',client.cookies)
        match=re.search(r'<form method="post" action="([^"]+)">',profile_response.content.decode())
        self.assertIsNotNone(match)
        action_url=html.unescape(match.group(1))
        action=urlsplit(action_url)
        self.assertEqual(action.path,'/accounts/google/login/')
        self.assertEqual(parse_qs(action.query),{'process':['connect'],'action':['reauthenticate']})
        response=client.post(action_url,HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code,302)
        target=urlsplit(response['Location'])
        self.assertEqual(target.hostname,'accounts.google.com')
        params=parse_qs(target.query)
        self.assertEqual(urlsplit(params['redirect_uri'][0]).path,'/accounts/google/login/callback/')
        self.assertEqual(set(params['scope'][0].split()),{'openid','email'})
        self.assertEqual(params['prompt'],['select_account consent'])

    def test_profile_google_connect_preserves_thai_mount_prefix(self):
        import html
        import re
        from django.urls import set_script_prefix
        set_script_prefix('/thai/')
        self.addCleanup(set_script_prefix,'/')
        user=get_user_model().objects.create_user(username='email-member',email='invited@example.invalid')
        MemberProfile.objects.create(user=user,email_key=user.email,email_login_enabled=True,email_verified_at=timezone.now(),nickname_key='email-member',accepted_at=timezone.now())
        EmailAddress.objects.create(user=user,email=user.email,verified=True,primary=True)
        client=Client(enforce_csrf_checks=True)
        client.force_login(user,backend='sesame.backends.ModelBackend')
        response=client.get('/accounts/profile/',SCRIPT_NAME='/thai')
        self.assertEqual(response.status_code,200)
        match=re.search(r'<form method="post" action="([^"]+)">',response.content.decode())
        self.assertIsNotNone(match)
        action_url=html.unescape(match.group(1))
        self.assertTrue(action_url.startswith('/thai/accounts/google/login/'))
        start=client.post('/accounts/google/login/',{'csrfmiddlewaretoken':client.cookies['csrftoken'].value},SCRIPT_NAME='/thai',HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(start.status_code,302)
        params=parse_qs(urlsplit(start['Location']).query)
        self.assertEqual(urlsplit(params['redirect_uri'][0]).path,'/thai/accounts/google/login/callback/')
        from config.adapters import GoogleOnlyAdapter
        self.assertEqual(GoogleOnlyAdapter().get_connect_redirect_url(start.wsgi_request,None),'/thai/accounts/profile/')

    def test_only_exact_oauth_endpoints_are_open(self):
        response=self.client.get('/accounts/google/login/callback/extra/')
        self.assertRedirects(response,'/accounts/login/',fetch_redirect_response=False)
        self.assertEqual(self.client.get('/api/v1/posts/').status_code,200)

    def test_get_google_start_does_not_redirect_without_confirmation(self):
        response=self.client.get('/accounts/google/login/')
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'socialaccount/login.html')
