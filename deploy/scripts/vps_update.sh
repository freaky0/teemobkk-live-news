#!/usr/bin/env bash
# Code-only publish for the ROOT News pages. Run from the repository root.
#
# Production routing is versioned: Caddy serves / from APP_DIR/landing.html and /news/* from a
# release directory; the news service serves other static pages from its WorkingDirectory. The
# Thai front end is independent. Build in a temporary directory and copy only ROOT News outputs to
# their active destinations. No service, Caddy, database, credentials, or Thai paths are changed.
set -euo pipefail

HOST="${HOST:-root@72.62.64.195}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_USER="${APP_USER:-teemo}"
STAGING_DIR="${STAGING_DIR:-/var/lib/teemo-live-news}"
SERVICE="${SERVICE:-teemo-live-news}"
PORT="${PORT:-8765}"
CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
KNOWN_NEWS_STATIC_ROOT="${KNOWN_NEWS_STATIC_ROOT:-/opt/teemo-live-news/releases/80fe0c703c6e3f6a5b0f4be10bb279c37416b518}"
KNOWN_SERVICE_ROOT="${KNOWN_SERVICE_ROOT:-/opt/teemo-live-news/releases/codex-korean-20261031}"
NEWS_STATIC_ROOT="${NEWS_STATIC_ROOT:-}"
SERVICE_ROOT="${SERVICE_ROOT:-}"
DATA_ROOT="${DATA_ROOT:-$APP_DIR}"
COMMIT="$(git rev-parse --short HEAD)"

SECTIONS=(
  "https://teemobkk.io/"
  "https://teemobkk.io/about/"
  "https://teemobkk.io/blog/"
  "https://teemobkk.io/tradingtalk/"
  "https://teemobkk.io/lab/"
  "https://teemobkk.io/perspectives/"
  "https://teemobkk.io/indicators/"
  "https://teemobkk.io/news/"
  "https://teemobkk.io/news/ko/"
  "https://teemobkk.io/thai/"
  "https://teemobkk.io/thai/news/"
  "https://teemobkk.io/thai/news/ko/"
  "https://teemobkk.io/privacy/"
  "https://teemobkk.io/privacy/en/"
  "https://teemobkk.io/robots.txt"
  "https://teemobkk.io/sitemap.xml"
  "https://teemobkk.io/admin"
)

say() { printf '  %s\n' "$*"; }
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }

say "local commit: $COMMIT"
if [ "${SKIP_TESTS:-0}" = "1" ]; then
  say "page checks: SKIPPED (SKIP_TESTS=1)"
else
  say "page checks (${PYTHON:-python} tests/run.py --local)"
  if ! "${PYTHON:-python}" tests/run.py --local; then
    say "page checks FAILED - nothing was published"
    exit 1
  fi
fi

# Resolve active destinations without writing to the host.
if [ -z "$SERVICE_ROOT" ]; then
  SERVICE_ROOT="$(remote "systemctl show -p WorkingDirectory --value '$SERVICE.service' 2>/dev/null" | tr -d '\r' || true)"
fi
if [ -z "$SERVICE_ROOT" ] || [ "$SERVICE_ROOT" = "/" ]; then
  SERVICE_ROOT="$KNOWN_SERVICE_ROOT"
fi

if [ -z "$NEWS_STATIC_ROOT" ]; then
  NEWS_STATIC_ROOT="$(remote "awk '\$1 == \"handle\" && \$2 == \"/news/*\" {inside=1; next} inside && \$1 == \"root\" && \$2 == \"*\" {print \$3; exit} inside && \$1 == \"}\" {inside=0}' '$CADDYFILE' 2>/dev/null" | tr -d '\r' || true)"
fi
if [ -z "$NEWS_STATIC_ROOT" ]; then
  NEWS_STATIC_ROOT="$KNOWN_NEWS_STATIC_ROOT"
fi
case "$NEWS_STATIC_ROOT" in
  */news) NEWS_DEST="$NEWS_STATIC_ROOT" ;;
  *) NEWS_DEST="$NEWS_STATIC_ROOT/news" ;;
