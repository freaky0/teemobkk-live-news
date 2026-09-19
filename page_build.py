"""Build every dashboard page from one source.

Three files are published and they must never drift apart:

    index.html            local, served by the collector on 127.0.0.1:8765 (admin extras)
    docs/index.html       public, GitHub Pages root
    docs/thai/index.html  public, same page one level deeper so /thai/ opens the Thailand tab

Before this module existed the three were edited by hand and a CSS class rename once
landed on only some of them, so colours silently stopped matching. Now the markup,
the stylesheet and the script live here once, and each target only differs in a small
config block.

Two data paths are supported and selected by `public`:

    public  static JSON on GitHub Pages. The page filters in the browser, groups the
            feed into time sections, and only downloads a regional file when the tiny
            index.json says that region actually changed.
    local   the collector's own /api/news endpoint, which filters and pages on the
            server, plus the admin panel (source health, poll interval, archive size).
"""
from __future__ import annotations

import datetime
import html
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"

CSS = """\
:root{
  --bg:#0a0e1a; --panel:#111a2c; --panel2:#16213a; --text:#eef3ff; --muted:#8b9bbd;
  --line:#243252; --line2:#2e3d61; --accent:#64d7ff; --thai:#ffd479; --hot:#ffb86b;
  --official:#8fe3a8; --warn:#ff9a3c; --r-card:14px; --r-ctl:10px; --r-pill:999px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
a{color:inherit;text-decoration:none}
button,input,select{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap;border:0}
.wrap{max-width:1180px;margin:0 auto;padding:26px 22px 40px}
.bar{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--line);
  background:rgba(10,14,26,.92);backdrop-filter:blur(10px)}
.bar-in{max-width:1180px;margin:0 auto;padding:14px 22px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-size:11px;color:var(--accent)}
h1{font-size:19px;margin:0;letter-spacing:-.01em}
.spacer{flex:1}
.stamp{color:var(--muted);font-size:12px;text-align:right;line-height:1.5}
.stamp b{color:var(--text);font-weight:600}
.stale{display:none;margin-top:5px;border:1px solid var(--warn);color:var(--warn);
  border-radius:var(--r-pill);padding:3px 10px;font-size:11.5px}
.stale[data-show="1"]{display:inline-block}
.tabs{display:flex;gap:6px;margin:22px 0 12px;border-bottom:1px solid var(--line)}
.tab{background:none;border:0;border-bottom:2px solid transparent;padding:11px 16px;cursor:pointer;
  color:var(--muted);font-weight:600;font-size:17px;letter-spacing:-.01em;margin-bottom:-1px}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.tab.th.active{color:var(--thai);border-bottom-color:var(--thai)}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
input[type=search],select{background:var(--panel2);border:1px solid var(--line);border-radius:var(--r-ctl);padding:9px 12px;min-width:0}
input[type=search]{flex:1 1 220px}
input[type=search]::placeholder{color:var(--muted)}
select{cursor:pointer}
.count{color:var(--muted);font-size:12px;margin-left:auto}
.newpill{display:none;align-items:center;background:#123047;border:1px solid var(--accent);color:var(--accent);
  border-radius:var(--r-pill);padding:7px 14px;cursor:pointer;font-size:12.5px;font-weight:600}
.newpill[data-show="1"]{display:inline-flex}
.pills{display:flex;gap:8px;overflow-x:auto;padding:2px 2px 8px;margin-bottom:6px}
.pills::-webkit-scrollbar{height:6px}
.pills::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}
@media (min-width:900px){.pills{flex-wrap:wrap;overflow-x:visible}}
.pills[hidden]{display:none!important}
.trend{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 10px;padding:2px}
.trend[hidden]{display:none!important}
.trend .tlabel{color:var(--muted);font-size:12px;white-space:nowrap}
.trend .n{color:var(--muted);font-size:11px;margin-left:6px}
/* Own class rather than the filter chips' ".chip.tap": those are toggles carrying
   aria-pressed, while a trend button is a one-shot search action. Reusing the class
   made every ".chip.tap" invariant assertion count a chip that is not a toggle. */
.trend .tbtn{border:1px solid var(--line);border-radius:var(--r-pill);padding:5px 11px;
  background:none;font-family:inherit;font-size:12.5px;color:var(--text);cursor:pointer;white-space:nowrap}
.trend .tbtn:hover{border-color:var(--accent);color:var(--accent)}
.pill{flex:0 0 auto;background:none;border:1px solid var(--line);border-radius:var(--r-pill);
  padding:7px 14px;cursor:pointer;font-size:12.5px;color:var(--muted);white-space:nowrap}
.pill.active{background:var(--panel2);border-color:var(--accent);color:var(--accent)}
.pill.th.active{border-color:var(--thai);color:var(--thai)}
.pill.on{border-color:var(--accent);color:var(--accent)}
/* Source chips sit in the same row as the category pills but are a different axis, so they
   are dashed and separated. */
.pill.src{border-style:dashed}
.pill.src.th.active{border-color:var(--thai);color:var(--thai)}
.pillsep{flex:0 0 auto;width:1px;margin:0 3px;background:var(--line2);align-self:stretch}
.pill i{font-style:normal;opacity:.6;margin-left:5px;font-size:11.5px}
.sec{display:flex;align-items:center;gap:10px;margin:18px 0 8px;color:var(--muted);font-size:12px;font-weight:600}
.sec::after{content:"";flex:1;height:1px;background:var(--line)}
.feed{display:grid;grid-template-columns:1fr;gap:12px;margin-top:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-card);padding:16px;
  border-left:3px solid var(--accent)}
.card.th{border-left-color:var(--thai)}
.card.new{border-left-color:var(--hot);box-shadow:0 0 0 1px rgba(255,184,107,.22)}
.meta{display:flex;gap:8px;flex-wrap:wrap;align-items:center;color:var(--muted);font-size:12px;margin-bottom:9px}
.chip{border:1px solid var(--line);border-radius:var(--r-pill);padding:5px 11px;white-space:nowrap;
  background:none;font-size:12px;font-family:inherit}
.chip.src{background:var(--panel);color:var(--text)}
.chip.official{border-color:var(--official);color:var(--official)}
.chip.hot{border-color:var(--hot);color:var(--hot)}
.chip.th{border-color:#5a4a24;color:var(--thai)}
.chip.speak{border-color:#ffb86b;color:#ffb86b}
.chip.verif{border-color:var(--line2);color:var(--muted);letter-spacing:.02em}
.chip.verif.off{border-color:var(--official);color:var(--official)}
.chip.verif.sns{border-color:#b48cff;color:#c7a8ff}
.chip.static{cursor:default}
.chip.tap{cursor:pointer}
.chip.tap:hover,.chip.tap.on{border-color:var(--accent);color:var(--accent)}
.title{font-size:17px;line-height:1.45;letter-spacing:-.01em;font-weight:600;margin:0 0 7px}
.title a:hover{color:var(--accent)}
.title a::after{content:"";position:absolute;inset:0}
.card{position:relative}
.chip.tap,.expand,.cal-n a{position:relative;z-index:1}
.summary{color:#c3cfe6;font-size:14px;max-width:65ch;margin:0 0 8px}
.summary.clamp{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.expand{background:none;border:0;padding:0 0 6px;color:var(--accent);font-size:12.5px;cursor:pointer;font-weight:600}
.card.th .expand{color:var(--thai)}
.open{color:var(--muted);font-size:12.5px;border-bottom:1px solid var(--line)}
.open:hover{color:var(--accent);border-bottom-color:var(--accent)}
mark{background:#3f3418;color:#ffe9b0;border-radius:3px;padding:0 2px}
.skel{border:1px solid var(--line);border-radius:var(--r-card);padding:16px;background:var(--panel)}
.skel span{display:block;height:12px;border-radius:6px;background:linear-gradient(90deg,#18233b,#22304f,#18233b);
  background-size:200% 100%;animation:sh 1.4s linear infinite;margin-bottom:10px}
.skel span:nth-child(1){width:35%}
.skel span:nth-child(2){width:90%}
.skel span:nth-child(3){width:70%}
@keyframes sh{0%{background-position:200% 0}100%{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){.skel span{animation:none}}
.empty{border:1px dashed var(--line);border-radius:var(--r-card);padding:44px 18px;text-align:center;color:var(--muted)}
.empty b{display:block;color:var(--text);margin-bottom:6px;font-size:15px}
.layout{display:grid;grid-template-columns:minmax(0,1fr);gap:18px}
.side{display:grid;gap:12px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:var(--r-card);padding:14px}
.box h2{font-size:12.5px;margin:0 0 9px;color:var(--muted);font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.box p{margin:0 0 8px}
.source{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;padding:4px 0;border-bottom:1px solid var(--line)}
.source:last-child{border-bottom:0}
.source .ok{color:var(--official)}
.source .bad{color:var(--hot)}
.note{color:var(--muted);font-size:12px}
.more-wrap{display:flex;justify-content:center;gap:10px;padding:20px 0 6px}
#more,#totop{padding:11px 28px;font-weight:700;background:var(--panel2);border:1px solid var(--line);
  border-radius:var(--r-ctl);cursor:pointer}
#more:hover,#totop:hover{border-color:var(--accent);color:var(--accent)}
.cal{display:none;margin:0 0 14px;padding:14px 16px;border:1px solid var(--line);border-radius:var(--r-card);background:var(--panel)}
.cal h2{margin:0 0 4px;font-size:12.5px;color:var(--muted);font-weight:600}
.cal-sum{color:var(--muted);font-size:11.5px;margin:0 0 12px}
.cal-grid{display:grid;grid-template-columns:1fr;gap:2px 22px}
.cal-day h3{margin:0 0 6px;font-size:13px}
.cal-row{display:grid;grid-template-columns:68px 26px 1fr auto;gap:8px;align-items:baseline;
  padding:4px 0 4px 8px;border-bottom:1px solid var(--line);border-left:2px solid transparent;font-size:13px}
.cal-row.i5{border-left-color:#e04242}
.cal-row.i4{border-left-color:#ff7a45}
.cal-t{font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}
.cal-s{font-size:10.5px;color:var(--hot)}
.cal-n{color:#c3cfe6}
.cal-v{color:var(--muted);font-size:12px}
.cal-v b.up{color:#5fd08a}
.cal-v b.down{color:#ff6b6b}
.cal-v b.flat{color:#ffd479}
.cal-v b{color:var(--official)}
.cal-s.i3{color:#e04242}
.cal-s.i2{color:#ff9a3c}
.cal-s.i1{color:#ffd479}
.cal-row.speech .cal-t{color:#8ea3c4}
.cal-row.earnings .cal-t{color:#e1ceb6}
.cal-row.potus .cal-t,.cal-row.potus .cal-n a{color:#ffb86b}
.cal-n a{color:inherit;text-decoration:none}
.cal-n a:hover{text-decoration:underline}
.cal-err{border:1px dashed var(--line);border-radius:var(--r-ctl);padding:14px;color:var(--muted);font-size:12.5px}
.cal-err button{margin-left:10px;background:var(--panel2);border:1px solid var(--line);
  border-radius:var(--r-ctl);padding:6px 14px;cursor:pointer}
@media (max-width:900px){.cal-row{grid-template-columns:68px 26px 1fr}.cal-row .cal-v{grid-column:1 / -1;padding-left:0}}
body.tab-cal .cal{display:block}
body.tab-cal .toolbar,body.tab-cal .pills,body.tab-cal .trend,body.tab-cal #feed,body.tab-cal .more-wrap,body.tab-cal .side{display:none!important}
body.tab-cal .layout{grid-template-columns:minmax(0,1fr)}
.foot{color:var(--muted);font-size:12px;border-top:1px solid var(--line);margin-top:26px;padding-top:16px;line-height:1.8}
body.public .admin{display:none!important}
body.public .side{display:none}
body.public .layout{grid-template-columns:minmax(0,1fr)}
/* The stretched title link (whole card clickable) is for readers. The local instance is
   a working copy: text has to stay selectable so a headline can be dragged out, so the
   overlay is switched off there and a plain 원문 열기 link is shown instead. */
body.local .title a::after{content:none}
body.local .card{cursor:auto}
@media (max-width:1000px){.layout{grid-template-columns:minmax(0,1fr)}.side{grid-template-columns:1fr}}
@media (min-width:1080px){.feed{grid-template-columns:1fr 1fr}.card.lead{grid-column:1 / -1}}
@media (max-width:820px){
  .wrap{padding:16px 14px 32px}
  .bar-in{padding:12px 14px}
  h1{font-size:17px}
  .stamp{text-align:left;font-size:11.5px}
  .lead .title{font-size:20px}
  .count{margin-left:0;width:100%}
  /* Three tab labels at the desktop size overflow a phone; step down and allow a scroll
     rather than letting the row break. */
  .tabs{overflow-x:auto}
  .tab{padding:10px 12px;font-size:16px}
}
"""

