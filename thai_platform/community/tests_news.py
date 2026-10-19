"""News integration contract. Fixture data is explicitly synthetic, never production data."""
import json
import sqlite3
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from . import news

class NewsTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(dir=Path(__file__).resolve().parent.parent / 'var')
        self.path = Path(self.tmp.name) / 'fixture.sqlite3'
        with sqlite3.connect(self.path) as c:
            c.executescript('''CREATE TABLE articles(link TEXT PRIMARY KEY,title_ko TEXT,summary_ko TEXT,summary TEXT,source TEXT,original_source TEXT,region TEXT,category TEXT,post_status TEXT,published_at TEXT,image_url TEXT);
CREATE TABLE hidden_links(link TEXT);
CREATE TABLE filter_rules(id INTEGER PRIMARY KEY,enabled INTEGER);
CREATE TABLE filter_hits(link TEXT,rule_id INTEGER);
CREATE TABLE filter_keeps(link TEXT);
CREATE TABLE settings(name TEXT PRIMARY KEY,value TEXT);''')
        self.settings_override = override_settings(POST_NEWS_DB=str(self.path))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.tmp.cleanup)
    def add(self, slug, **changes):
        from django.utils import timezone
        row = dict(link='https://example.org/'+slug,title_ko='검증용 태국 뉴스 '+slug,summary_ko='테스트 전용 한국어 요약입니다.',summary='Original summary',source='Fixture',original_source='',region='태국',category='생활',post_status='ready',published_at=timezone.now().isoformat(),image_url='')
        row.update(changes)
        with sqlite3.connect(self.path) as c:
            c.execute('INSERT INTO articles (link,title_ko,summary_ko,summary,source,original_source,region,category,post_status,published_at,image_url) VALUES (:link,:title_ko,:summary_ko,:summary,:source,:original_source,:region,:category,:post_status,:published_at,:image_url)',row)
        return row['link']
    def sql(self, statement, args=()):
        with sqlite3.connect(self.path) as c:
            c.execute(statement,args)
    def test_visibility_is_same_for_home_list_detail_api(self):
        public = self.add('public')
        self.add('legacy',post_status='legacy')
        blocked = [self.add('pending',post_status='pending'),self.add('unknown',post_status='draft'),self.add('global',region='글로벌'),self.add('untitled',title_ko=''),self.add('untranslated',summary_ko=''),self.add('hidden'),self.add('rule'),self.add('off',source='Disabled')]
        self.sql('INSERT INTO hidden_links VALUES (?)',(blocked[-3],))
        self.sql('INSERT INTO filter_rules VALUES (1,1)')
        self.sql('INSERT INTO filter_hits VALUES (?,1)',(blocked[-2],))
        self.sql('INSERT INTO settings VALUES (?,?)',('hidden_sources',json.dumps(['Disabled'])))
        result = news.list_articles()
        self.assertEqual(result.total,2)
        for endpoint in ['/', '/newsroom/', '/api/v1/news/']:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'검증용 태국 뉴스 public')
            for link in blocked:
                slug=link.rsplit('/',1)[-1]
                self.assertNotContains(response,'검증용 태국 뉴스 '+slug)
        for link in blocked:
            ident=sha256(link.encode()).hexdigest()
            self.assertEqual(self.client.get('/newsroom/'+ident+'/').status_code,404)
            self.assertEqual(self.client.get('/api/v1/news/'+ident+'/').status_code,404)
        ident=sha256(public.encode()).hexdigest()
        self.assertEqual(self.client.get('/newsroom/'+ident+'/').status_code,200)
        self.assertEqual(self.client.get('/api/v1/news/'+ident+'/').status_code,200)
    def test_article_image_is_projected_and_rendered_on_home_news_detail_and_api(self):
        image='https://images.publisher.example/story.jpg'
        link=self.add('with-image',image_url=image)
        ident=sha256(link.encode()).hexdigest()
        self.assertEqual(news.get_article(ident)['image_url'],image)
        self.assertContains(self.client.get('/'),image)
        self.assertContains(self.client.get('/newsroom/'),image)
        self.assertContains(self.client.get('/newsroom/'+ident+'/'),image)
        payload=self.client.get('/api/v1/news/').json()
        self.assertEqual(payload['results'][0]['image_url'],image)

    def test_article_image_rejects_non_https_and_credential_urls(self):
        unsafe=['http://images.publisher.example/story.jpg','https://user:pass@images.publisher.example/story.jpg','javascript:alert(1)']
        for index,image in enumerate(unsafe):
            with self.subTest(image=image):
                link=self.add('unsafe-image-'+str(index),image_url=image)
                self.assertEqual(news.get_article(sha256(link.encode()).hexdigest())['image_url'],'')

    def test_keep_and_disabled_rule_do_not_bypass_manual_hide(self):
        link=self.add('kept')
        self.sql('INSERT INTO filter_rules VALUES (1,1)')
        self.sql('INSERT INTO filter_hits VALUES (?,1)',(link,))
        self.assertEqual(news.list_articles().total,0)
        self.sql('INSERT INTO filter_keeps VALUES (?)',(link,))
        self.assertEqual(news.list_articles().total,1)
        self.sql('INSERT INTO hidden_links VALUES (?)',(link,))
        self.assertEqual(news.list_articles().total,0)
        self.sql('DELETE FROM hidden_links')
        self.sql('DELETE FROM filter_keeps')
        self.sql('UPDATE filter_rules SET enabled=0')
        self.assertEqual(news.list_articles().total,1)
    def test_read_only_open_and_no_source_modifications(self):
        self.add('readonly')
        before=self.path.read_bytes()
        with news.open_news() as c:
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("UPDATE articles SET title_ko='bad'")
        news.list_articles()
        self.assertEqual(self.path.read_bytes(),before)
    def test_missing_or_invalid_policy_fails_closed(self):
        self.add('safe')
        self.sql("INSERT INTO settings VALUES ('hidden_sources','not-json')")
        with self.assertRaises(news.NewsUnavailable):news.list_articles()
        self.assertEqual(self.client.get('/newsroom/').status_code,503)
        self.assertEqual(self.client.get('/api/v1/news/').status_code,503)
        self.sql('DELETE FROM settings')
        self.sql('DROP TABLE filter_rules')
        with self.assertRaises(news.NewsUnavailable):news.list_articles()
    def test_missing_database_does_not_create_file(self):
        missing=Path(self.tmp.name)/'missing.db'
        with override_settings(POST_NEWS_DB=str(missing)):
            self.assertEqual(self.client.get('/newsroom/').status_code,503)
            self.assertEqual(self.client.get('/').status_code,200)
        self.assertFalse(missing.exists())
    def test_search_pagination_readonly_methods_and_payload(self):
        self.add('first')
        self.add('second',summary_ko='검색키워드 포함')
        result=self.client.get('/api/v1/news/',{'q':'검색키워드'}).json()
        self.assertEqual(result['count'],1)
        self.assertEqual(len(result['results']),1)
        self.assertNotIn('post_status',result['results'][0])
        self.assertNotIn('summary_ko',result['results'][0])
        self.assertEqual(self.client.get('/api/v1/news/?page=bad').status_code,400)
        self.assertEqual(self.client.get('/api/v1/news/?page=999').json()['results'],[])
        self.assertEqual(self.client.post('/api/v1/news/',{}).status_code,405)
        self.assertEqual(self.client.get('/api/v1/news/?q=%27%20OR%201=1--').json()['count'],0)
    def test_invalid_source_urls_dates_and_future_are_excluded(self):
        self.add('js',link='javascript:alert(1)')
        self.add('creds',link='https://user:secret@example.org/a')
        self.add('future',published_at='2099-01-01T00:00:00Z')
        self.add('badtime',published_at='invalid')
        self.add('old',published_at='2000-01-01T00:00:00Z')
        self.assertEqual(news.list_articles().total,0)
    def test_detail_list_return_preserves_filter_and_page(self):
        from urllib.parse import urlencode
        link=self.add('return')
        query='?q=검증&page=2'
        path='/newsroom/'+sha256(link.encode()).hexdigest()+'/'
        response=self.client.get(path,{'from':query})
        self.assertEqual(response.context['back_url'],'/newsroom/'+query)
        response=self.client.get(path,{'from':'https://evil.example/'})
        self.assertEqual(response.context['back_url'],'/newsroom/')
        response=self.client.get('/newsroom/',{'q':'검증','page':1})
        self.assertContains(response,'?from=')

    def test_unconfigured_and_escaped_output(self):
        with override_settings(POST_NEWS_DB=''):
            with self.assertRaises(news.NewsUnavailable):news.list_articles()
        link=self.add('escaped',title_ko='<script>alert(1)</script>테스트',summary_ko='<img src=x onerror=alert(2)>요약')
        response=self.client.get('/newsroom/'+sha256(link.encode()).hexdigest()+'/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertNotContains(response,'<img src=x')
        self.assertContains(response,'rel="noopener noreferrer"')
