#!/usr/bin/env python3
"""Watch the running site and say something only when it is broken.

Runs from the host's cron every 30 minutes. The check is deliberately outside the collector: a
collector that has stopped inserting still answers 200 with a healthy-looking page, and a
collector that is fine still fails to reach a reader when TLS or Caddy is off. So the reader's own
addresses are fetched, and the freshness of the newest story is read from the API.

Why the host and not the Hermes container: measured on 2026-09-20, the container can reach
api.github.com and www.google.com but api.telegram.org is reset from inside it, while the host
reaches it normally. A watchdog that cannot send is a log line nobody reads.

Quiet by design. Nothing wrong means no output and no message; every run appends to --log only when
it has something to say, so the log is a list of incidents rather than a heartbeat.

    python tools/watch_site.py                 # one check, alert on problems
    python tools/watch_site.py --max-age 0     # force the freshness alert (rehearsal)
    python tools/watch_site.py --base http://127.0.0.1:8765   # check the host, not the domain
    python tools/watch_site.py --no-notify     # print only

Talking to a phone needs a channel, and none is configured yet: create /etc/teemo-watch.env
(600, root) with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and the same run starts sending. Until
then every alert is written to the log and to the cron output on the host.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICT = datetime.timezone(datetime.timedelta(hours=7))
PAGES = ("/", "/news/", "/news/ko/", "/thai/", "/thai/news/", "/thai/news/ko/", "/admin")
DEFAULT_BASE = "https://teemobkk.io"
DEFAULT_LOG = "/var/log/teemo-watch.log"
CHANNEL_FILE = "/etc/teemo-watch.env"
# A story older than this means collection stopped even though the page still answers. The collector
# runs every 60 seconds, so 35 minutes is many missed cycles rather than a quiet news hour.
DEFAULT_MAX_AGE_MIN = 35.0
# The backup cron runs daily and keeps seven copies, so a copy older than this means the cron broke.
BACKUP_MAX_AGE_HOURS = 36.0
# Source failures are reported per cycle; a handful is weather, a dozen means something structural.
RSS_FAILURE_LIMIT = 8


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def fetch(url: str, timeout: int = 15) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={
        "User-Agent": "TeemoBKK uptime watch/1.0 (+https://teemobkk.io)",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return answer.status, answer.read()


def parse_stamp(value: str) -> datetime.datetime | None:
    """Read a stored timestamp. Rows carry an offset; a bare one is treated as UTC, not as local."""
    try:
        stamp = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    return stamp


def service_state() -> str:
    """The unit's state, or a word saying this is not the host that runs it."""
    try:
        done = subprocess.run(["systemctl", "is-active", "teemo-live-news"],
                              capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return done.stdout.strip() or "unknown"


def journal_failures(minutes: int = 30) -> int:
    """How many source fetches failed lately, or -1 when the journal is not readable from here."""
    try:
        done = subprocess.run(["journalctl", "-u", "teemo-live-news", "--since", "%d min ago" % minutes,
                               "--no-pager"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return -1
    if done.returncode != 0:
        return -1
    return sum(1 for line in done.stdout.splitlines() if "RSS failed" in line)


def newest_backup(backup_dir: Path) -> tuple[str, float] | None:
    copies = sorted(backup_dir.glob("news-*.db"))
    if not copies:
        return None
    newest = copies[-1]
    age_hours = (now().timestamp() - newest.stat().st_mtime) / 3600.0
    return newest.name, age_hours


def check(base: str, max_age_min: float, backup_dir: Path, want_host: bool
          ) -> tuple[list[str], float | None]:
    """What failed (one line each) and the newest story's age. No problems means a healthy site."""
    problems: list[str] = []
    addresses = []

    for path in PAGES:
        url = base.rstrip("/") + path
        try:
            status, _body = fetch(url)
        except urllib.error.HTTPError as error:
            addresses.append("%s HTTP %s" % (path, error.code))
        except Exception as error:                                  # noqa: BLE001 - any failure counts
            addresses.append("%s %s" % (path, type(error).__name__))
        else:
            if status != 200:
                addresses.append("%s HTTP %s" % (path, status))
    if addresses:
        problems.append("주소가 200이 아닙니다: " + ", ".join(addresses))

    # Freshness comes from the API rather than from the page: the page can be an old file on disk
    # that Caddy keeps answering long after the collector stopped.
    newest_age = None
    try:
        _status, body = fetch(base.rstrip("/") + "/api/news?limit=1")
        payload = json.loads(body.decode("utf-8", "replace"))
        articles = payload.get("articles") if isinstance(payload, dict) else payload
        total = payload.get("total") if isinstance(payload, dict) else None
        if not articles:
            problems.append("API가 기사를 0건 돌려줍니다 (수집이 멈췄을 수 있습니다)")
        else:
            stamp = parse_stamp(articles[0].get("published_at"))
            if stamp is None:
                problems.append("최신 기사의 시각을 읽지 못했습니다: %r" % articles[0].get("published_at"))
            else:
                newest_age = (now() - stamp).total_seconds() / 60.0
                if newest_age > max_age_min:
                    problems.append("최신 기사가 %.0f분 전입니다 (기준 %.0f분, 창 총계 %s)"
                                    % (newest_age, max_age_min, total))
    except Exception as error:                                      # noqa: BLE001
        problems.append("API 조회 실패: %s %s" % (type(error).__name__, str(error)[:80]))

    if want_host:
        state = service_state()
        if state != "active":
            problems.append("teemo-live-news 서비스 상태: %s" % state)
        failures = journal_failures()
        if failures >= RSS_FAILURE_LIMIT:
            problems.append("최근 30분 소스 실패 %d회 (기준 %d회)" % (failures, RSS_FAILURE_LIMIT))
        backup = newest_backup(backup_dir)
        if backup is None:
            problems.append("백업 사본이 하나도 없습니다 (%s)" % backup_dir)
        elif backup[1] > BACKUP_MAX_AGE_HOURS:
            problems.append("최신 백업이 %.0f시간 전입니다 (%s)" % (backup[1], backup[0]))
        free = shutil.disk_usage("/").free / shutil.disk_usage("/").total
        if free < 0.10:
            problems.append("디스크 여유 %.1f%%" % (free * 100))

    return problems, newest_age


def render(problems: list[str], base: str, newest_age: float | None) -> str:
    stamp = now()
    head = "🔴 teemobkk.io 이상 %s" % stamp.astimezone(ICT).strftime("%m-%d %H:%M ICT")
    lines = [head, ""]
    lines += ["- " + item for item in problems]
    if newest_age is not None:
        lines.append("(최신 기사 %.0f분 전 · 확인 %s)" % (newest_age, base))
    lines.append("")
    lines.append("확인: ssh root@72.62.64.195 journalctl -u teemo-live-news -n 40")
    return "\n".join(lines)


def channel() -> tuple[str, str] | None:
    """The Telegram token and chat from the channel file, if somebody has set one up."""
    path = Path(os.environ.get("TEEMO_WATCH_ENV", CHANNEL_FILE))
    if not path.is_file():
        return None
    values = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    token = values.get("TELEGRAM_BOT_TOKEN", "")
    chat = values.get("TELEGRAM_CHAT_ID", "")
    return (token, chat) if token and chat else None


def notify(text: str) -> str:
    """Send through the channel file. Returns a word for the log, never the token."""
    pair = channel()
    if pair is None:
        return "no channel"
    token, chat = pair
    data = urllib.parse.urlencode({"chat_id": chat, "text": text,
                                   "disable_web_page_preview": "true"}).encode("utf-8")
    try:
        with urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage" % token,
                                    data=data, timeout=20) as answer:
            return "sent" if answer.status == 200 else "send returned %s" % answer.status
    except Exception as error:                                      # noqa: BLE001
        return "send failed: %s" % str(error)[:80]


def append_log(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text.replace("\n", " | ") + "\n")
    except OSError as error:
        print("could not write %s: %s" % (path, error))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.environ.get("TEEMO_WATCH_BASE", DEFAULT_BASE))
    parser.add_argument("--max-age", type=float, default=DEFAULT_MAX_AGE_MIN, help="minutes")
    parser.add_argument("--backup-dir", default="/opt/teemo-backup")
    parser.add_argument("--log", default=os.environ.get("TEEMO_WATCH_LOG", DEFAULT_LOG))
    parser.add_argument("--no-notify", action="store_true", help="print only, never send")
    parser.add_argument("--no-host", action="store_true",
                        help="skip the checks that only make sense on the host")
    args = parser.parse_args()

    problems, age = check(args.base, args.max_age, Path(args.backup_dir), want_host=not args.no_host)
    if not problems:
        return 0

    text = render(problems, args.base, age)
    print(text)
    result = "not sent (--no-notify)" if args.no_notify else notify(text)
    append_log(Path(args.log), "%s | %s | %s" % (now().isoformat(timespec="seconds"), result,
                                                 " ; ".join(problems)))
    return 0        # a watchdog that reports a failure is not itself a failed job


if __name__ == "__main__":
    sys.exit(main())
