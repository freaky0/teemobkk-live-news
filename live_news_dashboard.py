from __future__ import annotations

import argparse
import admin_auth
import admin_page
import category_rules as taxonomy
import econ_calendar
import filter_learn
import google_news
import bluesky_source
import sbh_open_news
import sbh_source
import telegram_source
import whitehouse_source
import difflib
import email.utils
import html
import json
import logging
import re
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / "news.db"
PUBLIC_MODE = False
DEFAULT_INTERVAL = 30
RETENTION_HOURS = 24
ARCHIVE_DAYS = 90
# How long a Teemo's Pick phrase may be. It shows as one truncated line in the row and opens in full
# on hover, so the ceiling is about what the operator would ever type, not about the screen.
PICK_NOTE_MAX = 300
DEFAULT_LIMIT = 300
MAX_LIMIT = 1000
ICT = timezone(timedelta(hours=7), name="ICT")
THAI_REGION = "태국"
GLOBAL_REGION = "글로벌"
GENERIC_CATEGORY = "일반"
STATIC_FILES = {
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/favicon-32.png": ("favicon-32.png", "image/png"),
    "/favicon-16.png": ("favicon-16.png", "image/png"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
    "/robots.txt": ("robots.txt", "text/plain; charset=utf-8"),
    "/sitemap.xml": ("sitemap.xml", "application/xml; charset=utf-8"),
    "/privacy": ("privacy.html", "text/html; charset=utf-8"),
    "/privacy/": ("privacy.html", "text/html; charset=utf-8"),
    "/privacy/en": ("privacy_en.html", "text/html; charset=utf-8"),
    "/privacy/en/": ("privacy_en.html", "text/html; charset=utf-8"),
}

USER_AGENT = "TeemoLiveNewsDashboard/1.0 (+local research dashboard)"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RSS_SOURCES = [
    ("CoinDesk", "crypto", "https://www.coindesk.com/arc/outboundfeeds/rss"),
    ("Cointelegraph", "crypto", "https://cointelegraph.com/rss"),
    ("The Block", "crypto", "https://www.theblock.co/rss.xml"),
    ("CryptoSlate", "crypto", "https://cryptoslate.com/feed/"),
    ("Decrypt", "crypto", "https://decrypt.co/feed"),
    ("Bitcoin Magazine", "crypto", "https://bitcoinmagazine.com/.rss/full/"),
    ("SEC", "official", "https://www.sec.gov/news/pressreleases.rss"),
    ("Federal Reserve", "official", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Fed Speeches", "official", "https://www.federalreserve.gov/feeds/speeches.xml"),
    ("ECB", "official", "https://www.ecb.europa.eu/rss/press.html"),
    ("Bank of England", "official", "https://www.bankofengland.co.uk/rss/news"),
    # Macro and market wires. Measured on the day they were added: 7-50 items each, newest within
    # a day, so they are alive rather than cached shells (tools/probe_sources.py).
    ("MarketWatch", "news", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("CNBC Finance", "news", "https://www.cnbc.com/id/10000664/device/rss/rss.html"),
    ("Yahoo Finance", "news", "https://finance.yahoo.com/news/rssindex"),
    ("Investing.com", "news", "https://www.investing.com/rss/news.rss"),
    ("Seeking Alpha", "news", "https://seekingalpha.com/market_currents.xml"),
    ("FinancialJuice", "breaking", "https://www.financialjuice.com/feed.ashx?xy=rss"),
]

# The last real answer per source, so a source that is skipped this cycle keeps showing what it
# actually said the last time it was asked.
_last_source_status: dict[str, Any] = {}
_cycle = {"count": 0}

# Sources that answer a datacenter address differently from a home connection, or that rate-limit a
# single host: fetched every Nth cycle instead of every cycle. Measured facts behind this list:
# FinancialJuice answered 429 intermittently (14 refusals in 24 hours while being fetched once a
# minute), and it is a wire that repeats itself, so a slower poll loses nothing. FXStreet was dropped
# instead of slowed: it answers 403 to the deployed host and 200 to a home connection, so it passed
# the check when it was added and never produced a single row in production.
SLOW_SOURCES = {"FinancialJuice": 5}

# 태국 교민용 일반 뉴스. 영문 매체와 태국어 매체를 함께 수집한다.
THAI_RSS_SOURCES = [
    ("Bangkok Post", "thai", "https://www.bangkokpost.com/rss/data/topstories.xml"),
    ("Bangkok Post Business", "thai", "https://www.bangkokpost.com/rss/data/business.xml"),
    ("Khaosod English", "thai", "https://www.khaosodenglish.com/feed/"),
    ("Thai Enquirer", "thai", "https://www.thaienquirer.com/feed/"),
    ("Prachatai English", "thai", "https://prachataienglish.com/feed/"),
    ("Thairath", "thai", "https://www.thairath.co.th/rss/news"),
    ("Matichon", "thai", "https://www.matichon.co.th/feed"),
]

COINNESS_BREAKING_URL = "https://api.coinness.com/feed/v2/breaking-news"
COINNESS_STOCK_URL = "https://api.coinness.com/feed/v1/stock-breaking-news"
SBH_SITEMAP_URL = "https://www.sbhnews.com/sitemap.xml"
SBH_SITEMAP_TTL = 600
_sbh_sitemap_cache: dict[str, Any] = {"at": 0.0, "urls": []}

GOOGLE_QUERIES = [
    ("Google News · Bitcoin", "bitcoin when:2d"),
    ("Google News · ETF", "bitcoin ETF when:2d"),
    ("Google News · 유동성", "bitcoin liquidity OR Treasury OR repo OR QT when:2d"),
    ("Google News · 금리·달러", "bitcoin Fed interest rates DXY yield when:2d"),
    ("Google News · 미국 정책·트럼프", "Trump crypto bitcoin White House tariff when:2d"),
    ("Google News · 지정학", "bitcoin Iran OR Israel OR Taiwan when:2d"),
    ("Google News · 파생상품", "bitcoin liquidation when:2d"),
    ("Google News · 온체인·기관", "bitcoin onchain when:2d"),
    ("Google News · 스테이블코인", "bitcoin stablecoin USDT USDC liquidity when:2d"),
    ("Google News · X 발언", "bitcoin Saylor OR Musk OR Dorsey when:2d"),
]

# 태국 관련 구글 뉴스. 한국어 쿼리는 태국 관련 항목만 남기도록 제목 필터를 건다.
THAI_GOOGLE_QUERIES = [
    ("Google News · 태국", "Thailand when:1d", ()),
    ("Google News · 방콕", "Bangkok when:1d", ()),
    ("Google News · 태국 교민", "태국 when:2d", ("태국", "방콕", "치앙마이", "푸껫", "파타야", "태국인")),
]

# 태국 탭에서 걸러낼 저품질·비태국 매체. 구글뉴스 제목 뒤에 붙는 매체명으로 판별한다.
THAI_BLOCK_TERMS = ("calgary roughnecks", "specialtimes", "vietnam.vn", "vietnamnet", "vnexpress", "baoquocte")

def fetch_bytes(url: str, timeout: int = 12) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, application/json, text/xml, */*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def first_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return clean_text(found.text)
    return ""


def parse_date(value: str) -> str:
    if not value:
        return ""
    # Some feeds use YYYYMMDDhhmmss, while RSS commonly uses RFC 822 or ISO 8601.
    if re.fullmatch(r"\d{14}", value.strip()):
        try:
            return datetime.strptime(value.strip(), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return ""
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            return ""


def parse_rss(payload: bytes, source: str, source_type: str, region: str = "글로벌") -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    output = []
    for item in entries:
        title = first_text(item, ("title", "{http://www.w3.org/2005/Atom}title"))
        link = first_text(item, ("link", "{http://www.w3.org/2005/Atom}link"))
        if not link:
            link_node = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_node.attrib.get("href", "") if link_node is not None else ""
        summary = first_text(item, ("description", "summary", "{http://www.w3.org/2005/Atom}summary", "{http://www.w3.org/2005/Atom}content"))
        published = first_text(item, ("pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"))
        # Google News names the publisher in <source>, and that name is the only one the feed
        # carries for the story: the row is filed under the collecting query ("Google News · ETF")
        # because that is what the source filter addresses, so the publisher name is kept apart in
        # its own field instead of replacing it. Feeds that carry no <source> leave it empty and the
        # page falls back to the hostname of the resolved link.
        original_source = first_text(item, ("source", "{http://www.w3.org/2005/Atom}source"))
        if title and link:
            output.append(make_article(title, link, summary, parse_date(published), source, source_type,
                                       region, original_source))
    return output


def canonical_link(link: str) -> str:
    """Drop tracking parameters that would turn one article into several rows.

    FinancialJuice serves the same story as ?xy=rss, ?xy=free, ?xy=1 or with no query at
    all, and which variant a request gets back varies from request to request. The link
    is the table's primary key, so without this the same story is stored once per variant
    and separated by whole collection cycles, which no in-cycle title check can catch.
    """
    link = (link or "").strip()
    if re.match(r"^https?://(?:www\.)?financialjuice\.com/news/", link, re.I):
        return link.split("?", 1)[0].split("#", 1)[0]
    return link


def make_article(title: str, link: str, summary: str, published: str, source: str, source_type: str,
                 region: str = "글로벌", original_source: str = "") -> dict[str, Any]:
    link = canonical_link(link)
    title = re.sub(r"^FinancialJuice:\s*", "", title or "")
    text = f"{title} {summary}".lower()
    categories = taxonomy.match_all(text, taxonomy.rules_for(region, THAI_REGION)) or [GENERIC_CATEGORY]
    category = categories[0]
    if region == "태국":
        asset = "태국"
        priority = 2
        if category in {"태국 정치·사회", "태국 경제"}:
            priority += 1
        if category in {"비자·이민", "사고·재난"}:
            priority += 2
        if source_type == "official":
            priority += 1
        if any(word in text for word in ("urgent", "breaking", "warning", "alert", "속보", "긴급", "경보")):
            priority += 1
    else:
        if "bitcoin" in text or "btc" in text or "비트코인" in text:
            asset = "BTC"
        elif "ethereum" in text or " ether " in f" {text} " or re.search(r"(?<![a-z])eth(?![a-z])", text):
            asset = "ETH"
        else:
            asset = "시장"
        priority = 3
        if source_type == "official":
            priority += 2
        # No blanket bonus for breaking-news feeds. FinancialJuice, SBHNews and CoinNess
        # stamp *every* item as breaking, which pinned a whole source at the top band no
        # matter what it published (measured: 100% of each source's day at 4+; after this
        # change the same sources sit at 17-40%). The per-article keyword check below
        # carries the real urgency signal.
        if category in {"ETF·수급", "규제·정책", "거시경제", "지정학"}:
            priority += 1
        if any(word in text for word in ("breaking", "urgent", "hack", "approval", "approved", "소식")):
            priority += 1
    return {
        "title": clean_text(title),
        "summary": clean_text(summary)[:800],
        "link": link.strip(),
        "source": source,
        # The publisher's own name from the feed, kept beside `source` rather than replacing it.
        "original_source": clean_text(original_source),
        "source_type": source_type,
        "region": region,
        "category": category,
        "categories": categories,
        "asset": asset,
        "priority": min(priority, 5),
        "published_at": published,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_google_news(source: str, query: str, region: str = "글로벌", require_terms: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    korean = any("\uac00" <= char <= "\ud7a3" for char in query)
    params = urllib.parse.urlencode({"q": query, "hl": "ko" if korean else "en-US", "gl": "KR" if korean else "US", "ceid": "KR:ko" if korean else "US:en"})
    url = f"https://news.google.com/rss/search?{params}"
    try:
        fetched = parse_rss(fetch_bytes(url), source, "aggregated", region)
    except Exception as exc:
        logging.warning("Google News failed (%s): %s", query, exc)
        return []
    if require_terms:
        fetched = [article for article in fetched if any(term in f"{article['title']} {article['summary']}" for term in require_terms)]
    if region == "태국":
        fetched = [article for article in fetched if not any(block in article["title"].lower() for block in THAI_BLOCK_TERMS)]
    return fetched


def _coinness_items(url: str, source: str, limit: int, link_path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target = f"{url}?limit={limit}"
    try:
        request = urllib.request.Request(target, headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Origin": "https://coinness.com", "Referer": "https://coinness.com/"})
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        items = data if isinstance(data, list) else data.get("items", [])
        output = []
        for item in items:
            title = clean_text(item.get("title", ""))
            # CoinNess sends no link for either feed, so the article URL is built per feed:
            # breaking news lives at /news/{id}, stock news at /stock-news/{id}/quote.
            link = (item.get("link") or "").strip() or "https://coinness.com/" + link_path.format(item_id=item.get("id", ""))
            if title and link:
                article = make_article(title, link, item.get("content", ""), parse_date(item.get("publishAt", "")), source, "breaking")
                if item.get("isImportant"):
                    article["priority"] = min(article["priority"] + 1, 5)
                output.append(article)
        return output, {"ok": True, "count": len(output), "fetched": len(items), "url": target}
    except Exception as exc:
        logging.warning("CoinNess failed (%s): %s", source, exc)
        return [], {"ok": False, "count": 0, "url": target, "error": str(exc)[:180]}


def fetch_coinness(limit: int = 30) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return _coinness_items(COINNESS_BREAKING_URL, "CoinNess", limit, "news/{item_id}")


def fetch_coinness_stock(limit: int = 30) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return _coinness_items(COINNESS_STOCK_URL, "CoinNess Stock", limit, "stock-news/{item_id}/quote")


def _sbh_recent_urls() -> list[str]:
    now = time.monotonic()
    if now - _sbh_sitemap_cache["at"] < SBH_SITEMAP_TTL and _sbh_sitemap_cache["urls"]:
        return _sbh_sitemap_cache["urls"]
    payload = fetch_bytes(SBH_SITEMAP_URL, timeout=25).decode("utf-8", errors="replace")
    locs = re.findall(r"<loc>(https://www\.sbhnews\.com/news/[^<]+)</loc>", payload)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)
    kst = timezone(timedelta(hours=9), name="KST")
    recent = []
    for loc in locs:
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})-(AM|PM)-(\d{2})-(\d{2})$", loc)
        if not match:
            continue
        year, mon, day, meridiem, hour, minute = match.groups()
        hour = int(hour) % 12 + (12 if meridiem == "PM" else 0)
        try:
            published = datetime(int(year), int(mon), int(day), hour, int(minute), tzinfo=kst).astimezone(timezone.utc)
        except ValueError:
            continue
        if published >= cutoff:
            recent.append((published, loc))
    recent.sort(reverse=True)
    urls = [loc for _, loc in recent]
    _sbh_sitemap_cache["at"] = now
    _sbh_sitemap_cache["urls"] = urls
    return urls


def _sbh_parse_page(payload: bytes) -> tuple[str, str, str]:
    text = payload.decode("utf-8", errors="replace")
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)
    if not match:
        return "", "", ""
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return "", "", ""
    if isinstance(data, list):
        data = next((entry for entry in data if isinstance(entry, dict) and entry.get("@type") == "NewsArticle"), {})
    if not isinstance(data, dict):
        return "", "", ""
    return clean_text(data.get("headline", "")), clean_text(data.get("description", "")), data.get("datePublished", "") or ""


def fetch_sbhnews(max_pages: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        urls = _sbh_recent_urls()
    except Exception as exc:
        logging.warning("SBHNews sitemap failed: %s", exc)
        return [], {"ok": False, "count": 0, "url": SBH_SITEMAP_URL, "error": str(exc)[:180]}
    try:
        seen = existing_links()
    except Exception:
        seen = set()
    pending = [url for url in urls if url not in seen][:max_pages]

    def load(url: str) -> tuple[str, tuple[str, str, str]]:
        try:
            return url, _sbh_parse_page(fetch_bytes(url, timeout=10))
        except Exception as exc:
            logging.warning("SBHNews page failed (%s): %s", url, exc)
            return url, ("", "", "")

    output: list[dict[str, Any]] = []
    if pending:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for url, (headline, description, published) in pool.map(load, pending):
                if headline:
                    output.append(make_article(headline, url, description, parse_date(published), "SBHNews", "breaking"))
    return output, {"ok": True, "count": len(output), "scanned": len(urls), "pending": len(pending), "url": SBH_SITEMAP_URL}


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", title.lower())


# Only remove a publisher suffix that matches the row's known publisher. A generic " - tail" rule
# can erase meaningful parts of headlines (for example, "... - after talks continue").
_PUBLISHER_ALIASES = {
    "新华网": ("Xinhua",),
    "xinhua": ("新华网",),
}


def dedupe_key(title: str, publisher: str = "") -> str:
    """The identity two copies of one story share.

    Measured on the live Thailand window (300 rows, 2026-09-26): the same wire story arrived as
    "Thailand issues warning of heavy rain" from Global Times, from english.news.cn twice under two
    different Google links, and from Xinhua. Their headlines are identical once the trailing outlet
    name is removed, which is what this key does before comparing anything.
    """
    text = str(title or "")
    publisher_names = [str(publisher or "").strip()]
    publisher_names.extend(_PUBLISHER_ALIASES.get(publisher_names[0].casefold(), ()))
    for name in publisher_names:
        if name:
            text = re.sub(r"\s*[-\u2013\u2014|]\s*" + re.escape(name) + r"\s*$", "", text,
                          flags=re.IGNORECASE)
    return normalize_title(text)


def publisher_url(link: str) -> str:
    """A story identity taken from a link that is the publisher's own: no query, no fragment.

    An aggregator link is not an identity - Google hands the same article out under several of them
    - so it answers "" here and the caller falls back to the title key.
    """
    link = canonical_link(link or "")
    if not link or google_news.is_aggregator(link):
        return ""
    return link.split("#", 1)[0].split("?", 1)[0]


def _story_identity(article: dict[str, Any], resolved: str = "") -> tuple[str, str]:
    """(title key, publisher url) for a row; the publisher url is "" when the story has none."""
    key = dedupe_key(str(article.get("title") or ""), str(article.get("original_source") or ""))
    url = publisher_url(str(article.get("link") or "")) or str(resolved or "")
    return key, url.split("#", 1)[0].split("?", 1)[0] if url else ""


def dedupe(articles: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    articles = sorted(articles, key=lambda item: (item.get("published_at", ""), item["priority"]), reverse=True)
    kept: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    urls: set[str] = set()
    keys: list[str] = []
    for article in articles:
        link = canonical_link(article["link"])
        key, url = _story_identity(article)
        if link in seen_links:
            continue
        if url and url in urls:
            continue
        if key and any(_similar_title(key, old) for old in keys):
            continue
        seen_links.add(link)
        if url:
            urls.add(url)
        keys.append(key)
        article["link"] = link
        kept.append(article)
    return kept if limit is None else kept[:limit]


def _similar_title(key: str, old: str) -> bool:
    # quick_ratio is an upper bound on ratio, so it safely prefilters the expensive compare.
    matcher = difflib.SequenceMatcher(None, key, old)
    return matcher.quick_ratio() >= 0.88 and matcher.ratio() >= 0.88


def dedupe_by_region(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    thai = [article for article in articles if article.get("region") == THAI_REGION]
    other = [article for article in articles if article.get("region") != THAI_REGION]
    return dedupe(other) + dedupe(thai)


def stored_identities(hours: int = RETENTION_HOURS) -> dict[str, tuple[set[str], set[str]]]:
    """{region: (title keys, publisher urls)} of the stories already stored inside the window.

    Per region on purpose: the same story is filed under both the global and the Thailand view, and
    each tab is meant to show it - the two views are not duplicates of each other.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(hours)))).isoformat()
    with DB_LOCK, db_connect() as connection:
        rows = connection.execute(
            "SELECT link, title, region, original_source FROM articles WHERE published_at >= ?",
            (cutoff,)).fetchall()
        try:
            resolved = google_news.load(connection)
        except sqlite3.Error:
            resolved = {}
    known: dict[str, tuple[set[str], set[str]]] = {}
    for row in rows:
        region = str(row["region"] or GLOBAL_REGION)
        keys, urls = known.setdefault(region, (set(), set()))
        key, url = _story_identity({"title": row["title"], "link": row["link"],
                                    "original_source": row["original_source"]},
                                   resolved.get(str(row["link"] or ""), ""))
        if key:
            keys.add(key)
        if url:
            urls.add(url)
    return known


def _identity_equal(key: str, url: str, keys: set[str], urls: set[str]) -> bool:
    """Whether this story is already in the set: the same link identity, or the same headline.

    The headline compare is exact and the fuzzy one is only used by the in-cycle dedupe, so two
    different stories that merely share a topic ("Flooding hits Bangkok…" and "Bangkok Flood Risk
    Rises…", measured 0.55 apart) stay two stories.
    """
    if url and url in urls:
        return True
    return bool(key) and key in keys


def drop_already_stored(articles: list[dict[str, Any]],
                        hours: int = RETENTION_HOURS) -> list[dict[str, Any]]:
    """The same story, seen again in a later cycle, is not stored twice.

    The link is the table's key, so an identical link could never be inserted twice - what got
    through was the same story arriving under a second Google link for the same article, or from a
    second outlet carrying the same wire copy. Measured on the live Thailand window: 52 of 300 rows
    (17%) repeated a story that was already there.
    """
    known = stored_identities(hours)
    kept: list[dict[str, Any]] = []
    for article in articles:
        region = str(article.get("region") or GLOBAL_REGION)
        keys, urls = known.setdefault(region, (set(), set()))
        key, url = _story_identity(article)
        if _identity_equal(key, url, keys, urls):
            continue
        if key:
            keys.add(key)
        if url:
            urls.add(url)
        kept.append(article)
    return kept


def dedupe_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same screen dedupe, applied to rows on their way out to a reader.

    Rows arrive newest first, and the newest copy is the one kept. This runs on the read paths that
    feed a screen - the API the pages read and the published JSON - so the duplicates already in the
    database stop being shown, while nothing is deleted and the push path keeps its own selection.
    """
    seen: dict[str, tuple[set[str], set[str]]] = {}
    seen_links: dict[str, set[str]] = {}
    out: list[dict[str, Any]] = []
    for item in items:
        region = str(item.get("region") or GLOBAL_REGION)
        keys, urls = seen.setdefault(region, (set(), set()))
        links = seen_links.setdefault(region, set())
        link = canonical_link(str(item.get("link") or ""))
        if link and link in links:
            continue
        key, url = _story_identity(item, str(item.get("original_link") or ""))
        if _identity_equal(key, url, keys, urls):
            continue
        if link:
            links.add(link)
        if key:
            keys.add(key)
        if url:
            urls.add(url)
        out.append(item)
    return out


def keep_recent(articles: list[dict[str, Any]], hours: int = RETENTION_HOURS) -> list[dict[str, Any]]:
    """Keep only articles with a parseable publication time inside the rolling window."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    ceiling = now + timedelta(hours=1)
    kept = []
    for article in articles:
        value = article.get("published_at", "")
        try:
            published = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
            if published > ceiling:
                # Some feeds mislabel local time; a far-future stamp would pin the card to the top forever.
                published = now
                article["published_at"] = now.isoformat()
            if published >= cutoff:
                kept.append(article)
        except (AttributeError, ValueError):
            continue
    return kept


DB_LOCK = threading.Lock()


def _kwmatch(text: str, needle: str) -> int:
    """SQL-callable wrapper for the shared term rule, so the filter runs inside the query.

    Filtering in Python after the query would break LIMIT/OFFSET: the page count comes from a COUNT
    over the same WHERE clause.
    """
    return 1 if taxonomy.text_matches(text, needle) else 0


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_FILE, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.create_function("kwmatch", 2, _kwmatch, deterministic=True)
    return connection


_ORIGINALS: dict[str, Any] = {"loaded_at": 0.0, "map": {}}
ORIGINALS_TTL_SECONDS = 300


def original_links() -> dict[str, str]:
    """Cached {Google News link: publisher url} for the pages that read the feed.

    The resolution itself happens outside the collector (publish job and the repair tool);
    here it is only read, at most once every five minutes, so a reader request never waits
    on Google. A read failure keeps the previous map rather than dropping every link back
    to the aggregator.
    """
    if time.monotonic() - _ORIGINALS["loaded_at"] < ORIGINALS_TTL_SECONDS:
        return _ORIGINALS["map"]
    try:
        with db_connect() as connection:
            fresh = google_news.load(connection)
    except sqlite3.Error:
        return _ORIGINALS["map"]
    _ORIGINALS["loaded_at"] = time.monotonic()
    _ORIGINALS["map"] = fresh
    return fresh


def init_db() -> None:
    with DB_LOCK, db_connect() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS articles ("
            "link TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT, source TEXT, source_type TEXT, "
            "region TEXT, category TEXT, categories TEXT, asset TEXT, priority INTEGER, "
            "published_at TEXT NOT NULL, collected_at TEXT)"
        )
        # A database created before multi-label matching has no `categories` column. Add it and
        # leave the old rows blank rather than guessing at them: split_categories() falls back to
        # `category`, and tools/retag_categories.py recomputes the archive from the stored text.
        columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
        if "categories" not in columns:
            connection.execute("ALTER TABLE articles ADD COLUMN categories TEXT")
        # The publisher's own name from the feed, for the rows whose Google News link has been
        # resolved. A database written before this column existed keeps NULL for every old row:
        # the page then falls back to the hostname of the resolved link, which needs no backfill.
        if "original_source" not in columns:
            connection.execute("ALTER TABLE articles ADD COLUMN original_source TEXT")
        # No index on `categories`: the filter is a contains-match, which no index can serve.
        for column in ("published_at", "region", "category", "source", "priority"):
            connection.execute(f"CREATE INDEX IF NOT EXISTS idx_articles_{column} ON articles({column})")
        # Hiding is a filter on every read path, not a delete: the row stays, so the same story
        # cannot come back through a different filter, and a wrong call can be undone. The link is
        # the key because that is what the collector and the reader both treat as the story.
        connection.execute(
            "CREATE TABLE IF NOT EXISTS hidden_links ("
            "link TEXT PRIMARY KEY, title TEXT, hidden_at TEXT)"
        )
        # What the operator has picked out. Separate from priority and the star rating on purpose:
        # those are computed from the text, this is a judgement, and a reader is meant to see the
        # difference. The sort order never consults it either - a quiet hour must not look like a
        # feed that stopped moving.
        connection.execute(
            "CREATE TABLE IF NOT EXISTS picked_links ("
            "link TEXT PRIMARY KEY, note TEXT, picked_at TEXT)"
        )
        # Operator settings that have to survive a restart. The collector holds the refresh interval
        # in memory and an update restarts it, so a change made from /admin used to be forgotten the
        # next time the service came up - the operator had to notice and set it again.
        connection.execute(
            "CREATE TABLE IF NOT EXISTS settings ("
            "name TEXT PRIMARY KEY, value TEXT, changed_at TEXT)"
        )
        # A pattern that keeps a story off the pages. Kept apart from hidden_links because the
        # reason is different: hiding is one judgement about one story, a rule is a judgement that
        # keeps being applied. The stories a rule catches are recorded in filter_hits, so turning
        # the rule off gives all of them back - filtering never becomes a silent delete.
        connection.execute(
            "CREATE TABLE IF NOT EXISTS filter_rules ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, pattern TEXT NOT NULL UNIQUE, kind TEXT,"
            "origin TEXT, enabled INTEGER NOT NULL DEFAULT 0, hits INTEGER NOT NULL DEFAULT 0,"
            "created_at TEXT, last_hit_at TEXT)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS filter_hits ("
            "link TEXT PRIMARY KEY, rule_id INTEGER, matched_at TEXT)"
        )
        # A story a rule caught that the operator chose to keep. Without this the only way to be
        # right about a false positive would be to give up the rule, and a rule that is mostly
        # right is worth more than one that catches nothing.
        connection.execute(
            "CREATE TABLE IF NOT EXISTS filter_keeps ("
            "link TEXT PRIMARY KEY, kept_at TEXT)"
        )


def insert_articles(articles: list[dict[str, Any]]) -> int:
    rows = [
        (
            article.get("link", ""), article.get("title", ""), article.get("summary", ""),
            article.get("source", ""), article.get("source_type", ""), article.get("region", GLOBAL_REGION),
            article.get("category", GENERIC_CATEGORY), taxonomy.join_categories(
                article.get("categories") or [article.get("category", GENERIC_CATEGORY)]),
            article.get("asset", ""), int(article.get("priority", 3)),
            article.get("published_at", ""), article.get("collected_at", ""),
            article.get("original_source", ""),
        )
        for article in articles
        if article.get("link") and article.get("published_at")
    ]
    if not rows:
        return 0
    with DB_LOCK, db_connect() as connection:
        before = connection.total_changes
        connection.executemany(
            "INSERT OR IGNORE INTO articles (link, title, summary, source, source_type, region, category, categories, asset, priority, published_at, collected_at, original_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        inserted = connection.total_changes - before
        # A row collected before this column existed - or one whose feed had not published a
        # publisher name yet - carries a blank name, and INSERT OR IGNORE would leave it blank for
        # good. The name therefore moves one way only: from empty to filled, and only for the row's
        # own link. Everything else about the row is left alone, and `source` is never part of this
        # update - it is the query identity the source filter, the source pills and the push history
        # address a story by, so a publisher name must not be able to rewrite it.
        backfills = [
            (str(article.get("original_source") or "").strip(), str(article.get("link") or ""))
            for article in articles
            if str(article.get("original_source") or "").strip() and article.get("link")
        ]
        if backfills:
            connection.executemany(
                "UPDATE articles SET original_source = ? "
                "WHERE link = ? AND (original_source IS NULL OR TRIM(original_source) = '')",
                backfills,
            )
            filled = connection.total_changes - before - inserted
            if filled:
                logging.info("publisher names backfilled: %d", filled)
        # The rules are asked about the stories in the same breath as the insert, so a filtered
        # story is registered and skipped in one transaction and cannot show up in between.
        _record_filter_hits(connection, rows)
        return inserted


def prune_archive(days: int = ARCHIVE_DAYS) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with DB_LOCK, db_connect() as connection:
        before = connection.total_changes
        connection.execute("DELETE FROM articles WHERE published_at < ?", (cutoff,))
        return connection.total_changes - before


def existing_links(hours: int = RETENTION_HOURS) -> set[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with DB_LOCK, db_connect() as connection:
        return {row[0] for row in connection.execute("SELECT link FROM articles WHERE published_at >= ?", (cutoff,))}


def archive_stats() -> dict[str, Any]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)).isoformat()
    with DB_LOCK, db_connect() as connection:
        total = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] or 0
        recent = connection.execute("SELECT COUNT(*) FROM articles WHERE published_at >= ?", (cutoff,)).fetchone()[0] or 0
        oldest = connection.execute("SELECT MIN(published_at) FROM articles").fetchone()[0]
        # Stored and hidden are two different numbers on purpose: the operator's archive count is
        # what the database holds, and the hidden count is what readers are not being shown.
        hidden = connection.execute("SELECT COUNT(*) FROM hidden_links").fetchone()[0] or 0
    return {"archived_total": int(total), "window_total": int(recent), "oldest_published_at": oldest,
            "archive_days": ARCHIVE_DAYS, "hidden_total": int(hidden)}


def picked_links(limit: int = 500) -> list[dict[str, Any]]:
    """Everything the operator has picked, newest first, with the headline from the archive."""
    with DB_LOCK, db_connect() as connection:
        rows = connection.execute(
            "SELECT p.link, COALESCE(NULLIF(a.title, ''), ''), a.source, a.published_at, p.note, p.picked_at "
            "FROM picked_links p LEFT JOIN articles a ON a.link = p.link "
            "ORDER BY p.picked_at DESC LIMIT ?", (int(limit),)).fetchall()
    return [{"link": row[0], "title": row[1] or "", "source": row[2] or "", "published_at": row[3] or "",
             "note": row[4] or "", "picked_at": row[5] or ""} for row in rows]


def pick_map() -> dict[str, str]:
    """The picks as {link: note}, for marking rows on their way out.

    A map rather than a join: the picks are a few dozen rows and the article query is the hot path,
    so the marking costs one small read instead of another clause on every page of the feed.
    """
    with DB_LOCK, db_connect() as connection:
        return {row[0]: (row[1] or "") for row in connection.execute("SELECT link, note FROM picked_links")}


def pick_link(link: str, note: str = "") -> int:
    when = datetime.now(timezone.utc).isoformat()
    with DB_LOCK, db_connect() as connection:
        connection.execute(
            "INSERT INTO picked_links (link, note, picked_at) VALUES (?, ?, ?) "
            "ON CONFLICT(link) DO UPDATE SET note = excluded.note, picked_at = excluded.picked_at",
            (link, note, when))
        return connection.execute("SELECT COUNT(*) FROM picked_links").fetchone()[0] or 0


def unpick_link(link: str) -> int:
    with DB_LOCK, db_connect() as connection:
        connection.execute("DELETE FROM picked_links WHERE link = ?", (link,))
        return connection.execute("SELECT COUNT(*) FROM picked_links").fetchone()[0] or 0


def setting_get(name: str) -> str | None:
    """A stored operator setting, or None when it has never been set."""
    with DB_LOCK, db_connect() as connection:
        row = connection.execute("SELECT value FROM settings WHERE name = ?", (name,)).fetchone()
    return None if row is None else row[0]


def setting_set(name: str, value: str) -> None:
    when = datetime.now(timezone.utc).isoformat()
    with DB_LOCK, db_connect() as connection:
        connection.execute(
            "INSERT INTO settings (name, value, changed_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value, changed_at = excluded.changed_at",
            (name, str(value), when))
    logging.info("setting %s = %s", name, value)


HIDDEN_SOURCES = "hidden_sources"


def hidden_sources() -> list[str]:
    """The sources the operator has switched off, as stored.

    Kept in the settings table rather than one of its own: it is a single list, it changes only when
    a person changes it, and the row that records when it changed is already there.
    """
    raw = setting_get(HIDDEN_SOURCES)
    try:
        values = json.loads(raw) if raw else []
    except ValueError:
        return []
    if not isinstance(values, list):
        return []
    return sorted({str(value).strip() for value in values if str(value).strip()})


def set_source_hidden(source: str, hidden: bool) -> list[str]:
    """Switch one source off or back on, and answer with the whole list as it now stands."""
    name = str(source or "").strip()
    current = hidden_sources()
    if not name:
        return current
    if hidden and name not in current:
        current.append(name)
    elif not hidden and name in current:
        current.remove(name)
    setting_set(HIDDEN_SOURCES, json.dumps(sorted(current), ensure_ascii=False))
    return sorted(current)

def _looks_like_link(value: str) -> bool:
    """Whether a string can be the key of a stored story.

    The link is the primary key on both tables, so this keeps a typo or a stray string from
    becoming a permanent hidden entry that nothing matches - and the same guard runs before an
    unhide, so a wrong call cannot silently do nothing.
    """
    if not value.startswith(("http://", "https://")) or len(value) > 2000:
        return False
    # A scheme with nothing behind it, or nothing that could be a host, is not a link.
    return len(value.split("://", 1)[1]) >= 4


def hide_link(link: str, title: str = "") -> int:
    """Stop showing one story. The row stays; every read path skips it."""
    when = datetime.now(timezone.utc).isoformat()
    with DB_LOCK, db_connect() as connection:
        connection.execute(
            "INSERT INTO hidden_links (link, title, hidden_at) VALUES (?, ?, ?) "
            "ON CONFLICT(link) DO UPDATE SET title = excluded.title, hidden_at = excluded.hidden_at",
            (link, title, when))
        return connection.execute("SELECT COUNT(*) FROM hidden_links").fetchone()[0] or 0


def unhide_link(link: str) -> int:
    with DB_LOCK, db_connect() as connection:
        connection.execute("DELETE FROM hidden_links WHERE link = ?", (link,))
        return connection.execute("SELECT COUNT(*) FROM hidden_links").fetchone()[0] or 0


def hidden_links(limit: int = 200) -> list[dict[str, Any]]:
    """What is hidden, newest first, with the title from the article row when it is still there.

    The archived row is kept, so a hidden story is usually still joinable back to its headline -
    which is what makes the restore list readable instead of a list of URLs.
    """
    with DB_LOCK, db_connect() as connection:
        rows = connection.execute(
            "SELECT h.link, COALESCE(NULLIF(h.title, ''), a.title, ''), a.source, a.published_at, h.hidden_at "
            "FROM hidden_links h LEFT JOIN articles a ON a.link = h.link "
            "ORDER BY h.hidden_at DESC LIMIT ?", (int(limit),)).fetchall()
    return [{"link": row[0], "title": row[1] or "", "source": row[2] or "", "published_at": row[3] or "",
             "hidden_at": row[4] or ""} for row in rows]


# ── 거르는 규칙 ─────────────────────────────────────────────────────────
# The operator hides stories one at a time and the same shapes keep coming back: a digest that is
# posted every hour, an ad for a casino, a wire that reposts its sports desk. A rule is that shape,
# written down once. Stories a rule catches are registered as usual and then skipped on every read
# path, so the only thing a rule changes is what a reader sees - and every catch is listed, so a
# wrong rule is visible instead of quietly eating the feed.

def _rule_regex(pattern: str) -> "re.Pattern[str]":
    """One rule as a regular expression. A Latin word has to start a word.

    'casino' must not fire inside 'fascinating', or the rule cannot be turned on. Korean has no word
    boundary to use - particles attach to the noun ("에어드롭이", "에어드롭은") - so it is matched as
    a plain substring.
    """
    text = (pattern or "").strip().lower()
    if re.match(r"^[0-9a-z]", text):
        return re.compile(r"(?<![0-9a-z])" + re.escape(text))
    return re.compile(re.escape(text))


def filter_rules(enabled_only: bool = False) -> list[dict[str, Any]]:
    """The rules. Switched-on first, then the ones that have caught the most."""
    sql = ("SELECT id, pattern, kind, origin, enabled, hits, created_at, last_hit_at FROM filter_rules")
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY enabled DESC, hits DESC, id DESC"
    with DB_LOCK, db_connect() as connection:
        rows = connection.execute(sql).fetchall()
    return [{"id": row[0], "pattern": row[1] or "", "kind": row[2] or "phrase", "origin": row[3] or "operator",
             "enabled": bool(row[4]), "hits": int(row[5] or 0), "created_at": row[6] or "",
             "last_hit_at": row[7] or ""} for row in rows]


def _record_filter_hits(connection: sqlite3.Connection, rows: list[tuple]) -> int:
    """Try the switched-on rules against the rows and record what they catch.

    Called with the rows handed to the insert, so the check happens where registration happens and
    the counting is idempotent: a story the collector sees again is already recorded and is not
    counted twice. One rule per story - the panel reads as "this rule caught this", which is what
    makes a rule judgeable.
    """
    rules = connection.execute("SELECT id, pattern FROM filter_rules WHERE enabled = 1").fetchall()
    if not rules:
        return 0
    matchers = [(row[0], _rule_regex(row[1])) for row in rules]
    when = datetime.now(timezone.utc).isoformat()
    added = 0
    for row in rows:
        link, title, summary = row[0], row[1] or "", row[2] or ""
        if not link:
            continue
        blob = (title + " " + summary).lower()
        for rule_id, rx in matchers:
            if not rx.search(blob):
                continue
            cursor = connection.execute(
                "INSERT OR IGNORE INTO filter_hits (link, rule_id, matched_at) VALUES (?, ?, ?)",
                (link, rule_id, when))
            if cursor.rowcount:
                connection.execute(
                    "UPDATE filter_rules SET hits = hits + 1, last_hit_at = ? WHERE id = ?", (when, rule_id))
                added += 1
            break
    return added


def rescan_filters() -> int:
    """Run the switched-on rules over the window the pages show.

    Turning a rule on has to act on what is already there, or the first day of a filter looks like
    nothing happened. The scan covers the retention window, which is exactly what a reader can see.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)).isoformat()
    with DB_LOCK, db_connect() as connection:
        enabled = [row[0] for row in connection.execute("SELECT id FROM filter_rules WHERE enabled = 1")]
        if not enabled:
            connection.execute("DELETE FROM filter_hits WHERE rule_id IN (SELECT id FROM filter_rules)")
            return 0
        connection.execute("DELETE FROM filter_hits WHERE rule_id IN (SELECT id FROM filter_rules WHERE enabled = 0)")
        rows = connection.execute("SELECT link, title, summary FROM articles WHERE published_at >= ?",
                                  (cutoff,)).fetchall()
        connection.execute("DELETE FROM filter_hits")
        return _record_filter_hits(connection, [tuple(r) for r in rows])


def add_filter_rule(pattern: str, kind: str = "phrase", origin: str = "operator",
                    enabled: bool = False) -> dict[str, Any]:
    """Add one rule. A pattern that is already there is left as it is."""
    text = (pattern or "").strip().lower()[:200]
    if not text:
        raise ValueError("empty pattern")
    when = datetime.now(timezone.utc).isoformat()
    with DB_LOCK, db_connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO filter_rules (pattern, kind, origin, enabled, hits, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)", (text, kind or "phrase", origin or "operator", 1 if enabled else 0, when))
        row = connection.execute("SELECT id, enabled FROM filter_rules WHERE pattern = ?", (text,)).fetchone()
    if row and row[1]:
        rescan_filters()
    return {"id": row[0], "pattern": text, "enabled": bool(row[1])}


def set_filter_rule(rule_id: int, enabled: "bool | None" = None, pattern: "str | None" = None) -> dict[str, Any]:
    """Switch a rule on or off, or reword it. Either way the catches are recomputed.

    A rule that is switched off gives its stories back - that is the whole point of recording them.
    """
    with DB_LOCK, db_connect() as connection:
        if pattern is not None:
            text = (pattern or "").strip().lower()[:200]
            if not text:
                raise ValueError("empty pattern")
            connection.execute("UPDATE filter_rules SET pattern = ? WHERE id = ?", (text, int(rule_id)))
        if enabled is not None:
            connection.execute("UPDATE filter_rules SET enabled = ? WHERE id = ?",
                               (1 if enabled else 0, int(rule_id)))
        row = connection.execute("SELECT id, pattern, enabled FROM filter_rules WHERE id = ?",
                                 (int(rule_id),)).fetchone()
    if row is None:
        raise ValueError("no such rule")
    if row[2]:
        rescan_filters()
    else:
        with DB_LOCK, db_connect() as connection:
            connection.execute("DELETE FROM filter_hits WHERE rule_id = ?", (int(rule_id),))
    return {"id": row[0], "pattern": row[1], "enabled": bool(row[2])}


def delete_filter_rule(rule_id: int) -> int:
    """Remove a rule. Its catches come back with it."""
    with DB_LOCK, db_connect() as connection:
        connection.execute("DELETE FROM filter_hits WHERE rule_id = ?", (int(rule_id),))
        connection.execute("DELETE FROM filter_rules WHERE id = ?", (int(rule_id),))
        return connection.execute("SELECT COUNT(*) FROM filter_rules").fetchone()[0] or 0


def keep_caught(link: str, keep: bool = True) -> int:
    """Keep one story a rule caught. The rule stays; this story does not go through it."""
    with DB_LOCK, db_connect() as connection:
        if keep:
            connection.execute(
                "INSERT INTO filter_keeps (link, kept_at) VALUES (?, ?) "
                "ON CONFLICT(link) DO UPDATE SET kept_at = excluded.kept_at",
                (link, datetime.now(timezone.utc).isoformat()))
        else:
            connection.execute("DELETE FROM filter_keeps WHERE link = ?", (link,))
        return connection.execute("SELECT COUNT(*) FROM filter_keeps").fetchone()[0] or 0


def caught_links(limit: int = 80) -> list[dict[str, Any]]:
    """What the rules caught, newest first, with the rule that caught it - the review list."""
    with DB_LOCK, db_connect() as connection:
        rows = connection.execute(
            "SELECT h.link, COALESCE(NULLIF(a.title, ''), ''), a.source, a.published_at, "
            "       r.pattern, r.id, h.matched_at "
            "FROM filter_hits h JOIN filter_rules r ON r.id = h.rule_id "
            "LEFT JOIN articles a ON a.link = h.link "
            "WHERE h.link NOT IN (SELECT link FROM filter_keeps) "
            "ORDER BY h.matched_at DESC LIMIT ?", (int(limit),)).fetchall()
        kept = connection.execute("SELECT COUNT(*) FROM filter_keeps").fetchone()[0] or 0
    return [{"link": row[0], "title": row[1] or "", "source": row[2] or "", "published_at": row[3] or "",
             "pattern": row[4] or "", "rule_id": row[5], "matched_at": row[6] or "", "kept_total": kept}
            for row in rows]


def learn_filter_rules(limit: int = 8) -> list[dict[str, Any]]:
    """Propose rules from the stories the operator has hidden by hand.

    The proposals arrive switched off, with what each would catch, because the decision to filter a
    whole shape of story is the operator's and a rule that is on by default is one that is never
    read.
    """
    with DB_LOCK, db_connect() as connection:
        hidden_titles = [row[0] or "" for row in connection.execute(
            "SELECT COALESCE(NULLIF(h.title, ''), a.title, '') FROM hidden_links h "
            "LEFT JOIN articles a ON a.link = h.link")]
        kept_texts = [(row[0] or "") + " " + (row[1] or "") for row in connection.execute(
            "SELECT title, summary FROM articles WHERE link NOT IN (SELECT link FROM hidden_links)")]
        existing = [(_rule_regex(row[0]), row[0]) for row in
                    connection.execute("SELECT pattern FROM filter_rules")]
    proposals = filter_learn.derive(hidden_titles, kept_texts, exclude={p for _, p in existing}, limit=limit)

    def covered(title: str) -> bool:
        return any(rx.search(title.lower()) for rx, _ in existing)

    # A proposal that says what a rule already says is not worth the operator's attention: pressing
    # learn twice must not keep growing the list with weaker wordings of the same shape. The check
    # runs as each one is added, so a phrase and the words inside it cannot both arrive.
    added = []
    for proposal in proposals:
        rx = _rule_regex(proposal["pattern"])
        if not any(rx.search(title.lower()) and not covered(title) for title in hidden_titles):
            continue
        added.append(add_filter_rule(proposal["pattern"], kind=proposal.get("kind", "phrase"), origin="learned"))
        existing.append((rx, proposal["pattern"]))
    return added


def _as_list(value: Any) -> list[str]:
    """One value or several, always as a list of non-empty strings.

    The API takes a repeated parameter for the axes that AND (`q`, `category`) and for the one that
    ORs (`source`): a query string can carry one value or many, so both shapes land here.
    """
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def query_articles(hours: int = RETENTION_HOURS, region: str = "", category: Any = "", source: Any = "",
                   source_type: str = "", minimum_priority: int = 0, text: Any = "",
                   picked_only: bool = False,
                   limit: int = DEFAULT_LIMIT, offset: int = 0) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Articles in the window, with every selected condition applied.

    `category` and `text` accept one value or a list, and a list means ALL of them: that is what a
    reader means by selecting several things. `source` accepts a list too but matches ANY of them,
    because a row has exactly one source and requiring two would always return nothing.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, min(int(hours), 24 * ARCHIVE_DAYS)))).isoformat()
    where = ["published_at >= ?"]
    params: list[Any] = [cutoff]
    # A hidden story is skipped on every read path, with no opt-out: the operator's own filters must
    # not be able to bring back the row that was hidden, or hiding would only work on the screen it
    # was done from. The restore path reads hidden_links directly instead.
    where.append("link NOT IN (SELECT link FROM hidden_links)")
    # A story a rule caught is skipped on every read path, exactly like a hidden one, and a story
    # the operator chose to keep is not skipped even though a rule caught it. The rule is joined
    # in rather than trusted: a rule that was switched off must not keep stories off the page
    # because a row was left behind somewhere.
    where.append("link NOT IN (SELECT h.link FROM filter_hits h JOIN filter_rules r ON r.id = h.rule_id "
                 "WHERE r.enabled = 1 AND h.link NOT IN (SELECT link FROM filter_keeps))")
    # A switched-off source is skipped on every read path, for the same reason a hidden story is: the
    # switch has to mean the same thing on the deployed pages as on the screen it was flipped from.
    # That also means a hidden source leaves the operator's own feed, so the way back is the source
    # list - the switch - rather than a filter that could bring the rows in again.
    off = hidden_sources()
    if off:
        where.append("source NOT IN (%s)" % ", ".join("?" * len(off)))
        params.extend(off)
    if region:
        where.append("region = ?")
        params.append(region)
    for value in _as_list(category):
        # A story can carry several categories, so the filter matches the list, not the first value:
        # a tariff bill filed under 미국 정책 must still answer a 트럼프 filter. The stored string is
        # wrapped in commas and the needle carries them too, so 금리 cannot match inside a longer
        # name. ESCAPE keeps a % or _ in a category name from acting as a wildcard. Several selected
        # categories are separate clauses, so they are ANDed.
        where.append("(',' || COALESCE(NULLIF(categories, ''), category) || ',') LIKE ? ESCAPE '\\'")
        params.append("%," + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + ",%")
    sources = _as_list(source)
    if sources:
        where.append("source IN (%s)" % ", ".join("?" * len(sources)))
        params.extend(sources)
    if source_type:
        where.append("source_type = ?")
        params.append(source_type)
    if minimum_priority:
        where.append("priority >= ?")
        params.append(int(minimum_priority))
    if picked_only:
        # The reader's view of what the operator picked. It filters and never sorts: a pick is a
        # judgement about a story, not a rank, and pinning picked rows would leave the top of the
        # feed unchanged for hours on a quiet day.
        where.append("link IN (SELECT link FROM picked_links)")
    for term in _as_list(text):
        # Two conditions per term on purpose. LIKE is a byte-level prefilter SQLite can reject a row
        # with, and kwmatch then applies the real rule only to the rows that survive it. Measured on
        # the whole archive (13,264 rows, three terms): 498 ms with kwmatch alone, because every row
        # called into Python for every term.
        # A % or _ inside the term only makes the prefilter more permissive, which is safe: it can
        # let a row through to the real rule, never reject one that rule would accept.
        where.append("(title LIKE ? OR summary LIKE ?) AND (kwmatch(title, ?) OR kwmatch(summary, ?))")
        needle = f"%{term}%"
        params.extend([needle, needle, term, term])
    clause = " AND ".join(where)
    with DB_LOCK, db_connect() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM articles WHERE {clause}", params).fetchone()[0] or 0
        rows = connection.execute(
            f"SELECT * FROM articles WHERE {clause} ORDER BY published_at DESC, priority DESC LIMIT ? OFFSET ?",
            params + [max(1, min(int(limit), MAX_LIMIT)), max(0, int(offset))],
        ).fetchall()
        region_counts = {row["region"]: row["n"] for row in connection.execute(
            "SELECT region, COUNT(*) AS n FROM articles WHERE published_at >= ? GROUP BY region", (cutoff,))}
    # The column is a comma-joined string on disk; the API and the page both want the list, and
    # every row written before the column existed falls back to its single stored value.
    picks = pick_map()
    items = []
    for row in rows:
        item = dict(row)
        item["categories"] = taxonomy.split_categories(item.get("categories"), item.get("category"))
        # Which language each part is in, so the card can say so and a browser translator works on
        # the right one. Per element: a headline and its summary sometimes differ.
        item["lang"] = taxonomy.detect_lang(item.get("title") or "")
        item["summary_lang"] = taxonomy.detect_lang(item.get("summary") or "")
        # The operator's judgement travels with the row, note and all, because the badge is for
        # readers: a pick is only worth something if the person reading the page can see it.
        note = picks.get(item.get("link"))
        item["picked"] = note is not None
        item["pick_note"] = note or ""
        items.append(item)
    return items, int(total), {str(k): int(v) for k, v in region_counts.items()}


def collect_news() -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    status: dict[str, Any] = {}
    all_rss_jobs = [(source, source_type, url, GLOBAL_REGION) for source, source_type, url in RSS_SOURCES]
    all_rss_jobs += [(source, source_type, url, THAI_REGION) for source, source_type, url in THAI_RSS_SOURCES]
    # A source on a slower poll is left out of this cycle entirely; its previous status is carried
    # over below, so the operator's panel shows the last real answer instead of a false failure.
    _cycle["count"] += 1
    turn = _cycle["count"]
    rss_jobs = [job for job in all_rss_jobs if turn % SLOW_SOURCES.get(job[0], 1) == 1]
    held_over = [job for job in all_rss_jobs if job not in rss_jobs]
    google_jobs = [(source, query, GLOBAL_REGION, ()) for source, query in GOOGLE_QUERIES]
    google_jobs += [(source, query, THAI_REGION, terms) for source, query, terms in THAI_GOOGLE_QUERIES]

    def run_rss(job: tuple[str, str, str, str]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        source, source_type, url, region = job
        try:
            fetched = parse_rss(fetch_bytes(url), source, source_type, region)
            return source, {"ok": True, "count": len(fetched), "url": url}, fetched
        except Exception as exc:
            logging.warning("RSS failed (%s): %s", source, exc)
            return source, {"ok": False, "count": 0, "url": url, "error": str(exc)[:180]}, []

    def run_google(job: tuple[str, str, str, tuple[str, ...]]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        source, query, region, require_terms = job
        fetched = fetch_google_news(source, query, region, require_terms)
        info: dict[str, Any] = {"ok": bool(fetched), "count": len(fetched), "query": query}
        if region == THAI_REGION:
            info["region"] = THAI_REGION
        return source, info, fetched

    with ThreadPoolExecutor(max_workers=10) as pool:
        rss_results = list(pool.map(run_rss, rss_jobs))
    with ThreadPoolExecutor(max_workers=4) as pool:
        google_results = list(pool.map(run_google, google_jobs))
    for source, info, items in rss_results + google_results:
        status[source] = info
        _last_source_status[source] = info
        articles.extend(items)
    # Sources on a slower poll: carry the last real answer forward, and label it so the panel and the
    # log do not read a skipped cycle as a failure.
    for source, _kind, url, _region in held_over:
        held = dict(_last_source_status.get(source) or {"ok": True, "count": 0, "url": url})
        held["note"] = "slower poll: not asked this cycle"
        status[source] = held
    coinness, coinness_status = fetch_coinness()
    articles.extend(coinness)
    status["CoinNess"] = coinness_status
    coinness_stock, coinness_stock_status = fetch_coinness_stock()
    articles.extend(coinness_stock)
    status["CoinNess Stock"] = coinness_stock_status
    articles.extend(sbh_source.fetch_into(status))
    articles.extend(sbh_open_news.fetch_into(status))
    articles.extend(bluesky_source.fetch_into(status))
    articles.extend(whitehouse_source.fetch_into(status))
    articles.extend(telegram_source.fetch_into(status))
    fresh_articles = keep_recent(articles)
    # Twice: inside the cycle, and against what the window already holds - the same wire story
    # arriving in a later cycle under another outlet's link is the repetition a reader notices.
    deduped = drop_already_stored(dedupe_by_region(fresh_articles))
    inserted = insert_articles(deduped)
    if inserted:
        prune_archive()
    _, window_total, region_counts = query_articles(hours=RETENTION_HOURS, limit=1)
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_at_ict": datetime.now(ICT).strftime("%Y-%m-%d %H:%M:%S ICT"),
        "window_hours": RETENTION_HOURS,
        "fresh_article_count": len(fresh_articles),
        "inserted_article_count": inserted,
        "article_count": window_total,
        "region_counts": region_counts,
        "sources": status,
        "archive": archive_stats(),
    }
    logging.info("Cycle fresh=%d inserted=%d window=%d", len(fresh_articles), inserted, window_total)
    return result


class NewsState:
    def __init__(self, interval: int):
        self.interval = max(10, interval)
        self.lock = threading.Lock()
        self.data: dict[str, Any] = {"updated_at": None, "updated_at_ict": None, "window_hours": RETENTION_HOURS, "article_count": 0, "region_counts": {}, "sources": {}, "archive": {}}
        try:
            init_db()
            # A stored interval wins over the command line: the operator changed it from the page,
            # and the flag is only the default a fresh install starts from.
            stored = setting_get("interval_seconds")
            if stored:
                self.interval = max(10, min(600, int(stored)))
                logging.info("Refresh interval restored from settings: %ds", self.interval)
            _, total, counts = query_articles(hours=RETENTION_HOURS, limit=1)
            self.data.update({"article_count": total, "region_counts": counts, "archive": archive_stats(), "updated_at_ict": "restored from archive"})
            logging.info("Archive restored: %d articles inside %dh window", total, RETENTION_HOURS)
        except Exception:
            logging.exception("Archive restore failed")

    def set_interval(self, interval: int) -> int:
        self.interval = max(10, min(600, int(interval)))
        # Written down as well as held: the service is restarted by every update, and an interval the
        # operator chose should not quietly revert to the command-line default when that happens.
        setting_set("interval_seconds", str(self.interval))
        return self.interval

    def refresh(self) -> None:
        try:
            data = collect_news()
            with self.lock:
                self.data = data
        except Exception:
            logging.exception("Collection cycle failed")

    def loop(self) -> None:
        while True:
            started = time.monotonic()
            self.refresh()
            time.sleep(max(1, self.interval - (time.monotonic() - started)))

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return json.loads(json.dumps(self.data))

    def query(self, **filters: Any) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
        return query_articles(**filters)


class Handler(BaseHTTPRequestHandler):
    # The operator document, rendered once per process on the first request that asks for it.
    _admin_html: str = ""

    state: NewsState

    def end_headers(self) -> None:
        # Permit index.html to work even when the user opens the file directly.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def send_json(self, payload: dict[str, Any], cookie: str = "") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self) -> dict[str, Any] | None:
        """The request body as JSON, or None when it is too large or not JSON."""
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            return None
        if length < 0 or length > admin_auth.MAX_BODY:
            return None
        if not length:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def session_cookie(self) -> str:
        return admin_auth.cookie_header(admin_auth.issue_token(), admin_auth.is_secure(self))

    def clear_session_cookie(self) -> str:
        return admin_auth.clear_cookie(admin_auth.is_secure(self))

    def is_admin(self) -> bool:
        """Whether this request carries an admin session, checked per request.

        The deployment runs in read-only public mode; a session upgrades that request only, so the
        operator sees what an anonymous visitor does not, in the same process.
        """
        return admin_auth.authenticated(self)

    def handle_session(self, request_path: str) -> None:
        """Login and logout: the only writes that must work on the public deployment.

        Without them there is no way to obtain a session at all, so they are answered before the
        session check rather than after it.
        """
        ip = admin_auth.client_ip(self)
        if request_path == "/api/logout":
            admin_auth.revoke(admin_auth.token_from_cookie(self.headers.get("Cookie", "")))
            logging.info("admin logout ip=%s", ip)
            self.send_json({"ok": True}, cookie=self.clear_session_cookie())
            return
        if not admin_auth.login_allowed(ip):
            logging.warning("admin login refused (too many attempts) ip=%s", ip)
            self.send_error(429, "Too many attempts")
            return
        payload = self.read_json_body()
        if payload is None:
            self.send_error(400, "Invalid JSON")
            return
        if not admin_auth.is_configured():
            # Nothing to compare against: answer like a wrong password, and say so in the log.
            admin_auth.note_failure(ip)
            logging.warning("admin login refused (no password file at %s) ip=%s",
                            admin_auth.PASSWORD_FILE, ip)
            self.send_error(401, "Wrong password")
            return
        if not admin_auth.check_password(str(payload.get("password") or "")):
            admin_auth.note_failure(ip)
            logging.warning("admin login failed ip=%s", ip)
            self.send_error(401, "Wrong password")
            return
        admin_auth.note_success(ip)
        logging.info("admin login ok ip=%s", ip)
        self.send_json({"ok": True}, cookie=self.session_cookie())

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def serve_admin(self) -> None:
        """Answer /admin: the login box, or the operator's dashboard for a session.

        This is the only place the operator page is handed out. It is not on disk, so it is not part
        of what the reverse proxy serves to everybody, and the anonymous answer carries no dashboard
        markup at all - a stranger reading the response learns nothing about the page behind it.
        """
        if not self.is_admin():
            body = admin_page.login_page().encode("utf-8")
        else:
            # Built once and kept: the document changes only when the code does, and every request
            # would otherwise re-render the whole page.
            if not Handler._admin_html:
                Handler._admin_html = admin_page.operator_page()
            body = Handler._admin_html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_hidden(self) -> None:
        """What has been hidden, for the restore list. The operator's view, so a session is needed."""
        if PUBLIC_MODE and not self.is_admin():
            self.send_error(404)
            return
        rows = hidden_links()
        self.send_json({"hidden": rows, "total": len(rows),
                        "hidden_total": archive_stats().get("hidden_total", 0)})

    def serve_picks(self) -> None:
        """What the operator has picked. Public on purpose: the badge is the whole point.

        This is the one operator-made list a reader sees, so it answers without a session - the
        write that fills it is what needs one.
        """
        rows = picked_links()
        self.send_json({"picked": rows, "total": len(rows)})

    def serve_filters(self) -> None:
        """The rules and what they caught, for the operator page."""
        if PUBLIC_MODE and not self.is_admin():
            self.send_error(404)
            return
        self.send_json({"rules": filter_rules(), "caught": caught_links()})

    def do_GET(self) -> None:
        request_path = urllib.parse.urlsplit(self.path).path
        if request_path in ("/admin", "/admin/"):
            self.serve_admin()
            return
        if request_path == "/api/hidden":
            self.serve_hidden()
            return
        if request_path == "/api/filters":
            self.serve_filters()
            return
        if request_path == "/api/picks":
            self.serve_picks()
            return
        if request_path == "/api/calendar":
            # Served, not read from a committed file: the indicator tab has to move on its own
            # the way the news feed does. The payload is cached in the collector process, so a
            # page that polls it costs nothing until the cache expires.
            try:
                self.send_json(econ_calendar.cached_payload())
            except Exception:
                logging.exception("calendar build failed")
                self.send_json({"days": [], "errors": ["달력 소스를 불러오지 못했습니다"]})
            return
        if request_path == "/api/news":
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)

            def pick(name: str) -> str:
                return (params.get(name, [""])[0] or "").strip()

            def pick_all(name: str) -> list[str]:
                """Every value of a repeatable parameter, in order.

                `?q=trump&q=tariff` means both terms, and `?category=A&category=B` means both
                categories - that is the AND a reader expects from selecting several things. The
                axes keep their own meaning: several sources match any of them.
                """
                return [str(value).strip() for value in params.get(name, []) if str(value).strip()]

            def number(name: str, default: int) -> int:
                try:
                    return int(pick(name) or default)
                except ValueError:
                    return default

            hours = max(1, min(number("hours", RETENTION_HOURS), 24 * ARCHIVE_DAYS))
            limit = max(1, min(number("limit", DEFAULT_LIMIT), MAX_LIMIT))
            offset = max(0, number("offset", 0))
            minimum_priority = max(0, min(number("priority", 0), 5))
            filters = {
                "hours": hours, "region": pick("region"), "category": pick_all("category"),
                "source": pick_all("source"), "source_type": pick("source_type"),
                "minimum_priority": minimum_priority, "text": pick_all("q"),
                "picked_only": pick("picked") in ("1", "true", "yes"),
            }
            articles, total, region_counts = self.state.query(**filters, limit=limit, offset=offset)
            # The reader is sent to the publisher, the operator keeps the stored link: the row's
            # primary key is the Google News URL, and hide/pick/push all identify a story by it,
            # so it is never rewritten - the resolved URL rides alongside as `original_link`.
            cached = original_links()
            if cached:
                for article in articles:
                    link = str(article.get("link") or "")
                    original = google_news.original_for(link, cached)
                    if original != link:
                        article["original_link"] = original
            # A reader should not meet one story twice: the duplicates already stored (a second
            # Google link for the same article, a second outlet carrying the same wire copy) are
            # dropped here, newest copy first, and nothing is deleted from the database. The
            # published JSON gets the same treatment, so a screen that reads either one agrees.
            articles = dedupe_rows(articles)
            payload = dict(self.state.snapshot())
            payload.update({
                "hours": hours, "limit": limit, "offset": offset, "total": total, "returned": len(articles),
                "has_more": offset + len(articles) < total,
                "archived_total": payload.get("archive", {}).get("archived_total", 0),
                # Echoed joined by commas: the response shape stays what a reader of the API already
                # expects, and several values are visible instead of silently dropped.
                # The operator's page shows this in its interval control, so the control reflects
                # what the collector is actually doing rather than what the page was built with.
                "interval_seconds": self.state.interval,
                "filter": {"region": filters["region"], "category": ",".join(filters["category"]),
                           "source": ",".join(filters["source"]), "source_type": filters["source_type"],
                           "priority": minimum_priority, "q": ",".join(filters["text"])},
                "region_counts": region_counts or payload.get("region_counts", {}),
                "articles": articles,
            })
            if PUBLIC_MODE and not self.is_admin():
                for key in ("sources", "archive", "archived_total", "fresh_article_count", "inserted_article_count",
                            "interval_seconds"):
                    payload.pop(key, None)
            self.send_json(payload)
            return
        if request_path == "/api/stats":
            if PUBLIC_MODE and not self.is_admin():
                self.send_error(404)
                return
            self.send_json({"archive": archive_stats(), "updated_at_ict": self.state.snapshot().get("updated_at_ict")})
            return
        if request_path == "/api/status":
            data = self.state.snapshot()
            payload = {"updated_at_ict": data.get("updated_at_ict"), "window_hours": data.get("window_hours", RETENTION_HOURS),
                       "article_count": data.get("article_count", 0), "region_counts": data.get("region_counts", {})}
            # The collection state, the retention counts and the refresh interval are the operator's
            # view; an anonymous visitor gets the clock and the counts, which the page needs. The
            # deployment in read-only mode used to answer with all of it (measured: sources and
            # archive present in the anonymous response).
            if not (PUBLIC_MODE and not self.is_admin()):
                rules = filter_rules()
                payload.update({"interval_seconds": self.state.interval, "archive": data.get("archive", {}),
                                "sources": data.get("sources", {}),
                                "hidden_sources": hidden_sources(),
                                "filter_rules": rules,
                                "filter_enabled": sum(1 for r in rules if r["enabled"])})
            self.send_json(payload)
            return
        static = STATIC_FILES.get(request_path)
        if static:
            filename, content_type = static
            target = ROOT / filename
            if target.exists():
                data = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_error(404)
            return
        path = "/index.html" if request_path in {"/", ""} else request_path
        if path == "/index.html":
            body = (ROOT / "index.html").read_bytes()
            if PUBLIC_MODE and not self.is_admin():
                body = body.replace(b"<script>", b"<script>window.__PUBLIC__=true;", 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        request_path = urllib.parse.urlsplit(self.path).path
        # Login and logout are answered before the session check: they are how a session is obtained.
        if request_path in ("/api/login", "/api/logout"):
            self.handle_session(request_path)
            return
        # A write needs a session whenever this server is public, and whenever the request arrived
        # over TLS - the second condition means a deployment that forgot --public, but sits behind
        # the TLS proxy, still refuses writes instead of trusting the flag. A local server (no
        # --public, plain http, loopback) keeps its previous behaviour, which is the operator's own
        # machine.
        if PUBLIC_MODE or admin_auth.is_secure(self):
            allowed, why = admin_auth.write_request_ok(self)
            if not allowed:
                logging.warning("write refused (%s) %s ip=%s", why, request_path,
                                admin_auth.client_ip(self))
                self.send_error(401, "Admin session required")
                return
        payload = self.read_json_body()
        if payload is None:
            self.send_error(400, "Invalid JSON")
            return
        if request_path == "/api/settings":
            try:
                interval = self.state.set_interval(int(payload.get("interval", DEFAULT_INTERVAL)))
            except (TypeError, ValueError):
                self.send_error(400, "Invalid interval")
                return
            response = {"ok": True, "interval_seconds": interval}
        elif request_path == "/api/source":
            # Switching a whole source on or off. The answer carries the whole list back, because
            # that list is what the operator page draws its switches from.
            source = str(payload.get("source") or "").strip()
            if not source:
                self.send_error(400, "Invalid source")
                return
            hidden = bool(payload.get("hidden"))
            pushed = set_source_hidden(source, hidden)
            logging.info("source %s by the operator: %s ip=%s",
                         "hidden" if hidden else "shown", source, admin_auth.client_ip(self))
            response = {"ok": True, "source": source, "hidden": hidden, "hidden_sources": pushed}
        elif request_path == "/api/filter":
            # One endpoint for the rules, because every action ends in the same answer: the list
            # the panel draws from. `learn` reads the stories the operator hid by hand and proposes
            # rules from them; the proposals arrive switched off.
            action = str(payload.get("action") or "").strip()
            try:
                if action == "add":
                    add_filter_rule(str(payload.get("pattern") or ""),
                                    kind="word" if payload.get("kind") == "word" else "phrase")
                elif action == "set":
                    set_filter_rule(int(payload.get("id") or 0),
                                    enabled=payload.get("enabled"),
                                    pattern=payload.get("pattern"))
                elif action == "delete":
                    delete_filter_rule(int(payload.get("id") or 0))
                elif action == "keep":
                    link = str(payload.get("link") or "").strip()
                    if not _looks_like_link(link):
                        self.send_error(400, "Invalid link")
                        return
                    keep_caught(link, bool(payload.get("keep", True)))
                elif action == "learn":
                    learn_filter_rules()
                else:
                    self.send_error(400, "Unknown filter action")
                    return
            except (TypeError, ValueError) as exc:
                self.send_error(400, "Invalid filter: %s" % exc)
                return
            logging.info("admin filter %s ip=%s", action, admin_auth.client_ip(self))
            rules = filter_rules()
            response = {"ok": True, "rules": rules, "caught": caught_links(),
                        "filter_enabled": sum(1 for r in rules if r["enabled"])}
        elif request_path in ("/api/hide", "/api/unhide", "/api/pick", "/api/unpick"):
            # One story changes state. The link identifies it, so it is the only thing that has to
            # be right; the title and the note are carried along so the operator's lists read as
            # headlines and phrases rather than as URLs.
            link = str(payload.get("link") or "").strip()
            if not _looks_like_link(link):
                self.send_error(400, "Invalid link")
                return
            if request_path == "/api/hide":
                total = hide_link(link, str(payload.get("title") or "")[:500])
            elif request_path == "/api/unhide":
                total = unhide_link(link)
            elif request_path == "/api/pick":
                total = pick_link(link, str(payload.get("note") or "").strip()[:PICK_NOTE_MAX])
            else:
                total = unpick_link(link)
            logging.info("admin %s %s ip=%s", request_path.rsplit("/", 1)[-1], link,
                         admin_auth.client_ip(self))
            # Both counts go back, because the two lists are two different lengths and the page
            # shows both of them.
            response = {"ok": True, "count": total,
                        "hidden_total": archive_stats().get("hidden_total", 0),
                        "picked_total": len(pick_map())}
        else:
            self.send_error(404)
            return
        logging.info("admin write %s ip=%s", request_path, admin_auth.client_ip(self))
        self.send_json(response)

    def log_message(self, fmt: str, *args: Any) -> None:
        logging.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="무료 RSS/API 기반 실시간 암호화폐·거시 뉴스 대시보드")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="bind address; 0.0.0.0 to allow LAN access")
    parser.add_argument("--public", action="store_true", help="read-only public mode")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="갱신 간격(초), 기본 30")
    args = parser.parse_args()
    global PUBLIC_MODE
    PUBLIC_MODE = bool(args.public)
    state = NewsState(args.interval)
    Handler.state = state
    threading.Thread(target=state.loop, daemon=True, name="news-collector").start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    logging.info("Dashboard: http://%s:%d (public=%s)", args.host, args.port, PUBLIC_MODE)
    logging.info("Refresh interval: %d seconds", state.interval)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Stopping dashboard")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
