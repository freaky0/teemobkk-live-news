"""Build every dashboard page from one source.

Three pages are built from one source and they must never drift apart:

    index.html            built per machine, never committed - the collector answers "/" with it
                          (operator page on a developer's box, landing page on the host)
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
import os
import shutil
from pathlib import Path

import landing
import landing_thai
import category_rules as taxonomy
import ui_text

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
#logout{cursor:pointer;background:none;border:1px solid var(--line);color:var(--muted);
  border-radius:var(--r-ctl);padding:8px 12px}
#logout:hover{border-color:var(--accent);color:var(--accent)}
.count{color:var(--muted);font-size:12px;margin-left:auto}
.newpill{display:none;align-items:center;background:#123047;border:1px solid var(--accent);color:var(--accent);
  border-radius:var(--r-pill);padding:7px 14px;cursor:pointer;font-size:12.5px;font-weight:600}
.newpill[data-show="1"]{display:inline-flex}
.pills{display:flex;gap:8px;overflow-x:auto;padding:2px 2px 8px;margin-bottom:6px}
.pills::-webkit-scrollbar{height:6px}
.pills::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}
@media (min-width:900px){.pills{flex-wrap:wrap;overflow-x:visible}}
.pills[hidden]{display:none!important}
.trend{display:flex;gap:0;align-items:stretch;flex-wrap:nowrap;overflow:visible;margin:0 0 10px;padding:0}
.trend .tlabel{flex:0 0 auto;display:flex;align-items:center;padding:2px 10px 8px 2px;
  border-right:1px solid var(--line);margin-right:10px}
.trend .ttrack{flex:1 1 auto;min-width:0;display:flex;gap:8px;overflow-x:auto;padding:2px 2px 8px}
.trend .ttrack::-webkit-scrollbar{height:6px}
.trend .ttrack::-webkit-scrollbar-thumb{background:var(--line2);border-radius:3px}
@media (hover:hover){}
.trend .tbtn.on{border-color:var(--accent);background:var(--accent);color:#08111f;font-weight:600}
.trend .tbtn.on .n{color:#08111f;opacity:.65}
.trend .tbtn.clear{border-style:dashed;border-color:var(--warn);color:var(--warn);font-weight:600}
@media (hover:hover){.trend .tbtn:hover{border-color:var(--accent);color:var(--accent)}}
@media (min-width:900px){.trend .ttrack{flex-wrap:wrap;overflow-x:visible}}
.trend[hidden]{display:none!important}
.trend .tlabel{color:var(--muted);font-size:12px;white-space:nowrap}
.trend .n{color:var(--muted);font-size:11px;margin-left:6px}
/* The selected conditions, in one row: every filter that is currently narrowing the list, each
   with its own count and a way out. The number after the arrow is what all of them together
   return, which is the difference between this row and the pill rows above it. */
.conds{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0 0 10px;padding:6px 8px;
  border:1px solid var(--line);border-radius:var(--r);background:var(--bg2)}
.conds[hidden]{display:none!important}
.conds .clabel{color:var(--muted);font-size:12px;white-space:nowrap;margin-right:2px}
.conds .cbtn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--accent);
  background:var(--accent);color:#08111f;font-weight:600;font-size:12px;
  border-radius:var(--r-pill);padding:4px 10px;cursor:pointer}
.conds .cbtn .n{color:#08111f;opacity:.7;font-size:11px}
/* A keyword condition is outlined, a category or source condition is filled: the difference has to
   be visible without a word, because a word here would need translating. */
.conds .cbtn.kw{background:none;color:var(--accent);border-color:var(--accent)}
.conds .cbtn.kw .n{color:var(--accent);opacity:.75}
.conds .sum{color:var(--muted);font-size:12px;margin-left:4px}
.conds .warn{color:var(--warn);font-weight:600}
.conds button.wide{border:1px dashed var(--accent);background:none;color:var(--accent);
  border-radius:var(--r-pill);padding:4px 10px;font-size:12px;cursor:pointer}
.qadd{border:1px solid var(--line);background:none;color:var(--muted);border-radius:var(--r-pill);
  padding:5px 10px;font-size:12px;white-space:nowrap;cursor:pointer}
/* The operator's way out of a story, and the strip that says what just went away. Hiding is not a
   delete, so the undo stays until the next action: the way back has to be where the click was. */
.acts{display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.acts .hide{background:none;border:0;cursor:pointer;font-family:inherit;padding:0}
.acts .hide:hover{color:var(--warn)}
.undobar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 12px;padding:8px 12px;
  border:1px solid var(--warn);border-radius:var(--r-card)}
.undobar[hidden]{display:none!important}
.undobar .clabel{color:var(--warn);font-size:12px;font-weight:600;white-space:nowrap}
.undobar .utext{color:var(--muted);font-size:12.5px;max-width:52ch;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.hidrow{display:flex;gap:10px;align-items:baseline;justify-content:space-between;padding:5px 0;
  border-bottom:1px solid var(--line);font-size:12.5px}
.hidrow:last-child{border-bottom:0}
.hidrow a{color:#c3cfe6;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hidrow a:hover{color:var(--accent)}
.unhide{background:none;border:1px solid var(--line);border-radius:var(--r-pill);padding:3px 10px;
  color:var(--muted);cursor:pointer;font-size:11.5px;flex:0 0 auto}
.unhide:hover{border-color:var(--accent);color:var(--accent)}
@media (hover:hover){.qadd:hover{border-color:var(--accent);color:var(--accent)}}
/* Own class rather than the filter chips' ".chip.tap": those are toggles carrying
   aria-pressed, while a trend button is a one-shot search action. Reusing the class
   made every ".chip.tap" invariant assertion count a chip that is not a toggle. */
.trend .tbtn{border:1px solid var(--line);border-radius:var(--r-pill);padding:5px 11px;
  background:none;font-family:inherit;font-size:12.5px;color:var(--text);cursor:pointer;white-space:nowrap}

.pill{flex:0 0 auto;background:none;border:1px solid var(--line);border-radius:var(--r-pill);
  padding:7px 14px;cursor:pointer;font-size:12.5px;color:var(--muted);white-space:nowrap}
.pill.active{background:var(--panel2);border-color:var(--accent);color:var(--accent)}
.pill.th.active{border-color:var(--thai);color:var(--thai)}
.pill.on{border-color:var(--accent);color:var(--accent)}
/* Source chips sit in the same row as the category pills but are a different axis, so they
   are dashed and separated. */
.pill.src{border-style:dashed}
/* Teemo's Pick: the operator's judgement, shown to readers. Warmer than the filter pills and never
   a rank - selecting it narrows the list, the order stays newest first. */
.pill.pick{border-color:#21c997;color:#21c997}
.pill.pick.active{background:#0d2b22;border-color:#21c997;color:#b9f5e1;font-weight:600}
.pickbadge{display:inline-flex;align-items:center;gap:8px;margin:0 0 8px;padding:3px 10px;
  border:1px solid #21c997;border-radius:var(--r-pill);color:#7de8c4;font-size:12px;font-weight:600}
/* The phrase is one line in the row, and the whole thing on hover: a long note used to be cut off
   with no way to read it. The overlay is absolute so it does not move the headline under it. */
.pickbadge .pnote{color:#d6f7ec;font-weight:500;max-width:46ch;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap;cursor:help}
.pickbadge:hover .pnote{position:absolute;z-index:5;margin-top:2px;max-width:min(72ch,84vw);white-space:normal;
  overflow:visible;background:var(--panel);border:1px solid #21c997;border-radius:var(--r-ctl);
  padding:8px 12px;box-shadow:0 6px 20px rgba(0,0,0,.5)}
.pill.src.th.active{border-color:var(--thai);color:var(--thai)}
.pillsep{flex:0 0 auto;width:1px;margin:0 3px;background:var(--line2);align-self:stretch}
.langbar{display:flex;gap:6px;align-items:center;font-size:13px}
.langbar a,.langbar b{padding:4px 10px;border:1px solid var(--line);border-radius:var(--r-pill);
  color:var(--muted);font-weight:500;text-decoration:none}
.langbar b{border-color:var(--accent);color:var(--accent);font-weight:600}
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
/* the switch sits in the collection-status row, left of the name */
.source.off > span:first-of-type{color:var(--muted);text-decoration:line-through}
.source > span:first-of-type{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sw{flex:0 0 auto;width:34px;height:18px;border-radius:999px;border:1px solid var(--line2);background:var(--panel2);position:relative;cursor:pointer;padding:0}
.sw .knob{position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:var(--muted);transition:left .14s}
.sw[aria-checked="true"]{border-color:var(--accent);background:rgba(100,215,255,.18)}
.sw[aria-checked="true"] .knob{left:18px;background:var(--accent)}
.rule{display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--line2)}
.rule .rp{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px}
.rule.off .rp{color:var(--muted);text-decoration:line-through}
.rule .rh{flex:0 0 auto;font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px}
.rule .rx{flex:0 0 auto;border:0;background:none;color:var(--muted);cursor:pointer;font-size:12px;padding:0 2px}
.rule .rx:hover{color:var(--accent)}
.frow{display:flex;gap:6px;margin:8px 0 6px}
.frow input{flex:1 1 auto;min-width:0;background:var(--panel2);border:1px solid var(--line2);color:inherit;
border-radius:6px;padding:5px 7px;font-size:12px}
.wide{width:100%;background:var(--panel2);border:1px solid var(--line2);color:inherit;border-radius:6px;
padding:5px 7px;font-size:12px;cursor:pointer}
.caught{display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid var(--line2)}
.caught .ct{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;color:var(--muted)}
.caught .keep{flex:0 0 auto;border:0;background:none;color:var(--accent);cursor:pointer;font-size:11px;padding:0}
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
// A session lives in a cookie this script cannot read, so the server says whether there is one by
// setting this flag on the document it answers /admin with.
const ADMIN=window.__ADMIN__===true;
function writeHeaders(){const h={'Content-Type':'application/json'};
  if(ADMIN)h['X-Requested-With']='teemo-admin';return h}
// The label a reader sees, written once. It carries an apostrophe, and this script builds its
// strings with single quotes: written inline it would have to be escaped twice over - once for the
// Python that holds this template, once for JavaScript - and the escaping is exactly where a
// mistake would break the whole page rather than one label.
const PICK="Teemo's Pick", PICK_ICON="\U0001F344";
const PAGE=25, BIG=25, STALE_MIN=35, GRACE_MS=3*3600000;
const GLOBAL_CATS=__CATS_GLOBAL__;
const THAI_CATS=__CATS_THAI__;
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

var V={tab:CFG.wantThai?'thai':'global',cats:[],hours:24,q:'',terms:[],limit:PAGE,tag:null,mode:'all',value:'',offset:0,pickOnly:false};
var MEM={},LATEST={},PENDING={},INDEX={},SEEN={},FULL={},DATA={articles:[],sources:{},total:0,has_more:false};
var archiveTotal=0,refreshTimer=null,hidden=false,lastRegion={};
if(CFG.wantThai)document.title=document.title.replace('Live News','Live News · 태국 소식');
try{const s=localStorage.getItem(CACHE_KEY);if(s){const p=JSON.parse(s);if(p&&p.articles)DATA=p}}catch(e){}

function region(){return V.tab==='thai'?'태국':'글로벌'}
// The period in words: the select offers hours up to a day and then days, and the stamp used to
// print "168시간" for a week and "2160시간" for the whole archive.
function hoursLabel(){const h=Number(V.hours)||24;
  return h>=2160?'전체 기간':(h>=48?Math.round(h/24)+'일':h+'시간')}
function articles(){return PUBLIC?(MEM[region()]||[]):(DATA.articles||[])}
function age(iso){if(!iso)return '시각 미상';const d=new Date(iso);if(isNaN(d))return '시각 미상';
  const sec=Math.max(0,(Date.now()-d.getTime())/1000);
  if(sec<60)return Math.floor(sec)+'초 전';if(sec<3600)return Math.floor(sec/60)+'분 전';
  if(sec<86400)return Math.floor(sec/3600)+'시간 전';
  return d.toLocaleString('ko-KR',{timeZone:'Asia/Bangkok',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})+' ICT'}
function bangkokDay(iso){const d=new Date(iso);if(isNaN(d))return '';
  return new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Bangkok'}).format(d)}
function bucket(iso){const t=new Date(iso).getTime();if(!isFinite(t))return '그 이전';
  const h=(Date.now()-t)/3600000;if(h<1)return '최근 1시간';
  const day=bangkokDay(iso),today=bangkokDay(new Date().toISOString());
  if(day===today)return '오늘';
  const y=new Date(Date.now()-86400000).toISOString();
  if(day===bangkokDay(y))return '어제';
  return '그 이전'}
function hl(t){const txt=esc(t);const q=(V.q||'').trim();if(!q)return txt;
  const qe=esc(q).replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&');
  try{return txt.replace(new RegExp('('+qe+')','gi'),'<mark>$1</mark>')}catch(e){return txt}}
// The same rule the server applies, so the static copy and the API agree on what a term matches.
// A Latin term is a whole word (with the plural s), a Korean or Thai term is a substring: measured,
// 'ai' as a substring matched 3,720 rows where the whole word matched 599 ("said", "Thailand").
// Written with indexOf instead of a RegExp on purpose: this script lives inside a Python string, and
// a regex character class written here arrives with its backslashes doubled - it still parses and
// then silently matches the wrong thing.
function isLatinTerm(n){for(let i=0;i<n.length;i++){if(n.charCodeAt(i)>0x2E7F)return false}return true}
function termMatch(text,needle){
  const t=String(text==null?'':text).toLowerCase(), n=String(needle==null?'':needle).trim().toLowerCase();
  if(!n)return false;
  if(!isLatinTerm(n))return t.indexOf(n)>=0;
  const plural=n.indexOf(' ')<0;
  for(let at=t.indexOf(n);at>=0;at=t.indexOf(n,at+1)){
    const before=t.charAt(at-1), after=t.charAt(at+n.length);
    if(before&&/[a-z0-9]/.test(before))continue;
    if(after&&/[a-z0-9]/.test(after)){
      if(!plural||after!=='s')continue;
      const next=t.charAt(at+n.length+1);
      if(next&&/[a-z0-9]/.test(next))continue;
    }
    return true}
  return false}
function catList(a){const c=a.categories;return (Array.isArray(c)&&c.length)?c:(a.category?[a.category]:[])}
function keep(a){
  const hours=Number(V.hours)||24,t=new Date(a.published_at).getTime();
  if(!isFinite(t)||Date.now()-t>hours*3600000)return false;
  // A story can carry several axes, so a selected category matches if it is any of the card's
  // labels, not only its first one - and several selected categories must ALL be on the card, which
  // is what the server does too (this path runs for the published static copy, which has no API).
  const labels=catList(a);
  if(V.cats.length&&!V.cats.every(c=>labels.indexOf(c)>=0))return false;
  if(V.terms.length&&!V.terms.every(t=>termMatch((a.title||'')+' '+(a.summary||''),t)))return false;
  if(V.tag&&(V.tag.k==='cat'?labels.indexOf(V.tag.v)<0:a.source!==V.tag.v))return false;
  // The operator's picks are a condition like any other on this path: a selected pill narrows the
  // list, it never reorders it.
  if(V.pickOnly&&!a.picked)return false;
  const q=(V.q||'').trim();
  if(q&&!termMatch((a.title||'')+' '+(a.summary||'')+' '+(a.source||'')+' '+labels.join(' '),q))return false;
  return true}
function visible(){return PUBLIC?articles().filter(keep):articles()}
function stars(a){const n=Number(a.priority)||0;
  return n>=4?'<button type="button" class="chip hot static" tabindex="-1" aria-hidden="true">'+String.fromCharCode(9733).repeat(Math.min(5,n))+'</button>':''}
function summaryBlock(a){
  const s=a.summary||'';if(!s)return '';
  const long=s.length>220;
  return '<div class="summary'+(long?' clamp':'')+'"'+langAttr(a.summary_lang)+'>'+hl(s)+'</div>'+
    (long?'<button class="expand" type="button" aria-expanded="false">펼쳐보기</button>':'')}
// The language of each part, from the collector. A browser translating a page decides per element
// with this attribute; without it, a Thai headline with an English summary is guessed wrong and the
// translator mangles the half it misread.
function langAttr(code){return code?' lang="'+code+'"':''}
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
  const srcOn=tag.k==='src'&&tag.v===a.source;
  const srcCls='chip src tap'+(a.source_type==='official'?' official':'')+(th?' th':'')+(srcOn?' on':'');
  return '<article class="card'+(th?' th':'')+(a.fresh?' new':'')+'">'+
    '<div class="meta">'+
      verifChip(a)+
      '<button type="button" class="'+srcCls+'" data-k="src" data-v="'+esc(a.source)+'" aria-pressed="'+(srcOn?'true':'false')+'">'+esc(a.source)+'</button>'+
      speakChip(a)+
      // Every label the story matched is a chip, and each one filters on its own. Measured over a
      // 24-hour window: 19% of rows carry two labels, 4.7% carry three or more.
      catList(a).map(v=>{const on=tag.k==='cat'&&tag.v===v;
        return '<button type="button" class="chip tap'+(on?' on':'')+'" data-k="cat" data-v="'+esc(v)+'" aria-pressed="'+(on?'true':'false')+'">'+esc(catLabel(v))+'</button>'}).join('')+
      '<span>'+age(a.published_at)+'</span>'+stars(a)+
    '</div>'+
    // The operator's judgement, shown to everybody: a badge and, when there is one, the phrase. It
    // sits above the headline rather than in the chip row, because it is not a filter over text.
    (a.picked?'<div class="pickbadge">'+PICK_ICON+' '+PICK+
      (a.pick_note?'<span class="pnote">'+esc(a.pick_note)+'</span>':'')+'</div>':'')+
    '<h2 class="title"'+langAttr(a.lang)+'><a href="'+esc(a.link)+'" target="_blank" rel="noopener nofollow">'+hl(a.title)+'</a></h2>'+
    summaryBlock(a)+
    (CFG.admin?cardActs(a):'')+
  '</article>'}

function catLabel(value){const map=CFG.catLabels||{};return map[value]||value}
function fmt(t,n,m){return String(t).replace("{n}",n).replace("{m}",m)}
function pillCount(cat){return articles().filter(a=>catList(a).indexOf(cat)>=0).length}
function catOn(v){return v==='전체'?!V.cats.length:V.cats.indexOf(v)>=0}
function renderPills(){
  const th=V.tab==='thai';
  const row=document.querySelector(th?'#filters-thai':'#filters-global');
  document.querySelector(th?'#filters-global':'#filters-thai').hidden=true;
  const cats=th?THAI_CATS:GLOBAL_CATS;
  // A source the operator switched off is dropped by the server, so a pill for it would
  // return nothing: leave it out rather than offer a filter that cannot match.
  const srcs=(th?THAI_SRC:GLOBAL_SRC).filter(s=>!(OFF&&OFF.indexOf(s)>=0));
  const items=[['전체','전체']].concat(cats.map(c=>Array.isArray(c)?c:[c,c]));
  // Teemo's Pick sits first because it is a mode, not a category: the operator's judgement, which a
  // reader can filter by. It composes with the rest - picking it together with 트럼프 asks for
  // stories that are both, which is what selecting two things means everywhere else on this page.
  const pickPill='<button type="button" class="pill pick'+(V.pickOnly?' active':'')+
    '" data-pick="1" aria-pressed="'+(V.pickOnly?'true':'false')+'">'+PICK_ICON+' '+PICK+'</button>';
  row.innerHTML=pickPill+items.map(pair=>{
    const n=PUBLIC?pillCount(pair[0]):0;
    const badge=(PUBLIC&&n&&pair[0]!=='전체')?'<i>'+n+'</i>':'';
    return '<button type="button" class="pill'+(th?' th':'')+(catOn(pair[0])?' active':'')+
      '" data-cat="'+esc(pair[0])+'">'+esc(pair[1])+badge+'</button>'}).join('')+
    (srcs.length?'<span class="pillsep"></span>':'')+
    srcs.map(s=>{
      const on=V.tag&&V.tag.k==='src'&&V.tag.v===s;
      return '<button type="button" class="pill src'+(th?' th':'')+(on?' active':'')+
        '" data-src="'+esc(s)+'" aria-pressed="'+(on?'true':'false')+'">'+esc(s)+'</button>'}).join('')+
    (V.tag?'<button type="button" class="pill on" id="clrtag">✕ '+esc(V.tag.v)+'</button>':'');
  row.hidden=false;
  const pickBtn=row.querySelector('button[data-pick]');
  if(pickBtn)pickBtn.onclick=()=>{V.pickOnly=!V.pickOnly;V.limit=PAGE;V.offset=0;renderPills();fetchFeed()};
  row.querySelectorAll('button[data-cat]').forEach(b=>b.onclick=()=>{
    // A category and a source are different axes and now compose: several conditions are ANDed,
    // which is what a reader gets from "FinancialJuice + Trump". Selecting one no longer releases
    // the other, because the intersection is the point.
    const v=b.dataset.cat;
    // 전체 is the one control that clears the lot and shows the whole list, so it releases the
    // source tag and the keywords as well; a single category toggles and composes with the rest.
    if(v==='전체'){V.cats=[];V.tag=null;V.pickOnly=false;clearText()}
    else{const i=V.cats.indexOf(v);if(i>=0)V.cats.splice(i,1);else V.cats.push(v)}
    V.mode='all';V.value='';
    V.limit=PAGE;V.offset=0;renderPills();fetchFeed()});
  row.querySelectorAll('button[data-src]').forEach(b=>b.onclick=()=>{
    const v=b.dataset.src;
    V.tag=(V.tag&&V.tag.k==='src'&&V.tag.v===v)?null:{k:'src',v:v};
    V.mode='all';V.value='';
    V.limit=PAGE;V.offset=0;renderPills();fetchFeed()});
  const clr=row.querySelector('#clrtag');
  // Releases this value only: the other conditions stay, because each one now has its own place in
  // the condition row above the feed.
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
const T_URL=/https?:\\/\\/\\S+|\\b[\\w-]+\\.(?:com|net|org|co|io|kr|uk|rs|me|ly|gov|ai|news)\\S*/gi;
const T_TAIL=/\\s+-\\s+[^-]{2,40}$/;
const T_TOK=/[0-9A-Za-z가-힣\\u0e00-\\u0e7f]+/g;
function tFold(w){if(!/^[a-z]+$/.test(w))return w;const s=w.replace(/s$/,'');return (s!==w&&s.length>=3)?s:w}
function trends(){
  const skip=T_SKIP[V.tab]||T_SKIP.global,uni={},bi={},form={};
  trendSource().forEach(a=>{
    let t=a.title||'';
    if((a.source||'').indexOf('Google News')===0)t=t.replace(T_TAIL,'');
    t=t.replace(T_URL,' ');
    const tl=t.toLowerCase(),keep=[];
    (tl.match(T_TOK)||[]).forEach((w,i)=>{
      if(/^\\d+$/.test(w))return;
      // Minimum length per script: Korean words are short and space-separated, while
      // Thai runs have no spaces between words, so anything short there is a particle
      // (the first run surfaced "นี้", meaning "this").
      const ko=/[\\uac00-\\ud7a3]/.test(w),thai=/[\\u0e00-\\u0e7f]/.test(w);
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
  el.innerHTML='<span class="tlabel">' + "지금 뜨는 키워드" + '</span><span class="ttrack">'+
    list.map(function(x){
      const on=V.terms.indexOf(x.t)>=0;
      return '<button type="button" class="tbtn'+(on?' on':'')+'" data-trend="'+esc(x.t)+
      '" aria-pressed="'+(on?'true':'false')+'">'+(on?'\u2713 ':'')+esc(x.t)+
      '<span class="n">'+x.c+'</span></button>'}).join('')+
    (V.terms.length?'<button type="button" class="tbtn clear" data-trend-clear="1">'
      +V.terms.length+'개 해제 \u2715</button>':'')+'</span>'; }
document.querySelector('#trend').onclick=ev=>{
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
};

function renderFeed(){
  loadTrends();renderTrends();loadCondCounts();renderConditions();
  const all=visible(),view=all.slice(0,V.limit),th=V.tab==='thai';
  const feed=document.querySelector('#feed');
  if(!view.length){
    feed.innerHTML=condList().length
      ?'<div class="empty"><b>선택한 조건을 모두 만족하는 뉴스가 없습니다</b>위 조건 줄에서 가장 좁은 조건을 풀거나 기간을 넓혀 보세요.</div>'
      :'<div class="empty"><b>조건에 맞는 뉴스가 없습니다</b>검색어를 지우거나 기간을 넓혀 보세요.</div>';
    document.querySelector('#counts').innerHTML=fmt('총 <b>{n}</b>건',all.length);
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
    ? fmt('총 <b>{n}</b>건, <b>{m}</b>건 표시',all.length,view.length)
    : fmt('총 <b>{n}</b>건, <b>{m}</b>건 표시',DATA.total==null?all.length:DATA.total,view.length)
      +(CFG.admin?'<span class="admin">'+fmt(', 보관 <b>{n}</b>건',archiveTotal)+'</span>':''));
  // Local: also require that the last request actually returned the whole window, so the
  // button disappears when the API's own limit caps the page instead of silently doing
  // nothing on every further click.
  document.querySelector('#more').hidden=!(PUBLIC
    ? all.length>view.length
    : (DATA.has_more&&view.length>=V.limit));
  const pend=PENDING[region()]||0,np=document.querySelector('#newpill');
  if(pend>0){np.textContent=fmt('새 글 {n}건 보기',pend);np.dataset.show='1'}
  else{np.dataset.show='0';np.textContent=''}
  const live=document.querySelector('#live');
  if(live)live.textContent=fmt('<b>{n}</b>건 표시 중',all.length)}
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
  if(regions)el.title=Object.keys(regions).map(k=>k+' '+
    (regions[k].count==null?'':fmt('{n}건',regions[k].count))).join(', ')}
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

// The keyword row and the search box are both text filters, so they stay mutually exclusive: a
// reader who picked keywords should not also be filtered by a leftover query, and a reader who
// typed one should not have keywords quietly narrowing the list. Every control that resets the
// filters calls this - that is what makes 전체 release a keyword instead of leaving the list stuck
// until the search box is cleared by hand, which needed going back a page.
function clearText(){
  V.q='';V.terms=[];
  const q=document.querySelector('#q');if(q&&q.value)q.value='';
  if(document.querySelector('#trend'))renderTrends()}

function buildQuery(){
  const p=new URLSearchParams();
  p.set('region',V.tab==='thai'?'태국':'글로벌');
  p.set('hours',V.hours);p.set('limit',V.limit);p.set('offset',V.offset);
  if(V.mode==='priority')p.set('priority',V.value||'5');
  else if(V.mode==='official')p.set('source_type','official');
  // Every selected condition goes into ONE request, and a repeated parameter means all of them:
  // the server ANDs terms and categories and matches any of several sources. This replaces the
  // path that fetched one request per (category, keyword) pair and merged them by link - that was
  // a union, the opposite of what selecting three things should do.
  // V.cats is a list; gating the old single-value branch on V.mode left a pill highlighted while
  // the server still returned the unfiltered list, so the values are read directly here.
  V.cats.forEach(c=>p.append('category',c));
  V.terms.forEach(t=>p.append('q',t));
  // A pick is one more condition, server-side, so it composes with everything else selected.
  if(V.pickOnly)p.set('picked','1');
  if(V.q)p.append('q',V.q);
  // Card chips set V.tag, not V.mode/V.value. Without this the local page sent an
  // unfiltered request, so clicking a chip only highlighted it and the list never moved.
  if(V.tag){if(V.tag.k==='cat')p.append('category',V.tag.v);else p.append('source',V.tag.v)}
  return p.toString()}

// --- the selected-condition row ----------------------------------------------------
// Every filter narrowing the list, each with what it returns on its own, and what all of them
// together return. A reader looking at "0건" needs to know which condition caused it: 관세 34건
// next to 트럼프 462건 with a total of 0 is a different situation from all three being small.
const COND={sig:'',counts:{}};
function condList(){
  const list=V.cats.map(c=>['cat',c]).concat(V.terms.map(t=>['term',t]));
  if(V.tag)list.push([V.tag.k==='cat'?'cat':'src',V.tag.v]);
  // The pick is a condition too, so it gets a count of its own and a way out from the same row as
  // everything else - which is what makes "0건" answerable.
  if(V.pickOnly)list.push(['pick',PICK]);
  return list}
function condKey(kind,value){return kind+':'+value}
function condHit(a,c){
  if(c[0]==='cat')return catList(a).indexOf(c[1])>=0;
  if(c[0]==='term')return termMatch((a.title||'')+' '+(a.summary||''),c[1]);
  if(c[0]==='pick')return !!a.picked;
  return a.source===c[1]}
function loadCondCounts(){
  const list=condList();
  const sig=V.tab+'|'+V.hours+'|'+list.map(c=>condKey(c[0],c[1])).join('|');
  if(COND.sig===sig)return;
  COND.sig=sig;COND.counts={};
  if(!list.length){renderConditions();return}
  if(PUBLIC){
    // The static copy has no API: these counts are what the rows it loaded contain, which is the
    // same basis its pill counts use.
    list.forEach(c=>{COND.counts[condKey(c[0],c[1])]=articles().filter(a=>condHit(a,c)).length});
    renderConditions();return}
  const p=new URLSearchParams({region:region(),hours:String(V.hours),limit:'1'});
  Promise.all(list.map(c=>{
    const q=new URLSearchParams(p.toString());
    if(c[0]==='cat')q.append('category',c[1]);
    else if(c[0]==='term')q.append('q',c[1]);
    else if(c[0]==='pick')q.set('picked','1');
    else q.append('source',c[1]);
    return fetch(API+'/api/news?'+q.toString(),{cache:'no-cache'})
      .then(r=>r.ok?r.json():null).catch(()=>null)}))
    .then(answers=>{answers.forEach((d,i)=>{if(d&&d.total!=null)COND.counts[condKey(list[i][0],list[i][1])]=d.total});
      renderConditions()})}
function renderConditions(){
  const el=document.querySelector('#conds');if(!el)return;
  const list=condList();
  if(!list.length){el.hidden=true;el.innerHTML='';COND.sig='';return}
  el.hidden=false;
  const counts=COND.counts||{},total=(DATA&&DATA.total!=null)?DATA.total:null;
  const known=list.filter(c=>counts[condKey(c[0],c[1])]!=null);
  const narrow=known.length>1?known.slice().sort(function(a,b){
    return counts[condKey(a[0],a[1])]-counts[condKey(b[0],b[1])]})[0]:null;
  el.innerHTML='<span class="clabel">선택한 조건</span>'+
    list.map(function(c){
      const key=condKey(c[0],c[1]),n=counts[key];
      // The kind is shown by the chip's style, not by a word: a keyword chip is outlined and a
      // category chip is filled. A text prefix would have to be translated, and a fragment like
      // "키워드 " also matches inside "지금 뜨는 키워드" in the translation pass.
      return '<button type="button" class="cbtn'+(c[0]==='term'?' kw':'')+
        '" data-cond-off="'+esc(key)+'" title="이 조건을 풉니다">'+esc(c[1])+
        (n==null?'':'<span class="n">'+n+'</span>')+'<span aria-hidden="true">\u2715</span></button>'}).join('')+
    '<span class="sum">'+(total==null?'':'\u2192 '+total+'\uAC74')+
      (narrow&&total===0?' \u00b7 <span class="warn">가장 좁은 조건: '+esc(narrow[1])+' ('+
        counts[condKey(narrow[0],narrow[1])]+'\uAC74)</span>':'')+'</span>'+
    (total===0&&V.hours<2160?'<button type="button" class="wide" data-cond-wide="1">'+
      '더 긴 기간에서 찾기</button>':'');
  el.querySelectorAll('[data-cond-off]').forEach(function(b){
    b.onclick=function(){dropCond(b.dataset.condOff)}});
  const wide=el.querySelector('[data-cond-wide]');
  if(wide)wide.onclick=function(){
    const h=document.querySelector('#hours');
    if(h){h.value='2160';h.onchange()}}}
function dropCond(key){
  const at=key.indexOf(':'),kind=key.slice(0,at),value=key.slice(at+1),i=
    kind==='cat'?V.cats.indexOf(value):(kind==='term'?V.terms.indexOf(value):-1);
  if(kind==='pick')V.pickOnly=false;
  else if(i>=0){if(kind==='cat')V.cats.splice(i,1);else V.terms.splice(i,1)}
  else if(V.tag&&V.tag.v===value)V.tag=null;
  V.limit=PAGE;V.offset=0;renderTrends();renderPills();fetchFeed()}

async function writeJSON(path,body){
  const r=await fetch(API+path,{method:'POST',headers:writeHeaders(),body:JSON.stringify(body||{})});
  if(!r.ok)throw Error(r.status);
  return r.json()}
// >>> operator-only
// --- hiding a story (operator only) --------------------------------------------------
// Hiding is a filter, not a delete: the row stays in the archive and the restore list is the way
// back. That is why the strip after a click matters - without it, a row that leaves the list looks
// like a lost story rather than a decision.
//
// The markers around this block are read by tools/probe_english_text.py: these labels are Korean on
// every page, because the operator's document is Korean, and they never render for a reader. Marked
// code that a reader can reach would hide a real gap from that check, so nothing else belongs here.
let HIDE_UNDO=null;
// The operator's controls on a card. Kept here, inside the marked block, because the labels are
// Korean and a reader's document carries this same script: the call site is one condition away.
function cardActs(a){
  return '<div class="acts"><a class="open" href="'+esc(a.link)+'" target="_blank" rel="noopener nofollow">원문 열기</a>'+
    '<button type="button" class="open" data-picklink="'+esc(a.link)+'" data-title="'+esc(a.title||'')+
      '" data-picked="'+(a.picked?'1':'0')+'">'+(a.picked?'Pick 해제':PICK_ICON+' Pick')+'</button>'+
    '<button type="button" class="open hide" data-hide="'+esc(a.link)+'" data-title="'+esc(a.title||'')+'">숨기기</button></div>'}
function renderUndo(){
  const el=document.querySelector('#undobar');if(!el)return;
  if(!HIDE_UNDO){el.hidden=true;el.innerHTML='';return}
  el.hidden=false;
  el.innerHTML='<span class="clabel">숨겼습니다</span><span class="utext">'+esc(HIDE_UNDO.title)+'</span>'+
    '<button type="button" class="cbtn" data-undo="1">되돌리기</button>';
  el.querySelector('[data-undo]').onclick=async()=>{
    const undone=HIDE_UNDO;HIDE_UNDO=null;renderUndo();
    try{await writeJSON('/api/unhide',{link:undone.link})}catch(e){alert('되돌리기 실패: '+e.message)}
    loadHidden();fetchFeed()}}
async function hideStory(link,title){
  try{await writeJSON('/api/hide',{link:link,title:title||''})}
  catch(e){alert('숨기기 실패: '+e.message);return}
  HIDE_UNDO={link:link,title:title||link};renderUndo();loadHidden();fetchFeed()}
// Teemo's Pick: the one thing this page writes that a reader is meant to see. The phrase is
// optional and asked for at the moment of picking, so a pick is never held up by an empty prompt -
// a cancel or a browser that refuses to show one still records the pick with no phrase.
function askPickNote(){
  try{return (window.prompt(PICK+' — 한 줄 문구 (비워도 됩니다)','')||'').trim().slice(0,300)}
  catch(e){return ''}}
async function togglePick(link,title,picked){
  const note=picked?'':askPickNote();
  try{await writeJSON(picked?'/api/unpick':'/api/pick',{link:link,note:note,title:title||''})}
  catch(e){alert('Pick 변경 실패: '+e.message);return}
  fetchFeed()}
async function loadHidden(){
  const el=document.querySelector('#hidden');if(!el)return;
  try{
    const d=await (await fetch(API+'/api/hidden',{cache:'no-cache'})).json();
    const rows=d.hidden||[];
    el.innerHTML=rows.length?rows.map(h=>'<div class="hidrow"><a href="'+esc(h.link)+
      '" target="_blank" rel="noopener nofollow">'+esc(h.title||h.link)+'</a>'+
      '<button type="button" class="unhide" data-unhide="'+esc(h.link)+'">되돌리기</button></div>').join('')
      :'<div class="note">숨긴 기사가 없습니다</div>';
    el.querySelectorAll('[data-unhide]').forEach(b=>b.onclick=async()=>{
      try{await writeJSON('/api/unhide',{link:b.dataset.unhide})}
      catch(e){alert('되돌리기 실패: '+e.message);return}
      if(HIDE_UNDO&&HIDE_UNDO.link===b.dataset.unhide){HIDE_UNDO=null;renderUndo()}
      loadHidden();fetchFeed()});
  }catch(e){el.innerHTML='<div class="note">목록을 불러오지 못했습니다</div>'}
}
// --- which sources the deployed pages show (operator only) --------------------------------
// The switch lives in the collection-status rows, because those rows are already the list of
// sources. It has nothing to filter here: a switched-off source is dropped by the server on every
// read path, so this is the switch itself. The state comes from the status answer, which carries
// source detail only for a session.
let OFF=null, SRC_STATE=null, SRC_MSG='';   // SRC_MSG survives the feed's redraw of the rows
function sourceSwitch(name){
  if(OFF===null)return '';
  const off=OFF.indexOf(name)>=0;
  return '<button type="button" class="sw" role="switch" aria-checked="'+(off?'false':'true')
    +'" data-source="'+esc(name)+'" title="'+(off?'공개로 되돌리기':'배포 페이지에서 감추기')
    +'"><span class="knob"></span></button>';
}
function srcNote(text){
  SRC_MSG=text||'';
  const el=document.querySelector('#sources');if(!el)return;
  let note=el.querySelector('#srcnote');
  if(!note){note=document.createElement('div');note.className='note';note.id='srcnote';el.append(note)}
  note.textContent=text||'';
  if(!text)note.remove();
}
async function loadSourceSwitches(){
  try{
    const d=await (await fetch(API+'/api/status',{cache:'no-cache'})).json();
    OFF=d.hidden_sources||[];SRC_STATE=d.sources||{};
  }catch(e){OFF=null}
  renderSources();renderPills();
}
async function switchSource(name){
  const off=OFF.indexOf(name)>=0;
  srcNote('저장 중…');
  try{
    const d=await writeJSON('/api/source',{source:name,hidden:!off});
    OFF=d.hidden_sources||OFF;
    const button=document.querySelector('#sources .sw[data-source="'+name+'"]');
    if(button){
      button.setAttribute('aria-checked',OFF.indexOf(name)>=0?'false':'true');
      const row=button.closest('.source');if(row)row.classList.toggle('off',OFF.indexOf(name)>=0);
    }
    srcNote(name+(off?' 공개로 되돌렸습니다':' 을 감췄습니다'));
    renderPills();
    fetchFeed();
  }catch(e){
    srcNote('저장하지 못했습니다 — '+e.message);
  }
}
  // ── 거르는 규칙 ──
  // A rule is described by what it caught, never by what it promises: every rule shows its catches,
  // and the catches can be read and kept before the rule is left on.
  let RULES=[],CAUGHT=[],FMSG='';
  function filterNote(text){
    FMSG=text||'';
    const el=document.querySelector('#fnote');if(el)el.textContent=text||'';
  }
  function ruleSwitch(id,on){
    return '<button type="button" class="sw" role="switch" aria-checked="'+(on?'true':'false')+'" data-rule="'+id
      +'" title="'+(on?'규칙 끄기 — 잡았던 기사가 돌아옵니다':'규칙 켜기')+'"><span class="knob"></span></button>';
  }
  function renderFilters(){
    const el=document.querySelector('#filters');if(!el)return;
    const on=RULES.filter(r=>r.enabled).length;
    let h='<div class="note">켜짐 '+on+'개 · 잡은 기사 '+CAUGHT.length+'건</div>';
    h+=RULES.length
      ?RULES.map(r=>'<div class="rule'+(r.enabled?'':' off')+'">'+ruleSwitch(r.id,r.enabled)
          +'<span class="rp" title="'+esc(r.pattern)+'">'+esc(r.pattern)+'</span>'
          +'<span class="rh">'+r.hits+'</span>'
          +'<button type="button" class="rx" data-del="'+r.id+'" title="규칙 지우기">✕</button></div>').join('')
      :'<div class="note">규칙 없음 — 숨긴 기사에서 뽑거나 직접 넣으세요</div>';
    if(CAUGHT.length){
      h+='<div class="note" style="margin-top:8px">규칙이 잡은 기사 '+CAUGHT.length+'건</div>';
      h+=CAUGHT.slice(0,6).map(c=>'<div class="caught"><span class="ct" title="'+esc(c.title||c.link)+'">'
          +esc(c.title||c.link)+'</span>'
          +'<button type="button" class="keep" data-keep="'+esc(c.link)+'" title="이 기사는 살립니다">살리기</button></div>').join('');
    }
    if(FMSG)h+='<div class="note">'+esc(FMSG)+'</div>';
    el.innerHTML=h;
    el.querySelectorAll('.sw').forEach(b=>b.onclick=()=>setRule(b.dataset.rule,b.getAttribute('aria-checked')!=='true'));
    el.querySelectorAll('.rx').forEach(b=>b.onclick=()=>setRule(b.dataset.del,null));
    el.querySelectorAll('.keep').forEach(b=>b.onclick=()=>keepStory(b.dataset.keep));
  }
  async function loadFilters(){
    try{
      const d=await (await fetch(API+'/api/filters',{cache:'no-cache'})).json();
      RULES=d.rules||[];CAUGHT=d.caught||[];
    }catch(e){FMSG='규칙을 불러오지 못했습니다'}
    renderFilters();
  }
  async function setRule(id,enable){
    filterNote('저장 중…');renderFilters();
    try{
      const d=await writeJSON('/api/filter',enable===null?{action:'delete',id:Number(id)}
                                                :{action:'set',id:Number(id),enabled:enable});
      RULES=d.rules||RULES;CAUGHT=d.caught||[];
      filterNote(enable===null?'규칙을 지웠습니다 — 잡혔던 기사가 돌아옵니다'
                :(enable?'규칙을 켰습니다':'규칙을 껐습니다 — 잡혔던 기사가 돌아옵니다'));
      renderFilters();fetchFeed();
    }catch(e){filterNote('저장하지 못했습니다 — '+e.message);renderFilters()}
  }
  async function addRule(){
    const input=document.querySelector('#fpattern');
    const pattern=input?input.value.trim():'';
    if(!pattern){filterNote('문구를 넣으세요');return}
    filterNote('더하는 중…');
    try{
      const d=await writeJSON('/api/filter',{action:'add',pattern:pattern});
      RULES=d.rules||RULES;CAUGHT=d.caught||[];
      if(input)input.value='';
      filterNote('규칙을 더했습니다 — 켜야 작동합니다');
      renderFilters();
    }catch(e){filterNote('더하지 못했습니다 — '+e.message);renderFilters()}
  }
  async function learnRules(){
    const before=RULES.length;
    filterNote('숨긴 기사에서 뽑는 중…');renderFilters();
    try{
      const d=await writeJSON('/api/filter',{action:'learn'});
      RULES=d.rules||RULES;CAUGHT=d.caught||[];
      filterNote(RULES.length>before?'후보 '+String(RULES.length-before)+'개를 올렸습니다 — 잡을 기사를 보고 켜세요'
                                    :'새로 뽑을 후보가 없습니다');
      renderFilters();
    }catch(e){filterNote('뽑지 못했습니다 — '+e.message);renderFilters()}
  }
  async function keepStory(link){
    filterNote('살리는 중…');
    try{
      const d=await writeJSON('/api/filter',{action:'keep',link:link});
      RULES=d.rules||RULES;CAUGHT=d.caught||[];
      filterNote('이 기사는 규칙을 통과해 살아납니다');
      renderFilters();fetchFeed();
    }catch(e){filterNote('살리지 못했습니다 — '+e.message);renderFilters()}
  }
  function wireFilters(){
    const add=document.querySelector('#fadd');if(add)add.onclick=addRule;
    const learn=document.querySelector('#flearn');if(learn)learn.onclick=learnRules;
    const input=document.querySelector('#fpattern');
    if(input)input.onkeydown=e=>{if(e.key==='Enter')addRule()};
  }
// <<< operator-only


async function fetchLocal(){
  const r=await fetch(API+'/api/news?'+buildQuery(),{cache:'no-cache'});
  if(!r.ok)throw Error(r.status);
  return r.json()}

function applyLocal(fresh){
  if(V.offset>0&&(DATA.articles||[]).length)fresh.articles=(DATA.articles||[]).concat(fresh.articles||[]);
  const before=(DATA.articles||[]).length?String(DATA.articles[0].published_at||''):'';
  if(before&&V.offset===0)(fresh.articles||[]).forEach(a=>{
    if(String(a.published_at||'')>before)a.fresh=true});
  DATA=fresh;
  archiveTotal=(fresh.archived_total!=null?fresh.archived_total:archiveTotal);
  try{localStorage.setItem(CACHE_KEY,JSON.stringify(DATA))}catch(e){}
  setStamp((fresh.updated_at_ict||'')+' · '+hoursLabel()+' · '+(fresh.total||0)+'건',fresh.region_counts);
  // The interval control shows what the collector is doing, restored value included, so the operator
  // never wonders whether the 5분 they chose is still in force after the next restart.
  const iv=document.querySelector('#interval');
  if(iv&&fresh.interval_seconds!=null)iv.value=String(fresh.interval_seconds);
  flagStale(fresh.updated_at);
  renderSources();renderPills();renderFeed()}

async function fetchFeed(){
  if(PUBLIC){try{await loadPublic(false)}catch(e){offline()}return}
  // Only the request is inside the try. Rendering used to be in here as well, so an error while
  // drawing the list was reported as a connection problem: the page looked fine and simply stopped
  // updating, which is the hardest kind of failure to notice. Now it reaches the console.
  let fresh=null;
  try{fresh=await fetchLocal()}
  catch(e){document.querySelector('#state')&&(document.querySelector('#state').textContent='재시도 중');
    renderFeed();return}
  applyLocal(fresh)}
function offline(){
  if(!articles().length){
    setStamp('연결 실패');
    document.querySelector('#feed').innerHTML='<div class="empty"><b>데이터를 불러오지 못했습니다</b>잠시 후 새로고침해 주세요.</div>'}}

function renderSources(){
  const el=document.querySelector('#sources');if(!el)return;
  // The feed's own map usually has it; the status answer is the fallback for the moment before a
  // collection cycle has run.
  const map=(Object.keys(DATA.sources||{}).length?DATA.sources:(SRC_STATE||{}));
  const rows=Object.entries(map);
  el.innerHTML=rows.length?rows.map(([name,s])=>
    '<div class="source'+((OFF&&OFF.indexOf(name)>=0)?' off':'')+'">'+sourceSwitch(name)+
    '<span>'+esc(name)+'</span><span class="'+(s.ok?'ok':'bad')+'">'+
      (s.ok?'정상 '+(s.count==null?0:s.count):'실패')+'</span></div>').join('')
    :'<div class="note">대기 중</div>';
  if(SRC_MSG)srcNote(SRC_MSG);
  el.querySelectorAll('.sw').forEach(b=>b.onclick=()=>switchSource(b.dataset.source));}
function renderGuide(){
  const el=document.querySelector('#tguide');if(!el)return;
  el.innerHTML=V.tab==='thai'
    ?'<h2>태국 소식</h2><p class="note">방콕포스트·카오솟·타이인콰이어러·프라차타이(영문), 타이랏·마티촌(태국어), 구글뉴스 태국·방콕·교민 검색을 모읍니다.</p><p class="note">비자·이민과 사고·재난을 우선 표시하며, 확정되지 않은 속보는 원문 확인 전까지 단정하지 않습니다.</p>'
    :'<h2>관찰 기준</h2><p class="note">금리·유동성, 미국 정책·트럼프, 지정학, ETF·기관 수급, 파생상품, 온체인, 스테이블코인, X 발언을 우선 수집합니다.</p><p class="note">뉴스 사실과 시장 해석을 분리합니다. X 게시물과 속보는 공식 발표나 원문 확인 전까지 확정 사실로 취급하지 않습니다.</p>'}

function setTab(next,silent){
  // The indicator tab toggles: pressing it again closes the panel and returns to the
  // last news tab. Previously the calendar stayed open above the feed once visited,
  // because it was shown with an inline style that the tab class could not undo.
  if(next==='cal'&&V.tab==='cal'&&!silent){setTab(V.lastNews||'global');return}
  if(next!=='cal')V.lastNews=next;
  V.tab=next;V.cats=[];V.tag=null;V.limit=PAGE;V.offset=0;V.mode='all';V.value='';V.pickOnly=false;clearText();
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
  document.querySelector('#cal-sum').textContent=fmt('앞으로 3일 일정 {n}건',total)
    +' · '+fmt('중요도 ★4 이상 {n}건',top)
    +' · '+'출처 나스닥 캘린더 · 연준 · 백악관 · Factba.se'
    +' · '+'시각 기준 KST(UTC+9) · 방콕은 여기서 2시간 뒤'
    +' · '+fmt('연준 인사 기준일 {n}',data.fed_roster_as_of||'?');
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
    // Typing no longer releases the keyword chips: a typed word and the chips are conditions on the
    // same axis and they are ANDed, which is what a reader selecting three things expects. The box
    // stays the immediate filter and "+ 조건 추가" turns what is in it into a chip.
    V.limit=PAGE;V.offset=0;fetchFeed()},350)};
document.querySelector('#qadd').onclick=()=>{
  const box=document.querySelector('#q'),value=(box.value||'').trim();
  if(!value)return;
  if(V.terms.indexOf(value)<0)V.terms.push(value);
  box.value='';V.q='';
  V.limit=PAGE;V.offset=0;renderTrends();fetchFeed()};
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
  const pickBtn=ev.target.closest('[data-picklink]');
  if(pickBtn){togglePick(pickBtn.dataset.picklink,pickBtn.dataset.title,pickBtn.dataset.picked==='1');return}
  const hide=ev.target.closest('[data-hide]');
  if(hide){hideStory(hide.dataset.hide,hide.dataset.title);return}
  const chip=ev.target.closest('.chip.tap');
  if(chip){const k=chip.dataset.k,v=chip.dataset.v;
    V.tag=(V.tag&&V.tag.k===k&&V.tag.v===v)?null:{k:k,v:v};
    // Chips compose with the pill rows and the keywords: everything selected is ANDed, so a card
    // chip is one more condition rather than a replacement for the rest.
    V.mode='all';V.value='';
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
    const r=await fetch(API+'/api/settings',{method:'POST',headers:writeHeaders(),
      body:JSON.stringify({interval:value})});
    if(!r.ok)throw Error(r.status);
    if(refreshTimer)clearInterval(refreshTimer);
    refreshTimer=setInterval(()=>{if(!hidden)fetchFeed()},value*1000);
    fetchFeed();
  }catch(e){alert('갱신 간격 변경 실패: '+e.message)}};
const logoutEl=document.querySelector('#logout');
if(logoutEl)logoutEl.onclick=async()=>{
  logoutEl.disabled=true;
  try{await fetch(API+'/api/logout',{method:'POST',headers:writeHeaders(),body:'{}'})}catch(e){}
  location.replace('/');};
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
  // A section landing links straight to a category: #cat=<stored value>. The filter state is
  // set before the first fetch rather than by pressing a pill, because the pills are only
  // built once data arrives and a click at this point would land on nothing.
  const catMatch=hash.match(/[#&]cat=([^&]+)/);
  if(catMatch){
    const wantFilter=decodeURIComponent(catMatch[1]);
    if(wantFilter&&wantFilter!=='전체'){V.cats=[wantFilter];V.tag=null;V.mode='all';V.value=''}
  }
  // The search box starts empty on every load. Restoring the last query meant a reload
  // silently kept filtering the list, which reads as the dashboard being stuck.
  skeleton();
  if(CFG.admin)loadHidden();
  if(CFG.admin)loadSourceSwitches();
  if(CFG.admin){wireFilters();loadFilters()}
  if(PUBLIC){fetchFeed();setInterval(()=>{if(!hidden&&V.tab!=='cal')fetchFeed()},300000)}
  else{fetchFeed();refreshTimer=setInterval(()=>{if(!hidden)fetchFeed()},30000)}
  if(V.tab==='cal')loadCalendar();
  setInterval(()=>{if(!hidden&&V.tab==='cal')loadCalendar()},900000);
})();
"""


