"""No email-based social auto-linking. Google OIDC validation stays in allauth.
https://docs.allauth.org/en/latest/socialaccount/adapter.html
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils import timezone
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from members.models import MemberProfile

class ClosedAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self,request):
        # Email signup is handled only by the explicit passwordless flow.
        return False
    def get_login_redirect_url(self,request):
        profile=MemberProfile.objects.filter(user=request.user).first()
        return '/accounts/profile/' if profile and profile.is_complete else '/accounts/onboarding/'

class GoogleOnlyAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self,request,sociallogin):
        return settings.GOOGLE_CONFIGURED and settings.POST_SIGNUP_ENABLED and sociallogin.account.provider=='google'
    def pre_social_login(self,request,sociallogin):
        if sociallogin.account.provider!='google' or sociallogin.state.get('process')=='connect':
            raise ImmediateHttpResponse(render(request,'members/provider_error.html',status=403))
        if sociallogin.is_existing:
            return
        verified=[address.email.strip().casefold() for address in sociallogin.email_addresses if address.verified]
        if len(verified)!=1 or not settings.POST_SIGNUP_ENABLED:
            raise ImmediateHttpResponse(render(request,'members/provider_error.html',status=403))
        email=verified[0]
        if get_user_model().objects.filter(email__iexact=email).exists() or EmailAddress.objects.filter(email__iexact=email).exists() or MemberProfile.objects.filter(email_key=email).exists():
            # Ownership of a provider email is not authorization to connect an
            # existing account. Explicit reauthenticated linking is future work.
            raise ImmediateHttpResponse(render(request,'members/provider_error.html',status=409))
    def save_user(self,request,sociallogin,form=None):
        from django.db import transaction
        with transaction.atomic():
            user=super().save_user(request,sociallogin,form)
            verified=next(address.email.strip().casefold() for address in sociallogin.email_addresses if address.verified)
            MemberProfile.objects.create(user=user,email_key=verified,email_login_enabled=False,email_verified_at=timezone.now())
            return user
