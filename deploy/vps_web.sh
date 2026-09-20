#!/usr/bin/env bash
# Put the collector behind Caddy and switch the firewall on.
#
# Two things happen here. TLS for the public name is Caddy's job. And the generated Korean page
# is served straight from disk, because the collector's own routing only covers the root index
# (it answers 404 for any nested path), while everything else - the page itself, the API, the
# icons - is proxied to it. That keeps the collector untouched.
set -euo pipefail

DOMAIN="${DOMAIN:-teemobkk.io}"
APP_DIR="${APP_DIR:-/opt/teemo-live-news}"
APP_PORT="${APP_PORT:-8765}"

say() { printf '  %s\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
if ! command -v caddy >/dev/null 2>&1; then
  say "installing caddy from the distribution packages (it gets security updates there)"
  apt-get update -qq
  apt-get install -y -qq caddy >/dev/null
fi
say "caddy: $(caddy version)"

say "writing /etc/caddy/Caddyfile for $DOMAIN"
cat > /etc/caddy/Caddyfile <<CADDY
# TeemoBKK. The collector listens on loopback; this is the only public door.
#
# The site root is a landing page (the domain will also carry a blog and indicator pages), so
# the dashboard lives under its own path. The section pages are generated files and the
# collector's routing only covers the root index, so Caddy serves them from disk; the landing
# page, /api/* and the icons are proxied to the collector.
$DOMAIN, www.$DOMAIN {
	encode zstd gzip

	handle /news/* {
		root * $APP_DIR
		file_server
	}

	handle /thai/* {
		root * $APP_DIR
		file_server
	}

	handle {
		reverse_proxy 127.0.0.1:$APP_PORT
	}

	header {
		-Server
		X-Content-Type-Options nosniff
		Referrer-Policy strict-origin-when-cross-origin
	}

	log {
		output file /var/log/caddy/access.log {
			roll_size 10MiB
			roll_keep 5
		}
	}
}
CADDY

mkdir -p /var/log/caddy
chown caddy:caddy /var/log/caddy
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
say "caddyfile valid"

systemctl enable --now caddy >/dev/null 2>&1 || true
systemctl reload caddy 2>/dev/null || systemctl restart caddy
sleep 2
say "caddy: $(systemctl is-active caddy)"

# SSH first, then the web ports, then switch it on: a mistake here would end the session.
say "firewall: allowing SSH, 80 and 443 before enabling"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
say "ufw: $(ufw status | head -1)"
ufw status | sed -n '2,8p' | sed 's/^/    /'

say "waiting for the certificate"
for i in 1 2 3 4 5 6 7 8 9 10; do
  sleep 6
  code=$(curl -s -o /dev/null -w '%{http_code}' "https://$DOMAIN/" --max-time 10 || true)
  say "attempt $i: https $code"
  if [ "$code" = "200" ]; then break; fi
done