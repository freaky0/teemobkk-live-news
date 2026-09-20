"""Keyword row: a label that cannot overlap, a selection you can actually see, and categories that
multi-select alongside keywords.

Three measured faults drove this:

1. The label was sticky inside the horizontal scroller, and it was 23px tall against 32px buttons,
   so buttons passed visibly above and below it - they appeared to overlap the label.
2. `.trend .tbtn{background:none}` sits after `.tbtn.on` at equal specificity, so the selected fill
   was flattened to transparent; the selected border-colour only showed while the pointer hovered,
   because the hover rule is what the eye was catching. Touch devices made it worse: :hover sticks
   after a tap, so an unselected button could look selected.
3. The keyword request never carried the selected category, so picking 거시경제 and then 트럼프
   silently dropped 거시경제. Categories were single-select, so they could not be combined either.
"""
import ast
import io

P = "C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py"
text = io.open(P, encoding="utf-8").read()
NL = "\n"


def splice(text, start_marker, end_marker, replacement, label):
    i = text.index(start_marker)
    j = text.index(end_marker, i) + len(end_marker)
    print("  %-22s replaced %d chars" % (label, j - i))
    return text[:i] + replacement + text[j:]


# ── 1. the row's CSS ────────────────────────────────────────────────────────────────────────────
CSS_NEW = """\
.trend{display:flex;gap:0;align-items:stretch;flex-wrap:nowrap;overflow:visible;margin:0 0 10px;padding:0}
.trend .tlabel{flex:0 0 auto;display:flex;align-items:center;padding:2px 10px 8px 2px;
  border-right:1px solid var(--line);margin-right:10px}
.trend .ttrack{flex:1 1 auto;min-width:0;display:flex;gap:8px;overflow-x:auto;padding:2px 2px 8px}
.trend .ttrack::-webkit-scrollbar{height:6px}
.trend .ttrack::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}
@media (hover:hover){.trend .tbtn:hover{border-color:var(--accent);color:var(--accent)}}
.trend .tbtn.on{border-color:var(--accent);background:var(--accent);color:#08111f;font-weight:600}
.trend .tbtn.on .n{color:#08111f;opacity:.65}
.trend .tbtn.clear{border-style:dashed;border-color:var(--warn);color:var(--warn);font-weight:600}
@media (min-width:900px){.trend .ttrack{flex-wrap:wrap;overflow-x:visible}}
"""

text = splice(text, ".trend{display:flex", ".trend[hidden]", CSS_NEW + ".trend[hidden]", "CSS 줄")
# the old hover rule would still apply on touch devices, where :hover sticks after a tap
old_hover = ".trend .tbtn:hover{border-color:var(--accent);color:var(--accent)}"
assert old_hover in text, "original hover rule missing"
text = text.replace(old_hover, "", 1)

# ── 2. the row markup: label outside the scroller, a tick on the selected ones ──────────────────
RENDER_NEW = '''el.innerHTML='<span class="tlabel">' + "지금 뜨는 키워드" + '</span><span class="ttrack">'+
    list.map(function(x){
      const on=V.terms.indexOf(x.t)>=0;
      return '<button type="button" class="tbtn'+(on?' on':'')+'" data-trend="'+esc(x.t)+
      '" aria-pressed="'+(on?'true':'false')+'">'+(on?'\\u2713 ':'')+esc(x.t)+
      '<span class="n">'+x.c+'</span></button>'}).join('')+
    (V.terms.length?'<button type="button" class="tbtn clear" data-trend-clear="1">'
      +V.terms.length+'개 해제 \\u2715</button>':'')+'</span>'; }'''

text = splice(text, "el.innerHTML='<span class=\"tlabel\">", "</button>':''); }", RENDER_NEW, "키워드 줄 마크업")

