"""Passwordless delivery uses django-sesame; raw tokens never enter logs or DB.
Sources: https://django-sesame.readthedocs.io/en/stable/howto.html
https://docs.djangoproject.com/en/5.2/topics/email/
"""
from datetime import timedelta
from hashlib import sha256
import logging
import hmac
from smtplib import SMTPException
from urllib.parse import urlencode
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from sesame.utils import get_token, get_user
from .models import EmailChallenge, MemberProfile, AccountClosureRequest

logger=logging.getLogger(__name__)

def digest(value):
    return sha256(value.encode()).hexdigest()


def rate_limited(namespace,value,limit,seconds):
    key='post-auth:'+namespace+':'+digest(value)
    cache.add(key,0,timeout=seconds)
    try:
        return cache.incr(key)>limit
    except ValueError:
        return True


def request_email(email,remote_addr,session_nonce):
    """Uniform result for existing, new, social-only and rate-limited addresses."""
    email=email.strip().casefold()
    if rate_limited('ip',remote_addr or 'unknown',20,600) or rate_limited('address',email,1,60) or rate_limited('daily',email,10,86400):
        return
    User=get_user_model()
    with transaction.atomic():
        profile=MemberProfile.objects.select_related('user').filter(email_key=email).first()
        if profile:
            user=profile.user
            if not profile.email_login_enabled or not user.is_active:
                return
        else:
            # Never enable email access to a Google-only/legacy account implicitly.
            if User.objects.filter(email__iexact=email).exists() or EmailAddress.objects.filter(email__iexact=email).exists() or not settings.POST_SIGNUP_ENABLED:
                return
            user=User(username='member_'+uuid.uuid4().hex,email=email)
            user.set_unusable_password()
            user.save()
            profile=MemberProfile.objects.create(user=user,email_key=email,email_login_enabled=True)
        if SocialAccount.objects.filter(user=user).exists() and not profile.email_login_enabled:
            return
        now=timezone.now()
        EmailChallenge.objects.filter(user=user,used_at__isnull=True).update(used_at=now)
        challenge=EmailChallenge(user=user,session_digest=digest(session_nonce),expires_at=now+timedelta(seconds=settings.SESAME_MAX_AGE))
        token=get_token(user,scope='post-email:'+str(challenge.pk))
        challenge.digest=digest(token)
        challenge.save()
    # Fragment is never sent in HTTP request URLs/access logs. The page requires
    # an explicit CSRF-protected POST, so mail link scanners cannot consume it.
    link=settings.POST_PUBLIC_ORIGIN+'/accounts/email/confirm/#'+urlencode({'id':str(challenge.pk),'token':token})
    body='TEEMOBKK POST 가입·로그인 요청입니다.\n\n'+link+'\n\n인증 링크는 10분 동안 한 번만 사용할 수 있습니다.\n신청한 브라우저에서 링크를 열어 주세요.\n직접 요청하지 않았다면 링크를 열지 마세요. 다른 사람에게 전달하지 마세요.'
    try:
        sent=send_mail('TEEMOBKK POST 이메일 인증',body,settings.DEFAULT_FROM_EMAIL,[email],fail_silently=False)
        if sent!=1:
            EmailChallenge.objects.filter(pk=challenge.pk).update(used_at=timezone.now())
    except (SMTPException,OSError):
        EmailChallenge.objects.filter(pk=challenge.pk).update(used_at=timezone.now())
        logger.warning('Authentication email delivery failed; challenge invalidated.')


@transaction.atomic
def consume_email(challenge_id,token,session_nonce):
    try:
        ident=uuid.UUID(str(challenge_id))
    except (ValueError,TypeError,AttributeError):
        return None
    if not isinstance(token,str) or len(token)>500:
        return None
    now=timezone.now()
    challenge=EmailChallenge.objects.select_for_update().select_related('user').filter(pk=ident,used_at__isnull=True,expires_at__gt=now).first()
    if not challenge or not challenge.user.is_active or not hmac.compare_digest(challenge.digest,digest(token)) or not hmac.compare_digest(challenge.session_digest,digest(session_nonce)):
        return None
    profile=MemberProfile.objects.select_for_update().filter(user=challenge.user).first()
    if not profile or not profile.email_login_enabled or profile.email_key!=challenge.user.email.strip().casefold():
        return None
    user=get_user(token,scope='post-email:'+str(ident),update_last_login=False)
    if user is None or user.pk!=challenge.user_id:
        return None
    # Conditional claim also protects SQLite, where SELECT FOR UPDATE is a no-op.
    if EmailChallenge.objects.filter(pk=ident,used_at__isnull=True,expires_at__gt=now).update(used_at=now)!=1:
        return None
    if EmailAddress.objects.filter(email__iexact=profile.email_key,verified=True).exclude(user=user).exists():
        return None
    address,_=EmailAddress.objects.get_or_create(user=user,email=profile.email_key,defaults={'verified':True,'primary':True})
    address.verified=True
    address.primary=True
    address.save(update_fields=['verified','primary'])
    if not profile.email_verified_at:
        profile.email_verified_at=now
        profile.save(update_fields=['email_verified_at'])
    return user


@transaction.atomic
def complete_profile(user,nickname):
    profile=MemberProfile.objects.select_for_update().get(user=user)
    if not profile.email_verified_at:
        raise ValueError('Email verification required.')
    if profile.is_complete:
        return
    profile.nickname_key=nickname.casefold()
    profile.terms_version=settings.POST_TERMS_VERSION
    profile.privacy_version=settings.POST_PRIVACY_VERSION
    profile.accepted_at=timezone.now()
    profile.save(update_fields=['nickname_key','terms_version','privacy_version','accepted_at'])
    user.username=nickname
    user.save(update_fields=['username'])


@transaction.atomic
def request_account_closure(user):
    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not locked_user.is_active:
        raise ValueError('An active account is required.')
    if AccountClosureRequest.objects.filter(user=locked_user, status=AccountClosureRequest.Status.PENDING_REVIEW).exists():
        raise ValueError('A closure request is already pending review.')
    closure = AccountClosureRequest.objects.create(user=locked_user)
    now = timezone.now()
    EmailChallenge.objects.filter(user=locked_user, used_at__isnull=True).update(used_at=now)
    locked_user.is_active = False
    locked_user.save(update_fields=['is_active'])
    return closure
