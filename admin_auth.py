"""Admin sessions for the deployed dashboard.

One password, kept in a file beside the collector and never in the repository, plus a signed cookie
that proves a session without server-side state:

    teemo_admin=<expiry>.<HMAC-SHA256 keyed on the password file>

The key is derived from the stored password, so changing the password invalidates every session at
once and there is nothing to clean up. The cookie is HttpOnly, SameSite=Strict, and Secure whenever
the request arrived over TLS (the reverse proxy says so in X-Forwarded-Proto).

Why this shape:

  * No password file means no sessions and no writes - the safe state for a checkout that has never
    been configured. Nothing is written to disk by this module on its own.
  * A wrong password and an unconfigured site answer the same way to an anonymous visitor (401); the
    log distinguishes them, so the operator can tell what happened without telling a stranger
    whether the site has an admin password.
  * Five failures per address per fifteen minutes, then 429. Sessions are remembered in memory only,
    which is all a single-process collector needs.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import threading
import time
from pathlib import Path

COOKIE = "teemo_admin"
TTL_SECONDS = 30 * 24 * 3600
FAIL_LIMIT = 5
FAIL_WINDOW = 15 * 60
MAX_BODY = 4096
REQUIRED_HEADER = "X-Requested-With"

ROOT = Path(__file__).resolve().parent
PASSWORD_FILE = ROOT / ".admin_password"

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}
_revoked: set[str] = set()


def password_bytes() -> bytes | None:
    """The stored password, or None when the site has not been configured."""
    try:
        raw = PASSWORD_FILE.read_bytes().strip()
    except OSError:
        return None
    return raw or None


def is_configured() -> bool:
    return password_bytes() is not None


def check_password(value: str) -> bool:
    stored = password_bytes()
    if not stored or not value:
        return False
    return hmac.compare_digest(hashlib.sha256(value.encode("utf-8")).digest(),
                               hashlib.sha256(stored).digest())


def _key() -> bytes | None:
    stored = password_bytes()
    if not stored:
        return None
    return hashlib.sha256(b"teemo-admin-v1\x00" + stored).digest()


def issue_token(now: float | None = None) -> str:
    key = _key()
    if not key:
        return ""
    expiry = int((now if now is not None else time.time()) + TTL_SECONDS)
    # The nonce is not decoration: without it two logins in the same second produce the same token
    # (the expiry has one-second resolution), so signing one out would sign the other out too.
    nonce = secrets.token_hex(8)
    return "%d.%s.%s" % (expiry, nonce, _sign(key, expiry, nonce))


def _sign(key: bytes, expiry: int, nonce: str) -> str:
    return hmac.new(key, ("%d.%s" % (expiry, nonce)).encode("ascii"), hashlib.sha256).hexdigest()


def verify_token(token: str, now: float | None = None) -> bool:
    key = _key()
    if not key or not token:
        return False
    if token in _revoked:
        # A signed cookie cannot be taken back without a list like this. Logging out has to mean
        # something, so a signed-out token is remembered here until it would have expired anyway.
        return False
    parts = token.split(".")
    if len(parts) != 3:
        return False
    expiry_text, nonce, signature = parts
    try:
        expiry = int(expiry_text)
    except ValueError:
        return False
    if expiry <= (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(signature, _sign(key, expiry, nonce))


def token_from_cookie(header: str) -> str:
    """The session token out of a Cookie header, or an empty string."""
    for part in str(header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE:
            return value.strip()
    return ""


def is_secure(handler) -> bool:
    """True when the request arrived over TLS, as reported by the reverse proxy."""
    return str(handler.headers.get("X-Forwarded-Proto", "")).split(",")[0].strip().lower() == "https"


def cookie_header(token: str, secure: bool) -> str:
    return "%s=%s; Path=/; Max-Age=%d; HttpOnly; SameSite=Strict%s" % (
        COOKIE, token, TTL_SECONDS, "; Secure" if secure else "")


def clear_cookie(secure: bool) -> str:
    return "%s=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict%s" % (COOKIE, "; Secure" if secure else "")


def client_ip(handler) -> str:
    """The caller's address, taking the proxy's forwarded header into account."""
    forwarded = str(handler.headers.get("X-Forwarded-For", "")).split(",")[0].strip()
    return forwarded or handler.client_address[0] or "-"


def login_allowed(ip: str, now: float | None = None) -> bool:
    moment = now if now is not None else time.time()
    with _lock:
        recent = [stamp for stamp in _failures.get(ip, []) if moment - stamp < FAIL_WINDOW]
        _failures[ip] = recent
        return len(recent) < FAIL_LIMIT


def note_failure(ip: str, now: float | None = None) -> None:
    moment = now if now is not None else time.time()
    with _lock:
        _failures.setdefault(ip, []).append(moment)


def note_success(ip: str) -> None:
    with _lock:
        _failures.pop(ip, None)


def revoke(token: str) -> None:
    """Forget a token, so signing out ends that session and not only its cookie."""
    if not token:
        return
    with _lock:
        _revoked.add(token)
        # Anything already expired would be refused on its own, so the list stays small.
        now = time.time()
        for stale in [item for item in _revoked if "." in item and _expiry_of(item) <= now]:
            _revoked.discard(stale)


def _expiry_of(token: str) -> float:
    try:
        return float(token.split(".", 1)[0])
    except (ValueError, AttributeError):
        return 0.0


def authenticated(handler) -> bool:
    """True when this request carries a valid session cookie."""
    return verify_token(token_from_cookie(handler.headers.get("Cookie", "")))


def write_request_ok(handler) -> tuple[bool, str]:
    """Whether a write may proceed, and why not when it may not.

    The custom header is not a password: it is there so a cross-site form post cannot reach a write
    endpoint even if a browser one day ignores SameSite. Sessions are required on top of it.
    """
    if not authenticated(handler):
        return False, "admin session required"
    if not str(handler.headers.get(REQUIRED_HEADER, "")).strip():
        return False, "missing %s header" % REQUIRED_HEADER
    return True, ""