def _lang_attr(code: str) -> str:
    return ' lang="%s"' % code if code else ""


def _pick_badge(item: dict) -> str:
    """Teemo's Pick as part of the first screen.

    A page read with scripts off, or one whose reader never triggers a fetch, still shows which
    stories the operator put their name on. Same markup the script renders, so the hover overlay
    that reveals a long phrase works here too.
    """
    if not item.get("picked"):
        return ""
    note = str(item.get("pick_note") or "")
    return ('<div class="pickbadge">\U0001f344 Teemo\'s Pick'
            + ('<span class="pnote">' + html.escape(note) + '</span>' if note else "")
            + '</div>')


def _ict_stamp(value) -> str:
    try:
        moment = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)[:16].replace("T", " ")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    shifted = moment.astimezone(datetime.timezone(datetime.timedelta(hours=7)))
    return shifted.strftime("%m-%d %H:%M")


def seed_feed(path: str, want_thai: bool, lang: str = "ko", limit: int = 25) -> str:
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
    return _seed_cards(items, want_thai, lang, limit)


def seed_from_db(db_path: str, region: str, want_thai: bool, lang: str,
                 limit: int = 25) -> str:
    """The same seed, read from a collector database instead of a generated JSON file.

    A deployed server collects into its own news.db and never runs the publishing step, so the
    JSON the static pages seed from does not exist there.

    The list column is optional here. A page is rebuilt as part of an update, and that can happen
    before the collector has restarted and added the column, so a database without it still seeds
    from the single stored value - a page with no seed is a first screen that only scripts fill in.
    """
    import sqlite3
    selects = (
        "SELECT title, summary, source, category, categories, link, published_at FROM articles "
        "WHERE region = ? AND title IS NOT NULL AND title != '' "
        "{hidden}ORDER BY published_at DESC LIMIT ?",
        "SELECT title, summary, source, category, NULL AS categories, link, published_at FROM articles "
        "WHERE region = ? AND title IS NOT NULL AND title != '' "
        "{hidden}ORDER BY published_at DESC LIMIT ?",
    )
    rows = []
    hidden = "" if not _has_table(db_path, "hidden_links") else "AND link NOT IN (SELECT link FROM hidden_links) "
    for query in selects:
        try:
            connection = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
            connection.row_factory = sqlite3.Row
            try:
                rows = connection.execute(query.format(hidden=hidden), (region, limit)).fetchall()
                break
            finally:
                connection.close()
        except sqlite3.Error:
            continue
    return _seed_cards(_with_picks(db_path, [dict(r) for r in rows]), want_thai, lang, limit)


