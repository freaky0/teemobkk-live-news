"""Turn a Google News aggregator link into the publisher's own article URL.

Google News search results carry a redirect of the form
`https://news.google.com/rss/articles/CBMi...`, which is what the reader ends up clicking
today. The publisher URL is not in the id any more: the base64 payload of a current id
decodes to a protobuf with no URL inside it (verified against 3 live rows, 2026-09-24), so
the only honest way to get the original is to ask Google for it.

The article page carries a timestamp (`data-n-a-ts`) and a signature (`data-n-a-sg`), and
those two plus the article id resolve the link through Google's own batchexecute RPC:

    POST https://news.google.com/_/DotsSplashUi/data/batchexecute
    f.req=[[["Fbv4je","[\"garturlreq\",[...],\"<id>\",<ts>,\"<sg>\"]",null,"generic"]]]
    -> )]}'  [[\"wrb.fr\",\"Fbv4je\",\"[\\\"garturlres\\\",\\\"https://publisher/…\\\",1]\"…

Rules this module keeps:

    * A URL is only ever returned when Google's answer contains one. Nothing is derived,
      guessed or assembled from the title, the source name or the id.
    * An answer pointing back at a Google host is refused: it would put the reader on the
      same redirect they started from.
    * Every failure is a `None`, never an exception, so a caller in a publishing path can
      treat "could not resolve" as "keep what is stored".

Results are cached in the collector database (`link_resolutions`), because resolution costs
two HTTP requests per link and the same links are read on every publish.
"""
from __future__ import annotations

import json
import re
import sqlite3
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

RPC_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
ARTICLE_MARK = "/articles/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 25
# Hosts whose answer is the redirect itself rather than a publisher.
GOOGLE_HOSTS = ("news.google.com", "google.com", "www.google.com", "googleusercontent.com")
TABLE = "link_resolutions"
SCHEMA = ("CREATE TABLE IF NOT EXISTS " + TABLE + " ("
          "link TEXT PRIMARY KEY, original TEXT NOT NULL, resolved_at TEXT NOT NULL)")
# The RPC needs the request shape Google's own page sends; the X placeholders are part of it.
GARTURLREQ = ('["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,'
              'null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"%s",%s,"%s"]')


def is_aggregator(link: str) -> bool:
    """True for a link that points at Google News rather than the publisher."""
    try:
        host = urllib.parse.urlsplit(str(link or "")).netloc.lower()
    except ValueError:
        return False
    return host.endswith("news.google.com")


def article_id(link: str) -> str:
    return str(link or "").split(ARTICLE_MARK, 1)[-1].split("?", 1)[0].strip()


def valid_original(url: str) -> bool:
    """A publisher URL: absolute http(s), a real host, and not Google's own redirect."""
    url = str(url or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return False
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.lower().split(":")[0]
    if not host or "." not in host or " " in host:
        return False
    return not any(host == g or host.endswith("." + g) for g in GOOGLE_HOSTS)


def signature(page_html: str) -> tuple[str, str] | None:
    """The timestamp and signature the article page hands to the RPC."""
    stamp = re.search(r'data-n-a-ts="(\d+)"', page_html or "")
    sign = re.search(r'data-n-a-sg="([^"]+)"', page_html or "")
    if not stamp or not sign:
        return None
    return stamp.group(1), sign.group(1)


def _unescape(text: str) -> str:
    """Undo the JSON escaping the RPC answer carries, in whatever depth it arrives.

    A URL with a query string comes back as `...?\\u0026xml\\u003d…`, so the unicode escapes
    have to be decoded as well - a reader sent to a URL containing a literal `\\u0026` lands on
    the wrong page.
    """
    text = text.replace("\\\\", "\\").replace('\\"', '"').replace("\\/", "/")
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), text)


def parse_rpc(raw: str) -> str | None:
    """Pull the publisher URL out of a batchexecute answer.

    The URL sits inside a JSON string that is itself nested in one, so the surrounding
    quotes arrive escaped (`\\"https://…\\"`).
    """
    index = str(raw or "").find("garturlres")
    if index < 0:
        return None
    tail = _unescape(raw[index:])
    if "\\" in tail:
        tail = _unescape(tail)
    match = re.search(r'"(https?://[^"\s]+)"', tail)
    if not match:
        return None
    candidate = match.group(1).rstrip("\\").replace("\\", "")
    return candidate if valid_original(candidate) else None


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def _post(url: str, body: str) -> str:
    request = urllib.request.Request(
        url, data=body.encode("utf-8"),
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def resolve(link: str, *, opener=_get, rpc=_post) -> str | None:
    """The publisher URL for a Google News link, or None when Google does not answer with one."""
    if not is_aggregator(link):
        return None
    ident = article_id(link)
    if not ident:
        return None
    try:
        page = opener(link)
        pair = signature(page)
        if not pair:
            return None
        stamp, sign = pair
        inner = GARTURLREQ % (ident, stamp, sign)
        body = "f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", inner, None, "generic"]]]))
        return parse_rpc(rpc(RPC_URL, body))
    except Exception:
        return None


def resolve_many(links, *, workers: int = 6, limit: int | None = None, opener=_get, rpc=_post):
    """Resolve several links in parallel; returns {link: original} for the ones that resolved."""
    wanted = [link for link in dict.fromkeys(links) if is_aggregator(link)]
    if limit is not None:
        wanted = wanted[:max(0, limit)]
    if not wanted:
        return {}
    found: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for link, original in zip(wanted, pool.map(lambda l: resolve(l, opener=opener, rpc=rpc), wanted)):
            if original:
                found[link] = original
    return found


def ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(SCHEMA)


def load(connection: sqlite3.Connection) -> dict[str, str]:
    """Every resolution cached so far, as {aggregator link: publisher url}."""
    try:
        ensure_table(connection)
        rows = connection.execute("SELECT link, original FROM " + TABLE).fetchall()
    except sqlite3.Error:
        return {}
    return {str(link): str(original) for link, original in rows
            if is_aggregator(link) and valid_original(original)}


def remember(connection: sqlite3.Connection, resolved: dict[str, str]) -> int:
    """Store resolutions; a link is written once, so a later run cannot rewrite history."""
    if not resolved:
        return 0
    ensure_table(connection)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = [(link, original, stamp) for link, original in resolved.items()
               if is_aggregator(link) and valid_original(original)]
    connection.executemany(
        "INSERT OR IGNORE INTO " + TABLE + " (link, original, resolved_at) VALUES (?,?,?)", payload)
    connection.commit()
    return len(payload)


def original_for(link: str, cached: dict[str, str]) -> str:
    """What the reader should be sent to: the publisher when known, the stored link otherwise."""
    return cached.get(str(link or "")) or str(link or "")
