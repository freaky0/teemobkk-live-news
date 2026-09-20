// The source switches: in the collection-status rows, and the pills that follow them.
//
// The write path is stubbed on purpose: switching a real source off would take its stories out of
// the feed the operator is looking at, and a check must not edit the data it inspects. What is
// checked is the wiring - one switch per collected source, left of its name, the name struck
// through while it is off, a switched-off source gone from the source pills, and a press posting
// the source and the new state.
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

const OFF_SOURCE = 'CoinNess';       // a name that is also one of the source pills
const ON_SOURCE = 'Reuters';
const now = Date.now();
let calls = [];
let hiddenNow = [OFF_SOURCE];

const ARTICLES = [
  { title: '보이는 기사', summary: '요약', link: 'https://e/1', source: ON_SOURCE, source_type: 'rss',
    region: '글로벌', category: '시장·가격', priority: 3,
    published_at: new Date(now - 600000).toISOString() },
];

function stubFetch(realFetch) {
  return async (u, o) => {
    const path = String(u).replace(/^https?:\/\/[^/]+/, '');
    const method = ((o && o.method) || 'GET').toUpperCase();
    if (path.startsWith('/api/source')) {
      calls.push({ path, method, body: JSON.parse((o && o.body) || '{}') });
      hiddenNow = JSON.parse((o && o.body) || '{}').hidden ? [OFF_SOURCE] : [];
      return { ok: true, json: async () => ({ ok: true, source: OFF_SOURCE,
                                              hidden: hiddenNow.length > 0, hidden_sources: hiddenNow }) };
    }
    if (path.startsWith('/api/status')) {
      return { ok: true, json: async () => ({
        article_count: 1, region_counts: { '글로벌': 1 },
        sources: { [ON_SOURCE]: { ok: true, count: 12 }, [OFF_SOURCE]: { ok: true, count: 4 } },
        hidden_sources: hiddenNow }) };
    }
    if (path.startsWith('/api/hidden')) return { ok: true, json: async () => ({ hidden: [] }) };
    if (path.startsWith('/api/news')) {
      return { ok: true, json: async () => ({
        articles: ARTICLES, total: ARTICLES.length, has_more: false, hours: 24, limit: 25, offset: 0,
        returned: ARTICLES.length, region_counts: { '글로벌': 1 },
        updated_at: new Date(now - 300000).toISOString(), updated_at_ict: '21:50', window_hours: 24,
        sources: { [ON_SOURCE]: { ok: true, count: 12 }, [OFF_SOURCE]: { ok: true, count: 4 } } }) };
    }
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

  const box = () => d.querySelector('#sources');
  const rows = () => Array.from(d.querySelectorAll('#sources .source'));
  const sw = (name) => d.querySelector('#sources .sw[data-source="' + name + '"]');
  const state = (name) => (sw(name) ? sw(name).getAttribute('aria-checked') : '없음');
  const pills = () => Array.from(d.querySelectorAll('#filters-global button[data-src]')).map((b) => b.dataset.src);

  await waitFor(() => box() && box().querySelectorAll('.sw').length > 0);
  check('별도 소스 공개 상자가 없음', !d.querySelector('#srcpanel'));
  check('수집 상태 패널에 스위치가 붙음', rows().length === 2, rows().length + '개');
  const first = rows()[0];
  check('스위치가 이름 왼쪽에 있음',
    !!first && first.firstElementChild && first.firstElementChild.classList.contains('sw'),
    first ? first.firstElementChild.className : '없음');
  check('켜짐/꺼짐이 구분됨', state(ON_SOURCE) === 'true' && state(OFF_SOURCE) === 'false',
    ON_SOURCE + '=' + state(ON_SOURCE) + ' ' + OFF_SOURCE + '=' + state(OFF_SOURCE));
  const offRow = d.querySelector('#sources .source.off');
  check('감춘 소스는 줄에 표시가 붙음', !!offRow && offRow.textContent.indexOf(OFF_SOURCE) >= 0,
    offRow ? offRow.textContent.replace(/\s+/g, ' ').trim() : '없음');

  const before = pills();
  check('감춘 소스는 알약에서 빠짐', before.indexOf(OFF_SOURCE) < 0, before.join(','));
  check('나머지 소스 알약은 남아 있음', before.length > 0, before.length + '개');

  sw(OFF_SOURCE).click();
  await waitFor(() => calls.length > 0);
  const post = calls[0] || {};
  check('스위치를 누르면 저장 요청을 보냄', post.path === '/api/source' && post.method === 'POST',
    (post.path || '') + ' ' + (post.method || ''));
  check('감춘 소스를 다시 누르면 공개로 되돌림',
    post.body && post.body.source === OFF_SOURCE && post.body.hidden === false,
    JSON.stringify(post.body || {}));
  await waitFor(() => state(OFF_SOURCE) === 'true');
  check('되돌리면 스위치가 켜짐', state(OFF_SOURCE) === 'true', state(OFF_SOURCE));
  await waitFor(() => pills().indexOf(OFF_SOURCE) >= 0);
  check('되돌리면 알약도 돌아옴', pills().indexOf(OFF_SOURCE) >= 0, pills().join(','));
  const note = d.querySelector('#srcnote');
  check('무슨 일이 있었는지 알려 줌', !!note && note.textContent.indexOf('되돌렸습니다') >= 0,
    note ? note.textContent.trim().slice(0, 40) : '없음');

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
