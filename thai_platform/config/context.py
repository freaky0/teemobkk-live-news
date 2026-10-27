from django.conf import settings

PUBLIC_ORIGIN = "https://teemobkk.io"
PUBLIC_PREFIX = "/thai"
SHARE_IMAGE_PATH = PUBLIC_PREFIX + "/static/assets/share-home-v1.jpg"


def _canonical_path(path):
    if path == PUBLIC_PREFIX or path.startswith(PUBLIC_PREFIX + "/"):
        return path
    return PUBLIC_PREFIX + (path if path.startswith("/") else "/" + path)


def runtime(request):
    path = request.path or "/"
    return {
        "signup_enabled": settings.POST_SIGNUP_ENABLED,
        "google_configured": settings.GOOGLE_CONFIGURED,
        "local_development": settings.LOCAL_DEVELOPMENT,
        "email_auth_enabled": settings.POST_AUTH_EMAIL_ENABLED,
        "policy_approved": settings.POST_POLICY_APPROVED,
        "terms_version": settings.POST_TERMS_VERSION,
        "privacy_version": settings.POST_PRIVACY_VERSION,
        "canonical_url": PUBLIC_ORIGIN + _canonical_path(path),
        "share_image_url": PUBLIC_ORIGIN + SHARE_IMAGE_PATH,
    }
