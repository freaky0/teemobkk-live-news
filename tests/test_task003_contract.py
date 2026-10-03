import datetime
import os
import subprocess
import unittest
import xml.etree.ElementTree as ET

import page_build


class Task003Contract(unittest.TestCase):
    def test_sitemap_lists_eleven_pages_with_build_day_lastmod(self):
        fixed = datetime.datetime(2026, 10, 3, 6, 11, 0,
                                  tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
        xml_text = page_build.sitemap_xml(fixed)
        root = ET.fromstring(xml_text)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        entries = root.findall("sm:url", namespace)
        locations = {entry.findtext("sm:loc", namespaces=namespace) for entry in entries}
        expected = {
            "https://teemobkk.io/",
            "https://teemobkk.io/about/",
            "https://teemobkk.io/tradingtalk/",
            "https://teemobkk.io/lab/",
            "https://teemobkk.io/thai/",
            "https://teemobkk.io/privacy/",
            "https://teemobkk.io/privacy/en/",
            "https://teemobkk.io/news/",
            "https://teemobkk.io/news/ko/",
            "https://teemobkk.io/perspectives/",
            "https://teemobkk.io/indicators/",
        }
        self.assertEqual(locations, expected)
        expected_lastmod = fixed.isoformat(timespec="seconds")
        self.assertTrue(all(entry.findtext("sm:lastmod", namespaces=namespace) == expected_lastmod
                            for entry in entries))
        dynamic = ET.fromstring(page_build.sitemap_xml())
        ict = datetime.timezone(datetime.timedelta(hours=7))
        today = datetime.datetime.now(ict).date()
        timestamps = [datetime.datetime.fromisoformat(entry.findtext("sm:lastmod", namespaces=namespace) or "")
                      for entry in dynamic.findall("sm:url", namespace)]
        self.assertTrue(all(stamp.date() == today and stamp.utcoffset() == datetime.timedelta(hours=7)
                            for stamp in timestamps))

    def test_english_dashboard_has_default_english_language_filter_and_badge_logic(self):
        page = page_build.render(public=False, datadir="", want_thai=False,
                                 icon_prefix="/", admin=False, lang="en")
        self.assertIn('id="language-filter"', page)
        self.assertIn('value="en" selected', page)
        self.assertIn("function articleLang(a)", page)
        self.assertIn("get('month')+' '+get('day')+', '+get('hour')+':'+get('minute')+' ICT'", page)

    def test_english_filter_hides_non_english_articles_until_all_languages_is_selected(self):
        page = page_build.render(public=False, datadir="", want_thai=False,
                                 icon_prefix="/", admin=False, lang="en")
        node_script = r'''const { JSDOM } = require("jsdom");
const rows = [
 {id:1,title:"English story",lang:"en",source:"Source A",published_at:"2026-10-03T01:00:00Z",categories:[]},
 {id:2,title:"한국 뉴스",lang:"ko",source:"Source B",published_at:"2026-10-03T01:00:00Z",categories:[]},
 {id:3,title:"ข่าวไทย",lang:"th",source:"Source C",published_at:"2026-10-03T01:00:00Z",categories:[]}
];
const payload = {articles:rows,total:3,has_more:false,updated_at:"2026-10-03T01:00:00Z",region_counts:{}};
const dom = new JSDOM(require("fs").readFileSync(0,"utf8"), {url:"https://teemobkk.io/news/",runScripts:"dangerously",
 beforeParse(w){ w.fetch=async()=>({ok:true,json:async()=>payload}); w.scrollTo=()=>{}; }});
setTimeout(()=>{
 const d=dom.window.document, filter=d.getElementById("language-filter");
 const visible=()=>[...d.querySelectorAll(".chip.lang")].map(x=>x.textContent.trim());
 const initial=visible();
 filter.value="all"; filter.dispatchEvent(new dom.window.Event("change",{bubbles:true}));
 setTimeout(()=>{
  const all=visible(); dom.window.close();
  if(initial.join(",")!=="EN") throw Error("default filter leaked languages: "+initial);
  if(all.length!==3 || !["EN","KO","TH"].every(x=>all.includes(x))) throw Error("all-languages mode badges incorrect: "+all);
 },0);
},25);'''
        env = os.environ.copy()
        env["NODE_PATH"] = "/opt/data/cache/scratch/jsdom-mailbox/node_modules"
        result = subprocess.run(["node", "-e", node_script], input=page, text=True,
                                capture_output=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_korean_dashboard_has_korean_date_words_and_no_english_filter(self):
        page = page_build.render(public=False, datadir="", want_thai=False,
                                 icon_prefix="/", admin=False, lang="ko")
        self.assertIn('get(\'month\')+CFG.monthSuffix+\' \'+get(\'day\')+\'일 \'+get(\'hour\')', page)
        self.assertNotIn('id="language-filter"', page)


if __name__ == "__main__":
    unittest.main()
