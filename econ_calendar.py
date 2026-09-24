"""Economic calendar for the dashboard: today and tomorrow, Korea time.

Source: Nasdaq's public economic calendar JSON (no key, no token, no paid tier).

Two quirks of that source are handled here, both verified against the data:

    * The time column is labelled "gmt" but holds US Eastern time (retail sales
      reads 08:30 for an 08:30 ET release), so times are read as ET.
    * The page for date D lists the events of ET day D-1 (the FOMC that settled
      on 16 Sep ET appears on the 17 Sep page), so the date is shifted back one day.

Importance is not published, so it is derived by keyword:

    Releases are ranked by keyword (3 = FOMC, CPI, PCE, payrolls, GDP, jobless claims,
    retail sales; 2 = PPI, ISM, PMI, housing, inventories, exports, imports, ...).
    Level 2 and above is published for every country in COUNTRIES, level 1 is dropped.

Three kinds of row are published:

    econ     the indicator releases above
    speech   central bank speakers and press conferences, ranked by who speaks
             (chair or president level first). The same feed names the speaker,
             e.g. "ECB President Lagarde Speaks", "FOMC Member Bowman Speaks".
    earnings mega-cap company results, from Nasdaq's earnings calendar, listed as
             before-the-bell or after-the-close because the source gives no clock.

Times are KST only, and the list is deliberately short: a glance list.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import potus_schedule

SOURCE_URL = "https://api.nasdaq.com/api/calendar/economicevents?date=%s"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
KST = timezone(timedelta(hours=9))
ET = timezone(timedelta(hours=-4))  # the source's time column is Eastern, not GMT

# Only these countries are shown; everything else is dropped as noise.
COUNTRIES = (
    "United States", "Japan", "United Kingdom", "South Korea", "China",
    "Euro Zone", "Germany", "Canada", "Australia",
)
COUNTRY_CODE = {
    "United States": "US",
    "Japan": "JP",
    "United Kingdom": "UK",
    "South Korea": "KR",
    "China": "CN",
    "Euro Zone": "EU",
    "Germany": "DE",
    "Canada": "CA",
    "Australia": "AU",
}
LEVEL3 = (
    "fomc", "fed funds", "interest rate decision", "rate decision",
    "powell", "cpi", "consumer price", "pce", "personal consumption", "nonfarm",
    "non-farm", "unemployment rate", "employment report", "payroll", "gdp",
    "gross domestic product", "jobless claims", "retail sales",
)
LEVEL2 = (
    "ppi", "producer price", "ism", "pmi", "durable goods", "industrial production",
    "consumer confidence", "consumer sentiment", "housing starts", "building permits",
    "trade balance", "adp", "crude oil inventories", "factory orders", "current account",
    "business confidence", "wholesale", "import price", "export price",
    # Korea's monthly trade report is a headline for the won and for risk appetite,
    # and Nasdaq names the parts plainly.
    "exports", "imports",
)
# Non-US releases used to be gated on this list; every listed country is now ranked
# with LEVEL3/LEVEL2 like the US, so the constant is gone.
# Minutes, auctions and forecast models stay out; speakers are kept as their own kind.
NOISE = ("minutes", "auction", "nowcast", "gdpnow", "4-week")
SPEAK_WORDS = ("speaks", "speech", "press conference", "testifies", "testimony", "remarks")
# Who is speaking decides the stars: chair and president level first, then the rest.
SPEAK_TOP = (
    "chair powell", "federal reserve chair", "fomc press conference", "ecb president",
    "president lagarde", "boj governor", "boj press conference", "bank of england governor",
    "treasury secretary", "vice chair",
)
SPEAK_HIGH = ("fomc member", "ecb's", "governor", "buba president", "rba gov", "deputy governor", "gov ")

# 2026 FOMC: who actually votes. From federalreserve.gov (the FOMC membership page and the
# July 2026 minutes' attendance list). The roster turns over at the first meeting of each
# year, so it carries its own as-of value and the page states it. A speaker is annotated
# only when the event name also says Fed/FOMC, so an ECB or Buba speaker whose surname
# happens to match is left alone.
FED_ROSTER_AS_OF = "2026"
FED_VOTERS = (
    "warsh", "williams", "barr", "bowman", "cook", "hammack",
    "jefferson", "kashkari", "logan", "paulson", "powell", "waller",
)
FED_NONVOTERS = (
    "barkin", "daly", "goolsbee", "shukla", "venable",   # 2026 alternates
    "bostic", "collins", "musalem", "schmid",            # attend, no vote this year
)
FED_MARKS = ("fed", "fomc", "federal reserve", "board of governors")


def fed_vote(name: str) -> str:
    """Return whether a Fed speaker votes in 2026, or '' when the speaker is not one.

    Word boundaries matter here for the same reason they do in the classifier: a bare
    substring test would let 'Barr' fire inside another name.
    """
    lowered = (name or "").lower()
    if not any(mark in lowered for mark in FED_MARKS):
        return ""
    for surname in FED_NONVOTERS:
        if re.search(r"\b" + surname + r"\b", lowered):
            return "비투표권"
    for surname in FED_VOTERS:
        if re.search(r"\b" + surname + r"\b", lowered):
            return "투표권"
    return ""
EARNINGS_URL = "https://api.nasdaq.com/api/calendar/earnings?date=%s"
# Only mega-caps: the calendar is a glance list, not an earnings dump.
EARNINGS_MIN_CAP = 50_000_000_000
EARNINGS_WHEN = {
    "time-pre-market": ("장전", "21:00"),
    "time-after-hours": ("장후", "05:00"),
    "time-not-supplied": ("시간미정", ""),
}
LABELS = {-1: "\uc5b4\uc81c", 0: "\uc624\ub298", 1: "\ub0b4\uc77c"}  # yesterday, today, tomorrow
WEEKDAYS = "\uc6d4\ud654\uc218\ubaa9\uae08\ud1a0\uc77c"  # Mon..Sun


def clean(value: Any) -> str:
    text = str(value if value is not None else "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def speaker_stars(name: str) -> int:
    """Rank a speaker by who is talking rather than by the event name."""
    lowered = name.lower()
    if any(key in lowered for key in SPEAK_TOP):
        return 5
    if any(key in lowered for key in SPEAK_HIGH):
        return 4
    return 3


def classify(name: str, country: str) -> tuple[int, str]:
    """Return (importance, kind), or (0, "") when the row should be dropped."""
    country = clean(country)
    if country not in COUNTRIES:
        return (0, "")
    lowered = name.lower()
    if any(word in lowered for word in NOISE):
        return (0, "")
    if any(word in lowered for word in SPEAK_WORDS):
        return (speaker_stars(name), "speech")
    level = 3 if any(key in lowered for key in LEVEL3) else (2 if any(key in lowered for key in LEVEL2) else 1)
    # Every listed country is ranked the same way: level 2 and up is published, level 1
    # is dropped. The old rule required a non-US name to *start* with one of a short
    # list of headline words, which silently dropped Korea entirely - its releases are
    # named plainly ("PPI", "Exports", "Consumer Confidence").
    return (level if level >= 2 else 0, "econ")


def decimal(text: str) -> str:
    """Turn a Fed style fraction ("3-3/4", "1/4", "4") into a decimal string."""
    text = text.strip()
    mixed = re.match(r"^(\d+)-(\d+)/(\d+)$", text)
    if mixed:
        return "%.2f" % (int(mixed.group(1)) + int(mixed.group(2)) / int(mixed.group(3)))
    frac = re.match(r"^(\d+)/(\d+)$", text)
    if frac:
        return "%.2f" % (int(frac.group(1)) / int(frac.group(2)))
    plain = re.match(r"^\d+(\.\d+)?$", text)
    return ("%.2f" % float(text)) if plain else text


def fed_funds_range(timeout: int = 40) -> str:
    """Fallback for the rate decision: Nasdaq often leaves that row blank, so read
    the target range straight out of the Federal Reserve's own FOMC statement."""
    import urllib.request

    feed = urllib.request.urlopen(urllib.request.Request(
        "https://www.federalreserve.gov/feeds/press_monetary.xml",
        headers={"User-Agent": UA}), timeout=timeout).read().decode("utf-8", "replace")
    link = ""
    for item in re.findall(r"<item>(.*?)</item>", feed, re.S):
        title = re.search(r"<title>(.*?)</title>", item, re.S)
        if title and "fomc statement" in title.group(1).lower():
            found = re.search(r"<link>(.*?)</link>", item, re.S)
            link = re.sub(r"<!\[CDATA\[|\]\]>", "", found.group(1)).strip() if found else ""
            break
    if not link:
        return ""
    page = urllib.request.urlopen(urllib.request.Request(
        link, headers={"User-Agent": UA}), timeout=timeout).read().decode("utf-8", "replace")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page))
    found = re.search(r"federal funds rate.*?to ([0-9/\-]+) to ([0-9/\-]+) percent", text, re.I)
    if not found:
        return ""
    return "%s~%s%%" % (decimal(found.group(1)), decimal(found.group(2)))


