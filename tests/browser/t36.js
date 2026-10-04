// Hiding a story, from the operator's side of the page.
//
// The write path is stubbed here on purpose: a check that hides a real article would remove it from
// the archive the operator is looking at, and a test must not edit the data it is inspecting. What
// is checked is the wiring - the control exists on the operator page only, it posts the link, the
// undo strip appears and posts the way back, and the restore list does the same.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
// The reader's copy is not loaded from here: the public documents are built by the deployment and
// do not exist on a development machine. What must not appear on them is checked where they are
// built instead (tests/test_admin_page.py, which reads the documents themselves).
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (fn, ms = 20000, step = 300) => {
  const until = Date.now() + ms;
  while (Date.now() < until) { if (fn()) return true; await sleep(step); }
  return false;
};
const pass = [];
const check = (n, ok, d) => { pass.push(ok); console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', n, d ? '  (' + d + ')' : ''); };

const STUB_LINK = 'https://example.com/hidden-story';
let calls = [];

function stubFetch(w, realFetch) {
  return async (u, o) => {
    const path = String(u).replace(/^https?:\/\/[^/]+/, '');
    const method = ((o && o.method) || 'GET').toUpperCase();
    if (path.startsWith('/api/hide') || path.startsWith('/api/unhide')) {
      calls.push({ path, method, headers: (o && o.headers) || {}, body: JSON.parse((o && o.body) || '{}') });
      const ok = { ok: true, json: async () => ({ ok: true, hidden_total: 1 }) };
      return ok;
    }
    if (path.startsWith('/api/hidden')) {
      calls.push({ path, method, headers: (o && o.headers) || {}, body: {} });
      return { ok: true, json: async () => ({ hidden: [{ link: STUB_LINK, title: '가려진 예시 기사', source: 'Example', hidden_at: 'now' }], total: 1 }) };
    }
    return realFetch(new URL(String(u), URL_).href,
      { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default', method });
  };
}

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) { w.fetch = stubFetch(w, fetch); },
  });
  const w = dom.window, d = w.document;
  await waitFor(() => d.querySelectorAll('#feed .card').length > 0);
  await sleep(1200);

  const cards = () => Array.from(d.querySelectorAll('#feed .card'));
  const undoBar = () => d.querySelector('#undobar') || {};
  const undoText = () => (undoBar().textContent || '').replace(/\s+/g, ' ').trim();
  const hiddenPanel = () => d.querySelector('#hidden') || {};
  const posts = (p) => calls.filter((c) => c.path.startsWith(p));

  // This page is the operator's, so hiding is offered on every card.
  const hides = cards().map((c) => c.querySelector('[data-hide]')).filter(Boolean);
  check('카드마다 숨기기 컨트롤이 있음', hides.length === cards().length && hides.length > 0,
    hides.length + '/' + cards().length);
  check('되돌리기 띠가 준비되어 있음', !!d.querySelector('#undobar'));
  check('숨긴 기사 패널이 있음', /숨긴 기사/.test((hiddenPanel().textContent || '') + (d.querySelector('.side') || {}).textContent));
  check('처음에는 되돌리기 띠가 숨겨져 있음', undoBar().hidden === true, String(undoBar().hidden));

  const firstLink = hides[0].dataset.hide;
  const firstTitle = hides[0].dataset.title;
  hides[0].click();
  await sleep(1500);

  const hideCall = posts('/api/hide')[0];
  check('숨기기 클릭이 링크를 보냄', !!hideCall && hideCall.body.link === firstLink,
    hideCall ? hideCall.body.link.slice(0, 46) : '호출 없음');
  check('제목도 함께 보냄', !!hideCall && hideCall.body.title === firstTitle,
    hideCall ? (hideCall.body.title || '').slice(0, 30) : '없음');
  check('숨긴 뒤 되돌리기 띠가 뜸', undoBar().hidden === false && /되돌리기/.test(undoText()),
    undoText().slice(0, 60));
  check('띠가 방금 숨긴 기사를 가리킴', undoText().indexOf((firstTitle || '').slice(0, 20)) >= 0,
    undoText().slice(0, 60));

  const undo = undoBar().querySelector('[data-undo]');
  check('띠에 되돌리기 버튼이 있음', !!undo);
  if (undo) {
    undo.click();
    await sleep(1500);
    check('되돌리기가 같은 링크를 보냄', posts('/api/unhide').length === 1
      && posts('/api/unhide')[0].body.link === firstLink,
      posts('/api/unhide').length ? posts('/api/unhide')[0].body.link.slice(0, 46) : '호출 없음');
    check('되돌린 뒤 띠가 사라짐', undoBar().hidden === true, String(undoBar().hidden));
  }

  // The restore list is the only place a hidden story can come back from, so it has to work on its own.
  const row = hiddenPanel().querySelector('.hidrow');
  check('숨긴 목록에 항목이 그려짐', !!row, (hiddenPanel().textContent || '').slice(0, 50));
  if (row) {
    const panelUndo = row.querySelector('[data-unhide]');
    check('목록 항목에 되돌리기가 있음', !!panelUndo);
    const before = posts('/api/unhide').length;
    if (panelUndo) {
      panelUndo.click();
      await sleep(1200);
      check('목록의 되돌리기가 그 링크를 보냄',
        posts('/api/unhide').length === before + 1
        && posts('/api/unhide').slice(-1)[0].body.link === STUB_LINK,
        posts('/api/unhide').slice(-1)[0].body.link.slice(0, 46));
    }
  }

  const bad = pass.filter((x) => !x).length;
  console.log('\n  %d/%d', pass.length - bad, pass.length);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.log('  [error]', e.message); process.exit(1); });