SCRIPT = """\
const CFG=__CONFIG__;
const PUBLIC=CFG.public, DATADIR=CFG.datadir, API=CFG.api;
const PAGE=25, BIG=25, STALE_MIN=35, GRACE_MS=3*3600000;
const GLOBAL_CATS=['유동성·금리','미국 정책·트럼프','지정학','ETF·수급','파생상품·청산','온체인·기관','스테이블코인','X 발언','주식·원자재','채굴','규제·정책','거시경제','시장·가격','이더리움·알트'];
const THAI_CATS=[['비자·이민','비자·이민'],['사고·재난','사고·재난'],['태국 생활','생활·교통·날씨'],['태국 경제','태국 경제'],['태국 정치·사회','정치·사회'],['태국 관광','관광'],['태국 보건','보건']];
// Source chips. The list is data, not preference: the server matches the source column exactly
// (source = ?), so each string has to be one that actually appears in the feed. Same-source
// feeds are listed separately when the collector names them differently (CoinNess / CoinNess
// Stock, Bangkok Post / Bangkok Post Business).
const GLOBAL_SRC=['Whale Alert','Walter Bloomberg','FinancialJuice','SBHNews','CoinNess','CoinNess Stock'];
const THAI_SRC=['Matichon','Thairath','Bangkok Post','Bangkok Post Business'];
const CAL_URL=CFG.calendar;
const CACHE_KEY='teemo-live-news-cache-v4';

const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const shown=(s,label)=>{const t=String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  return '실제 <b class="'+label+'">'+t+'</b>'};

var V={tab:CFG.wantThai?'thai':'global',filter:'전체',hours:24,q:'',limit:PAGE,tag:null,mode:'all',value:'',offset:0};
var MEM={},LATEST={},PENDING={},INDEX={},SEEN={},FULL={},DATA={articles:[],sources:{},total:0,has_more:false};
var archiveTotal=0,refreshTimer=null,hidden=false,lastRegion={};
if(CFG.wantThai)document.title=document.title.replace('Live News','Live News · 태국 소식');
try{const s=localStorage.getItem(CACHE_KEY);if(s){const p=JSON.parse(s);if(p&&p.articles)DATA=p}}catch(e){}

function region(){return V.tab==='thai'?'태국':'글로벌'}
function articles(){return PUBLIC?(MEM[region()]||[]):(DATA.articles||[])}
function age(iso){if(!iso)return '시각 미상';const d=new Date(iso);if(isNaN(d))return '시각 미상';
  const sec=Math.max(0,(Date.now()-d.getTime())/1000);
  if(sec<60)return Math.floor(sec)+'초 전';if(sec<3600)return Math.floor(sec/60)+'분 전';
  if(sec<86400)return Math.floor(sec/3600)+'시간 전';
  return d.toLocaleString('ko-KR',{timeZone:'Asia/Bangkok',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})+' ICT'}
function bangkokDay(iso){const d=new Date(iso);if(isNaN(d))return '';
  return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Bangkok'}).format(d)}
function bucket(iso){const t=new Date(iso).getTime();if(!isFinite(t))return '이전';
  const h=(Date.now()-t)/3600000;if(h<1)return '최근 1시간';
  const day=bangkokDay(iso),today=bangkokDay(new Date().toISOString());
  if(day===today)return '오늘';
  const y=new Date(Date.now()-86400000).toISOString();
  if(day===bangkokDay(y))return '어제';
  return '이전'}
function hl(t){const txt=esc(t);const q=(V.q||'').trim();if(!q)return txt;
  const qe=esc(q).replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&');
  try{return txt.replace(new RegExp('('+qe+')','gi'),'<mark>$1</mark>')}catch(e){return txt}}
function keep(a){
  const hours=Number(V.hours)||24,t=new Date(a.published_at).getTime();
  if(!isFinite(t)||Date.now()-t>hours*3600000)return false;
  if(V.filter!=='전체'&&a.category!==V.filter)return false;
  if(V.tag&&(V.tag.k==='cat'?a.category!==V.tag.v:a.source!==V.tag.v))return false;
  const q=(V.q||'').trim().toLowerCase();
  if(q&&(((a.title||'')+' '+(a.summary||'')+' '+(a.source||'')+' '+(a.category||'')).toLowerCase().indexOf(q)<0))return false;
  return true}
function visible(){return PUBLIC?articles().filter(keep):articles()}
function stars(a){const n=Number(a.priority)||0;
  return n>=4?'<button type="button" class="chip hot static" tabindex="-1" aria-hidden="true">'+String.fromCharCode(9733).repeat(Math.min(5,n))+'</button>':''}
function summaryBlock(a){
  const s=a.summary||'';if(!s)return '';
  const long=s.length>220;
  return '<div class="summary'+(long?' clamp':'')+'">'+hl(s)+'</div>'+
    (long?'<button class="expand" type="button" aria-expanded="false">펼쳐보기</button>':'')}
const SPEAKERS=['트럼프','Trump','TRUMP','머스크','Musk','MUSK','파월','Powell','워시','Warsh','베센트','Bessent','라가르드','Lagarde','푸틴','Putin','시진핑','Xi Jinping','네타냐후','Netanyahu','우에다','Ueda'];
function speakChip(a){const t=(a.title||'')+' '+(a.summary||'');
  return SPEAKERS.some(n=>t.indexOf(n)>=0)?'<span class="chip speak">인물 발언</span>':''}
// Verification level, not a second source name. The source chip already says who
// published it, so only the levels that change how much a line should be trusted are
// shown, and they are meant to be rare: measured over a day, official is 0.5% and
// social is 10.6%, while breaking (37%) and aggregated (41%) are ordinary media
// volume - labelling those would put a badge on four cards out of five and mean
// nothing. A "[카더라]" style label is not derived here: that is an editor's
// annotation on the other site, and this collector sees zero such markers in the
// wire text it receives.
function verifChip(a){
  if(a.source_type==='official')return '<span class="chip verif off" title="공식 기관이 직접 발표한 문서">공식</span>';
  if(a.source_type==='social')return '<span class="chip verif sns" title="소셜·채널 게시물 — 언론 보도가 아니며 원문 확인이 필요함">SNS</span>';
  return ''}
function card(a,th,lead){
  const tag=V.tag||{};
  const srcOn=tag.k==='src'&&tag.v===a.source,catOn=tag.k==='cat'&&tag.v===a.category;
  const srcCls='chip src tap'+(a.source_type==='official'?' official':'')+(th?' th':'')+(srcOn?' on':'');
  const catCls='chip tap'+(catOn?' on':'');
  return '<article class="card'+(th?' th':'')+(a.fresh?' new':'')+'">'+
    '<div class="meta">'+
      verifChip(a)+
      '<button type="button" class="'+srcCls+'" data-k="src" data-v="'+esc(a.source)+'" aria-pressed="'+(srcOn?'true':'false')+'">'+esc(a.source)+'</button>'+
      speakChip(a)+
      '<button type="button" class="'+catCls+'" data-k="cat" data-v="'+esc(a.category)+'" aria-pressed="'+(catOn?'true':'false')+'">'+esc(a.category)+'</button>'+
      '<span>'+age(a.published_at)+'</span>'+stars(a)+
    '</div>'+
    '<h2 class="title"><a href="'+esc(a.link)+'" target="_blank" rel="noopener nofollow">'+hl(a.title)+'</a></h2>'+
    summaryBlock(a)+
    (CFG.admin?'<a class="open" href="'+esc(a.link)+'" target="_blank" rel="noopener nofollow">원문 열기</a>':'')+
  '</article>'}

function pillCount(cat){return articles().filter(a=>a.category===cat).length}
function renderPills(){
  const th=V.tab==='thai';
  const row=document.querySelector(th?'#filters-thai':'#filters-global');
  document.querySelector(th?'#filters-global':'#filters-thai').hidden=true;
  const cats=th?THAI_CATS:GLOBAL_CATS;
  const srcs=th?THAI_SRC:GLOBAL_SRC;
  const items=[['전체','전체']].concat(cats.map(c=>Array.isArray(c)?c:[c,c]));
  row.innerHTML=items.map(pair=>{
    const n=PUBLIC?pillCount(pair[0]):0;
    const badge=(PUBLIC&&n&&pair[0]!=='전체')?'<i>'+n+'</i>':'';
    return '<button type="button" class="pill'+(th?' th':'')+(pair[0]===V.filter?' active':'')+
      '" data-cat="'+esc(pair[0])+'">'+esc(pair[1])+badge+'</button>'}).join('')+
    (srcs.length?'<span class="pillsep"></span>':'')+
    srcs.map(s=>{
      const on=V.tag&&V.tag.k==='src'&&V.tag.v===s;
      return '<button type="button" class="pill src'+(th?' th':'')+(on?' active':'')+
        '" data-src="'+esc(s)+'" aria-pressed="'+(on?'true':'false')+'">'+esc(s)+'</button>'}).join('')+
    (V.tag?'<button type="button" class="pill on" id="clrtag">✕ '+esc(V.tag.v)+'</button>':'');
  row.hidden=false;
  row.querySelectorAll('button[data-cat]').forEach(b=>b.onclick=()=>{
    // Same exclusivity as the card chips: a category and a source tag sent together are ANDed
    // server-side, which usually returns nothing at all.
    V.filter=b.dataset.cat;V.tag=null;V.mode='all';V.value='';
    V.limit=PAGE;V.offset=0;renderPills();fetchFeed()});
  row.querySelectorAll('button[data-src]').forEach(b=>b.onclick=()=>{
    const v=b.dataset.src;
    V.tag=(V.tag&&V.tag.k==='src'&&V.tag.v===v)?null:{k:'src',v:v};
    V.filter='전체';V.mode='all';V.value='';
    V.limit=PAGE;V.offset=0;renderPills();fetchFeed()});
  const clr=row.querySelector('#clrtag');
  if(clr)clr.onclick=()=>{V.tag=null;V.limit=PAGE;V.offset=0;renderPills();fetchFeed()};
  document.querySelectorAll('.tab').forEach(b=>{
    const on=b.dataset.tab===V.tab;
    b.classList.toggle('active',on);
    b.setAttribute('aria-selected',on?'true':'false')});
}

// --- trend strip ------------------------------------------------------------------
// What the wire is talking about, counted in the browser from headlines already in
// hand, so no endpoint or core change is needed and the local and hosted pages run the
// same code. Two structural cleanings come first, both measured on a day of data:
// Google News titles carry a " - Publisher" tail (1820 of 1833), which is where
// post/nation/the/yahoo/tradingview noise came from, and social posts embed short links
// (reut.rs/4Ao...) which produced "reut" and "rs".
const T_STOP=new Set(("그리고 그러나 또한 이번 지난 오늘 어제 내일 관련 발표 예정 가능 필요 대해 통해 위해 때문 이라 라고 이라고 있다 없다 했다 한다 된다 등등 경우 상황 내용 사실 우리 전체 주요 최근 현재 기록 "
 +"the and for with from that this will said says after over into its his her has have was were are not but you your more than about could would should may might what "
 +"new now out off all one two three how why who when where first last next week month year day time report news update live exclusive "
 +"actual forecast previous consensus revised mom yoy qoq things best top world center "
  +"unknown transferred minted burned treasury wallet details "
   +"very reach foreign amid ahead survive "
   +"jan feb mar apr may jun jul aug sep sept oct nov dec").split(' '));
// The whole page is about these, so they would head the list every hour and say nothing.
const T_SKIP={
  global:new Set('bitcoin btc crypto cryptocurrency 비트코인 암호화폐 코인'.split(' ')),
  thai:new Set('태국 방콕 태국인 교민 thai thailand bangkok'.split(' '))};
const T_URL=/https?:\/\/\S+|\b[\w-]+\.(?:com|net|org|co|io|kr|uk|rs|me|ly|gov|ai|news)\S*/gi;
const T_TAIL=/\s+-\s+[^-]{2,40}$/;
const T_TOK=/[0-9A-Za-z가-힣\u0e00-\u0e7f]+/g;
function tFold(w){if(!/^[a-z]+$/.test(w))return w;const s=w.replace(/s$/,'');return (s!==w&&s.length>=3)?s:w}
function trends(){
  const skip=T_SKIP[V.tab]||T_SKIP.global,uni={},bi={},form={};
  trendSource().forEach(a=>{
    let t=a.title||'';
    if((a.source||'').indexOf('Google News')===0)t=t.replace(T_TAIL,'');
    t=t.replace(T_URL,' ');
    const tl=t.toLowerCase(),keep=[];
    (tl.match(T_TOK)||[]).forEach((w,i)=>{
      if(/^\d+$/.test(w))return;
      // Minimum length per script: Korean words are short and space-separated, while
      // Thai runs have no spaces between words, so anything short there is a particle
      // (the first run surfaced "นี้", meaning "this").
      const ko=/[\uac00-\ud7a3]/.test(w),thai=/[\u0e00-\u0e7f]/.test(w);
      if(w.length<(ko?2:(thai?5:3)))return;
      keep.push({w:w,raw:w,i:i})});
    const good=[],seenU={},seenB={};
    keep.forEach(g=>{const f=tFold(g.w);
      if(T_STOP.has(g.w)||T_STOP.has(f)||skip.has(f))return;good.push({w:f,raw:g.raw,i:g.i})});
    good.forEach(g=>{
      if(!seenU[g.w]){seenU[g.w]=1;uni[g.w]=(uni[g.w]||0)+1;
        const m=form[g.w]||(form[g.w]={});m[g.raw]=(m[g.raw]||0)+1}});
    for(let k=0;k+1<good.length;k++){
      if(good[k+1].i!==good[k].i+1)continue;
      // Only keep a pair the title actually contains as one phrase, so clicking it
      // finds the same stories it was counted from.
      if(tl.indexOf(good[k].raw+' '+good[k+1].raw)<0)continue;
      const key=good[k].w+' '+good[k+1].w;
      if(seenB[key])continue;seenB[key]=1;bi[key]=(bi[key]||0)+1}
  });
  const show=k=>{const m=form[k];if(!m)return k;let best=k,bc=-1;
    for(const r in m)if(m[r]>bc){bc=m[r];best=r}return best};
  const out=[],used={};
  Object.keys(bi).sort((x,y)=>bi[y]-bi[x]).forEach(k=>{
      const c=bi[k];if(c<4)return;
      const p=k.split(' ');
      // Drop a pair that only repeats one word of a stronger phrase already taken: that is
      // how fragments like "reach asian" (out of "reach Asian Games") got in.
      if(used[p[0]]||used[p[1]])return;
      const lo=Math.min(uni[p[0]]||0,uni[p[1]]||0);
      if(c<0.5*lo)return;
      used[p[0]]=1;used[p[1]]=1;out.push({t:show(p[0])+' '+show(p[1]),c:c})});
  Object.keys(uni).sort((x,y)=>uni[y]-uni[x]).forEach(k=>{
    if(used[k]||uni[k]<3)return;out.push({t:show(k),c:uni[k]})});
  out.sort((x,y)=>y.c-x.c);
  return out.slice(0,10);
}
const T_DATA={},T_FETCH={},T_CACHE={sig:'',list:[]};
// The feed only holds one page (25 rows on the local page), so counting from it ranked
// whatever happened to be on screen: the first run put "reut 4" on top. Trends need the
// window, so the local page asks for it separately (capped at 300 rows) and the hosted
// page uses the file it already loaded.
function trendSource(){return PUBLIC?(MEM[region()]||[]):(T_DATA[region()]||[])}
function loadTrends(force){
  if(PUBLIC){renderTrends();return}
  const r=region(),now=Date.now();
  if(!force&&T_FETCH[r]&&now-T_FETCH[r]<60000)return;
  T_FETCH[r]=now;
  const p=new URLSearchParams({region:r,hours:String(V.hours),limit:'300',offset:'0'});
  fetch(API+'/api/news?'+p.toString(),{cache:'no-cache'})
    .then(x=>x.ok?x.json():null)
    .then(d=>{if(d)T_DATA[r]=d.articles||[];renderTrends()})
    .catch(()=>{});
}
function renderTrends(){
  const el=document.querySelector('#trend');if(!el)return;
  const a=trendSource(),sig=V.tab+'|'+V.hours+'|'+a.length+'|'+((a[0]||{}).link||'');
  if(T_CACHE.sig!==sig){T_CACHE.sig=sig;T_CACHE.list=trends()}
  const list=T_CACHE.list||[];
  if(!list.length){el.hidden=true;el.innerHTML='';return}
  el.hidden=false;
  el.innerHTML='<span class="tlabel">지금 뜨는 키워드</span>'+list.map(function(x){
    return '<button type="button" class="tbtn" data-trend="'+esc(x.t)+'">'+esc(x.t)+
          '<span class="n">'+x.c+'</span></button>'}).join('');
}
document.querySelector('#trend').onclick=ev=>{
  const b=ev.target.closest('[data-trend]');if(!b)return;
  // Reuse the search box's own handler so a trend click behaves exactly like typing.
  const q=document.querySelector('#q');q.value=b.dataset.trend;q.oninput();
};

function renderFeed(){
  loadTrends();renderTrends();
  const all=visible(),view=all.slice(0,V.limit),th=V.tab==='thai';
  const feed=document.querySelector('#feed');
  if(!view.length){
    feed.innerHTML='<div class="empty"><b>조건에 맞는 뉴스가 없습니다</b>검색어를 지우거나 기간을 넓혀 보세요.</div>';
    document.querySelector('#counts').innerHTML='총 <b>'+all.length+'</b>건';
    document.querySelector('#more').hidden=true;return}
  // Strictly newest first, with light time headings. An earlier version pinned the
  // highest-priority story of the last three hours to the top; a reader watching a
  // quiet feed could not tell it was intentional, so the promotion is gone.
  let html='',current='';
  view.forEach(a=>{
    if(PUBLIC){
      const b=bucket(a.published_at);
      if(b!==current){current=b;html+='<div class="sec">'+esc(b)+'</div>'}
    }
    html+=card(a,th,false)});
  feed.innerHTML=html;
  document.querySelector('#counts').innerHTML=(PUBLIC
    ? '총 <b>'+all.length+'</b>건, <b>'+view.length+'</b>건 표시'
    : '총 <b>'+(DATA.total==null?all.length:DATA.total)+'</b>건, <b>'+view.length+'</b>건 표시'
      +(CFG.admin?'<span class="admin">, 보관 <b>'+archiveTotal+'</b>건</span>':''));
  // Local: also require that the last request actually returned the whole window, so the
  // button disappears when the API's own limit caps the page instead of silently doing
  // nothing on every further click.
  document.querySelector('#more').hidden=!(PUBLIC
    ? all.length>view.length
    : (DATA.has_more&&view.length>=V.limit));
  const pend=PENDING[region()]||0,np=document.querySelector('#newpill');
  if(pend>0){np.textContent='새 글 '+pend+'건 보기';np.dataset.show='1'}
  else{np.dataset.show='0';np.textContent=''}
  const live=document.querySelector('#live');
  if(live)live.textContent=all.length+'건 표시 중'}
function skeleton(){
  const feed=document.querySelector('#feed');
  // The page ships the latest headlines in its own HTML (see seed_feed) so a language
  // detector has real article text to read before the script runs. Leave that content in
  // place; renderFeed() replaces it as soon as the fetch returns.
  if(feed.children.length)return;
  feed.innerHTML='<div class="skel"><span></span><span></span><span></span></div>'.repeat(2)}

function setStamp(text,regions){
  const el=document.querySelector('#updated');
  el.textContent=text||'-';
  if(regions)el.title=Object.keys(regions).map(k=>k+' '+(regions[k].count==null?'':regions[k].count)+'건').join(', ')}
function flagStale(iso){
  const box=document.querySelector('#stale');
  const t=iso?new Date(iso).getTime():NaN;
  const late=!isFinite(t)||(Date.now()-t)/60000>STALE_MIN;
  box.dataset.show=late?'1':'0';
  box.textContent=late?'수집이 지연되고 있습니다 — 표시된 시각 이후 새 데이터가 없습니다':''}

async function getJSON(url){
  const r=await fetch(url,{cache:'no-cache'});
  if(!r.ok)throw Error(r.status);
  return r.json()}

function regionFile(suffix){return DATADIR+(region()==='태국'?'thai':'global')+suffix}
function regionMeta(){return (INDEX.regions||{})[region()]||{}}
async function loadFull(){
  const payload=await getJSON(regionFile('.json'));
  MEM[region()]=payload.articles||[];LATEST[region()]=MEM[region()];FULL[region()]=true;
  const meta=regionMeta();SEEN[region()]={stamp:meta.stamp,recent_stamp:meta.recent_stamp};
  renderPills();renderFeed()}

async function loadPublic(force){
  INDEX=await getJSON(DATADIR+'index.json');
  const meta=regionMeta(),seen=SEEN[region()];
  setStamp(INDEX.updated_at_ict+' ICT · '+(INDEX.window_hours||24)+'시간',INDEX.regions);
  flagStale(INDEX.updated_at);
  // Compare the content stamp, not the clock: index.json is rewritten every cycle but a
  // region file only changes when its rows do, so an untouched region is not re-read.
  const key=FULL[region()]?'stamp':'recent_stamp';
  if(!force&&seen&&seen[key]&&meta[key]===seen[key]){renderPills();renderFeed();return}
  const payload=await getJSON(regionFile(FULL[region()]?'.json':'-recent.json'));
  const fresh=payload.articles||[],current=MEM[region()];
  if(current&&current.length&&!FULL[region()]){
    const links=new Set(current.map(a=>a.link));
    LATEST[region()]=fresh;
    PENDING[region()]=fresh.filter(a=>!links.has(a.link)).length;
  }else{MEM[region()]=fresh;LATEST[region()]=fresh;PENDING[region()]=0}
  SEEN[region()]={stamp:meta.stamp,recent_stamp:meta.recent_stamp};
  renderPills();renderFeed()}

function buildQuery(){
  const p=new URLSearchParams();
  p.set('region',V.tab==='thai'?'태국':'글로벌');
  p.set('hours',V.hours);p.set('limit',V.limit);p.set('offset',V.offset);
  if(V.q)p.set('q',V.q);
  if(V.mode==='priority')p.set('priority',V.value||'5');
  else if(V.mode==='official')p.set('source_type','official');
  else if(V.mode==='source'&&V.value)p.set('source',V.value);
  // V.filter is only ever a category name or '전체'. The category pill row sets it without
  // setting V.mode, so gating this branch on the mode left the pill highlighted while the
  // server still returned the unfiltered list.
  if(V.filter&&V.filter!=='전체')p.set('category',V.filter);
  // Card chips set V.tag, not V.mode/V.value. Without this the local page sent an
  // unfiltered request, so clicking a chip only highlighted it and the list never moved.
  if(V.tag){if(V.tag.k==='cat')p.set('category',V.tag.v);else p.set('source',V.tag.v)}
  return p.toString()}
async function loadLocal(){
  const r=await fetch(API+'/api/news?'+buildQuery(),{cache:'no-cache'});
  if(!r.ok)throw Error(r.status);
  const fresh=await r.json();
  if(V.offset>0&&(DATA.articles||[]).length)fresh.articles=(DATA.articles||[]).concat(fresh.articles||[]);
  const before=(DATA.articles||[]).length?String(DATA.articles[0].published_at||''):'';
  if(before&&V.offset===0)(fresh.articles||[]).forEach(a=>{
    if(String(a.published_at||'')>before)a.fresh=true});
  DATA=fresh;
  archiveTotal=(fresh.archived_total!=null?fresh.archived_total:archiveTotal);
  try{localStorage.setItem(CACHE_KEY,JSON.stringify(DATA))}catch(e){}
  setStamp((fresh.updated_at_ict||'')+' · '+(fresh.window_hours||24)+'시간 · '+(fresh.total||0)+'건',fresh.region_counts);
  flagStale(fresh.updated_at);
  renderSources();renderPills();renderFeed()}

async function fetchFeed(){
  if(PUBLIC){try{await loadPublic(false)}catch(e){offline()}return}
  try{await loadLocal()}catch(e){document.querySelector('#state')&&(document.querySelector('#state').textContent='재시도 중');renderFeed()}}
function offline(){
  if(!articles().length){
    setStamp('연결 실패');
    document.querySelector('#feed').innerHTML='<div class="empty"><b>데이터를 불러오지 못했습니다</b>잠시 후 새로고침해 주세요.</div>'}}

function renderSources(){
  const el=document.querySelector('#sources');if(!el)return;
  const rows=Object.entries(DATA.sources||{});
  el.innerHTML=rows.length?rows.map(([name,s])=>
    '<div class="source"><span>'+esc(name)+'</span><span class="'+(s.ok?'ok':'bad')+'">'+
      (s.ok?'정상 '+(s.count==null?0:s.count):'실패')+'</span></div>').join('')
    :'<div class="note">대기 중</div>'}
function renderGuide(){
  const el=document.querySelector('#tguide');if(!el)return;
  el.innerHTML=V.tab==='thai'
    ?'<h2>태국 소식</h2><p class="note">방콕포스트·카오솟·타이인콰이어러·프라차타이(영문), 타이랏·마티촌(태국어), 구글뉴스 태국·방콕·교민 검색을 모읍니다.</p><p class="note">비자·이민과 사고·재난을 우선 표시하며, 확정되지 않은 속보는 원문 확인 전까지 단정하지 않습니다.</p>'
    :'<h2>관찰 기준</h2><p class="note">유동성·금리, 달러·국채, 미국 정책, 지정학, ETF·기관 수급, 파생상품, 온체인, 스테이블코인, X 발언을 우선 수집합니다.</p><p class="note">뉴스 사실과 시장 해석을 분리합니다. X 게시물과 속보는 공식 발표나 원문 확인 전까지 확정 사실로 취급하지 않습니다.</p>'}

function setTab(next,silent){
  // The indicator tab toggles: pressing it again closes the panel and returns to the
  // last news tab. Previously the calendar stayed open above the feed once visited,
  // because it was shown with an inline style that the tab class could not undo.
  if(next==='cal'&&V.tab==='cal'&&!silent){setTab(V.lastNews||'global');return}
  if(next!=='cal')V.lastNews=next;
  V.tab=next;V.filter='전체';V.tag=null;V.limit=PAGE;V.offset=0;V.mode='all';V.value='';
  document.body.classList.toggle('tab-cal',next==='cal');
  document.querySelectorAll('.tab').forEach(b=>{
    const on=b.dataset.tab===next;b.classList.toggle('active',on);b.setAttribute('aria-selected',on?'true':'false')});
  const gRow=document.querySelector('#filters-global'),tRow=document.querySelector('#filters-thai');
  const gHide=next!=='global',tHide=next!=='thai';
  gRow.hidden=gHide;tRow.hidden=tHide;
  gRow.style.display=gHide?'none':'flex';tRow.style.display=tHide?'none':'flex';
  renderGuide();
  // Reflect the tab in the URL so a view can be linked. Written on every change, but
  // not on the silent first call: /thai/ already implies the Thailand tab.
  if(!silent&&history.replaceState){
    const hash=next==='cal'?'#tab=cal':next==='thai'?'#tab=thai':'';
    history.replaceState(null,'',hash||location.pathname+location.search)};
  if(next==='cal'){loadCalendar();return}
  if(PUBLIC){if(MEM[region()]&&MEM[region()].length){renderPills();renderFeed()}else{skeleton();fetchFeed()}}
  else{fetchFeed()}}

function calendarFailure(message){
  document.querySelector('#cal-stamp').textContent='';
  document.querySelector('#cal-body').innerHTML='<div class="cal-err">'+esc(message)+
    '<button type="button" id="cal-retry">다시 시도</button></div>';
  const b=document.querySelector('#cal-retry');
  if(b)b.onclick=()=>{document.querySelector('#cal-body').innerHTML='<div class="note">불러오는 중…</div>';loadCalendar()}}
function calEsc(s){return esc(s)}
function calNum(t){const m=String(t==null?'':t).replace(/,/g,'').match(/-?\\d+(\\.\\d+)?/);return m?parseFloat(m[0]):null}
function calTone(e){const a=calNum(e.actual),c=calNum(e.consensus);if(a===null||c===null)return 'flat';
  const tol=Math.abs(c)*0.02;return Math.abs(a-c)<=tol?'flat':(a>c?'up':'down')}
function paintCalendar(data){
  const days=(data&&data.days)||[];
  if(!days.length){document.querySelector('#cal-stamp').textContent='';
    document.querySelector('#cal-body').innerHTML='<div class="note">표시할 일정이 없습니다.</div>';return}
  let total=0,top=0;
  days.forEach(d=>{total+=d.events.length;d.events.forEach(e=>{if(e.importance>=4)top++})});
  document.querySelector('#cal-stamp').textContent=(data.updated_at_kst||'')+' KST';
  document.querySelector('#cal-sum').textContent='앞으로 3일 일정 '+total+'건 · 중요도 ★4 이상 '+top+'건 · 출처 나스닥 캘린더 · 연준 · 백악관 · Factba.se'
    +' · 시각 기준 KST(UTC+9) · 방콕은 여기서 2시간 뒤'
    +' · 연준 인물 명단 '+(data.fed_roster_as_of||'?')+'년 기준';
  document.querySelector('#cal-body').innerHTML=days.map(d=>{
    const rows=d.events.length?d.events.map(e=>{
      const parts=[];
      if(e.kind==='earnings'){parts.push('실적 발표')}
      else if(e.kind==='potus'){parts.push('대통령 일정')}
      else{
        if(e.kind==='speech'&&e.fed_vote)parts.push(e.fed_vote);
        if(e.released)parts.push(shown(e.actual,calTone(e)));
        else if(e.passed)parts.push('발표');
        if(e.consensus)parts.push('예상 '+calEsc(e.consensus));
        if(e.previous)parts.push('이전 '+calEsc(e.previous));
      }
      const val=parts.join(' · ');
      const label=calEsc(e.country_code||e.country)+' · ';
      const name=e.source_url?label+'<a href="'+calEsc(e.source_url)+'" target="_blank" rel="noopener">'+calEsc(e.name)+'</a>':label+calEsc(e.name);
      let at=calEsc(e.kst||'');
      if(e.approx&&at)at='~'+at;
      return '<div class="cal-row '+(e.kind||'econ')+' i'+e.importance+'">'+
        '<span class="cal-t">'+at+'</span>'+
        '<span class="cal-s i'+e.importance+'">'+new Array(e.importance+1).join('*')+'</span>'+
        '<span class="cal-n">'+name+'</span><span class="cal-v">'+val+'</span></div>'}).join('')
      :'<div class="note">주요 지표 없음</div>';
    return '<div class="cal-day"><h3>'+calEsc(d.label)+' <span>'+calEsc(String(d.date).slice(5))+' ('+calEsc(d.weekday)+')</span></h3>'+rows+'</div>'}).join('')}
function loadCalendar(){
  fetch(CAL_URL,{cache:'no-cache'}).then(r=>{
    if(!r.ok)throw Error(r.status);return r.json()
  }).then(paintCalendar).catch(()=>calendarFailure('경제지표 데이터를 불러오지 못했습니다.'))}

document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>setTab(b.dataset.tab));
// The category and source rows are built by renderPills(), which binds each button as it
// writes them. An earlier build also had a static `.pill[data-filter]` row here; nothing in
// the template carries that attribute any more, so the handler was removed rather than left
// as a second, dead copy of the filter logic.
document.querySelector('#q').oninput=()=>{clearTimeout(window.__qt);
  window.__qt=setTimeout(()=>{V.q=document.querySelector('#q').value.trim();
    V.limit=PAGE;V.offset=0;fetchFeed()},350)};
document.querySelector('#hours').onchange=()=>{V.hours=Number(document.querySelector('#hours').value)||24;
  V.limit=PAGE;V.offset=0;fetchFeed()};
document.querySelector('#more').onclick=async()=>{
  if(PUBLIC){
    if(V.limit+PAGE>articles().length&&!FULL[region()])await loadFull();
    V.limit+=PAGE;renderFeed()}
  // Local: the feed is rendered from visible().slice(0,V.limit), so raising the offset
  // alone grew the stored rows but left the reader looking at the same first page.
  // Grow the window and refetch from the top instead; the API caps the response anyway.
  else{
    const cap=DATA.total||0;
    V.limit=cap?Math.min(V.limit+PAGE,cap):V.limit+PAGE;
    V.offset=0;fetchFeed()}};
document.querySelector('#newpill').onclick=()=>{const t=region();
  if(LATEST[t]){
    // Mark what arrived since the reader last looked, so the swap is visible.
    const before=(MEM[t]||[]).length?String((MEM[t]||[])[0].published_at||''):'';
    LATEST[t].forEach(a=>{if(before&&String(a.published_at||'')>before)a.fresh=true});
    MEM[t]=LATEST[t]}
  PENDING[t]=0;V.limit=PAGE;renderFeed()};
document.querySelector('#feed').addEventListener('click',ev=>{
  const chip=ev.target.closest('.chip.tap');
  if(chip){const k=chip.dataset.k,v=chip.dataset.v;
    V.tag=(V.tag&&V.tag.k===k&&V.tag.v===v)?null:{k:k,v:v};
    // The category pill row and the card chips are two different filters. Left alone they
    // would be sent together and ANDed on the server, which usually returns nothing.
    V.filter='전체';V.mode='all';V.value='';
    V.limit=PAGE;V.offset=0;renderPills();fetchFeed();return}
  const btn=ev.target.closest('.expand');
  if(!btn)return;
  const s=btn.previousElementSibling;
  const open=s.classList.toggle('clamp')===false;
  btn.textContent=open?'접기':'펼쳐보기';
  btn.setAttribute('aria-expanded',open?'true':'false')});
const intervalEl=document.querySelector('#interval');
if(intervalEl)intervalEl.onchange=async()=>{
  const value=Number(intervalEl.value);
  try{
    const r=await fetch(API+'/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({interval:value})});
    if(!r.ok)throw Error(r.status);
    if(refreshTimer)clearInterval(refreshTimer);
    refreshTimer=setInterval(()=>{if(!hidden)fetchFeed()},value*1000);
    fetchFeed();
  }catch(e){alert('갱신 간격 변경 실패: '+e.message)}};
const topEl=document.querySelector('#totop');
if(topEl)topEl.onclick=()=>scrollTo({top:0,behavior:'smooth'});
document.addEventListener('keydown',ev=>{
  if(ev.key==='/'&&document.activeElement!==document.querySelector('#q')){ev.preventDefault();document.querySelector('#q').focus()}});
document.addEventListener('visibilitychange',()=>{hidden=document.hidden;
  if(!hidden)fetchFeed()});

(function start(){
  const hash=location.hash||'';
  renderGuide();
  if(CFG.wantThai||hash.indexOf('tab=thai')>=0)setTab('thai',true);
  else if(hash.indexOf('tab=cal')>=0)setTab('cal',true);
  // The search box starts empty on every load. Restoring the last query meant a reload
  // silently kept filtering the list, which reads as the dashboard being stuck.
  skeleton();
  if(PUBLIC){fetchFeed();setInterval(()=>{if(!hidden&&V.tab!=='cal')fetchFeed()},300000)}
  else{fetchFeed();refreshTimer=setInterval(()=>{if(!hidden)fetchFeed()},30000)}
  if(V.tab==='cal')loadCalendar();
  setInterval(()=>{if(!hidden&&V.tab==='cal')loadCalendar()},900000);
})();
"""