def _with_picks(db_path: str, rows: list[dict]) -> list[dict]:
    """Mark the seeded rows the operator picked, from a read-only look at the same database."""
    import sqlite3
    if not rows or not _has_table(db_path, "picked_links"):
        return rows
    try:
        connection = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
        try:
            picks = {row[0]: (row[1] or "") for row in connection.execute("SELECT link, note FROM picked_links")}
        finally:
            connection.close()
    except sqlite3.Error:
        return rows
    for row in rows:
        note = picks.get(row.get("link"))
        row["picked"] = note is not None
        row["pick_note"] = note or ""
    return rows


def _has_table(db_path: str, name: str) -> bool:
    """Whether this database has a table yet.

    The page is built before the collector restarts, and that is what adds these tables, so a build
    against a database from just before a change must not fail - it seeds without that clause for
    one run, and the next build (after the collector has started) is complete again.
    """
    import sqlite3
    try:
        connection = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    except sqlite3.Error:
        return False
    try:
        found = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
        return bool(found)
    except sqlite3.Error:
        return False
    finally:
        connection.close()


def _seed_labels(item: dict) -> list:
    """The labels a seeded card shows.

    The published JSON carries a list; a row read straight out of a collector database carries the
    comma-joined column; a row written before the column existed carries only `category`.
    """
    raw = item.get("categories")
    if isinstance(raw, (list, tuple)):
        names = [str(x) for x in raw if x]
    else:
        names = [part for part in str(raw or "").split(",") if part]
    if not names:
        names = [str(item.get("category") or "")]
    return [name for name in names if name]


