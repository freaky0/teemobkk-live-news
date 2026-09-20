"""Keyword multi-select, sideways keyword row, and a release path that works.

The two script regions are replaced by locating their markers rather than retyping their contents:
a stray space or a newline inside a hand-copied anchor makes the whole edit miss.
"""
import ast
import io

P = "C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py"
text = io.open(P, encoding="utf-8").read()
NL = "\n"

RENDER_START = "el.innerHTML='<span class=\"tlabel\">"
RENDER_END = "}).join('');" + NL + "}"
CLICK_START = "document.querySelector('#trend').onclick=ev=>{"
CLICK_END = "q.oninput();" + NL + "};"


def splice(text, start_marker, end_marker, replacement):
    i = text.index(start_marker)
    j = text.index(end_marker, i) + len(end_marker)
    print("  replaced %d chars at %d" % (j - i, i))
    return text[:i] + replacement + text[j:]


RENDER_NEW = '''el.innerHTML='<span class="tlabel">' + "지금 뜨는 키워드" + '</span>'+list.map(function(x){
    const on=V.terms.indexOf(x.t)>=0;
    return '<button type="button" class="tbtn'+(on?' on':'')+'" data-trend="'+esc(x.t)+
    '" aria-pressed="'+(on?'true':'false')+'">'+esc(x.t)+
    '<span class="n">'+x.c+'</span></button>'}).join('')+
    (V.terms.length?'<button type="button" class="tbtn clear on" data-trend-clear="1">선택 '
      +V.terms.length+'개 해제 ✕</button>':''); }'''

CLICK_NEW = '''document.querySelector('#trend').onclick=ev=>{
  if(ev.target.closest('[data-trend-clear]')){
    V.terms=[];V.limit=PAGE;V.offset=0;renderTrends();fetchFeed();return}
  const b=ev.target.closest('[data-trend]');if(!b)return;
  // A keyword is a toggle and several can be on at once. Pressing the same one again releases it,
  // so a reader never has to go back a page to undo a click.
  const term=b.dataset.trend,i=V.terms.indexOf(term);
  if(i>=0)V.terms.splice(i,1);else V.terms.push(term);
  V.q='';const q=document.querySelector('#q');if(q&&q.value)q.value='';
  V.limit=PAGE;V.offset=0;renderTrends();fetchFeed();
};'''

text = splice(text, RENDER_START, RENDER_END, RENDER_NEW)
text = splice(text, CLICK_START, CLICK_END, CLICK_NEW)