def _script_lang(text: str) -> str:
    """Dominant script of a headline, used as the lang attribute on seeded cards."""
    ko = th = latin = 0
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            ko += 1
        elif 0x0E00 <= code <= 0x0E7F:
            th += 1
        elif ch.isalpha():
            latin += 1
    if not (ko or th or latin):
        return ""
    if th >= ko and th >= latin:
        return "th"
    return "ko" if ko > latin else "en"


def _ict_stamp(value) -> str:
    try:
        moment = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)[:16].replace("T", " ")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    shifted = moment.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
    return shifted.strftime("%m-%d %H:%M")


def seed_feed(path: str, want_thai: bool, limit: int = 25) -> str:
    """Render the latest headlines into the page itself.

    The feed is built by the script from JSON, so when a browser first looks at the page the
    only words on it are the Korean interface. Safari decides the page language on the device
    at that moment, concludes the page is Korean, and then offers to translate it into
    English instead of into Korean. News sites do not have this problem because their article
    text is in the HTML from the start. Seeding the same headlines here gives the same signal,
    and the page also reads correctly when scripts are disabled.
    """
    try:
        with io.open(path, encoding="utf-8") as handle:
            items = json.load(handle).get("articles") or []
    except (OSError, ValueError):
        return ""
    rows = []
    for item in items[:limit]:
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        if not title:
            continue
        lang = _script_lang(title + " " + summary)
        attr = ' lang="%s"' % lang if lang else ""
        rows.append(
            '<article class="card seed' + (" th" if want_thai else "") + '">'
            '<div class="meta"><span class="chip src">' + html.escape(str(item.get("source") or "")) + '</span>'
            '<span class="chip">' + html.escape(str(item.get("category") or "")) + '</span>'
            '<span>' + html.escape(_ict_stamp(item.get("published_at"))) + '</span></div>'
            '<h2 class="title"' + attr + '><a href="' + html.escape(str(item.get("link") or ""))
            + '" target="_blank" rel="noopener nofollow">' + html.escape(title) + '</a></h2>'
            '<p class="summary clamp"' + attr + '>' + html.escape(summary) + '</p>'
            '</article>')
    return "".join(rows)


