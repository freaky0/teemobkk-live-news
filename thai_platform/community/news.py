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
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
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
    categories: tuple = ()
    category: str = ''
    region_groups: tuple = ()
    region_group: str = ''

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

# The public feed stores Thai-wide articles, not province metadata. Match the
# places named in the Korean headline or summary and expose a small, curated set
# of regional groups. Keep aliases here so the groups can be expanded safely.
REGION_GROUPS = (
    ('north', '북부'),
    ('central', '중부'),
    ('south', '남부'),
)
REGION_ALIASES = {
    'north': (
        '북부', '북부 태국', '태국 북부', 'Northern Thailand',
        '치앙마이', 'Chiang Mai', 'Chiangmai',
        '치앙라이', 'Chiang Rai', 'Chiangrai',
        '람빵', '람팡', 'Lampang', '람푼', 'Lamphun',
        '매홍손', 'Mae Hong Son', '파야오', 'Phayao', '프래', 'Phrae',
    ),
    'central': (
        '중부', '중부 태국', '태국 중부', 'Central Thailand',
        '방콕', 'Bangkok', '논타부리', 'Nonthaburi', '파타야', 'Pattaya',
        '촌부리', 'Chonburi', 'Chon Buri',
        '사뭇쁘라깐', '사뭇프라칸', 'Samut Prakan',
        '빠툼타니', '빠툼 타니', 'Pathum Thani',
        '아유타야', 'Ayutthaya', '나콘빠톰', '나콘파톰', 'Nakhon Pathom',
    ),
    'south': (
        '남부', '남부 태국', '태국 남부', 'Southern Thailand',
        '푸껫', '푸켓', 'Phuket', '끄라비', '크라비', 'Krabi',
        '핫야이', 'Hat Yai', 'Hatyai', '송클라', 'Songkhla',
        '코사무이', '꼬사무이', 'Koh Samui', 'Ko Samui',
        '수랏타니', 'Surat Thani', '팡아', '팡응아', 'Phang Nga',
        '뜨랑', '트랑', 'Trang', '나콘시탐마랏', 'Nakhon Si Thammarat',
        '사툰', 'Satun', '파타니', '빠따니', 'Pattani', '얄라', 'Yala',
        '나라티왓', 'Narathiwat',
    ),
}


def projection_fields(conn):
    columns={row['name'] for row in conn.execute('PRAGMA table_info(articles)')}
    if 'image_url' in columns:
        image="CASE WHEN safe_url(a.image_url)=1 AND lower(a.image_url) LIKE 'https://%' THEN a.image_url ELSE '' END AS image_url"
    else:
        image="'' AS image_url"
    if 'video_url' in columns:
        video="CASE WHEN safe_url(a.video_url)=1 AND lower(a.video_url) LIKE 'https://%' THEN a.video_url ELSE '' END AS video_url"
    else:
        video="'' AS video_url"
    return FIELDS+','+image+','+video


def project_video(value):
    """Return a playable URL only for direct files and explicitly supported embeds."""
    if not safe_url(value):
        return {'kind':'','url':'','embed_url':''}
    parsed=urlsplit(value)
    if parsed.scheme.lower()!='https':
        return {'kind':'','url':'','embed_url':''}
    host=(parsed.hostname or '').lower().rstrip('.')
    path_parts=[part for part in parsed.path.split('/') if part]
    suffix=Path(parsed.path).suffix.lower()
    if suffix in {'.mp4','.m4v','.webm','.ogv','.ogg'}:
        return {'kind':'file','url':value,'embed_url':''}

    video_id=''
    if host in {'youtube.com','www.youtube.com','m.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be'}:
        if host=='youtu.be' and path_parts:
            video_id=path_parts[0]
        elif path_parts and path_parts[0] in {'embed','v','shorts','live'} and len(path_parts)>1:
            video_id=path_parts[1]
        elif path_parts and path_parts[0]=='watch':
            video_id=parse_qs(parsed.query).get('v',[''])[0]
        if re.fullmatch(r'[A-Za-z0-9_-]{11}',video_id):
            return {'kind':'embed','url':'','embed_url':'https://www.youtube-nocookie.com/embed/'+video_id}
    if host in {'vimeo.com','www.vimeo.com','player.vimeo.com'} and path_parts:
        video_id=path_parts[-1] if path_parts[-1].isdigit() else ''
        if video_id:
            return {'kind':'embed','url':'','embed_url':'https://player.vimeo.com/video/'+video_id}
    return {'kind':'','url':'','embed_url':''}