def _seed_cards(items: list, want_thai: bool, lang: str, limit: int = 25) -> str:
    rows = []
    labels = ui_text.cat_labels(lang)
    for item in items[:limit]:
        title = str(item.get("title") or "")
        summary = str(item.get("summary") or "")
        if not title:
            continue
        # Per element, like the script does: a Thai headline with an English summary is one card and
        # two languages, and one attribute for both makes a browser translator mangle half of it.
        title_attr = _lang_attr(taxonomy.detect_lang(title))
        summary_attr = _lang_attr(taxonomy.detect_lang(summary))
        chips = "".join('<span class="chip">' + html.escape(labels.get(name, name)) + '</span>'
                        for name in _seed_labels(item))
        badge = _pick_badge(item)
        rows.append(
            '<article class="card seed' + (" th" if want_thai else "") + '">'
            '<div class="meta"><span class="chip src">' + html.escape(str(item.get("source") or "")) + '</span>'
            + chips +
            '<span>' + html.escape(_ict_stamp(item.get("published_at"))) + '</span></div>'
            + badge +
            '<h2 class="title"' + title_attr + '><a href="' + html.escape(str(item.get("link") or ""))
            + '" target="_blank" rel="noopener nofollow">' + html.escape(title) + '</a></h2>'
            '<p class="summary clamp"' + summary_attr + '>' + html.escape(summary) + '</p>'
            '</article>')
    return "".join(rows)