def fetch_day(day: str, timeout: int = 40) -> list[dict[str, Any]]:
    import urllib.request

    request = urllib.request.Request(SOURCE_URL % day, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    rows = (payload.get("data") or {}).get("rows") or []
    return [row for row in rows if isinstance(row, dict)]


def fetch_earnings(day: str, timeout: int = 40) -> list[dict[str, Any]]:
    import urllib.request

    request = urllib.request.Request(EARNINGS_URL % day, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read())
    rows = (payload.get("data") or {}).get("rows") or []
    return [row for row in rows if isinstance(row, dict)]


def money(value: Any) -> int:
    digits = re.sub(r"[^0-9]", "", str(value or ""))
    return int(digits) if digits else 0


def earnings_rows(page_date: date, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mega-cap results. The source publishes no clock, only before or after the bell,
    so each row carries an approximate KST time instead: 21:00 for a before-the-bell
    report, and 05:00 on the next KST day for an after-the-close one.

    Unlike the economic calendar, the earnings page is NOT shifted a day: the page for
    date D carries the companies reporting on ET D. Verified against COST, whose last
    report date (9/25/2025) and this year's page (9/24/2026) are both the last
    Thursday of September.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        symbol = clean(row.get("symbol"))
        cap = money(row.get("marketCap"))
        if not symbol or cap < EARNINGS_MIN_CAP:
            continue
        label, clock = EARNINGS_WHEN.get(clean(row.get("time")), ("", ""))
        day = page_date + timedelta(days=1) if label == "장후" else page_date
        company = clean(row.get("name"))
        out.append({
            "kst": clock,
            "approx": True,
            "date": day.isoformat(),
            "country": "United States",
            "country_code": "US",
            "name": ("%s %s (%s)" % (symbol, company, label)) if label else ("%s %s" % (symbol, company)),
            "kind": "earnings",
            "importance": 4 if cap >= 500_000_000_000 else 3,
            "actual": "",
            "consensus": "",
            "previous": "",
            "released": False,
            "passed": datetime.combine(day, datetime.min.time(), tzinfo=KST) <= datetime.now(KST),
        })
    return out


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

    for offset in (-2, -1, 0, 1, 2):  # covers the KST days either side of now
        page_date = anchor + timedelta(days=offset)
        try:
            rows = fetch_day(page_date.isoformat())
        except Exception as exc:  # a network problem must never break the dashboard
            errors.append("%s: %s" % (page_date.isoformat(), exc))
            continue
        # The page for date D lists ET day D-1, and its times are Eastern.
        midnight = datetime.combine(page_date - timedelta(days=1), datetime.min.time(), tzinfo=ET)
        for row in rows:
            parsed = clock(row.get("gmt"))
            name = clean(row.get("eventName"))
            country = clean(row.get("country"))
            if not parsed or not name:
                continue
            level, kind = classify(name, country)
            if not level:
                continue
            hour, minute = parsed
            moment = (midnight + timedelta(hours=hour, minutes=minute)).astimezone(KST)
            events.append({
                "kst": moment.strftime("%H:%M"),
                "date": moment.date().isoformat(),
                "country": country,
                "country_code": COUNTRY_CODE.get(country, country),
                "name": name,
                "kind": kind,
                "importance": level,
                "fed_vote": fed_vote(name) if kind == "speech" else "",
                "actual": clean(row.get("actual")),
                "consensus": clean(row.get("consensus")),
                "previous": clean(row.get("previous")),
                "released": bool(clean(row.get("actual"))),
                "passed": moment <= now,
            })

    # Mega-cap results, which the economic feed does not carry at all.
    for offset in (-1, 0, 1):
        page_date = anchor + timedelta(days=offset)
        try:
            rows = fetch_earnings(page_date.isoformat())
        except Exception as exc:  # a network problem must never break the dashboard
            errors.append("earnings %s: %s" % (page_date.isoformat(), exc))
            continue
        events.extend(earnings_rows(page_date, rows))

    # The President's public schedule, filtered down to newsworthy entries.
    try:
        events.extend(potus_schedule.fetch())
    except Exception as exc:  # a network problem must never break the dashboard
        errors.append("potus schedule: %s" % exc)

    # Nasdaq leaves the rate-decision row blank. Once that release is out, fill it from
    # the Fed's own statement rather than showing no result at all.
    try:
        target = fed_funds_range()
    except Exception:
        target = ""
    if target:
        for event in events:
            if (not event["released"] and event["passed"] and event["country"] == "United States"
                    and "interest rate decision" in event["name"].lower()):
                event["actual"] = target
                event["released"] = True

    # One release arrives as several rows (CPI / CPI n.s.a / CPIH). Keep the shortest
    # name per time and country, and drop any name that starts with it. Only indicator
    # releases are collapsed: several companies can report at the same minute and
    # several White House entries can share a slot, so folding those by name length
    # would silently delete most of them.
    kept: list[dict[str, Any]] = [event for event in events if event["kind"] != "econ"]
    release_rows = [event for event in events if event["kind"] == "econ"]
    groups = {(event["date"], event["kst"], event["country"]) for event in release_rows}
    for group in sorted(groups):
        chosen: list[dict[str, Any]] = []
        for event in sorted([e for e in release_rows if (e["date"], e["kst"], e["country"]) == group],
                            key=lambda item: len(item["name"])):
            if any(event["name"].lower().startswith(other["name"].lower()) for other in chosen):
                continue
            chosen.append(event)
        kept.extend(chosen)
    # A result with no clock goes last inside its own day.
    kept.sort(key=lambda item: (item["date"], item["kst"] or "99:99"))

    days: list[dict[str, Any]] = []
    for offset in (-1, 0, 1):
        day_date = anchor + timedelta(days=offset)
        mine = [event for event in kept if event["date"] == day_date.isoformat()]
        if not mine:
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
        "fed_roster_as_of": FED_ROSTER_AS_OF,
        "countries": list(COUNTRIES),
        "errors": errors,
        "days": days,
    }


def write(path: str) -> int:
    text = json.dumps(collect(), ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return len(text.encode("utf-8"))


# The dashboard serves the calendar from /api/calendar, so the build has to be cheap to call
# repeatedly and must not go blank when the source hiccups. One cached payload per process:
# rebuilt at most every max_age seconds, and on failure the previous payload is returned.
_PAYLOAD: dict[str, Any] = {"built_at": 0.0, "payload": None}
PAYLOAD_MAX_AGE = 300


def cached_payload(max_age: int = PAYLOAD_MAX_AGE) -> dict[str, Any]:
    """The calendar as a dict, rebuilt at most once every max_age seconds."""
    payload = _PAYLOAD["payload"]
    if payload is not None and time.monotonic() - _PAYLOAD["built_at"] < max_age:
        return payload
    try:
        fresh = collect()
    except Exception:
        if payload is not None:
            return payload
        raise
    _PAYLOAD["built_at"] = time.monotonic()
    _PAYLOAD["payload"] = fresh
    return fresh


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "calendar.json"
    print("wrote %s (%d bytes)" % (target, write(target)))
    payload = json.loads(open(target, encoding="utf-8").read())
    for day in payload["days"]:
        print("%s %s (%s) - %d" % (day["label"], day["date"], day["weekday"], len(day["events"])))
        for event in day["events"]:
            value = (" = %s" % event["actual"]) if event["released"] else (" vs %s" % event["consensus"] if event["consensus"] else "")
            print("   %s  %s %-3s %s%s" % (event["kst"], "*" * event["importance"], event["country_code"], event["name"][:50], value))
    if payload["errors"]:
        print("errors:", payload["errors"])
