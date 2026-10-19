"""Strictly read-only projection of the existing Thai news database.

No collector imports, ORM registration, migration, translation or source fetch.
An unavailable visibility policy fails closed on every read path.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.html import strip_tags

class NewsUnavailable(Exception):
    pass

@dataclass(frozen=True)
class NewsPage:
    items: list
    total: int
    page: int
    page_size: int = 20

    @property
    def has_next(self):
        return self.page * self.page_size < self.total

    @property
    def has_previous(self):
        return self.page > 1


def public_id(link):
    return sha256(link.encode('utf-8')).hexdigest()


def safe_url(value):
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme in ('http','https') and parsed.hostname and not parsed.username and not parsed.password and not any(ord(c)<33 for c in value))
    except (TypeError,ValueError):
        return False


@contextmanager
def open_news():
    value = getattr(settings,'POST_NEWS_DB','')
    if not value:
        raise NewsUnavailable('News is not configured.')
    conn = None
    try:
        # mode=ro refuses creation and writes. query_only is an additional guard.
        path = Path(value).expanduser().resolve(strict=True)
        conn = sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=1)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        deadline = time.monotonic()+2
        conn.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
        conn.create_function('public_id',1,public_id,deterministic=True)
        conn.create_function('safe_url',1,safe_url,deterministic=True)
        yield conn
    except (sqlite3.Error,OSError,ValueError,TypeError) as exc:
        raise NewsUnavailable('News cannot be read safely.') from exc
    finally:
        if conn is not None:
            conn.close()


def visibility(conn):
    required={'articles','hidden_links','settings','filter_rules','filter_hits','filter_keeps'}
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required.issubset(tables):
        raise NewsUnavailable('Required visibility policy is unavailable.')
    # Read only this non-secret setting; never enumerate service settings.
    row=conn.execute("SELECT value FROM settings WHERE name='hidden_sources'").fetchone()
    try:
        off=json.loads(row[0]) if row else []
    except (ValueError,TypeError) as exc:
        raise NewsUnavailable('Visibility policy is invalid.') from exc
    if not isinstance(off,list) or not all(isinstance(s,str) for s in off):
        raise NewsUnavailable('Visibility policy is invalid.')
    now=timezone.now()
    conditions=[
        'a.region = ?',
        "a.post_status IN ('ready','legacy')",
        "TRIM(COALESCE(a.title_ko,'')) <> ''",
        "(TRIM(COALESCE(a.summary,'')) = '' OR TRIM(COALESCE(a.summary_ko,'')) <> '')",
        'safe_url(a.link) = 1',
        'julianday(a.published_at) BETWEEN julianday(?) AND julianday(?)',
        'NOT EXISTS (SELECT 1 FROM hidden_links h WHERE h.link=a.link)',
        'NOT EXISTS (SELECT 1 FROM filter_hits h JOIN filter_rules r ON r.id=h.rule_id WHERE h.link=a.link AND r.enabled=1 AND NOT EXISTS (SELECT 1 FROM filter_keeps k WHERE k.link=a.link))',
    ]
    params=['태국',(now-timedelta(days=30)).isoformat(),(now+timedelta(minutes=1)).isoformat()]
    if off:
        conditions.append('a.source NOT IN ('+','.join('?' for _ in off)+')')
        params.extend(off)
    return conditions,params


FIELDS='a.link,a.title_ko,a.summary_ko,a.source,a.original_source,a.category,a.published_at'


def projection_fields(conn):
    columns={row['name'] for row in conn.execute('PRAGMA table_info(articles)')}
    if 'image_url' in columns:
        image="CASE WHEN safe_url(a.image_url)=1 AND lower(a.image_url) LIKE 'https://%' THEN a.image_url ELSE '' END AS image_url"
    else:
        image="'' AS image_url"
    return FIELDS+','+image


def project(row):
    published=parse_datetime(row['published_at'])
    if published and timezone.is_naive(published):
        published=published.replace(tzinfo=dt_timezone.utc)
    return {
        'id':public_id(row['link']),
        'title':strip_tags(row['title_ko']).strip(),
        'summary':strip_tags(row['summary_ko'] or '').strip(),
        'source':(row['original_source'] or row['source'] or '').strip(),
        'category':row['category'] or '',
        'published_at':published,
        'source_url':row['link'],
        'image_url':row['image_url'] or '',
    }


def list_articles(page=1,query='',page_size=20):
    page=max(1,min(int(page),10000))
    page_size=max(1,min(int(page_size),20))
    with open_news() as conn:
        conn.execute('BEGIN') # Consistent policy, count and rows in one read snapshot.
        conditions,params=visibility(conn)
        fields=projection_fields(conn)
        if query:
            needle='%'+query[:200].replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            conditions.append("(a.title_ko LIKE ? ESCAPE '\\' OR a.summary_ko LIKE ? ESCAPE '\\')")
            params.extend([needle,needle])
        clause=' AND '.join(conditions)
        total=conn.execute('SELECT COUNT(*) FROM articles a WHERE '+clause,params).fetchone()[0]
        rows=conn.execute('SELECT '+fields+' FROM articles a WHERE '+clause+' ORDER BY a.published_at DESC,a.link LIMIT ? OFFSET ?',params+[page_size,(page-1)*page_size]).fetchall()
        return NewsPage([project(row) for row in rows],total,page,page_size)


def get_article(article_id):
    if len(article_id)!=64 or any(c not in '0123456789abcdef' for c in article_id):
        return None
    with open_news() as conn:
        conn.execute('BEGIN')
        conditions,params=visibility(conn)
        fields=projection_fields(conn)
        conditions.append('public_id(a.link)=?')
        row=conn.execute('SELECT '+fields+' FROM articles a WHERE '+' AND '.join(conditions),params+[article_id]).fetchone()
        return project(row) if row else None