def render(*, public: bool, datadir: str, want_thai: bool, icon_prefix: str, admin: bool,
           html_lang: str = "en", seed_path: str = "") -> str:
    config = {
        "public": public,
        "datadir": datadir,
        "wantThai": want_thai,
        "admin": admin,
        "api": "",
        "calendar": "https://raw.githubusercontent.com/freaky0/teemobkk-live-news/main/docs/calendar.json",
    }
    stamp = ('<div class="stamp"><span id="state">연결 중</span> <b id="updated">-</b>'
             if admin else '<div class="stamp">업데이트 <b id="updated">-</b>')
    admin_toolbar = ('' if not admin else
                     '<label class="note admin" for="interval">갱신</label>'
                     '<select id="interval" class="admin" aria-label="갱신 간격">'
                     '<option value="10">10초</option><option value="30">30초</option>'
                     '<option value="60" selected>1분</option><option value="120">2분</option>'
                     '<option value="300">5분</option></select>')
    side = ('' if not admin else
            '<aside class="side admin"><div class="box"><h2>수집 상태</h2><div id="sources">'
            '<div class="note">대기 중</div></div></div><div class="box" id="tguide"></div></aside>')
    og = ('' if admin else
          '<meta name="description" content="비트코인·매크로·태국 뉴스를 5분마다 모아 보여주는 실시간 대시보드. 경제지표와 주요 일정 포함.">\n'
          '<meta property="og:title" content="TeemoBKK Live News">\n'
          '<meta property="og:description" content="비트코인·매크로·태국 뉴스 실시간 대시보드. 경제지표·연설·실적 일정 포함.">\n'
          '<meta property="og:type" content="website">\n'
          '<meta property="og:image" content="' + icon_prefix + 'og-image.png">\n'
          '<meta name="twitter:card" content="summary_large_image">\n')
    title = "TeemoBKK Live News" + (" · 태국 소식" if want_thai else "")
    script = SCRIPT.replace("__CONFIG__", json.dumps(config, ensure_ascii=False, separators=(",", ":")))
    seed = seed_feed(seed_path, want_thai) if seed_path else ""
    return f"""<!doctype html>
<html lang="{html_lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
{og}<link rel="icon" href="{icon_prefix}favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="{icon_prefix}favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="{icon_prefix}favicon-16.png">
<link rel="apple-touch-icon" href="{icon_prefix}apple-touch-icon.png">
<title>{title}</title>
<style>
{CSS}</style>
</head>
<body class="{"public" if public else "local"}">
<header class="bar">
  <div class="bar-in">
    <div>
      <div class="brand">TeemoBKK Live News</div>
      <h1>실시간 뉴스 대시보드</h1>
    </div>
    <div class="spacer"></div>
    {stamp}<br><span id="stale" class="stale"></span></div>
  </div>
</header>

<main class="wrap">
  <div class="tabs" role="tablist">
    <button id="tab-global" class="tab active" data-tab="global" role="tab" aria-selected="true">경제 소식</button>
    <button id="tab-cal" class="tab" data-tab="cal" role="tab" aria-selected="false">경제 지표</button>
    <button id="tab-thai" class="tab th" data-tab="thai" role="tab" aria-selected="false">태국 소식</button>
  </div>

  <section class="cal" id="cal">
    <h2>경제지표 · 연설 · 실적 · 대통령 일정 <span class="note" id="cal-stamp"></span></h2>
    <p class="cal-sum" id="cal-sum"></p>
    <div class="cal-grid" id="cal-body"><div class="note">불러오는 중…</div></div>
  </section>

  <section class="toolbar">
    <input id="q" type="search" placeholder="제목·요약·출처 검색 ( / )" aria-label="뉴스 검색">
    <select id="hours" aria-label="기간">
      <option value="1">최근 1시간</option>
      <option value="6">최근 6시간</option>
      <option value="12">최근 12시간</option>
      <option value="24" selected>최근 24시간</option>
    </select>
    {admin_toolbar}
    <button id="newpill" class="newpill" type="button"></button>
    <span class="count" id="counts"></span>
  </section>

  <section class="trend" id="trend" hidden></section>

  <section id="filters-global" class="pills"></section>
  <section id="filters-thai" class="pills th" hidden></section>

  <div class="layout">
    <section>
      <div id="feed" class="feed">{seed}</div>
      <span class="sr-only" aria-live="polite" id="live"></span>
      <div class="more-wrap">
        <button id="more" type="button" hidden>더 보기</button>
        <button id="totop" type="button">맨 위로</button>
      </div>
    </section>
    {side}
  </div>

  <footer class="foot">
    각 기사의 저작권은 원 매체에 있습니다. 제목과 요약, 그리고 원문 링크만 표시하며 원문 확인은 링크를 통해 해 주세요.<br>
    자동 수집 결과이므로 표기 오류나 지연이 있을 수 있습니다. 투자 판단의 근거로 사용하지 마세요.
  </footer>
</main>

<script>
{script}</script>
</body></html>
"""


