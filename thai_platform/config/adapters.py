"""No email-based social auto-linking. Google OIDC validation stays in allauth.
https://docs.allauth.org/en/latest/socialaccount/adapter.html
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from members.models import MemberProfile
from members.return_to import finish_login, safe_return, SESSION_KEY

class ClosedAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self,request):
        # Email signup is handled only by the explicit passwordless flow.
        return False
    def post_login(self, request, user, *, email_verification, signal_kwargs, email, signup, redirect_url):
        # allauth otherwise gives its explicit OAuth state next precedence over
        # the account adapter, allowing incomplete profiles to skip onboarding.
        if redirect_url is not None:
            target = safe_return(request, redirect_url)
            if target:
                request.session[SESSION_KEY] = target
            else:
                request.session.pop(SESSION_KEY, None)
        profile = MemberProfile.objects.filter(user=user).first()
        destination = finish_login(request, bool(profile and profile.is_complete))
        return super().post_login(request, user, email_verification=email_verification,
                                  signal_kwargs=signal_kwargs, email=email, signup=signup,
                                  redirect_url=destination)
    def get_login_redirect_url(self,request):
        profile=MemberProfile.objects.filter(user=request.user).first()
        return finish_login(request, bool(profile and profile.is_complete))
    def get_signup_redirect_url(self,request):
        return self.get_login_redirect_url(request)

class GoogleOnlyAdapter(DefaultSocialAccountAdapter):
    def get_connect_redirect_url(self,request,socialaccount):
        return reverse('member-profile')
    def validate_disconnect(self,account,accounts):
        raise ValidationError('Google 연결 해제는 현재 지원하지 않습니다.')
    def is_open_for_signup(self,request,sociallogin):
        verified=[address.email.strip().casefold() for address in sociallogin.email_addresses if address.verified]
        return (settings.GOOGLE_CONFIGURED and settings.POST_SIGNUP_ENABLED
                and sociallogin.account.provider=='google' and len(verified)==1)
    def pre_social_login(self,request,sociallogin):
        process=sociallogin.state.get('process','login')
        if sociallogin.account.provider!='google' or process not in {'login','connect'}:
            raise ImmediateHttpResponse(render(request,'members/provider_error.html',status=403))
        if process=='connect':
            profile=MemberProfile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
            verified=[address.email.strip().casefold() for address in sociallogin.email_addresses if address.verified]
            account_email=request.user.email.strip().casefold() if request.user.is_authenticated else ''
            if (profile is None or not profile.email_login_enabled or not profile.email_verified_at
                    or len(verified)!=1 or verified[0]!=profile.email_key.strip().casefold()
                    or verified[0]!=account_email
                    or not EmailAddress.objects.filter(user=request.user,email__iexact=profile.email_key,verified=True).exists()
                    or (sociallogin.is_existing and sociallogin.user.pk!=request.user.pk)):
                raise ImmediateHttpResponse(render(request,'members/provider_error.html',{'link_failure':True},status=403))
            return
        if sociallogin.is_existing:
            return
        verified=[address.email.strip().casefold() for address in sociallogin.email_addresses if address.verified]
        if len(verified)!=1 or not settings.POST_SIGNUP_ENABLED:
            raise ImmediateHttpResponse(render(request,'members/provider_error.html',status=403))
        email=verified[0]
        if get_user_model().objects.filter(email__iexact=email).exists() or EmailAddress.objects.filter(email__iexact=email).exists() or MemberProfile.objects.filter(email_key=email).exists():
            # Email ownership alone never links accounts; linking requires an
            # authenticated connect flow with a matching verified identity above.
            raise ImmediateHttpResponse(render(request,'members/provider_error.html',status=409))
    def save_user(self,request,sociallogin,form=None):
        from django.db import transaction
        with transaction.atomic():
            user=super().save_user(request,sociallogin,form)
            verified=next(address.email.strip().casefold() for address in sociallogin.email_addresses if address.verified)
            MemberProfile.objects.create(user=user,email_key=verified,email_login_enabled=False,email_verified_at=timezone.now())
            return user
