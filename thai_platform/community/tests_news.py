"""News integration contract. Fixture data is explicitly synthetic, never production data."""
import json
import gc
import sqlite3
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase, override_settings
from django.db import connections
from . import news

class NewsTests(TestCase):
    def setUp(self):
        # SQLite fixture files must live outside the synced source tree on Windows.
        # OneDrive can retain a handle briefly after sqlite3 connections close.
        self.tmp = TemporaryDirectory()
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
        # Close any deferred Django cursors before deleting the fixture on Windows.
        self.addCleanup(connections.close_all)
        self.addCleanup(gc.collect)
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

    def test_public_categories_filter_newsroom_and_stay_in_page_results(self):
        self.add('life-category', category='생활')
        self.add('visa-category', category='비자')
        self.add('pending-category', category='미공개', post_status='pending')

        page = news.list_articles(category='비자', include_categories=True)
        self.assertEqual(page.categories, ('비자', '생활'))
        self.assertEqual(page.category, '비자')
        self.assertEqual(page.total, 1)
        self.assertEqual([item['category'] for item in page.items], ['비자'])

        response = self.client.get('/newsroom/', {'q': '태국 뉴스', 'category': '비자'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '검증용 태국 뉴스 visa-category')
        self.assertNotContains(response, '검증용 태국 뉴스 life-category')
        self.assertContains(response, '<option value="비자" selected>비자</option>', html=True)
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

    def test_social_previews_are_stable_on_home_and_article_specific(self):
        from html.parser import HTMLParser
        class Meta(HTMLParser):
            def __init__(self):
                super().__init__(); self.tags = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'meta': self.tags.append((attrs.get('property', attrs.get('name')), attrs.get('content')))
        def metadata(response):
            parser = Meta(); parser.feed(response.content.decode()); return parser.tags
        image = 'https://images.publisher.example/story.jpg'
        link = self.add('social-story', image_url=image)
        ident = sha256(link.encode()).hexdigest()
        home = metadata(self.client.get('/?utm_source=test'))
        branded = 'https://teemobkk.io/thai/static/assets/share-home-v1.jpg'
        self.assertEqual([v for k, v in home if k == 'og:image'], [branded])
        self.assertIn(('twitter:image', branded), home)
        self.assertIn(('og:url', 'https://teemobkk.io/thai/'), home)
        self.assertIn(('og:image:type', 'image/jpeg'), home)
        self.assertIn(('og:image:width', '1200'), home)
        self.assertIn(('og:image:height', '630'), home)
        detail = metadata(self.client.get('/newsroom/'+ident+'/'))
        self.assertEqual([v for k, v in detail if k == 'og:image'], [image])
        self.assertIn(('twitter:image', image), detail)
        self.assertIn(('og:title', '검증용 태국 뉴스 social-story'), detail)
        self.assertIn(('og:url', 'https://teemobkk.io/thai/newsroom/'+ident+'/'), detail)
        no_image = self.add('social-no-image')
        missing = metadata(self.client.get('/newsroom/'+sha256(no_image.encode()).hexdigest()+'/'))
        self.assertEqual([v for k, v in missing if k == 'og:image'], [branded])
        self.assertIn(('twitter:image', branded), missing)
        self.assertIn(('og:title', '검증용 태국 뉴스 social-no-image'), missing)
        from PIL import Image
        from django.contrib.staticfiles import finders
        asset = Path(__file__).resolve().parent.parent / 'static/assets/share-home-v1.jpg'
        self.assertEqual(Path(finders.find('assets/share-home-v1.jpg')).resolve(), asset.resolve())
        with Image.open(asset) as graphic:
            self.assertEqual((graphic.format, graphic.size), ('JPEG', (1200, 630)))
            graphic.verify()

    def test_homepage_featured_story_is_the_newest_visible_article(self):
        from datetime import timedelta
        from django.utils import timezone

        now = timezone.now()
        self.add('older-home-story', published_at=(now - timedelta(hours=1)).isoformat())
        self.add('newest-home-story', published_at=now.isoformat())
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('home-news-card is-featured'), 1)
        self.assertLess(html.index('newest-home-story'), html.index('older-home-story'))

    def test_known_external_publisher_images_remain_rendered(self):
        hosts=['assets.aseannow.com','www.matichon.co.th','mpics2.mgronline.com']
        for index,host in enumerate(hosts):
            image=f'https://{host}/teemobkk-preview-{index}.jpg'
            link=self.add('publisher-image-'+str(index),image_url=image)
            ident=sha256(link.encode()).hexdigest()
            self.assertEqual(news.get_article(ident)['image_url'],image)
            for path in ['/', '/newsroom/', '/newsroom/'+ident+'/']:
                with self.subTest(host=host,path=path):
                    self.assertContains(self.client.get(path),image)
        payload=self.client.get('/api/v1/news/').json() or {}
        image_urls={row['image_url'] for row in payload.get('results',[]) if row.get('image_url')}
        self.assertTrue(all(any(url.startswith('https://'+host+'/') for url in image_urls) for host in hosts))

    def test_video_uses_static_poster_in_list_and_player_in_detail(self):
        poster='https://images.publisher.example/video-poster.jpg'
        video='https://video.publisher.example/story.mp4'
        self.sql('ALTER TABLE articles ADD COLUMN video_url TEXT')
        link=self.add('with-video',image_url=poster)
        self.sql('UPDATE articles SET video_url=? WHERE link=?',(video,link))
        ident=sha256(link.encode()).hexdigest()
        article=news.get_article(ident)
        self.assertEqual(article['video_kind'],'file')
        self.assertEqual(article['video_url'],video)
        listing=self.client.get('/newsroom/')
        self.assertContains(listing,poster)
        self.assertNotContains(listing,'<video')
        detail=self.client.get('/newsroom/'+ident+'/')
        self.assertContains(detail,'<video')
        self.assertContains(detail,'controls')
        self.assertContains(detail,'poster="'+poster+'"')
        self.assertContains(detail,video)

    def test_youtube_video_is_projected_to_a_privacy_enhanced_player(self):
        self.sql('ALTER TABLE articles ADD COLUMN video_url TEXT')
        link=self.add('with-youtube')
        self.sql('UPDATE articles SET video_url=? WHERE link=?',('https://www.youtube.com/watch?v=dQw4w9WgXcQ',link))
        article=news.get_article(sha256(link.encode()).hexdigest())
        self.assertEqual(article['video_kind'],'embed')
        self.assertEqual(article['video_embed_url'],'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')
        detail=self.client.get('/newsroom/'+sha256(link.encode()).hexdigest()+'/')
        self.assertContains(detail,'<iframe')
        self.assertContains(detail,article['video_embed_url'])

    def test_video_projection_rejects_untrusted_schemes_and_hosts(self):
        self.sql('ALTER TABLE articles ADD COLUMN video_url TEXT')
        for index,video in enumerate(('javascript:alert(1)','https://evil.example/embed/abc')):
            link=self.add('unsafe-video-'+str(index))
            self.sql('UPDATE articles SET video_url=? WHERE link=?',(video,link))
            article=news.get_article(sha256(link.encode()).hexdigest())
            self.assertEqual(article['video_kind'],'')
            self.assertEqual(article['video_url'],'')
            self.assertEqual(article['video_embed_url'],'')

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

    def test_article_detail_shows_share_like_count_and_comment_form(self):
        link=self.add('interactions')
        ident=sha256(link.encode()).hexdigest()
        response=self.client.get('/newsroom/'+ident+'/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'공유하기')
        self.assertContains(response,'좋아요')
        self.assertContains(response,'댓글')
        self.assertContains(response,'로그인하고 댓글 쓰기')

    def test_news_like_is_member_only_and_toggles_for_current_user(self):
        from django.contrib.auth import get_user_model
        link=self.add('like')
        ident=sha256(link.encode()).hexdigest()
        self.assertEqual(self.client.post('/newsroom/'+ident+'/like/').status_code,302)
        user=get_user_model().objects.create_user(username='news-liker')
        self.client.force_login(user)
        self.assertEqual(self.client.post('/newsroom/'+ident+'/like/').status_code,302)
        response=self.client.get('/newsroom/'+ident+'/')
        self.assertContains(response,'aria-pressed="true"')
        self.assertContains(response,'좋아요 1')
        self.assertEqual(self.client.post('/newsroom/'+ident+'/like/').status_code,302)
        response=self.client.get('/newsroom/'+ident+'/')
        self.assertContains(response,'aria-pressed="false"')
        self.assertContains(response,'좋아요 0')

    def test_news_comment_is_member_only_saved_and_escaped(self):
        from django.contrib.auth import get_user_model
        from .models import NewsComment
        link=self.add('comment')
        ident=sha256(link.encode()).hexdigest()
        payload={'body':'<script>alert(1)</script>태국 뉴스에 남기는 검증 댓글입니다.'}
        self.assertEqual(self.client.post('/newsroom/'+ident+'/comments/',payload).status_code,302)
        user=get_user_model().objects.create_user(username='news-commenter')
        self.client.force_login(user)
        self.assertEqual(self.client.post('/newsroom/'+ident+'/comments/',payload).status_code,302)
        self.assertEqual(NewsComment.objects.get().article_id,ident)
        detail=self.client.get('/newsroom/'+ident+'/')
        self.assertContains(detail,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(detail,'<script>alert(1)</script>')

    def test_hidden_news_comments_are_not_rendered_publicly(self):
        from django.contrib.auth import get_user_model
        from .models import NewsComment
        link=self.add('hidden-comment')
        ident=sha256(link.encode()).hexdigest()
        author=get_user_model().objects.create_user(username='hidden-news-comment-author')
        NewsComment.objects.create(
            article_id=ident,
            author=author,
            body='This hidden comment must not be public.',
            status=NewsComment.Status.HIDDEN,
        )
        response=self.client.get('/newsroom/'+ident+'/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'This hidden comment must not be public.')

    def test_news_comment_rejects_short_and_hidden_article_writes(self):
        from django.contrib.auth import get_user_model
        from .models import NewsComment
        link=self.add('comment-validation')
        ident=sha256(link.encode()).hexdigest()
        user=get_user_model().objects.create_user(username='news-comment-validation')
        self.client.force_login(user)
        invalid=self.client.post('/newsroom/'+ident+'/comments/',{'body':'too'})
        self.assertEqual(invalid.status_code,400)
        self.assertContains(invalid,'aria-invalid="true"',status_code=400)
        self.assertContains(invalid,'aria-describedby="news-comment-error"',status_code=400)
        self.assertEqual(NewsComment.objects.count(),0)
        self.sql('INSERT INTO hidden_links VALUES (?)',(link,))
        self.assertEqual(self.client.post('/newsroom/'+ident+'/comments/',{'body':'이 뉴스는 공개 대상이 아니므로 댓글이 저장되면 안 됩니다.'}).status_code,404)
        self.assertEqual(NewsComment.objects.count(),0)
