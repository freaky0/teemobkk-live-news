from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import F, Q
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_GET

from members.models import MemberProfile
from members.services import rate_limited
from .models import MemberBlock, Notification, PrivateMessage


class MessageForm(forms.Form):
    recipient = forms.CharField(label='받는 회원 닉네임', max_length=40)
    body = forms.CharField(label='쪽지 내용', max_length=3000, widget=forms.Textarea)


def require_member(user):
    if not user.is_active or not MemberProfile.objects.filter(user=user, nickname_key__isnull=False, accepted_at__isnull=False, email_verified_at__isnull=False).exclude(nickname_key='').exists():
        raise PermissionDenied


def private_response(response):
    response['Cache-Control'] = 'no-store, private'
    return response


def lock_pair(a, b):
    # Write locks on both users, in a stable order, serialize block/send on
    # SQLite as well as databases supporting row-level locks.
    for pk in sorted((a, b)):
        get_user_model().objects.filter(pk=pk).update(last_login=F('last_login'))


@login_required
@never_cache
@require_POST
def block_member(request, pk):
    require_member(request.user)
    target = get_object_or_404(MemberProfile, user_id=pk, user__is_active=True, accepted_at__isnull=False, email_verified_at__isnull=False, nickname_key__isnull=False)
    if pk == request.user.pk or not target.nickname_key:
        raise PermissionDenied
    with transaction.atomic():
        lock_pair(request.user.pk, pk)
        MemberBlock.objects.get_or_create(blocker=request.user, blocked_id=pk)
    return private_response(redirect('member-block-list'))


@login_required
@never_cache
@require_POST
def unblock_member(request, pk):
    require_member(request.user)
    with transaction.atomic():
        lock_pair(request.user.pk, pk)
        MemberBlock.objects.filter(blocker=request.user, blocked_id=pk).delete()
    return private_response(redirect('member-block-list'))


@login_required
@never_cache
@require_GET
def block_list(request):
    require_member(request.user)
    blocks = MemberBlock.objects.filter(blocker=request.user).select_related('blocked__membership')
    return private_response(render(request, 'community/block_list.html', {'blocks': blocks}))


@login_required
@never_cache
@require_GET
def inbox(request, sent=False):
    require_member(request.user)
    items = PrivateMessage.objects.filter(**({'sender': request.user} if sent else {'recipient': request.user})).select_related('sender', 'recipient', 'sender__membership', 'recipient__membership')[:100]
    recipient_id = request.GET.get('to', '')
    recipient = MemberProfile.objects.filter(user_id=int(recipient_id), user__is_active=True, accepted_at__isnull=False, email_verified_at__isnull=False).first() if recipient_id.isdecimal() and len(recipient_id) < 19 else None
    initial = {'recipient': recipient.nickname_key} if recipient and recipient.nickname_key else {}
    return private_response(render(request, 'community/private_messages.html', {'items': items, 'sent': sent, 'form': MessageForm(initial=initial)}))


@login_required
@never_cache
@require_POST
def send(request):
    require_member(request.user)
    if rate_limited('private-message-send', str(request.user.pk), 10, 60):
        return private_response(HttpResponse('잠시 후 다시 시도해 주세요.', status=429))
    form = MessageForm(request.POST)
    if form.is_valid():
        recipient = MemberProfile.objects.filter(nickname_key=form.cleaned_data['recipient'].casefold(), user__is_active=True, accepted_at__isnull=False, email_verified_at__isnull=False).select_related('user').first()
        if not recipient or recipient.user_id == request.user.pk:
            form.add_error('recipient', '받는 회원을 확인해 주세요.')
        else:
            with transaction.atomic():
                lock_pair(request.user.pk, recipient.user_id)
                blocked = MemberBlock.objects.filter(Q(blocker=request.user, blocked=recipient.user) | Q(blocker=recipient.user, blocked=request.user)).exists()
                if blocked:
                    form.add_error('recipient', '이 회원에게 쪽지를 보낼 수 없습니다.')
                else:
                    PrivateMessage.objects.create(sender=request.user, recipient=recipient.user, body=form.cleaned_data['body'])
                    Notification.objects.create(recipient=recipient.user, kind=Notification.Kind.PRIVATE_MESSAGE)
                    return private_response(redirect('private-messages-sent'))
    return private_response(render(request, 'community/private_messages.html', {'items': [], 'form': form}, status=400))


@login_required
@never_cache
@require_POST
def read(request, pk):
    require_member(request.user)
    item = get_object_or_404(PrivateMessage, pk=pk, recipient=request.user)
    if item.read_at is None:
        PrivateMessage.objects.filter(pk=item.pk, recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return private_response(redirect('private-messages'))