def project(row):
    published=parse_datetime(row['published_at'])
    if published and timezone.is_naive(published):
        published=published.replace(tzinfo=dt_timezone.utc)
    video=project_video(row['video_url'] or '')
    return {
        'id':public_id(row['link']),
        'title':strip_tags(row['title_ko']).strip(),
        'summary':strip_tags(row['summary_ko'] or '').strip(),
        'source':(row['original_source'] or row['source'] or '').strip(),
        'category':(row['category'] or '').strip(),
        'published_at':published,
        'source_url':row['link'],
        'image_url':row['image_url'] or '',
        'video_kind':video['kind'],
        'video_url':video['url'],
        'video_embed_url':video['embed_url'],
    }


def list_articles(page=1,query='',page_size=20,category='',region_group='',include_categories=False):
    page=max(1,min(int(page),10000))
    page_size=max(1,min(int(page_size),20))
    with open_news() as conn:
        conn.execute('BEGIN') # Consistent policy, count and rows in one read snapshot.
        conditions,params=visibility(conn)
        fields=projection_fields(conn)
        if include_categories:
            category_rows=conn.execute(
                'SELECT DISTINCT TRIM(COALESCE(a.category,\'\')) AS category FROM articles a WHERE '
                +' AND '.join(conditions)+" AND TRIM(COALESCE(a.category,'')) <> '' ORDER BY category COLLATE NOCASE",
                params,
            ).fetchall()
            categories=tuple(row['category'] for row in category_rows)
        else:
            categories=()
        category=category.strip()[:200] if isinstance(category,str) else ''
        if category not in categories:
            category=''
        region_group=region_group.strip() if isinstance(region_group,str) else ''
        if region_group not in REGION_ALIASES:
            region_group=''
        if query:
            needle='%'+query[:200].replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            conditions.append("(a.title_ko LIKE ? ESCAPE '\\' OR a.summary_ko LIKE ? ESCAPE '\\')")
            params.extend([needle,needle])
        if category:
            conditions.append("TRIM(COALESCE(a.category,'')) = ?")
            params.append(category)
        if region_group:
            aliases=REGION_ALIASES[region_group]
            conditions.append('('+' OR '.join(
                "COALESCE(a.title_ko,'') LIKE ? ESCAPE '\\' OR COALESCE(a.summary_ko,'') LIKE ? ESCAPE '\\'"
                for _ in aliases
            )+')')
            for alias in aliases:
                needle='%'+alias.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
                params.extend((needle,needle))
        clause=' AND '.join(conditions)
        total=conn.execute('SELECT COUNT(*) FROM articles a WHERE '+clause,params).fetchone()[0]
        rows=conn.execute('SELECT '+fields+' FROM articles a WHERE '+clause+' ORDER BY a.published_at DESC,a.link LIMIT ? OFFSET ?',params+[page_size,(page-1)*page_size]).fetchall()
        return NewsPage([project(row) for row in rows],total,page,page_size,categories,category,REGION_GROUPS,region_group)


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


def sitemap_article_count():
    with open_news() as conn:
        conn.execute('BEGIN')
        conditions,params=visibility(conn)
        row=conn.execute(
            'SELECT COUNT(*) FROM articles a WHERE '+' AND '.join(conditions),
            params,
        ).fetchone()
        return int(row[0])


def sitemap_articles(limit=50000, offset=0):
    limit=max(1,min(int(limit),50000))
    offset=max(0,int(offset))
    with open_news() as conn:
        conn.execute('BEGIN')
        conditions,params=visibility(conn)
        rows=conn.execute(
            'SELECT public_id(a.link) AS id,a.published_at AS published_at FROM articles a WHERE '
            +' AND '.join(conditions)
            +' ORDER BY a.published_at DESC,a.link LIMIT ? OFFSET ?',
            params+[limit,offset],
        ).fetchall()
        return [
            {'id':row['id'],'published_at':parse_datetime(row['published_at'])}
            for row in rows
        ]
