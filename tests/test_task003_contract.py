import datetime
import os
import subprocess
import unittest
import xml.etree.ElementTree as ET

import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from pages.build import page_build

class Task003Contract(unittest.TestCase):
    def test_sitemap_lists_thirteen_pages_with_build_day_lastmod(self):
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
            "https://teemobkk.io/thai/news/",
            "https://teemobkk.io/thai/news/ko/",
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
        # resolve jsdom like tests/run.py does: tests/browser/node_modules first,
        # then the legacy scratch location
        here = os.path.dirname(os.path.abspath(__file__))
        cands = [os.path.join(here, "browser", "node_modules"),
                 "/opt/data/cache/scratch/jsdom-mailbox/node_modules"]
        env["NODE_PATH"] = os.pathsep.join(c for c in cands if os.path.isdir(c))
        result = subprocess.run(["node", "-e", node_script], input=page, text=True,
                                capture_output=True, env=env, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_korean_dashboard_has_korean_date_words_and_no_english_filter(self):
        page = page_build.render(public=False, datadir="", want_thai=False,
                                 icon_prefix="/", admin=False, lang="ko")
        self.assertIn('get(\'month\')+CFG.monthSuffix+\' \'+get(\'day\')+\'일 \'+get(\'hour\')', page)
        self.assertNotIn('id="language-filter"', page)

class Task018CanonicalThaiEntry(unittest.TestCase):
    """018: Thai news and economic news are fully separated.

    The economic dashboard carries no Thai tab at all; the Thai dashboard
    links back to the global dashboard with a plain canonical link.
    """

    def _render(self, want_thai, lang):
        return page_build.render(public=True, datadir="", want_thai=want_thai,
                                 icon_prefix="/", admin=False, lang=lang,
                                 seed_html="", briefing_html="", briefing_source="")

    def test_global_dashboard_has_no_thai_tab(self):
        for lang in ("ko", "en"):
            page = self._render(False, lang)
            self.assertNotIn('id="tab-thai"', page)

    def test_thai_dashboard_global_tab_links_back_to_global_dashboard(self):
        ko = self._render(True, "ko")
        self.assertIn('<a id="tab-global" class="tab" href="/news/ko/">경제 소식</a>', ko)
        en = self._render(True, "en")
        self.assertIn('<a id="tab-global" class="tab" href="/news/">Markets</a>', en)

    def test_canonical_tab_links_carry_no_data_tab(self):
        # the canonical links carry no data-tab, so the tab click wiring skips them
        for want_thai, lang in ((True, "ko"), (True, "en")):
            page = self._render(want_thai, lang)
            before, _, after = page.partition('id="tab-global"')
            self.assertTrue(before.rstrip().endswith("<a"), "tab-global")
            self.assertNotIn("data-tab", after.split(">", 1)[0])

if __name__ == "__main__":
    unittest.main()
