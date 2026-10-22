"""Read-only smoke check for an already running local development server.

Never creates users, posts, translations or source DB rows. Captures actual news.
"""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from playwright.sync_api import sync_playwright

root='http://127.0.0.1:8870'
out=Path(__file__).resolve().parents[1]/'var'/'news-preview'
out.mkdir(parents=True,exist_ok=True)
with urlopen(Request(root+'/api/v1/news/',headers={'Accept':'application/json'}),timeout=10) as response:
    payload=json.load(response)
assert payload['count']>0 and payload['results'], 'No actual public translated news found'
first=payload['results'][0]
paths={'home':'/','news-list':'/news/','news-detail':'/news/'+first['id']+'/'}
checks=[]
with sync_playwright() as pw:
    launch={'headless':True,'args':['--no-sandbox']}
    if os.environ.get('POST_BROWSER_EXECUTABLE'):
        launch['executable_path']=os.environ['POST_BROWSER_EXECUTABLE']
    browser=pw.chromium.launch(**launch)
    context=browser.new_context(reduced_motion='reduce')
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda err: errors.append(str(err)))
    page.on('console',lambda msg: errors.append(msg.text) if msg.type=='error' else None)
    for width in [320,390,768,1024,1440]:
        page.set_viewport_size({'width':width,'height':1000})
        for name,path in paths.items():
            assert page.goto(root+path,wait_until='networkidle').status==200
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(width,path)
            assert page.locator('img').evaluate_all('items=>items.every(i=>i.complete&&i.naturalWidth>0)'),(width,path)
            assert page.get_by_role('link',name=first['title'],exact=True).count() or name=='news-detail'
            if width in [390,1440]:
                page.screenshot(path=str(out/f'{name}-{width}.png'),full_page=(name!='home'))
            checks.append({'width':width,'page':name,'status':200,'overflow':False})
    page.goto(root+'/news/',wait_until='networkidle')
    page.locator('.news-item h3 a').first.click()
    page.wait_for_url(root+paths['news-detail'])
    assert page.locator('h1').inner_text()==first['title']
    assert page.locator('dialog[open]').count()==0
    page.reload(wait_until='networkidle')
    assert page.locator('h1').inner_text()==first['title']
    page.go_back(wait_until='networkidle')
    page.locator('#news-query').fill(first['title'][:8])
    page.get_by_role('button',name='검색',exact=True).click()
    page.wait_for_load_state('networkidle')
    assert page.locator('.news-item h3 a').count()>0
    if page.get_by_role('link',name='다음',exact=True).count():
        page.get_by_role('link',name='다음',exact=True).click()
        page.wait_for_load_state('networkidle')
        assert 'page=2' in page.url
    assert not errors,errors
    browser.close()
report={'source':'actual existing news DB, read-only','public_count':payload['count'],'views':checks,'console_errors':errors,'detail_reload_back_search':'PASS'}
(out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'public_count':payload['count'],'responsive_views':len(checks),'console_errors':len(errors),'flow':'PASS','screenshots':str(out)},ensure_ascii=False))
