"""Google OAuth boundary tests; fixture credentials, no real provider traffic."""
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
from django.conf import settings
from django.test import Client, TestCase, override_settings

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
        self.assertEqual(SocialAccount.objects.count(),0)
        self.assertEqual(get_user_model().objects.get().pk,user.pk)

    def test_only_exact_oauth_endpoints_are_open(self):
        response=self.client.get('/accounts/google/login/callback/extra/')
        self.assertRedirects(response,'/accounts/login/',fetch_redirect_response=False)
        self.assertEqual(self.client.get('/api/v1/posts/').status_code,200)

    def test_get_google_start_does_not_redirect_without_confirmation(self):
        response=self.client.get('/accounts/google/login/')
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'socialaccount/login.html')
