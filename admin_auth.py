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
    stamp = str(expiry).encode("ascii")
    return "%d.%s" % (expiry, hmac.new(key, stamp, hashlib.sha256).hexdigest())


def verify_token(token: str, now: float | None = None) -> bool:
    key = _key()
    if not key or not token or "." not in token:
        return False
    expiry_text, signature = token.split(".", 1)
    try:
        expiry = int(expiry_text)
    except ValueError:
        return False
    if expiry <= (now if now is not None else time.time()):
        return False
    expected = hmac.new(key, expiry_text.encode("ascii"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


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
