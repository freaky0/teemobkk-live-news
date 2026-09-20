// The source switches, from the operator's side of the page.
//
// The write path is stubbed on purpose: switching a real source off would take its stories out of
// the feed the operator is looking at, and a check must not edit the data it inspects. What is
// checked is the wiring - the panel is on the operator page, it draws one switch per collected
// source, a switched-off source is shown as off, and pressing a switch posts the source and the new
// state and redraws from the answer.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
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

const OFF_SOURCE = 'CoinNess';
const ON_SOURCE = 'Reuters';
let calls = [];
let hiddenNow = [OFF_SOURCE];

function stubFetch(realFetch) {
  return async (u, o) => {
    const path = String(u).replace(/^https?:\/\/[^/]+/, '');
    const method = ((o && o.method) || 'GET').toUpperCase();
    if (path.startsWith('/api/source')) {
      calls.push({ path, method, body: JSON.parse((o && o.body) || '{}') });
      hiddenNow = JSON.parse((o && o.body) || '{}').hidden ? [OFF_SOURCE] : [];
      return { ok: true, json: async () => ({ ok: true, source: OFF_SOURCE, hidden: hiddenNow.length > 0,
                                              hidden_sources: hiddenNow }) };
    }
    if (path.startsWith('/api/status')) {
      return { ok: true, json: async () => ({
        article_count: 2, region_counts: { '글로벌': 2 },
        sources: { [ON_SOURCE]: { ok: true, count: 12 }, [OFF_SOURCE]: { ok: true, count: 4 } },
        hidden_sources: hiddenNow }) };
    }
    if (path.startsWith('/api/hidden')) return { ok: true, json: async () => ({ hidden: [] }) };
    return realFetch(new URL(String(u), URL_).href,
      { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default', method });
  };
}

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) { w.fetch = stubFetch(fetch); },
  });
  const d = dom.window.document;

  const panel = () => d.querySelector('#srcpanel');
  const rows = () => Array.from(d.querySelectorAll('#srcpanel .srcrow'));
  const sw = (name) => d.querySelector('#srcpanel .sw[data-source="' + name + '"]');
  const state = (name) => (sw(name) ? sw(name).getAttribute('aria-checked') : '없음');

  await waitFor(() => panel() && panel().querySelectorAll('.sw').length > 0);
  check('운영자 페이지에 소스 공개 상자가 있음', !!panel());
  check('소스마다 스위치가 하나씩', rows().length === 2, rows().length + '개');
  check('스위치가 켜짐/꺼짐을 구분함', state(ON_SOURCE) === 'true' && state(OFF_SOURCE) === 'false',
    ON_SOURCE + '=' + state(ON_SOURCE) + ' ' + OFF_SOURCE + '=' + state(OFF_SOURCE));
  const offRow = d.querySelector('#srcpanel .srcrow.off .srcname');
  check('감춘 소스는 줄에 표시가 붙음', !!offRow && offRow.textContent === OFF_SOURCE,
    offRow ? offRow.textContent : '없음');
  const note = d.querySelector('#srcnote');
  check('숨김 개수를 알려 줌', !!note && note.textContent.indexOf('숨김 1개') >= 0,
    note ? note.textContent.trim().slice(0, 40) : '없음');

  // pressing a switch sends the source and the new state
  sw(OFF_SOURCE).click();
  await waitFor(() => calls.length > 0);
  const post = calls[0] || {};
  check('스위치를 누르면 저장 요청을 보냄', post.path === '/api/source' && post.method === 'POST',
    (post.path || '') + ' ' + (post.method || ''));
  check('감춘 소스를 다시 누르면 공개로 되돌림',
    post.body && post.body.source === OFF_SOURCE && post.body.hidden === false,
    JSON.stringify(post.body || {}));
  await waitFor(() => state(OFF_SOURCE) === 'true');
  check('저장 뒤 화면이 새 상태로 다시 그려짐', state(OFF_SOURCE) === 'true', state(OFF_SOURCE));

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
