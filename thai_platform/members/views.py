import secrets
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, OperationalError
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.views.generic.edit import FormView
from allauth.account.models import EmailAddress
from allauth.account.views import PasswordSetView as AllauthPasswordSetView
from allauth.socialaccount.models import SocialAccount
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .forms import AnswerEmailNotificationForm, AccountClosureForm, EmailRequestForm, MemberPasswordLoginForm, OnboardingForm
from .models import MemberProfile
from . import services

@never_cache
@require_http_methods(['GET'])
def login_choice(request):
    return render(request,'account/login.html')

@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class MemberPasswordLoginView(FormView):
    template_name='account/password_login.html'
    form_class=MemberPasswordLoginForm
    def get_form_kwargs(self):
        kwargs=super().get_form_kwargs()
        kwargs['request']=self.request
        return kwargs
    def form_valid(self,form):
        user=form.user
        login(self.request,user,backend='allauth.account.auth_backends.AuthenticationBackend')
        profile=MemberProfile.objects.filter(user=user).first()
        if not profile or not profile.is_complete:
            return redirect('member-onboarding')
        next_url = self.request.GET.get('next', '')
        if next_url.startswith('/') and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure()):
            return redirect(next_url)
        return redirect('member-profile')

@method_decorator(login_required, name='dispatch')
class MemberPasswordSetView(AllauthPasswordSetView):
    template_name='members/password_set.html'
    def get_default_success_url(self):
        return reverse('member-profile')
    def dispatch(self,request,*args,**kwargs):
        profile=MemberProfile.objects.filter(
            user=request.user,
            email_login_enabled=True,
            email_verified_at__isnull=False,
        ).first()
        if not profile:
            return HttpResponseForbidden('이메일 인증 계정만 비밀번호를 설정할 수 있습니다.')
        if request.user.has_usable_password():
            return redirect('member-profile')
        return super().dispatch(request,*args,**kwargs)

@never_cache
@require_http_methods(['GET','POST'])
@sensitive_post_parameters('email')
def email_request(request):
    if request.user.is_authenticated:
        return redirect('member-profile')
    form=EmailRequestForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        if not settings.POST_AUTH_EMAIL_ENABLED:
            return render(request,'members/email_request.html',{'form':form,'email_unavailable':True},status=503)
        nonce=request.session.get('post_email_nonce') or secrets.token_urlsafe(32)
        request.session['post_email_nonce']=nonce
        try:
            services.request_email(form.cleaned_data['email'],request.META.get('REMOTE_ADDR',''),nonce)
        except (IntegrityError,OperationalError):
            # Races/DB contention must not disclose account existence.
            pass
        return redirect('email-sent')
    return render(request,'members/email_request.html',{'form':form})

@never_cache
def email_sent(request):
    return render(request,'members/email_sent.html')

@never_cache
@require_http_methods(['GET','POST'])
@sensitive_post_parameters('token')
def email_confirm(request):
    if request.method=='GET':
        return render(request,'members/email_confirm.html')
    token=request.POST.get('token','')
    nonce=request.session.get('post_email_nonce','')
    if not nonce or not settings.POST_AUTH_EMAIL_ENABLED:
        return render(request,'members/email_invalid.html',status=400)
    if services.rate_limited('confirm-ip',request.META.get('REMOTE_ADDR','unknown'),30,600):
        return render(request,'members/email_invalid.html',status=429)
    try:
        user=services.consume_email(request.POST.get('challenge',''),token,nonce)
    except (IntegrityError,OperationalError):
        user=None
    if user is None:
        return render(request,'members/email_invalid.html',status=400)
    login(request,user,backend='sesame.backends.ModelBackend')
    request.session.pop('post_email_nonce',None)
    return redirect('member-profile' if user.membership.is_complete else 'member-onboarding')

@never_cache
@login_required
@require_http_methods(['GET','POST'])
def onboarding(request):
    profile=MemberProfile.objects.filter(user=request.user).first()
    if profile is None:
        return redirect('post-list')
    if profile.is_complete:
        return redirect('member-profile')
    if not profile.email_verified_at:
        return redirect('account_login')
    form=OnboardingForm(request.POST or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        if not settings.POST_SIGNUP_ENABLED:
            form.add_error(None,'가입 공개 전 약관·개인정보 안내 승인이 필요합니다.')
        else:
            try:
                services.complete_profile(request.user,form.cleaned_data['nickname'])
                return redirect('member-profile')
            except (IntegrityError,ValueError):
                form.add_error('nickname','닉네임을 확인하고 다시 입력해 주세요.')
    return render(request,'members/onboarding.html',{'form':form,'profile':profile})

@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def profile(request):
    member=MemberProfile.objects.filter(user=request.user).first()
    if member and not member.is_complete:
        return redirect('member-onboarding')
    answer_email_form = None
    if member:
        answer_email_form = AnswerEmailNotificationForm(
            request.POST if request.method == 'POST' else None,
            initial={'email_answer_notifications': member.email_answer_notifications},
        )
        if request.method == 'POST' and answer_email_form.is_valid():
            enabled = answer_email_form.cleaned_data['email_answer_notifications']
            email = member.email_key.strip().casefold()
            verified = bool(
                member.email_verified_at
                and email
                and request.user.email.strip().casefold() == email
                and EmailAddress.objects.filter(user=request.user, email__iexact=email, verified=True).exists()
            )
            if enabled and not verified:
                answer_email_form.add_error('email_answer_notifications', '인증된 이메일 주소를 확인한 뒤 다시 설정해 주세요.')
            else:
                member.email_answer_notifications = enabled
                member.save(update_fields=['email_answer_notifications'])
                messages.success(request, '답변 알림 설정을 저장했습니다.')
                return redirect('member-profile')
    google_connected=SocialAccount.objects.filter(user=request.user,provider='google').exists()
    google_email_verified=bool(member and member.email_login_enabled and member.email_verified_at
        and request.user.email.strip().casefold()==member.email_key.strip().casefold()
        and EmailAddress.objects.filter(user=request.user,email__iexact=member.email_key,verified=True).exists())
    google_link_available=bool(google_email_verified and settings.GOOGLE_CONFIGURED and not google_connected)
    return render(request,'members/profile.html',{'profile':member,'google_connected':google_connected,'google_link_available':google_link_available,'answer_email_form':answer_email_form})

@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def deactivate(request):
    form = AccountClosureForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            try:
                services.request_account_closure(request.user)
            except ValueError as exc:
                form.add_error(None, str(exc))
            else:
                logout(request)
                messages.info(request, '계정을 비활성화했습니다. 질문과 답변은 보존되며 영구 삭제는 진행하지 않았습니다.')
                return redirect('member-login')
        return render(request, 'members/deactivate.html', {'form': form}, status=400)
    return render(request, 'members/deactivate.html', {'form': form})


@never_cache
def policy(request,kind):
    if kind not in ('terms','privacy'):
        return HttpResponse(status=404)
    return render(request,'members/policy.html',{'kind':kind,'policy_text':settings.POST_POLICY_TEXTS.get(kind,'')})

@api_view(['GET'])
def me(request):
    response=Response({'detail':'로그인이 필요합니다.'},status=403)
    if request.user.is_authenticated:
        profile=MemberProfile.objects.filter(user=request.user).first()
        response=Response({'id':request.user.pk,'nickname':request.user.username,'email':request.user.email,'onboarding_complete':bool(profile and profile.is_complete)})
    response['Cache-Control']='no-store, private'
    return response
