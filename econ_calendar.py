"""Economic calendar for the top of the dashboard: today and tomorrow, Korea time.

Source: Nasdaq's public economic calendar JSON (no key, no token, no paid tier).
It publishes no importance level, so one is derived here by keyword:

    US releases at level 2 or above are kept (3 = FOMC, CPI, PCE, payrolls, GDP,
    jobless claims, retail sales; 2 = PPI, ISM, PMI, housing, inventories, ...).
    Non-US releases are kept only when the name starts with a headline release.
    Speakers, press conferences, minutes and duplicate variants of one release
    are dropped.

Times are KST only, and the list is deliberately short: a glance list.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

SOURCE_URL = "https://api.nasdaq.com/api/calendar/economicevents?date=%s"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
KST = timezone(timedelta(hours=9))
ET = timezone(timedelta(hours=-4))  # the source's time column is Eastern, not GMT

LEVEL3 = (
    "fomc", "fed funds", "interest rate decision", "rate decision", "federal reserve",
    "powell", "cpi", "consumer price", "pce", "personal consumption", "nonfarm",
    "non-farm", "unemployment rate", "employment report", "payroll", "gdp",
    "gross domestic product", "jobless claims", "treasury", "retail sales",
)
LEVEL2 = (
    "ppi", "producer price", "ism", "pmi", "durable goods", "industrial production",
    "consumer confidence", "consumer sentiment", "housing starts", "building permits",
    "trade balance", "adp", "crude oil inventories", "factory orders", "current account",
    "business confidence", "wholesale", "import price", "export price",
)
# Non-US: matched on the start of the name, so "Current Account % of GDP" is out.
WORLD = (
    "interest rate decision", "rate decision", "cpi", "gdp", "unemployment rate",
    "employment change", "retail sales", "payroll", "inflation rate", "trade balance",
    "monetary policy",
)
NOISE = ("speaks", "speech", "press conference", "minutes", "testifies", "testimony", "auction")
LABELS = ("\uc624\ub298", "\ub0b4\uc77c")  # today, tomorrow
WEEKDAYS = "\uc6d4\ud654\uc218\ubaa9\uae08\ud1a0\uc77c"  # Mon..Sun


def clean(value: Any) -> str:
    text = str(value if value is not None else "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def is_us(country: str) -> bool:
    return clean(country).lower() in ("united states", "u.s.", "us", "usa")


def wanted(name: str, country: str) -> int:
    """Importance level to publish, or 0 to drop the event."""
    lowered = name.lower()
    if any(word in lowered for word in NOISE) and "powell" not in lowered:
        return 0  # ponytail: speakers are noise; loosen when a Fed chair talk matters
    level = 3 if any(key in lowered for key in LEVEL3) else (2 if any(key in lowered for key in LEVEL2) else 1)
    if is_us(country):
        return level if level >= 2 else 0
    return 3 if lowered.startswith(WORLD) else 0


def fetch_day(day: str, timeout: int = 40) -> list[dict[str, Any]]:
    import urllib.request

    request = urllib.request.Request(SOURCE_URL % day, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    rows = (payload.get("data") or {}).get("rows") or []
    return [row for row in rows if isinstance(row, dict)]


def clock(value: Any) -> tuple[int, int] | None:
    match = re.match(r"^\s*(\d{1,2}):(\d{2})", str(value or ""))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    return (hour, minute) if hour <= 23 and minute <= 59 else None


def collect(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    anchor = now.astimezone(KST).date()
    events: list[dict[str, Any]] = []
    errors: list[str] = []

    for offset in (-1, 0, 1, 2):  # one day either side so KST rollover is covered
        day_date = anchor + timedelta(days=offset)
        try:
            rows = fetch_day(day_date.isoformat())
        except Exception as exc:  # a network problem must never break the dashboard
            errors.append("%s: %s" % (day_date.isoformat(), exc))
            continue
        # Nasdaq labels this column "gmt", but the values are US Eastern time (retail
        # sales reads 08:30 for an 08:30 ET release). Convert from ET, not from UTC.
        midnight = datetime.combine(day_date, datetime.min.time(), tzinfo=ET)
        for row in rows:
            parsed = clock(row.get("gmt"))
            name = clean(row.get("eventName"))
            country = clean(row.get("country"))
            if not parsed or not name:
                continue
            level = wanted(name, country)
            if not level:
                continue
            hour, minute = parsed
            moment = (midnight + timedelta(hours=hour, minutes=minute)).astimezone(KST)
            events.append({
                "kst": moment.strftime("%H:%M"),
                "date": moment.date().isoformat(),
                "country": country,
                "name": name,
                "importance": level,
                "actual": clean(row.get("actual")),
                "consensus": clean(row.get("consensus")),
                "previous": clean(row.get("previous")),
                "released": bool(clean(row.get("actual"))),
            })

    # One release arrives as several rows (CPI / CPI n.s.a / CPIH). Keep the shortest
    # name per time and country, and drop any name that starts with it.
    kept: list[dict[str, Any]] = []
    groups = {(event["date"], event["kst"], event["country"]) for event in events}
    for group in sorted(groups):
        chosen: list[dict[str, Any]] = []
        for event in sorted([e for e in events if (e["date"], e["kst"], e["country"]) == group],
                            key=lambda item: len(item["name"])):
            if any(event["name"].lower().startswith(other["name"].lower()) for other in chosen):
                continue
            chosen.append(event)
        kept.extend(chosen)
    kept.sort(key=lambda item: (item["date"], item["kst"]))

    days: list[dict[str, Any]] = []
    for offset in (0, 1):
        day_date = anchor + timedelta(days=offset)
        mine = [event for event in kept if event["date"] == day_date.isoformat()]
        if not mine and offset == 1:
            continue
        days.append({
            "date": day_date.isoformat(),
            "label": LABELS[offset],
            "weekday": WEEKDAYS[day_date.weekday()],
            "events": mine,
        })

    return {
        "updated_at": now.isoformat(),
        "updated_at_kst": now.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
        "source": "Nasdaq economic calendar",
        "timezone": "KST",
        "errors": errors,
        "days": days,
    }


def write(path: str) -> int:
    text = json.dumps(collect(), ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return len(text.encode("utf-8"))


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "calendar.json"
    print("wrote %s (%d bytes)" % (target, write(target)))
    payload = json.loads(open(target, encoding="utf-8").read())
    for day in payload["days"]:
        print("%s %s (%s) - %d" % (day["label"], day["date"], day["weekday"], len(day["events"])))
        for event in day["events"]:
            value = (" = %s" % event["actual"]) if event["released"] else (" vs %s" % event["consensus"] if event["consensus"] else "")
            print("   %s  %s %-14s %s%s" % (event["kst"], "*" * event["importance"], event["country"][:14], event["name"][:50], value))
    if payload["errors"]:
        print("errors:", payload["errors"])
