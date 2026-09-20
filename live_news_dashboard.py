from __future__ import annotations

import argparse
import category_rules as taxonomy
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
}

USER_AGENT = "TeemoLiveNewsDashboard/1.0 (+local research dashboard)"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RSS_SOURCES = [
    ("CoinDesk", "crypto", "https://www.coindesk.com/arc/outboundfeeds/rss"),
    ("Decrypt", "crypto", "https://decrypt.co/feed"),
    ("Bitcoin Magazine", "crypto", "https://bitcoinmagazine.com/.rss/full/"),
    ("SEC", "official", "https://www.sec.gov/news/pressreleases.rss"),
    ("Federal Reserve", "official", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Fed Speeches", "official", "https://www.federalreserve.gov/feeds/speeches.xml"),
    ("Bank of England", "official", "https://www.bankofengland.co.uk/rss/news"),
    ("FinancialJuice", "breaking", "https://www.financialjuice.com/feed.ashx?xy=rss"),
]

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
        if title and link:
            output.append(make_article(title, link, summary, parse_date(published), source, source_type, region))
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


def make_article(title: str, link: str, summary: str, published: str, source: str, source_type: str, region: str = "글로벌") -> dict[str, Any]:
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


def dedupe(articles: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    articles = sorted(articles, key=lambda item: (item.get("published_at", ""), item["priority"]), reverse=True)
    kept: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    keys: list[str] = []
    for article in articles:
        link = canonical_link(article["link"])
        key = normalize_title(article["title"])
        if link in seen_links:
            continue
        if key and any(_similar_title(key, old) for old in keys):
            continue
        seen_links.add(link)
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


def db_connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_FILE, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


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
        # No index on `categories`: the filter is a contains-match, which no index can serve.
        for column in ("published_at", "region", "category", "source", "priority"):
            connection.execute(f"CREATE INDEX IF NOT EXISTS idx_articles_{column} ON articles({column})")


def insert_articles(articles: list[dict[str, Any]]) -> int:
    rows = [
        (
            article.get("link", ""), article.get("title", ""), article.get("summary", ""),
            article.get("source", ""), article.get("source_type", ""), article.get("region", GLOBAL_REGION),
            article.get("category", GENERIC_CATEGORY), taxonomy.join_categories(
                article.get("categories") or [article.get("category", GENERIC_CATEGORY)]),
            article.get("asset", ""), int(article.get("priority", 3)),
            article.get("published_at", ""), article.get("collected_at", ""),
        )
        for article in articles
        if article.get("link") and article.get("published_at")
    ]
    if not rows:
        return 0
    with DB_LOCK, db_connect() as connection:
        before = connection.total_changes
        connection.executemany(
            "INSERT OR IGNORE INTO articles (link, title, summary, source, source_type, region, category, categories, asset, priority, published_at, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        return connection.total_changes - before


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
    return {"archived_total": int(total), "window_total": int(recent), "oldest_published_at": oldest, "archive_days": ARCHIVE_DAYS}


def query_articles(hours: int = RETENTION_HOURS, region: str = "", category: str = "", source: str = "",
                   source_type: str = "", minimum_priority: int = 0, text: str = "",
                   limit: int = DEFAULT_LIMIT, offset: int = 0) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(1, min(int(hours), 24 * ARCHIVE_DAYS)))).isoformat()
    where = ["published_at >= ?"]
    params: list[Any] = [cutoff]
    if region:
        where.append("region = ?")
        params.append(region)
    if category:
        # A story can carry several categories, so the filter matches the list, not the first
        # value: a tariff bill filed under 미국 정책 must still answer a 트럼프 filter. The stored
        # string is wrapped in commas and the needle carries them too, so 금리 cannot match inside
        # a longer name. ESCAPE keeps a % or _ in a category name from acting as a wildcard.
        where.append("(',' || COALESCE(NULLIF(categories, ''), category) || ',') LIKE ? ESCAPE '\\'")
        params.append("%," + category.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + ",%")
    if source:
        where.append("source = ?")
        params.append(source)
    if source_type:
        where.append("source_type = ?")
        params.append(source_type)
    if minimum_priority:
        where.append("priority >= ?")
        params.append(int(minimum_priority))
    if text:
        where.append("(title LIKE ? OR summary LIKE ?)")
        needle = f"%{text}%"
        params.extend([needle, needle])
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
    items = []
    for row in rows:
        item = dict(row)
        item["categories"] = taxonomy.split_categories(item.get("categories"), item.get("category"))
        items.append(item)
    return items, int(total), {str(k): int(v) for k, v in region_counts.items()}


def collect_news() -> dict[str, Any]:
    articles: list[dict[str, Any]] = []
    status: dict[str, Any] = {}
    rss_jobs = [(source, source_type, url, GLOBAL_REGION) for source, source_type, url in RSS_SOURCES]
    rss_jobs += [(source, source_type, url, THAI_REGION) for source, source_type, url in THAI_RSS_SOURCES]
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
        articles.extend(items)
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
    deduped = dedupe_by_region(fresh_articles)
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
            _, total, counts = query_articles(hours=RETENTION_HOURS, limit=1)
            self.data.update({"article_count": total, "region_counts": counts, "archive": archive_stats(), "updated_at_ict": "restored from archive"})
            logging.info("Archive restored: %d articles inside %dh window", total, RETENTION_HOURS)
        except Exception:
            logging.exception("Archive restore failed")

    def set_interval(self, interval: int) -> int:
        self.interval = max(10, min(600, int(interval)))
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
    state: NewsState

    def end_headers(self) -> None:
        # Permit index.html to work even when the user opens the file directly.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        request_path = urllib.parse.urlsplit(self.path).path
        if request_path == "/api/news":
            params = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)

            def pick(name: str) -> str:
                return (params.get(name, [""])[0] or "").strip()

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
                "hours": hours, "region": pick("region"), "category": pick("category"), "source": pick("source"),
                "source_type": pick("source_type"), "minimum_priority": minimum_priority, "text": pick("q"),
            }
            articles, total, region_counts = self.state.query(**filters, limit=limit, offset=offset)
            payload = dict(self.state.snapshot())
            payload.update({
                "hours": hours, "limit": limit, "offset": offset, "total": total, "returned": len(articles),
                "has_more": offset + len(articles) < total,
                "archived_total": payload.get("archive", {}).get("archived_total", 0),
                "filter": {"region": filters["region"], "category": filters["category"], "source": filters["source"],
                           "source_type": filters["source_type"], "priority": minimum_priority, "q": filters["text"]},
                "region_counts": region_counts or payload.get("region_counts", {}),
                "articles": articles,
            })
            if PUBLIC_MODE:
                for key in ("sources", "archive", "archived_total", "fresh_article_count", "inserted_article_count"):
                    payload.pop(key, None)
            self.send_json(payload)
            return
        if request_path == "/api/stats":
            if PUBLIC_MODE:
                self.send_error(404)
                return
            self.send_json({"archive": archive_stats(), "updated_at_ict": self.state.snapshot().get("updated_at_ict")})
            return
        if request_path == "/api/status":
            data = self.state.snapshot()
            self.send_json({"updated_at_ict": data.get("updated_at_ict"), "window_hours": data.get("window_hours", RETENTION_HOURS), "article_count": data.get("article_count", 0), "interval_seconds": self.state.interval, "region_counts": data.get("region_counts", {}), "archive": data.get("archive", {}), "sources": data.get("sources", {})})
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
            if PUBLIC_MODE:
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
        if PUBLIC_MODE:
            self.send_error(403, "Read-only public mode")
            return
        request_path = urllib.parse.urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_error(400, "Invalid JSON")
            return
        if request_path == "/api/settings":
            try:
                interval = self.state.set_interval(int(payload.get("interval", DEFAULT_INTERVAL)))
            except (TypeError, ValueError):
                self.send_error(400, "Invalid interval")
                return
            response = {"ok": True, "interval_seconds": interval}
        else:
            self.send_error(404)
            return
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