esac

validate_release_path() {
  local label="$1" path="$2"
  case "$path" in
    "$APP_DIR"/releases/*) ;;
    *) say "refusing $label outside $APP_DIR/releases: $path"; return 1 ;;
  esac
  case "$path" in
    */thai|*/thai/*) say "refusing a Thai path for $label: $path"; return 1 ;;
  esac
}
validate_release_path "news destination" "$NEWS_DEST"
validate_release_path "service root" "$SERVICE_ROOT"
case "$DATA_ROOT" in
  "$APP_DIR"|"$APP_DIR"/releases/*) ;;
  *) say "refusing ROOT data destination outside $APP_DIR: $DATA_ROOT"; exit 1 ;;
esac
case "$DATA_ROOT" in
  */thai|*/thai/*) say "refusing a Thai path for ROOT data: $DATA_ROOT"; exit 1 ;;
esac

say "active roots: landing=$APP_DIR/landing.html news=$NEWS_DEST service=$SERVICE_ROOT pages=$DATA_ROOT"
if ! remote "systemctl is-active --quiet '$SERVICE.service' && test -d '$APP_DIR' && test -d '$NEWS_STATIC_ROOT' && test -d '$SERVICE_ROOT' && test -d '$DATA_ROOT'"; then
  say "service or active publish directory is unavailable; nothing was published"
  exit 1
fi

# Create an isolated build from tracked files only. The repository checkout, its untracked server
# files, the active release directories, and all Thai paths remain outside the build operation.
remote "install -d -o '$APP_USER' -g '$APP_USER' -m 0755 '$STAGING_DIR'"
BUILD_DIR="$(remote "runuser -u '$APP_USER' -- mktemp -d '$STAGING_DIR/root-build.XXXXXX'" | tr -d '\r')"
case "$BUILD_DIR" in
  "$STAGING_DIR"/root-build.*) ;;
  *) say "unexpected staging path: $BUILD_DIR"; exit 1 ;;
esac
cleanup() {
  case "${BUILD_DIR:-}" in
    "$STAGING_DIR"/root-build.*) remote "runuser -u '$APP_USER' -- rm -rf -- '$BUILD_DIR'" >/dev/null 2>&1 || true ;;
  esac
}
trap cleanup EXIT

git archive --format=tar HEAD | remote "runuser -u '$APP_USER' -- tar -x -C '$BUILD_DIR'"
say "building ROOT News pages with the production database opened read-only"
remote "cd '$BUILD_DIR' && runuser -u '$APP_USER' -- python3 -c 'from pages.build import page_build; page_build.build_server(db_path=\"$APP_DIR/news.db\")' >/dev/null"

for staged in index.html news/index.html news/ko/index.html news/assets/dashboard.css blog/index.html perspectives/index.html indicators/index.html sitemap.xml pages/static/lab/index.html pages/static/tradingtalk/index.html assets/landing/mexc-ticker.css assets/landing/mexc-ticker.js; do
  if ! remote "test -s '$BUILD_DIR/$staged'"; then
    say "missing staged ROOT output: $staged"
    exit 1
  fi
done

# Publish only ROOT paths. The builder's thai/ output is discarded with the staging directory.
say "publishing shared ROOT MEXC ticker assets"
remote "mkdir -p '$DATA_ROOT/assets/landing' &&
        cp -p '$BUILD_DIR/assets/landing/mexc-ticker.css' '$DATA_ROOT/assets/landing/.mexc-ticker.css.$COMMIT.tmp' &&
        cp -p '$BUILD_DIR/assets/landing/mexc-ticker.js' '$DATA_ROOT/assets/landing/.mexc-ticker.js.$COMMIT.tmp' &&
        mv -f '$DATA_ROOT/assets/landing/.mexc-ticker.css.$COMMIT.tmp' '$DATA_ROOT/assets/landing/mexc-ticker.css' &&
        mv -f '$DATA_ROOT/assets/landing/.mexc-ticker.js.$COMMIT.tmp' '$DATA_ROOT/assets/landing/mexc-ticker.js'"
say "publishing ROOT landing and news pages"
PAGE_TMP="$APP_DIR/.landing.html.$COMMIT.tmp"
remote "runuser -u '$APP_USER' -- cp -p '$BUILD_DIR/index.html' '$PAGE_TMP' && runuser -u '$APP_USER' -- mv -f '$PAGE_TMP' '$APP_DIR/landing.html'"
# The news static root is writable by APP_USER. The active service release is deliberately
# read-only, so root writes only the whitelisted ROOT page files/directories below without changing
# existing release directory permissions or ownership.
remote "runuser -u '$APP_USER' -- mkdir -p '$NEWS_DEST'"
remote "runuser -u '$APP_USER' -- cp -a '$BUILD_DIR/news/.' '$NEWS_DEST/'"
remote "mkdir -p '$SERVICE_ROOT/blog' '$SERVICE_ROOT/perspectives' '$SERVICE_ROOT/indicators' '$SERVICE_ROOT/pages/build' '$SERVICE_ROOT/pages/static/lab' '$SERVICE_ROOT/pages/static/tradingtalk' &&
        cp -a '$BUILD_DIR/blog/.' '$SERVICE_ROOT/blog/' &&
        cp -a '$BUILD_DIR/perspectives/.' '$SERVICE_ROOT/perspectives/' &&
        cp -a '$BUILD_DIR/indicators/.' '$SERVICE_ROOT/indicators/' &&
        cp -p '$BUILD_DIR/index.html' '$SERVICE_ROOT/index.html' &&
        cp -p '$BUILD_DIR/sitemap.xml' '$SERVICE_ROOT/sitemap.xml' &&
        cp -p '$BUILD_DIR/pages/build/landing.py' '$BUILD_DIR/pages/build/theme.py' '$BUILD_DIR/pages/build/page_build.py' '$SERVICE_ROOT/pages/build/' &&
        cp -p '$BUILD_DIR/pages/static/lab/index.html' '$SERVICE_ROOT/pages/static/lab/index.html' &&
        cp -p '$BUILD_DIR/pages/static/tradingtalk/index.html' '$SERVICE_ROOT/pages/static/tradingtalk/index.html'"

# The running handler reads public section files from TEEMO_DATA_ROOT (APP_DIR in production),
# while its Python code lives in SERVICE_ROOT. Publish only these ROOT News page outputs there.
# This deliberately does not touch the database, news release, Caddy config, or Thai tree.
remote "mkdir -p '$DATA_ROOT/blog' '$DATA_ROOT/perspectives' '$DATA_ROOT/indicators' '$DATA_ROOT/pages/static/lab' '$DATA_ROOT/pages/static/tradingtalk' &&
        cp -a '$BUILD_DIR/blog/.' '$DATA_ROOT/blog/' &&
        cp -a '$BUILD_DIR/perspectives/.' '$DATA_ROOT/perspectives/' &&
        cp -a '$BUILD_DIR/indicators/.' '$DATA_ROOT/indicators/' &&
        cp -p '$BUILD_DIR/index.html' '$DATA_ROOT/index.html' &&
        cp -p '$BUILD_DIR/sitemap.xml' '$DATA_ROOT/sitemap.xml' &&
        cp -p '$BUILD_DIR/pages/static/lab/index.html' '$DATA_ROOT/pages/static/lab/index.html' &&
        cp -p '$BUILD_DIR/pages/static/tradingtalk/index.html' '$DATA_ROOT/pages/static/tradingtalk/index.html'"

# The live handlers reread these files for each request; backend code and service state are unchanged.
say "runtime status (no restart)"
remote "printf '    service: %s\n' \"\$(systemctl is-active '$SERVICE.service')\" &&
        printf '    http:    %s\n' \"\$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/)\""

missing=""
for url in "${SECTIONS[@]}"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$url" --max-time 15 || true)
  printf '  %-40s %s\n' "$url" "$code"
  [ "$code" = "200" ] || missing="$missing $url($code)"
done

if [ -n "$missing" ]; then
  say "these addresses did not answer 200:$missing"
  exit 1
fi

say "ROOT News publish complete"
