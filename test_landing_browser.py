"""Run isolated Chromium checks without changing the desktop browser profile.
Usage: python test_landing_browser.py [--live]
Requires Playwright; optional HERMES_BROWSER_TOOLS path for isolated install.
"""
import os,sys,json,datetime
from pathlib import Path
if os.environ.get('HERMES_BROWSER_TOOLS'): sys.path.insert(0,os.environ['HERMES_BROWSER_TOOLS'])
from playwright.sync_api import sync_playwright
import requests
import landing

OUT=Path('C:/Users/freak/AppData/Local/hermes/cache/scratch/teemo-redesign')
OUT.mkdir(parents=True,exist_ok=True)
BASE='https://teemobkk.io/'
LIVE='--live' in sys.argv
payload=requests.get(BASE+'api/news',params={'region':'글로벌','hours':24,'limit':100},timeout=30).json()
checks=[]
def check(name,condition):
    checks.append({'check':name,'pass':bool(condition)})
    assert condition,name
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    if not LIVE:
        page.route(BASE,lambda route:route.fulfill(content_type='text/html',body=landing.render_landing()))
        page.route('**/api/news?*',lambda route:route.fulfill(json=payload))
    page.goto(BASE,wait_until='networkidle')
    page.wait_for_function("document.querySelector('#news-list').getAttribute('aria-busy')==='false'")
    check('headline',page.locator('h1').inner_text().replace('\n','').find('경제 뉴스와 시장 관점')>=0)
    check('six_real_news',page.locator('.news-item h3').count()==6)
    check('no_platform_label','서브스택' not in page.locator('body').inner_text())
    for width in [1440,1024,768,390,320]:
        page.set_viewport_size({'width':width,'height':900})
        check('no_horizontal_overflow_'+str(width),page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.set_viewport_size({'width':1440,'height':1000})
    page.locator('#indicators').scroll_into_view_if_needed();page.wait_for_timeout(1500)
    check('real_chart_images_loaded',page.locator('.chart-open img').evaluate_all('(imgs)=>imgs.length===2 && imgs.every(i=>i.complete&&i.naturalWidth>0)'))
    page.locator('.chart-open').first.click();check('chart_dialog_opens',page.locator('dialog').evaluate('(d)=>d.open'));page.keyboard.press('Escape');check('escape_closes_dialog',not page.locator('dialog').evaluate('(d)=>d.open'))
    page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(OUT/('live-desktop.png' if LIVE else 'desktop.png')),full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(OUT/('live-mobile.png' if LIVE else 'mobile.png')),full_page=True)
    check('no_javascript_errors',not errors)
    if not LIVE:
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        def article(title,region='글로벌',link='https://example.com/news'):
            return {'title':title,'region':region,'link':link,'published_at':now,'source':'Test source','category':'거시경제'}
        sample={'updated_at':now,'articles':[article('on.wsj.com/abc'),article('태국 관련 테스트 뉴스','태국'),article('금리 결정 관련 시장 테스트 제목 - 매체A'),article('금리 결정 관련 시장 테스트 제목 - 매체B'),article('악성 링크를 제외하는 테스트 제목',link='javascript:alert(1)'),article('<img src=x onerror=alert(1)> 안전 표시 테스트'),{**article('퇴직 경찰 관련 일반 사회 뉴스'),'category':'일반'}, {**article('Gold rises as bond yields fall'),'category':'일반'}]}
        page.route('**/api/news?*',lambda route:route.fulfill(json=sample));page.reload(wait_until='networkidle')
        check('exclude_thai_url_only_duplicates_unsafe_links',page.locator('.news-item h3').count()==3)
        check('untrusted_title_is_text',page.locator('#news-list img').count()==0)
        page.route('**/api/news?*',lambda route:route.abort());page.evaluate("document.querySelector('#retry').hidden=false");page.locator('#retry').click();page.wait_for_function("document.querySelector('#update-status').textContent.includes('갱신 실패')")
        check('failure_preserves_previous_news',page.locator('.news-item h3').count()==3)
        page.reload(wait_until='networkidle');check('initial_failure_honest',page.locator('#update-status').inner_text()=='뉴스를 불러오지 못했습니다')
        page.route('**/api/news?*',lambda route:route.fulfill(json={'articles':[]}));page.locator('#retry').click();page.wait_for_function("document.querySelector('#update-status').textContent==='수집 시각을 확인할 수 없습니다'")
        check('empty_state', '표시할 뉴스가 없습니다' in page.locator('#news-list').inner_text())
        old=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(hours=2)).isoformat()
        page.route('**/api/news?*',lambda route:route.fulfill(json={'articles':[],'updated_at':old}));page.locator('#retry').click();page.wait_for_function("document.querySelector('#update-status').textContent.includes('갱신 지연')")
        check('stale_timestamp_warning',True)
    browser.close()
print(json.dumps({'mode':'live' if LIVE else 'local','checks':checks,'total':len(checks),'passed':sum(c['pass'] for c in checks)},ensure_ascii=False,indent=2))
