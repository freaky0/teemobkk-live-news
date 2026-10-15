from django.conf import settings
def runtime(request):
    return {"google_configured": settings.GOOGLE_CONFIGURED, "local_development": settings.LOCAL_DEVELOPMENT}
