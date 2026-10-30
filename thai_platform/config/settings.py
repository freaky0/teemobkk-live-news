from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse_lazy
BASE_DIR = Path(__file__).resolve().parent.parent
POST_SCRIPT_PREFIX = os.environ.get("POST_SCRIPT_PREFIX", "").strip()
if POST_SCRIPT_PREFIX and (
    not POST_SCRIPT_PREFIX.startswith("/")
    or POST_SCRIPT_PREFIX.endswith("/")
    or "//" in POST_SCRIPT_PREFIX
    or any(part in {"", ".", ".."} for part in POST_SCRIPT_PREFIX[1:].split("/"))
    or any(char in POST_SCRIPT_PREFIX for char in "?#\\")
):
    raise ImproperlyConfigured("POST_SCRIPT_PREFIX must be an absolute path without a trailing slash.")
FORCE_SCRIPT_NAME = POST_SCRIPT_PREFIX or None
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
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "django.contrib.sites", "rest_framework", "allauth", "allauth.account", "allauth.socialaccount", "allauth.socialaccount.providers.google", "community", "members"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware", "allauth.account.middleware.AccountMiddleware", "config.middleware.SecurityHeadersMiddleware", "members.middleware.AuthBoundaryMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "config.context.runtime"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DB_PATH = Path(os.environ.get("POST_DB_PATH", str(BASE_DIR / "var" / "community.sqlite3"))).resolve()
if LOCAL_DEVELOPMENT and not DB_PATH.is_relative_to((BASE_DIR / "var").resolve()):
    raise ImproperlyConfigured("Development DB must remain inside thai_platform/var.")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DB_PATH, "OPTIONS": {"timeout": 10}}}
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "allauth.account.auth_backends.AuthenticationBackend", "sesame.backends.ModelBackend"]
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"}, {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"}, {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"}, {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Bangkok"
USE_TZ = True
POST_NEWS_DB = os.environ.get("POST_NEWS_DB", "")
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TEST_RUNNER = "config.test_runner.IsolatedCacheTestRunner"
SITE_ID = 1
LOGIN_URL = reverse_lazy("member-login")
LOGIN_REDIRECT_URL = reverse_lazy("post-list")
ACCOUNT_LOGOUT_REDIRECT_URL = reverse_lazy("home")
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
SOCIALACCOUNT_PROVIDERS = {"google": {"SCOPE": ["openid", "email"], "AUTH_PARAMS": {"access_type": "online"}, "OAUTH_PKCE_ENABLED": True}}
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
# Passwordless links: expiring, single-use and restricted to a dedicated scope.
SESAME_MAX_AGE = 600
SESAME_ONE_TIME = True
SESAME_INVALIDATE_ON_EMAIL_CHANGE = True
POST_PUBLIC_ORIGIN = os.environ.get("POST_PUBLIC_ORIGIN", "http://127.0.0.1:8870" if LOCAL_DEVELOPMENT else "").rstrip("/")
# Use a browser key restricted to the Maps Embed API and teemobkk.io HTTP referrers.
GOOGLE_MAPS_EMBED_API_KEY = os.environ.get("GOOGLE_MAPS_EMBED_API_KEY", "").strip()
from urllib.parse import urlsplit
_origin = urlsplit(POST_PUBLIC_ORIGIN)
if POST_PUBLIC_ORIGIN and (not _origin.hostname or _origin.username or _origin.password or _origin.path or _origin.query or _origin.fragment or (_origin.scheme != "https" and not (LOCAL_DEVELOPMENT and _origin.scheme == "http" and _origin.hostname in {"127.0.0.1", "localhost", "testserver"}))):
    raise ImproperlyConfigured("POST_PUBLIC_ORIGIN must be an explicit HTTPS origin (local loopback HTTP allowed).")
POST_POLICY_APPROVED = os.environ.get("POST_POLICY_APPROVED") == "1"
POST_TERMS_VERSION = os.environ.get("POST_TERMS_VERSION", "draft-v1")
POST_PRIVACY_VERSION = os.environ.get("POST_PRIVACY_VERSION", "draft-v1")
POST_POLICY_TEXTS = {}
if POST_POLICY_APPROVED:
    _policy_dir = Path(os.environ.get("POST_POLICY_DIR", ""))
    for _kind in ("terms", "privacy"):
        _file = _policy_dir / (_kind + ".txt")
        if not _file.is_file() or not _file.read_text().strip():
            raise ImproperlyConfigured("Approved terms and privacy text files are required.")
        POST_POLICY_TEXTS[_kind] = _file.read_text()
    if POST_TERMS_VERSION.startswith("draft") or POST_PRIVACY_VERSION.startswith("draft"):
        raise ImproperlyConfigured("Approved policies need non-draft version identifiers.")
else:
    # Show the approved draft documents for review, but never treat them as
    # accepted policies or use them to enable public signup.
    _draft_policy_dir = BASE_DIR / "docs" / "policy-draft"
    for _kind in ("terms", "privacy"):
        _file = _draft_policy_dir / (_kind + ".txt")
        if not _file.is_file() or not _file.read_text().strip():
            raise ImproperlyConfigured("Bundled policy draft files are required.")
        POST_POLICY_TEXTS[_kind] = _file.read_text()
# Signup is public once the approved policy text is configured; invitation
# allowlists are not part of the open-beta account flow.
POST_SIGNUP_ENABLED = LOCAL_DEVELOPMENT or POST_POLICY_APPROVED
# Enable only behind the loopback-bound, trusted reverse proxy.
if os.environ.get("POST_TRUST_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
POST_MAIL_ENABLED = os.environ.get("POST_MAIL_ENABLED") == "1"
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend" if POST_MAIL_ENABLED or not LOCAL_DEVELOPMENT else "django.core.mail.backends.locmem.EmailBackend"
EMAIL_HOST = os.environ.get("POST_EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("POST_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("POST_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("POST_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("POST_EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("POST_DEFAULT_FROM_EMAIL", "")
POST_AUTH_EMAIL_ENABLED = bool(POST_MAIL_ENABLED and EMAIL_HOST and DEFAULT_FROM_EMAIL and POST_PUBLIC_ORIGIN and POST_SIGNUP_ENABLED)
LOGGING = {"version": 1, "disable_existing_loggers": False, "filters": {"redact_auth": {"()": "members.middleware.AuthLogFilter"}}, "handlers": {"safe_server": {"class": "logging.StreamHandler", "filters": ["redact_auth"]}}, "loggers": {"django.server": {"handlers": ["safe_server"], "level": "INFO", "propagate": False}}}
