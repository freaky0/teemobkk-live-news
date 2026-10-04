#!/usr/bin/env bash
# Install the collector and dashboard on a Debian/Ubuntu host.
#
# The collector keeps its own news.db and serves a page that reads the API, so the host needs
# nothing but python3 and git: the project uses the standard library only. The web server binds
# to loopback; the public side is meant to be a reverse proxy in front of it.
#
# Safe to re-run: it updates the checkout instead of cloning again, and rewrites the units.
set -euo pipefail

APP_USER="${APP_USER:-teemo}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
REPO="${REPO:-https://github.com/freaky0/teemobkk-live-news.git}"
PORT="${PORT:-8765}"
INTERVAL="${INTERVAL:-60}"

say() { printf '  %s\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root" >&2
  exit 1
fi

say "python3: $(python3 -V 2>&1)"
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  say "create service user $APP_USER"
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
else
  say "service user $APP_USER exists"
fi

if [ -d "$APP_DIR/.git" ]; then
  say "update checkout in $APP_DIR"
  if git -C "$APP_DIR" -c credential.helper= fetch --quiet origin main 2>/dev/null; then
    git -C "$APP_DIR" reset --hard --quiet origin/main
  else
    say "remote not reachable without a credential; keeping the current checkout"
  fi
elif [ -f "$APP_DIR/live_news_dashboard.py" ]; then
  # The repository is private, so a host may receive the files by upload instead of a clone.
  # A deploy key can be added later to turn the checkout into a git one; until then this is a
  # plain directory and the setup is otherwise identical.
  say "using the files already in $APP_DIR (no .git)"
else
  say "clone $REPO into $APP_DIR"
  if ! git clone --quiet "$REPO" "$APP_DIR" 2>/dev/null; then
    echo "clone failed - the repository is private. Upload the files, or add a deploy key." >&2
    exit 1
  fi
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

say "build the page the server will serve"
cd "$APP_DIR"
runuser -u "$APP_USER" -- python3 -c "import page_build; page_build.build_server()" \
  || say "page build skipped (no database yet; the timer will build it)"

cat > /etc/systemd/system/teemo-live-news.service <<UNIT
[Unit]
Description=TeemoBKK Live News collector and dashboard
Documentation=https://github.com/freaky0/teemobkk-live-news
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStartPre=/usr/bin/python3 -c "import page_build; page_build.build_server()"
ExecStart=/usr/bin/python3 live_news_dashboard.py --public --host 127.0.0.1 --port $PORT --interval $INTERVAL
Restart=always
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=$APP_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/teemo-live-news-page.service <<UNIT
[Unit]
Description=Rebuild the served page so its seed headlines stay current

[Service]
Type=oneshot
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 -c "import page_build; page_build.build_server()"
UNIT

cat > /etc/systemd/system/teemo-live-news-page.timer <<UNIT
[Unit]
Description=Rebuild the served page every ten minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now teemo-live-news.service
systemctl enable --now teemo-live-news-page.timer
sleep 4

say "service: $(systemctl is-active teemo-live-news.service)"
say "timer:   $(systemctl is-active teemo-live-news-page.timer)"
curl -sS -o /dev/null -w "  local HTTP %{http_code}\n" "http://127.0.0.1:$PORT/" || true
curl -sS -o /dev/null -w "  api  HTTP %{http_code}\n" "http://127.0.0.1:$PORT/api/news?limit=1" || true
