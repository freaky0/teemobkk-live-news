"""Fail-closed, email-verified access gate for an isolated review environment."""
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from .models import MemberProfile


class RestrictedPreviewMiddleware(MiddlewareMixin):
    public_paths = frozenset({
        '/accounts/login/', '/accounts/email/', '/accounts/email/sent/',
        '/accounts/email/confirm/', '/accounts/logout/',
    })

    def process_request(self, request):
        if not settings.POST_RESTRICTED_PREVIEW:
            return None
        if request.path == '/accounts/email/' and request.method == 'POST':
            email = request.POST.get('email', '').strip().casefold()
            if email not in settings.POST_PREVIEW_ALLOWED_EMAILS:
                # Same response as an accepted request; no account or mail is created.
                return redirect('email-sent')
        if settings.GOOGLE_CONFIGURED and request.path in {
            '/accounts/google/login/', '/accounts/google/login/callback/',
        }:
            # Allauth owns OAuth state/CSRF checks. Do not open other account routes.
            return None
        if request.path in self.public_paths or request.path.startswith('/static/'):
            return None
        if request.user.is_authenticated and request.user.is_active:
            email = request.user.email.strip().casefold()
            if email in settings.POST_PREVIEW_ALLOWED_EMAILS and MemberProfile.objects.filter(
                user=request.user, email_key=email, email_verified_at__isnull=False,
            ).exists():
                return None
            return HttpResponse('검토 환경 접근 권한이 없습니다.', status=403)
        if request.path.startswith('/api/'):
            return JsonResponse({'detail': '검토 환경은 초대받은 회원만 이용할 수 있습니다.'}, status=403)
        return redirect('member-login')

    def process_response(self, request, response):
        if settings.POST_RESTRICTED_PREVIEW:
            response['Cache-Control'] = 'private, no-store'
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return response
