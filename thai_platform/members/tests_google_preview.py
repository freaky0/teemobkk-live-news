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
        self.assertFalse(set(params['scope'][0].split())-{'openid','email','profile'})
        self.assertEqual(params['access_type'],['online'])

    def test_callback_reaches_allauth_but_invalid_state_never_calls_google(self):
        with patch('requests.sessions.Session.request',side_effect=AssertionError('No real Google traffic permitted')):
            response=self.client.get('/accounts/google/login/callback/',{'state':'invalid-test-state','code':'fixture-not-a-real-code'})
        self.assertEqual(response.status_code,401)
        self.assertTemplateUsed(response,'socialaccount/authentication_error.html')
        self.assertNotIn('_auth_user_id',self.client.session)