def write(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return len(text.encode("utf-8"))


def build_all() -> dict[str, int]:
    """Rewrite the local page and both published pages."""
    sizes = {}
    sizes["index.html"] = write(ROOT / "index.html", render(
        public=False, datadir="", want_thai=False, icon_prefix="", admin=True,
        seed_path=str(DOCS / "global-recent.json")))
    sizes["docs/index.html"] = write(DOCS / "index.html", render(
        public=True, datadir="", want_thai=False, icon_prefix="", admin=False,
        seed_path=str(DOCS / "global-recent.json")))
    # The published Thai page declares Thai. Its headlines are Thai (Matichon, Thairath)
    # and English (Bangkok Post, Khaosod, most Google News hits); only 9% are Korean.
    # Declaring it ko made Safari treat the page as already-Korean and never offer
    # translation. Safari decides on the device, so this is a hypothesis to test on a
    # phone, not a guarantee. This is a deliberate override of the en default.
    sizes["docs/thai/index.html"] = write(DOCS / "thai" / "index.html", render(
        public=True, datadir="../", want_thai=True, icon_prefix="../", admin=False,
        html_lang="th", seed_path=str(DOCS / "thai-recent.json")))
    return sizes


if __name__ == "__main__":
    for name, size in build_all().items():
        print("wrote %s (%d bytes)" % (name, size))
