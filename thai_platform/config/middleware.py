class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        from django.conf import settings
        from django.http import HttpResponse
        if request.path_info.startswith("/accounts/google/") and not settings.GOOGLE_CONFIGURED:
            return HttpResponse("Google 로그인 연결 전입니다.", status=503, content_type="text/plain; charset=utf-8")
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https:; media-src 'self' https:; frame-src 'self' https://www.youtube-nocookie.com https://player.vimeo.com https://www.google.com https://maps.google.com; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' https://accounts.google.com")
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("X-Robots-Tag", "noindex, follow")
        return response