def _langbar(lang: str, alt: str) -> str:
    """Language links. Plain anchors, so the switcher works with scripts disabled."""
    if not alt:
        return ""
    parts = []
    for code, label in ((c, ui_text.LANG_LABEL[c]) for c in ui_text.LANGS):
        if code == lang:
            parts.append('<b aria-current="true">%s</b>' % label)
        else:
            parts.append('<a href="%s" lang="%s">%s</a>' % (alt, code, label))
    return '<nav class="langbar" aria-label="Language">%s</nav>' % "".join(parts)


def _phrase_table(lang: str) -> list[tuple[str, str]]:
    """Korean phrase -> this language's phrase, longest first so a shorter phrase inside a
    longer one cannot be replaced first (발표 before 실적 발표 would mangle the label)."""
    ko, other = ui_text.UI["ko"], ui_text.UI[lang]
    pairs = {}
    for key, value in ko.items():
        if value and value != other[key]:
            pairs.setdefault(value, other[key])
    return sorted(pairs.items(), key=lambda kv: -len(kv[0]))


def localize(page: str, lang: str) -> str:
    """Rewrite interface text into `lang`. Category values, region names and the trend word
    lists are deliberately absent from the table: they are data, not interface."""
    if lang == "ko":
        return page
    for source, target in _phrase_table(lang):
        page = page.replace(source, target)
    return page


