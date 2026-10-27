import secrets
import io
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator

from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.views.generic.edit import FormView
from allauth.account.models import EmailAddress
from allauth.account.views import PasswordSetView as AllauthPasswordSetView
from allauth.socialaccount.models import SocialAccount
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .forms import AnswerEmailNotificationForm, AccountClosureForm, EmailRequestForm, MemberPasswordLoginForm, OnboardingForm, ProfileNicknameForm, AvatarForm
from .models import MemberProfile
from . import services
from .return_to import remember_return, finish_login

@never_cache
@require_http_methods(['GET'])
def login_choice(request):
    remember_return(request)
    return render(request,'account/login.html')

@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class MemberPasswordLoginView(FormView):
    template_name='account/password_login.html'
    form_class=MemberPasswordLoginForm
    def dispatch(self, request, *args, **kwargs):
        remember_return(request)
        return super().dispatch(request, *args, **kwargs)
    def get_form_kwargs(self):
        kwargs=super().get_form_kwargs()
        kwargs['request']=self.request
        return kwargs
    def form_valid(self,form):
        user=form.user
        login(self.request,user,backend='allauth.account.auth_backends.AuthenticationBackend')
        profile=MemberProfile.objects.filter(user=user).first()
        return redirect(finish_login(self.request, bool(profile and profile.is_complete)))

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
    remember_return(request)
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
    return redirect(finish_login(request, user.membership.is_complete))

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
                return redirect(finish_login(request, True))
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
    return render(request,'members/profile.html',{'profile':member,'google_connected':google_connected,'google_link_available':google_link_available,'answer_email_form':answer_email_form, 'nickname_form':ProfileNicknameForm(user=request.user, initial={'nickname':request.user.username}), 'avatar_form':AvatarForm(initial={'avatar':member.avatar}) if member else None})

@never_cache
@login_required
@require_http_methods(['POST'])
def edit_nickname(request):
    try:
        return _edit_nickname(request)
    except OperationalError:
        return HttpResponse('일시적인 오류입니다. 잠시 후 다시 시도해 주세요.', status=503)

def _edit_nickname(request):
    member = MemberProfile.objects.filter(user=request.user).first()
    if not member or not member.is_complete:
        return HttpResponseForbidden()
    form = ProfileNicknameForm(request.POST, user=request.user)
    if form.is_valid():
        nickname = form.cleaned_data['nickname']
        if nickname == request.user.username:
            return redirect('member-profile')
        now = timezone.now()
        try:
            with transaction.atomic():
                updated = MemberProfile.objects.filter(pk=member.pk).filter(Q(nickname_changed_at__isnull=True) | Q(nickname_changed_at__lte=now-timedelta(days=30))).update(nickname_key=nickname.casefold(), nickname_changed_at=now)
                if updated:
                    get_user_model().objects.filter(pk=request.user.pk).update(username=nickname)
        except (IntegrityError, OperationalError):
            updated = 0
        if updated:
            messages.success(request, '닉네임을 변경했습니다.')
        else:
            messages.error(request, '닉네임은 30일마다 변경할 수 있습니다. 중복 여부도 확인해 주세요.')
    else:
        messages.error(request, '닉네임을 확인하고 다시 입력해 주세요.')
    return redirect('member-profile')

@never_cache
@login_required
@require_http_methods(['POST'])
def edit_avatar(request):
    member = MemberProfile.objects.filter(user=request.user).first()
    if not member or not member.is_complete:
        return HttpResponseForbidden()
    form = AvatarForm(request.POST)
    if form.is_valid():
        MemberProfile.objects.filter(pk=member.pk).update(avatar=form.cleaned_data['avatar'], avatar_image=None)
        messages.success(request, '프로필 아이콘을 변경했습니다.')
    else:
        messages.error(request, '프로필 아이콘을 확인해 주세요.')
    return redirect('member-profile')

@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def profile_image(request):
    member = MemberProfile.objects.filter(user=request.user).first()
    if not member or not member.is_complete:
        return HttpResponseForbidden()
    if request.method == 'GET':
        if not member.avatar_image:
            return HttpResponse(status=404)
        response = HttpResponse(bytes(member.avatar_image), content_type='image/png')
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Security-Policy'] = "default-src 'none'; sandbox"
        return response
    if request.POST.get('remove') == '1':
        MemberProfile.objects.filter(pk=member.pk).update(avatar_image=None)
        messages.success(request, '프로필 사진을 삭제했습니다.')
        return redirect('member-profile')
    uploaded = request.FILES.get('image')
    try:
        if not uploaded or uploaded.size > 1024 * 1024:
            raise ValueError('size')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(uploaded) as source:
                if source.format not in ('PNG', 'JPEG') or getattr(source, 'n_frames', 1) != 1:
                    raise ValueError('format')
                width, height = source.size
                if width < 1 or height < 1 or width > 4096 or height > 4096 or width * height > 4_000_000:
                    raise ValueError('dimensions')
                source.load()
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((256, 256))
                # A fresh image strips EXIF, comments, and other source metadata.
                clean = Image.new('RGB', image.size)
                clean.paste(image)
                output = io.BytesIO()
                clean.save(output, format='PNG')
        MemberProfile.objects.filter(pk=member.pk).update(avatar_image=output.getvalue())
        messages.success(request, '프로필 사진을 변경했습니다.')
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError):
        messages.error(request, 'PNG 또는 JPEG 사진을 확인해 주세요 (최대 1MB, 400만 픽셀).')
    return redirect('member-profile')

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
