from django.conf import settings
def runtime(request):
    return {"signup_enabled": settings.POST_SIGNUP_ENABLED, "google_configured": settings.GOOGLE_CONFIGURED, "local_development": settings.LOCAL_DEVELOPMENT, "email_auth_enabled": settings.POST_AUTH_EMAIL_ENABLED, "policy_approved": settings.POST_POLICY_APPROVED, "terms_version": settings.POST_TERMS_VERSION, "privacy_version": settings.POST_PRIVACY_VERSION}