def render(*, public: bool, datadir: str, want_thai: bool, icon_prefix: str, admin: bool,
           lang: str = "ko", alt: str = "", seed_path: str = "",
           seed_html: str = "") -> str:
    config = {
        "public": public,
        "datadir": datadir,
        "wantThai": want_thai,
        "admin": admin,
        "api": "",
        "calendar": "https://raw.githubusercontent.com/freaky0/teemobkk-live-news/main/docs/calendar.json",
        "lang": lang,
        "catLabels": ui_text.cat_labels(lang),
    }
    stamp = ('<div class="stamp"><span id="state">연결 중</span> <b id="updated">-</b>'
             if admin else '<div class="stamp">업데이트 <b id="updated">-</b>')
    admin_toolbar = ('' if not admin else
                     '<label class="note admin" for="interval">갱신</label>'
                     '<select id="interval" class="admin" aria-label="갱신 간격">'
                     '<option value="10">10초</option><option value="30">30초</option>'
                     '<option value="60" selected>1분</option><option value="120">2분</option>'
                     '<option value="300">5분</option></select>'
                     # The way out of a session belongs with the other operator controls, and only
                     # on the page that was served to a session in the first place.
                     + LOGOUT_CONTROL)
    side = ('' if not admin else
            '<aside class="side admin"><div class="box"><h2>수집 상태</h2><div id="sources">'
            '<div class="note">대기 중</div></div></div>'
            # The rules live next to the collection state because both are the operator's
            # decisions about what comes in: the switches work on a source, the rules on a
            # wording. A rule arrives off and shows what it would catch, because filtering a
            # whole shape of story is a judgement that has to be read before it is made.
            '<div class="box"><h2>거르는 규칙</h2>'
            '<div id="filters"><div class="note">불러오는 중…</div></div>'
            '<div class="frow"><input id="fpattern" placeholder="문구 — 제목·요약에 있으면 뺀다" maxlength="120">'
            '<button type="button" id="fadd">추가</button></div>'
            '<button type="button" class="wide" id="flearn">숨긴 기사에서 규칙 뽑기</button>'
            '<div class="note" id="fnote"></div></div>'
            # The restore list lives with the other operator panels. A hidden story is never in the
            # feed again, so this is the only place it can be brought back from.
            '<div class="box"><h2>숨긴 기사</h2><div id="hidden"><div class="note">불러오는 중</div></div></div>'
            '<div class="box" id="tguide"></div></aside>')
    undobar = ('' if not admin else
               '<section class="undobar" id="undobar" hidden></section>')
    og = ('' if admin else
          '<meta name="description" content="비트코인·매크로·태국 뉴스를 5분마다 모아 보여주는 실시간 대시보드. 경제지표와 주요 일정 포함.">\n'
          '<meta property="og:title" content="TeemoBKK Live News">\n'
          '<meta property="og:description" content="비트코인·매크로·태국 뉴스 실시간 대시보드. 경제지표·연설·실적 일정 포함.">\n'
          '<meta property="og:type" content="website">\n'
          '<meta property="og:image" content="' + icon_prefix + 'og-image.png">\n'
          '<meta name="twitter:card" content="summary_large_image">\n')
    title = "TeemoBKK Live News" + (" · 태국 소식" if want_thai else "")
    # Back to the section that introduced this dashboard.
    home = "/thai/" if want_thai else "/"
    langbar = _langbar(lang, alt)
    script = SCRIPT.replace("__CONFIG__", json.dumps(config, ensure_ascii=False, separators=(",", ":")))
    script = script.replace("__CATS_GLOBAL__", json.dumps(
        ui_text.cats(lang)["global"], ensure_ascii=False, separators=(",", ":")))
    script = script.replace("__CATS_THAI__", json.dumps(
        ui_text.cats(lang)["thai"], ensure_ascii=False, separators=(",", ":")))
    seed = seed_html or (seed_feed(seed_path, want_thai, lang) if seed_path else "")
    page = f"""<!doctype html>
<html lang="{lang}">
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
      <a class="brand" href="{home}">TeemoBKK Live News</a>
      <h1>실시간 뉴스 대시보드</h1>
    </div>
    <div class="spacer"></div>
    {langbar}
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
    <button id="qadd" class="qadd" type="button" title="검색어를 조건으로 고정합니다">+ 조건 추가</button>
    <select id="hours" aria-label="기간">
      <option value="1">최근 1시간</option>
      <option value="6">최근 6시간</option>
      <option value="12">최근 12시간</option>
      <option value="24" selected>최근 24시간</option>
      <option value="168">최근 7일</option>
      <option value="2160">전체 기간</option>
    </select>
    {admin_toolbar}
    <button id="newpill" class="newpill" type="button"></button>
    <span class="count" id="counts"></span>
  </section>

  <section class="trend" id="trend" hidden></section>
  <section class="conds" id="conds" hidden></section>
{undobar}

  <section id="filters-global" class="pills"></section>
  <section id="filters-thai" class="pills th" hidden></section>

  <div class="layout">
    <section>
      <div id="feed" class="feed">__SEED__</div>
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
    page = localize(page, lang).replace("__SEED__", seed)
    return page


def write(path: Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return len(text.encode("utf-8"))


# Where each published address should send its reader. The domain was split into sections
# (/news, /thai) and the collector runs on its own host, so these addresses are old links.
MOVED = {
    "docs/index.html": "https://teemobkk.io/",
    "docs/ko/index.html": "https://teemobkk.io/news/ko/",
    "docs/thai/index.html": "https://teemobkk.io/thai/",
    "docs/ko/thai/index.html": "https://teemobkk.io/thai/news/ko/",
}

REDIRECT = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TeemoBKK</title>
<link rel="canonical" href="__TO__">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url=__TO__">
<style>
html{background:#05070d;color:#8b9bbd;font:14px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;text-align:center}
b{display:block;color:#eef3ff;font-size:17px;letter-spacing:-.02em;margin-bottom:10px}
a{color:#64d7ff;word-break:break-all}
</style>
</head>
<body>
<main>
<b>TeemoBKK has moved.</b>
<a href="__TO__">__TO__</a>
</main>
<script>location.replace("__TO__");</script>
</body>
</html>
"""


