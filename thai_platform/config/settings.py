from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DEVELOPMENT = os.environ.get("POST_LOCAL_DEVELOPMENT") == "1"
DEBUG = LOCAL_DEVELOPMENT and os.environ.get("POST_DEBUG") == "1"
SECRET_KEY = os.environ.get("POST_SECRET_KEY", "")
if not SECRET_KEY and LOCAL_DEVELOPMENT and (BASE_DIR / ".dev-secret").exists():
    SECRET_KEY = (BASE_DIR / ".dev-secret").read_text().strip()
if not SECRET_KEY:
    raise ImproperlyConfigured("POST_SECRET_KEY is required. See README.")
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("POST_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver" if LOCAL_DEVELOPMENT else "").split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("POST_ALLOWED_HOSTS is required.")
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "django.contrib.sites", "rest_framework", "allauth", "allauth.account", "allauth.socialaccount", "allauth.socialaccount.providers.google", "community"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "allauth.account.middleware.AccountMiddleware", "config.middleware.SecurityHeadersMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "config.context.runtime"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DB_PATH = Path(os.environ.get("POST_DB_PATH", str(BASE_DIR / "var" / "community.sqlite3"))).resolve()
if LOCAL_DEVELOPMENT and not DB_PATH.is_relative_to((BASE_DIR / "var").resolve()):
    raise ImproperlyConfigured("Development DB must remain inside thai_platform/var.")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DB_PATH, "OPTIONS": {"timeout": 10}}}
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "allauth.account.auth_backends.AuthenticationBackend"]
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Bangkok"
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = 1
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/community/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_ADAPTER = "config.adapters.ClosedAccountAdapter"
SOCIALACCOUNT_ADAPTER = "config.adapters.GoogleOnlyAdapter"
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_STORE_TOKENS = False
GOOGLE_CONFIGURED = bool(os.environ.get("POST_GOOGLE_CLIENT_ID") and os.environ.get("POST_GOOGLE_CLIENT_SECRET"))
SOCIALACCOUNT_PROVIDERS = {"google": {"SCOPE": ["profile", "email"], "AUTH_PARAMS": {"access_type": "online"}}}
if GOOGLE_CONFIGURED:
    SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {"client_id": os.environ["POST_GOOGLE_CLIENT_ID"], "secret": os.environ["POST_GOOGLE_CLIENT_SECRET"], "key": ""}
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"], "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"], "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination", "PAGE_SIZE": 20, "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle", "rest_framework.throttling.UserRateThrottle"], "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "120/min"}}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not LOCAL_DEVELOPMENT
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7
CSRF_COOKIE_SECURE = not LOCAL_DEVELOPMENT
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = not LOCAL_DEVELOPMENT
SECURE_HSTS_SECONDS = 31536000 if not LOCAL_DEVELOPMENT else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not LOCAL_DEVELOPMENT
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend" if LOCAL_DEVELOPMENT else "django.core.mail.backends.smtp.EmailBackend"