pairs = [
    ("var V={tab:CFG.wantThai?'thai':'global',filter:'전체',hours:24,q:'',limit:PAGE,tag:null,mode:'all',value:'',offset:0};",
     "var V={tab:CFG.wantThai?'thai':'global',filter:'전체',hours:24,q:'',terms:[],limit:PAGE,tag:null,mode:'all',value:'',offset:0};"),
    (".trend{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 10px;padding:2px}",
     ".trend{display:flex;gap:8px;align-items:center;flex-wrap:nowrap;overflow-x:auto;margin:0 0 10px;"
     "padding:2px 2px 8px;scrollbar-width:thin}"
     ".trend::-webkit-scrollbar{height:6px}"
     ".trend::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}"
     ".trend .tlabel{position:sticky;left:0;z-index:1;background:var(--bg);padding:2px 8px 2px 0}"
     ".tbtn.on{border-color:var(--accent);color:var(--accent);background:rgba(100,215,221,.12)}"
     ".tbtn.clear{border-style:dashed}"
     "@media (min-width:900px){.trend{flex-wrap:wrap;overflow:visible}.trend .tlabel{position:static}}"),
    ("function buildQuery(){",
     """// The keyword row and the search box are both text filters, so they stay mutually exclusive: a
// reader who picked keywords should not also be filtered by a leftover query, and a reader who
// typed one should not have keywords quietly narrowing the list. Every control that resets the
// filters calls this - that is what makes 전체 release a keyword instead of leaving the list stuck
// until the search box is cleared by hand, which needed going back a page.
function clearText(){
  V.q='';V.terms=[];
  const q=document.querySelector('#q');if(q&&q.value)q.value='';
  if(document.querySelector('#trend'))renderTrends()}

function buildQuery(){"""),
    ("    V.filter=b.dataset.cat;V.tag=null;V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;renderPills();fetchFeed()});",
     "    V.filter=b.dataset.cat;V.tag=null;V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed()});"),
    ("    V.filter='전체';V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;renderPills();fetchFeed()});",
     "    V.filter='전체';V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed()});"),
    ("if(clr)clr.onclick=()=>{V.tag=null;V.limit=PAGE;V.offset=0;renderPills();fetchFeed()};",
     "if(clr)clr.onclick=()=>{V.tag=null;V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed()};"),
    ("V.tab=next;V.filter='전체';V.tag=null;V.limit=PAGE;V.offset=0;V.mode='all';V.value='';",
     "V.tab=next;V.filter='전체';V.tag=null;V.limit=PAGE;V.offset=0;V.mode='all';V.value='';clearText();"),
    ("    V.filter='전체';V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;renderPills();fetchFeed();return}",
     "    V.filter='전체';V.mode='all';V.value='';" + NL +
     "    V.limit=PAGE;V.offset=0;clearText();renderPills();fetchFeed();return}"),
    ("""document.querySelector('#q').oninput=()=>{clearTimeout(window.__qt);
  window.__qt=setTimeout(()=>{V.q=document.querySelector('#q').value.trim();
    V.limit=PAGE;V.offset=0;fetchFeed()},350)};""",
     """document.querySelector('#q').oninput=()=>{clearTimeout(window.__qt);
  window.__qt=setTimeout(()=>{V.q=document.querySelector('#q').value.trim();
    if(V.terms.length){V.terms=[];renderTrends()}
    V.limit=PAGE;V.offset=0;fetchFeed()},350)};"""),
    ("async function loadLocal(){" + NL + "  const r=await fetch(API+'/api/news?'+buildQuery(),{cache:'no-cache'});",
     """// A keyword selection is several searches, because the API takes one q. Each keyword is fetched
// on its own and the results are merged by link, so three keywords cover the whole stored window
// instead of only what one query happened to return. The merged set is kept and paging slices it,
// so 더 보기 does not refetch.
const TERMS={sig:'',list:[],updated:'',ict:'',counts:null};
async function loadTerms(){
  const sig=V.tab+'|'+V.hours+'|'+V.terms.slice().sort().join(',');
  if(TERMS.sig!==sig){
    const pages=await Promise.all(V.terms.map(function(t){
      const p=new URLSearchParams({region:region(),hours:String(V.hours),limit:'300',offset:'0',q:t});
      return fetch(API+'/api/news?'+p.toString(),{cache:'no-cache'})
        .then(function(r){return r.ok?r.json():null}).catch(function(){return null})}));
    const seen={},merged=[];
    pages.forEach(function(d){(d&&d.articles||[]).forEach(function(a){
      const k=String(a.link||'');if(!k||seen[k])return;seen[k]=1;merged.push(a)})});
    merged.sort(function(a,b){return String(b.published_at||'').localeCompare(String(a.published_at||''))});
    TERMS.sig=sig;TERMS.list=merged;
    TERMS.updated=(pages[0]&&pages[0].updated_at)||'';
    TERMS.ict=(pages[0]&&pages[0].updated_at_ict)||'';
    TERMS.counts=(pages[0]&&pages[0].region_counts)||null;
  }
  const all=TERMS.list,shown=all.slice(0,V.limit);
  DATA={articles:shown,total:all.length,has_more:all.length>shown.length,
        updated_at:TERMS.updated,updated_at_ict:TERMS.ict,window_hours:V.hours,
        region_counts:TERMS.counts||{}};
  setStamp((TERMS.ict||'')+' · '+V.hours+'시간 · 키워드 '+V.terms.length+'개 · '+all.length+'건',TERMS.counts);
  flagStale(TERMS.updated);
  renderPills();renderFeed()}

async function loadLocal(){
  if(V.terms.length){await loadTerms();return}
  const r=await fetch(API+'/api/news?'+buildQuery(),{cache:'no-cache'});"""),
]

missing = [old for old, _ in pairs if old not in text]
if missing:
    for old in missing:
        print("  MISS %s" % old[:78].replace(NL, " | "))
    raise SystemExit(1)
for old, new in pairs:
    if text.count(old) != 1:
        print("  anchor x%d: %s" % (text.count(old), old[:60]))
        raise SystemExit(1)
    text = text.replace(old, new, 1)

io.open(P, "w", encoding="utf-8", newline="").write(text)
ast.parse(io.open(P, encoding="utf-8").read())
print("  page_build.py updated, ast OK")
