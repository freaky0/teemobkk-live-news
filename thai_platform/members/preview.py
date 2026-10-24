"""Fail-closed access gate: public reads, invited and verified preview writes."""
import re
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from .models import MemberProfile


class RestrictedPreviewMiddleware(MiddlewareMixin):
    public_paths = frozenset({
        '/accounts/login/', '/accounts/login/options/', '/accounts/password/login/', '/accounts/email/', '/accounts/email/sent/',
        '/accounts/email/confirm/', '/accounts/logout/',
    })
    public_read_paths = frozenset({
        '/', '/community/', '/newsroom/', '/api/v1/news/', '/api/v1/posts/',
    })
    public_read_patterns = (
        re.compile(r'/community/[0-9]+/'),
        re.compile(r'/newsroom/[^/]+/'),
        re.compile(r'/api/v1/news/[^/]+/'),
        re.compile(r'/api/v1/posts/[0-9]+/'),
        re.compile(r'/api/v1/posts/[0-9]+/comments/'),
    )

    @classmethod
    def is_public_read(cls, request):
        if request.method not in {'GET', 'HEAD'}:
            return False
        path = request.path_info
        return path in cls.public_read_paths or any(
            pattern.fullmatch(path) for pattern in cls.public_read_patterns
        )

    def process_request(self, request):
        if not settings.POST_RESTRICTED_PREVIEW:
            return None
        if request.path_info == '/accounts/email/' and request.method == 'POST':
            email = request.POST.get('email', '').strip().casefold()
            if email not in settings.POST_PREVIEW_ALLOWED_EMAILS:
                # Same response as an accepted request; no account or mail is created.
                return redirect('email-sent')
        if settings.GOOGLE_CONFIGURED and request.path_info in {
            '/accounts/google/login/', '/accounts/google/login/callback/',
        }:
            # Allauth owns OAuth state/CSRF checks. Do not open other account routes.
            return None
        if request.method in {'GET', 'HEAD'} and request.path_info in {
            '/accounts/policy/terms/', '/accounts/policy/privacy/',
        }:
            # Publish only the two read-only notices, not the account namespace.
            return None
        if self.is_public_read(request):
            return None
        if request.path_info in self.public_paths or request.path_info.startswith('/static/'):
            return None
        if request.user.is_authenticated and request.user.is_active:
            email = request.user.email.strip().casefold()
            if email in settings.POST_PREVIEW_ALLOWED_EMAILS and MemberProfile.objects.filter(
                user=request.user, email_key=email, email_verified_at__isnull=False,
            ).exists():
                return None
            return HttpResponse('검토 환경 접근 권한이 없습니다.', status=403)
        if request.path_info.startswith('/api/'):
            return JsonResponse({'detail': '검토 환경은 초대받은 회원만 이용할 수 있습니다.'}, status=403)
        return redirect('member-login')

    def process_response(self, request, response):
        if settings.POST_RESTRICTED_PREVIEW:
            response['Cache-Control'] = 'private, no-store'
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return response