# ── 3. clicking a keyword: a toggle that keeps the categories ───────────────────────────────────
CLICK_NEW = '''document.querySelector('#trend').onclick=ev=>{
  if(ev.target.closest('[data-trend-clear]')){
    V.terms=[];V.limit=PAGE;V.offset=0;renderTrends();fetchFeed();return}
  const b=ev.target.closest('[data-trend]');if(!b)return;
  // A keyword is a toggle and several can be on at once. Pressing the same one again releases it,
  // so a reader never has to go back a page to undo a click. Categories are left alone: 트럼프 and
  // 거시경제 are two axes and are asked for together.
  const term=b.dataset.trend,i=V.terms.indexOf(term);
  if(i>=0)V.terms.splice(i,1);else V.terms.push(term);
  const q=document.querySelector('#q');if(q&&q.value)q.value='';V.q='';
  V.limit=PAGE;V.offset=0;renderTrends();fetchFeed();
};'''

text = splice(text, "document.querySelector('#trend').onclick=ev=>{", "renderTrends();fetchFeed();" + NL + "};",
              CLICK_NEW, "키워드 클릭")

# ── 4. one loader for any combination of categories and keywords ────────────────────────────────
LOAD_NEW = '''// Categories and keywords are two axes and both multi-select, so a request is one (category,
// keyword) pair per combination - the API takes a single value for each. The pair results are
// merged by link, which is exactly "one of the chosen categories and one of the chosen keywords".
// Two categories alone still work: that is one request per category over the same window. The
// merged set is kept and paging slices it, so 더 보기 never refetches.
const COMBO={sig:'',list:[],updated:'',ict:'',counts:null,label:''};
async function loadCombo(){
  const cats=V.cats.length?V.cats:[''], terms=V.terms.length?V.terms:[''];
  const sig=V.tab+'|'+V.hours+'|'+cats.slice().sort().join(',')+'|'+terms.slice().sort().join(',');
  if(COMBO.sig!==sig){
    const pairs=[];cats.forEach(function(c){terms.forEach(function(t2){pairs.push([c,t2])})});
    const pages=await Promise.all(pairs.map(function(pr){
      const p=new URLSearchParams({region:region(),hours:String(V.hours),limit:'300',offset:'0'});
      if(pr[0])p.set('category',pr[0]);
      if(pr[1])p.set('q',pr[1]);
      return fetch(API+'/api/news?'+p.toString(),{cache:'no-cache'})
        .then(function(r){return r.ok?r.json():null}).catch(function(){return null})}));
    const seen={},merged=[];
    pages.forEach(function(d){(d&&d.articles||[]).forEach(function(a){
      const k=String(a.link||'');if(!k||seen[k])return;seen[k]=1;merged.push(a)})});
    merged.sort(function(a,b){return String(b.published_at||'').localeCompare(String(a.published_at||''))});
    COMBO.sig=sig;COMBO.list=merged;
    COMBO.updated=(pages[0]&&pages[0].updated_at)||'';
    COMBO.ict=(pages[0]&&pages[0].updated_at_ict)||'';
    COMBO.counts=(pages[0]&&pages[0].region_counts)||null;
    COMBO.label=cats.filter(Boolean).join(" \\u00b7 ")+(terms.filter(Boolean).length
      ?(cats.filter(Boolean).length?" + ":"")+"\\uD0a4\\uC6CC\\uB4DC "+terms.filter(Boolean).length+"\\uAC1C":"");
  }
  const all=COMBO.list,shown=all.slice(0,V.limit);
  DATA={articles:shown,total:all.length,has_more:all.length>shown.length,
        updated_at:COMBO.updated,updated_at_ict:COMBO.ict,window_hours:V.hours,
        region_counts:COMBO.counts||{}};
  setStamp((COMBO.ict||'')+' \\u00b7 '+V.hours+'\\uC2DC\\uAC04 \\u00b7 '+COMBO.label+' \\u00b7 '+all.length+'\\uAC74',COMBO.counts);
  flagStale(COMBO.updated);
  renderPills();renderFeed()}

'''

