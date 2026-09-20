"""스위치를 수집 상태 패널 안으로 옮기고, 감춘 소스는 알약에서도 뺀다.

사용자 지시: 별도 '소스 공개' 상자를 만들지 말고 수집 상태 행 왼쪽에 스위치만 달 것, 그리고 소스
알약에서도 감춘 소스를 뺄 것. 스위치 자체는 그대로 서버 DB에 저장되고 서버가 읽기 경로에서 거른다.
"""
import ast
import io

P = "C:/AI/Work_Folders/News_Macros/live_news_dashboard/page_build.py"
text = io.open(P, encoding="utf-8").read()
NL = "\n"


def splice(text, start_marker, end_marker, replacement, label):
    i = text.index(start_marker)
    j = text.index(end_marker, i) + len(end_marker)
    print("  %-18s %d자 교체" % (label, j - i))
    return text[:i] + replacement + text[j:]


# ── 1. 별도 상자를 없앤다 ───────────────────────────────────────────────────────────────────────
BOX_LINE = ("            '<div class=\"box\"><h2>소스 공개</h2><div id=\"srcpanel\">"
            "<div class=\"note\">불러오는 중</div></div></div>'" + NL)
assert BOX_LINE in text, "box line missing"
text = text.replace(BOX_LINE, "", 1)
print("  별도 상자 제거")

# ── 2. 스위치는 수집 상태 행 왼쪽에, 알약에서는 제외 ────────────────────────────────────────────
text = text.replace("  const srcs=th?THAI_SRC:GLOBAL_SRC;",
                    "  // A source the operator switched off is dropped by the server, so a pill for it would\n"
                    "  // return nothing: leave it out rather than offer a filter that cannot match.\n"
                    "  const srcs=(th?THAI_SRC:GLOBAL_SRC).filter(s=>!(OFF&&OFF.indexOf(s)>=0));", 1)

OLD_RENDER = '''function renderSources(){
  const el=document.querySelector('#sources');if(!el)return;
  const rows=Object.entries(DATA.sources||{});
  el.innerHTML=rows.length?rows.map(([name,s])=>
    '<div class="source"><span>'+esc(name)+'</span><span class="'+(s.ok?'ok':'bad')+'">'+
      (s.ok?'정상 '+(s.count==null?0:s.count):'실패')+'</span></div>').join('')
    :'<div class="note">대기 중</div>'
  if(CFG.admin)renderSourcePanel();}'''

NEW_RENDER = '''function renderSources(){
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
  el.querySelectorAll('.sw').forEach(b=>b.onclick=()=>switchSource(b.dataset.source));}'''

assert OLD_RENDER in text, "renderSources not found"
text = text.replace(OLD_RENDER, NEW_RENDER, 1)
print("  수집 상태 행에 스위치 추가")

# ── 3. 패널 JS 를 스위치 부품으로 바꾼다 ────────────────────────────────────────────────────────
JS_NEW = '''// --- which sources the deployed pages show (operator only) --------------------------------
// The switch lives in the collection-status rows, because those rows are already the list of
// sources. It has nothing to filter here: a switched-off source is dropped by the server on every
// read path, so this is the switch itself. The state comes from the status answer, which carries
// source detail only for a session.
let OFF=null, SRC_STATE=null;
function sourceSwitch(name){
  if(OFF===null)return '';
  const off=OFF.indexOf(name)>=0;
  return '<button type="button" class="sw" role="switch" aria-checked="'+(off?'false':'true')
    +'" data-source="'+esc(name)+'" title="'+(off?'공개로 되돌리기':'배포 페이지에서 감추기')
    +'"><span class="knob"></span></button>';
}
function srcNote(text){
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
'''

text = splice(text, "// --- which sources the deployed pages show", "// <<< operator-only", JS_NEW, "패널 JS")

# ── 4. 안 쓰는 CSS 를 정리하고 스위치를 행 안에 맞춘다 ──────────────────────────────────────────
i = text.find(".srcrow{display:flex")
j = text.find(".sw[aria-checked=\"true\"] .knob{left:18px;background:var(--accent)}")
assert 0 < i < j, "panel CSS not found"
j += len(".sw[aria-checked=\"true\"] .knob{left:18px;background:var(--accent)}")
CSS_NEW = ("/* the switch sits in the collection-status row, left of the name */" + NL +
           ".source.off > span:first-of-type{color:var(--muted);text-decoration:line-through}" + NL +
           ".source > span:first-of-type{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;"
           "white-space:nowrap}" + NL +
           ".sw{flex:0 0 auto;width:34px;height:18px;border-radius:999px;border:1px solid var(--line2);"
           "background:var(--panel2);position:relative;cursor:pointer;padding:0}" + NL +
           ".sw .knob{position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;"
           "background:var(--muted);transition:left .14s}" + NL +
           '.sw[aria-checked="true"]{border-color:var(--accent);background:rgba(100,215,255,.18)}' + NL +
           '.sw[aria-checked="true"] .knob{left:18px;background:var(--accent)}')
text = text[:i] + CSS_NEW + text[j:]
print("  CSS 정리")

io.open(P, "w", encoding="utf-8", newline="").write(text)
src = io.open(P, encoding="utf-8").read()
ast.parse(src)
bad = [c for c in src if 0x1100 <= ord(c) <= 0x11FF or ord(c) == 0xFFFD]
print("  ast OK · 자모 손상 %d · srcpanel %d · sourceSwitch %d · OFF 필터 %d"
      % (len(bad), src.count("srcpanel"), src.count("sourceSwitch"), src.count("OFF.indexOf(s)")))