def redirect_page(to: str) -> str:
    """A pointer, not a second copy.

    These addresses were published before the domain was split into sections, so links to them
    exist and must keep working. A copy of the dashboard here would be stale the moment the
    collector moved on, and a reader landing on it would have no way to know. So: a meta refresh
    for the browser, a real link for a reader whose refresh is blocked, and noindex so the old
    address is not what a search result offers.
    """
    return REDIRECT.replace("__TO__", to)


def build_public() -> dict[str, int]:
    """Write the published pages as redirects to the live site.

    Only docs/ is touched. An earlier version also rewrote the local page at the repository
    root, which left an unstaged modification in the CI working tree on every run, so
    `git pull --rebase` refused to start ("cannot pull with rebase: You have unstaged changes")
    and the published site silently stopped updating while the workflow still reported a run
    every five minutes.

    The redirects are rewritten every cycle on purpose: whatever the publish step does, the old
    address must not come back as a copy of the dashboard.
    """
    sizes = {}
    for name, to in MOVED.items():
        sizes[name] = write(ROOT / name, redirect_page(to))
    return sizes


def _prune_sections(keep) -> list:
    """Delete generated section directories that are not part of the current layout.

    A section path can change - the Thailand dashboard moved from /thai/ to /thai/news/ when the
    section gained a front page - and the old directory stays on the host. A directory that still
    holds an index.html keeps answering at its old address, so the redirect written for that
    address never runs and readers keep getting the previous layout out of a stale file.
    Only the section trees are walked; docs/ and the repository root are never touched.
    """
    keep = {Path(p) for p in keep}
    removed = []
    for section in ("news", "thai"):
        base = ROOT / section
        if not base.is_dir():
            continue
        for dirpath, _dirnames, filenames in os.walk(base, topdown=False):
            here = Path(dirpath)
            if "index.html" in filenames and here not in keep:
                shutil.rmtree(here)
                removed.append(here.relative_to(ROOT).as_posix())
    return removed


