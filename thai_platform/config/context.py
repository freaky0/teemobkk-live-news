from django.conf import settings
def runtime(request):
    return {"restricted_preview": settings.POST_RESTRICTED_PREVIEW, "google_configured": settings.GOOGLE_CONFIGURED, "local_development": settings.LOCAL_DEVELOPMENT, "email_auth_enabled": settings.POST_AUTH_EMAIL_ENABLED, "policy_approved": settings.POST_POLICY_APPROVED, "terms_version": settings.POST_TERMS_VERSION, "privacy_version": settings.POST_PRIVACY_VERSION}