text = splice(text, "// A keyword selection is several searches", "renderPills();renderFeed()}" + NL + NL + "async function loadLocal(){", LOAD_NEW + "async function loadLocal(){", "통합 로더")
text = text.replace("  if(V.terms.length){await loadTerms();return}",
                    "  if(V.cats.length||V.terms.length){await loadCombo();return}", 1)

# ── 5. categories become a list, and the three axes stop fighting ───────────────────────────────
pairs = [
    # state
    ("filter:'전체',hours:24,q:'',terms:[]", "cats:[],hours:24,q:'',terms:[]"),
    # what the list shows
    ("  if(V.filter!=='전체'&&a.category!==V.filter)return false;",
     "    if(V.cats.length&&V.cats.indexOf(a.category)<0)return false;"),
    # which pills are marked
    ("function renderPills(){" + NL + "  const th=V.tab==='thai';",
     "function catOn(v){return v==='전체'?!V.cats.length:V.cats.indexOf(v)>=0}" + NL +
     "function renderPills(){" + NL + "  const th=V.tab==='thai';"),
    ("(pair[0]===V.filter?' active':'')", "(catOn(pair[0])?' active':'')"),
    # clicking a category: toggle, keep the keywords, and let 전체 clear everything
    ("    V.filter=b.dataset.cat;V.tag=null;V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed()});",
     "    const v=b.dataset.cat;" + NL +
     "    // 전체 is the one control that clears the lot and shows the whole list; a single category" + NL +
     "    // toggles and composes with the keyword row." + NL +
     "    if(v==='전체'){V.cats=[];clearText()}" + NL +
     "    else{const i=V.cats.indexOf(v);if(i>=0)V.cats.splice(i,1);else V.cats.push(v)}" + NL +
     "    V.tag=null;V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;renderPills();fetchFeed()});"),
    # a source pill is the other axis, so it still clears the categories
    ("    V.filter='전체';V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed()});",
     "    V.cats=[];V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed()});"),
    # a card chip is the other axis as well; the source-pill reset above has the same text, so the
    # following line tells them apart
    ("    V.filter='전체';V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed();return}",
     "    V.cats=[];V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed();return}"),
    # switching tabs starts clean
    ("V.tab=next;V.filter='전체';", "V.tab=next;V.cats=[];"),
    # buildQuery still sends the single-category form when only one is chosen
    ("  // V.filter is only ever a category name or '전체'. The category pill row sets it without",
     "  // V.cats is empty or a list of category names."),
    ("if(V.filter&&V.filter!=='전체')p.set('category',V.filter);",
     "if(V.cats.length)p.set('category',V.cats[0]);"),
    # the deep link from the section landing page
    ("if(wantFilter&&wantFilter!=='전체'){V.filter=wantFilter;",
     "if(wantFilter&&wantFilter!=='전체'){V.cats=[wantFilter];"),
]

missing = [o for o, _ in pairs if o not in text]
if missing:
    for o in missing:
        print("  MISS %s" % o[:80].replace(NL, " | "))
    raise SystemExit(1)
for old, new in pairs:
    if text.count(old) != 1:
        print("  anchor x%d: %s" % (text.count(old), old[:70].replace(NL, " | ")))
        raise SystemExit(1)
    text = text.replace(old, new, 1)

if "V.filter" in text:
    for line in text.split(NL):
        if "V.filter" in line:
            print("  남은 V.filter: %s" % line.strip()[:90])
    raise SystemExit(1)

io.open(P, "w", encoding="utf-8", newline="").write(text)
src = io.open(P, encoding="utf-8").read()
ast.parse(src)
bad = [c for c in src if 0x1100 <= ord(c) <= 0x11FF or 0xFFFD == ord(c)]
print("  ast OK · 깨진 자모/치환문자 %d" % len(bad))