def build_server(db_path: str = "news.db") -> dict[str, int]:
    """The pages a deployed server serves: dynamic API data, no operator panels.

    `public=True` (the published static pages) means the script reads pre-generated JSON;
    `public=False` means it reads the API, which is what a server wants so that filtering and
    paging cover the whole stored window. `admin=False` drops the collection panel, the archive
    count and the original-link control, which are the operator's view.

    Sections are separate documents - /news and /thai - so the domain can also host a blog and
    indicator pages later. Each has an English default and a Korean copy one directory down,
    which keeps the language switcher a plain relative link.
    """
    sizes = {}
    global_seed = seed_from_db(db_path, "\uae00\ub85c\ubc8c", False, "en")
    thai_seed = seed_from_db(db_path, "\ud0dc\uad6d", True, "en")
    # The section roots are in the keep set: build_server writes them (the section front pages and
    # the news dashboard), and pruning them first would leave a window where nothing answers.
    targets = ("news", "news/ko", "thai", "thai/news", "thai/news/ko")
    pruned = _prune_sections(ROOT / t for t in targets)
    for gone in pruned:
        print("removed stale section %s (its address now redirects)" % gone)
    sizes["index.html"] = write(ROOT / "index.html", landing.render_landing())
    sizes["thai/index.html"] = write(ROOT / "thai" / "index.html",
                                     landing_thai.render_thai_landing())
    # Sections: /news is the market dashboard, /thai introduces the Thailand material and
    # /thai/news is its dashboard. Each has an English default and a Korean copy one level
    # down, so the language switcher stays a plain relative link.
    for section, want_thai, seed in (("news", False, global_seed),
                                     ("news/ko", False, global_seed),
                                     ("thai/news", True, thai_seed),
                                     ("thai/news/ko", True, thai_seed)):
        code = "ko" if section.endswith("/ko") else "en"
        alt = "../index.html" if code == "ko" else "ko/index.html"
        sizes["%s/index.html" % section] = write(
            ROOT / section / "index.html",
            render(public=False, datadir="", want_thai=want_thai, icon_prefix="/",
                   admin=False, lang=code, alt=alt, seed_html=seed))
    return sizes


def build_all() -> dict[str, int]:
    """Rewrite the local page and both published pages (used when building by hand)."""
    sizes = {"index.html": write(ROOT / "index.html", admin_page())}
    sizes.update(build_public())
    return sizes


LOGOUT_CONTROL = ('<button type="button" id="logout" class="admin" '
                  'aria-label="로그아웃">로그아웃</button>')


def admin_page(icon_prefix: str = "") -> str:
    """The operator's dashboard as a string, for the collector to answer /admin with.

    Same document the public sees, built with the operator panels and configured to read the API
    rather than a pre-generated JSON file. It is returned rather than written: the deployment serves
    its section pages from disk, so a file like this placed among them would be public, and the
    collector is the only thing that should ever hand it out - and only to a session.

    `icon_prefix` stays relative by default, which is what the page opened from disk needs; the
    collector passes "/" because it answers a path with a directory in it.
    """
    return render(public=False, datadir="", want_thai=False, icon_prefix=icon_prefix, admin=True,
                  lang="ko", seed_path=str(DOCS / "global-recent.json"))


if __name__ == "__main__":
    for name, size in build_all().items():
        print("wrote %s (%d bytes)" % (name, size))
