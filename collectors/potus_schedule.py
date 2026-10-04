"""Presidential schedule rows for the indicator tab.

Source: the calendar feed the Roll Call / Factba.se "President's Public Schedule"
page loads itself - https://media-cdn.factba.se/rss/json/trump/calendar.json
(public JSON on their CDN, no key, no login). rollcall.com robots.txt allows
general agents (`User-agent: * / Allow: /`); it only blocks named AI-training
crawlers, so this is read as a plain news source and every row links back to that
page in the UI.

The raw feed is a dump of the last few weeks, roughly 40% of it pool logistics
("Executive Time", "Policy Meeting", "Call Time", "Full lid"). Only entries a
market reader cares about survive the filter: remarks, speeches, press
conferences, ceremonies, rallies, signings and meetings that were open to press.

Times are US Eastern and converted to KST (+13h), exactly like the Nasdaq feed.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

SOURCE = "https://media-cdn.factba.se/rss/json/trump/calendar.json"
PAGE = "https://rollcall.com/factbase/trump/calendar/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TYPE = "President Schedule"
KST_SHIFT = timedelta(hours=13)  # ET -> KST

# Kept: events that move markets or make the news.
KEEP = (
    "remarks", "speech", "press conference", "press briefing", "ceremony",
    "announcement", "announces", "roundtable", "reception", "rally", "interview",
    "meeting with", "summit", "delivers", "address", "signs", "bill signing",
    "executive order", "swearing-in",
)
# Dropped: internal time-keeping and logistics.
DROP = (
    "executive time", "policy meeting", "call time", "lid", "photo opportunity",
    "intelligence briefing", "signing time", "pre-tape", "church service",
)
TRAVEL = re.compile(r"^(tbd:\s*)?the president (departs|arrives)", re.I)
CLOSED = ("closed press",)
# A closed-press item is still worth knowing when the event itself is the news.
NEWSWORTHY = ("remarks", "signs", "ceremony", "announcement", "executive order", "rally", "meeting with")
BIG = ("remarks", "speech", "press conference", "rally", "bill signing", "executive order", "swearing-in")
PLACES = ("the white house", "oval office", "the sticks", "")


def wanted(entry: dict[str, Any]) -> bool:
    details = str(entry.get("details") or "")
    lowered = details.lower()
    coverage = str(entry.get("coverage") or "").lower()
    if any(word in lowered for word in DROP) or TRAVEL.match(details.strip()):
        return False
    if any(word in coverage for word in CLOSED) and not any(word in lowered for word in NEWSWORTHY):
        return False
    if any(word in lowered for word in KEEP):
        return True
    return any(word in coverage for word in ("pre-credentialed", "open press", "restricted pool"))


def clock(value: Any) -> tuple[int, int] | None:
    match = re.match(r"^\s*(\d{1,2}):(\d{2})", str(value or ""))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    return (hour, minute) if hour <= 23 and minute <= 59 else None


def rows_for(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter one feed dump down to publishable schedule events."""
    out: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") != TYPE or not wanted(entry):
            continue
        details = re.sub(r"^tbd:\s*", "", str(entry.get("details") or "").strip(), flags=re.I)
        details = re.sub(r"^the president\b", "President", details, flags=re.I)
        details = re.sub(r"\s+", " ", details).strip()
        place = str(entry.get("location") or "").strip()
        if place and place.lower() not in PLACES:
            details = "%s (%s)" % (details, place)
        parsed = clock(entry.get("time"))
        if parsed:  # ET -> KST; the date follows the converted time
            try:
                day = date.fromisoformat(str(entry.get("date")))
            except ValueError:
                continue
            moment = datetime.combine(day, datetime.min.time()) + timedelta(hours=parsed[0], minutes=parsed[1]) + KST_SHIFT
        else:  # undated items keep the feed's date and sort to the end of the day
            try:
                moment = datetime.combine(date.fromisoformat(str(entry.get("date"))), datetime.min.time())
            except ValueError:
                continue
        lowered = details.lower()
        out.append({
            "kst": moment.strftime("%H:%M") if parsed else "",
            "date": moment.date().isoformat(),
            "country": "United States",
            "country_code": "US",
            "name": details[:150],
            "kind": "potus",
            "importance": 4 if any(word in lowered for word in BIG) else 3,
            "source_url": PAGE,
            "actual": "",
            "consensus": "",
            "previous": "",
            "released": False,
            "passed": moment <= datetime.now(),
        })
    return out


def fetch() -> list[dict[str, Any]]:
    import urllib.request

    request = urllib.request.Request(SOURCE, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=40) as response:
        payload = json.loads(response.read())
    return rows_for(payload if isinstance(payload, list) else [])
