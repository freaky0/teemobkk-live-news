// The rules panel, from the operator's side of the page.
//
// The write path is stubbed on purpose: switching a real rule on would take stories out of the feed
// the operator is looking at, and a check must not edit the data it inspects. What is checked is the
// wiring - a rule per row with its switch and its catch count, a switch that posts the rule and the
// new state, a caught story that can be kept, a pattern that can be added, delete, and the learn
// button that asks for proposals from the stories the operator hid by hand.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (fn, ms = 20000, step = 250) => {
  const until = Date.now() + ms;
  while (Date.now() < until) { if (fn()) return true; await sleep(step); }
  return false;
};
const pass = [];
const check = (n, ok, d) => { pass.push(ok); console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', n, d ? '  (' + d + ')' : ''); };

const now = Date.now();
const CAUGHT_LINK = 'https://example.com/digest';
let calls = [];
let rules = [
  { id: 1, pattern: 'bloomberg news now', kind: 'phrase', origin: 'operator', enabled: true, hits: 9, last_hit_at: '' },
  { id: 2, pattern: 'casino', kind: 'word', origin: 'learned', enabled: false, hits: 0, last_hit_at: '' },
];
let caught = [{ link: CAUGHT_LINK, title: 'Bloomberg News Now is a comprehensive audio report',
                source: 'Bluesky · bloomberg.com', published_at: '', pattern: 'bloomberg news now',
                rule_id: 1, matched_at: '', kept_total: 0 }];
const answer = () => ({ ok: true, rules, caught, filter_enabled: rules.filter((r) => r.enabled).length });

function stubFetch(realFetch) {
  return async (u, o) => {
    const path = String(u).replace(/^https?:\/\/[^/]+/, '');
    const body = (o && o.body) ? JSON.parse(o.body) : {};
    if (path === '/api/filter') {
      calls.push({ path, method: ((o && o.method) || 'GET').toUpperCase(), body });
      if (body.action === 'set') rules = rules.map((r) => (r.id === body.id ? { ...r, enabled: body.enabled, hits: body.enabled ? 9 : 0 } : r));
      if (body.action === 'delete') { rules = rules.filter((r) => r.id !== body.id); caught = []; }
      if (body.action === 'add') rules = rules.concat([{ id: 3, pattern: String(body.pattern).toLowerCase(), kind: 'phrase', origin: 'operator', enabled: false, hits: 0, last_hit_at: '' }]);
      if (body.action === 'learn') rules = rules.concat([{ id: 4, pattern: 'top crypto casinos', kind: 'phrase', origin: 'learned', enabled: false, hits: 0, last_hit_at: '' }]);
      if (body.action === 'keep') caught = [];
      return { ok: true, json: async () => answer() };
    }
    if (path.startsWith('/api/filters')) return { ok: true, json: async () => answer() };
    if (path.startsWith('/api/status')) return { ok: true, json: async () => ({ article_count: 1, region_counts: { '글로벌': 1 }, sources: {}, hidden_sources: [], filter_rules: rules, filter_enabled: 1 }) };
    if (path.startsWith('/api/hidden')) return { ok: true, json: async () => ({ hidden: [] }) };
    if (path.startsWith('/api/news')) return { ok: true, json: async () => ({ articles: [], total: 0, has_more: false, hours: 24, limit: 25, offset: 0, returned: 0, region_counts: { '글로벌': 0 }, updated_at: new Date(now - 60000).toISOString(), updated_at_ict: '21:50', window_hours: 24, sources: {} }) };
    return realFetch(new URL(String(u), URL_).href, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default', method: (o && o.method) || 'GET' });
  };
}

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) { w.fetch = stubFetch(fetch); },
  });
  const d = dom.window.document;
  const box = () => d.querySelector('#filters');
  const rows = () => Array.from(d.querySelectorAll('#filters .rule'));
  const sw = (id) => d.querySelector('#filters .sw[data-rule="' + id + '"]');
  const state = (id) => (sw(id) ? sw(id).getAttribute('aria-checked') : '없음');

  await waitFor(() => box() && rows().length >= 2);
  check('규칙 상자가 있음', !!d.querySelector('#flearn') && !!d.querySelector('#fpattern'));
  check('규칙마다 한 줄', rows().length === 2, rows().length + '줄');
  check('켜짐/꺼짐이 구분됨', state(1) === 'true' && state(2) === 'false', '1=' + state(1) + ' 2=' + state(2));
  const offRow = d.querySelector('#filters .rule.off');
  check('꺼진 규칙은 줄에 표시가 붙음', !!offRow && offRow.textContent.indexOf('casino') >= 0,
    offRow ? offRow.textContent.replace(/\s+/g, ' ').trim() : '없음');
  check('잡은 건수가 보임', (rows()[0] || { textContent: '' }).textContent.indexOf('9') >= 0,
    (rows()[0] || { textContent: '' }).textContent.replace(/\s+/g, ' ').trim());
  check('뽑은 규칙도 구분됨', rows().some((r) => r.textContent.indexOf('learned') < 0 && r.textContent.indexOf('casino') >= 0));

  // 켜기
  sw(2).click();
  await waitFor(() => calls.some((c) => c.body.action === 'set'));
  let post = calls.filter((c) => c.body.action === 'set')[0] || {};
  check('규칙을 켜면 저장 요청을 보냄', post.path === '/api/filter' && post.method === 'POST', (post.path || '') + ' ' + (post.method || ''));
  check('켜라는 뜻을 정확히 보냄', post.body.action === 'set' && post.body.id === 2 && post.body.enabled === true, JSON.stringify(post.body));
  await waitFor(() => state(2) === 'true');
  check('켜면 스위치가 켜짐', state(2) === 'true', state(2));

  // 살리기
  const keep = d.querySelector('#filters .keep');
  check('잡은 기사가 보임', !!keep, keep ? keep.textContent : '없음');
  keep.click();
  await waitFor(() => calls.length > 1);
  post = calls[calls.length - 1];
  check('살리기가 그 기사를 보냄', post.body.action === 'keep' && post.body.link === CAUGHT_LINK, JSON.stringify(post.body));

  // 추가
  const input = d.querySelector('#fpattern');
  input.value = 'Top Crypto Casinos';
  d.querySelector('#fadd').click();
  await waitFor(() => calls.length > 2);
  post = calls[calls.length - 1];
  check('추가가 문구를 보냄', post.body.action === 'add' && post.body.pattern === 'Top Crypto Casinos', JSON.stringify(post.body));
  await waitFor(() => rows().length === 3);
  check('추가한 규칙이 목록에 들어옴', rows().length === 3, rows().length + '줄');
  check('추가 뒤 입력칸이 비워짐', input.value === '', JSON.stringify(input.value));

  // 뽑기
  d.querySelector('#flearn').click();
  await waitFor(() => calls.some((c) => c.body.action === 'learn'));
  post = calls.filter((c) => c.body.action === 'learn')[0];
  check('뽑기가 학습을 요청함', post.body.action === 'learn', JSON.stringify(post.body));
  await waitFor(() => rows().length === 4);
  check('뽑은 후보가 목록에 들어옴', rows().length === 4, rows().length + '줄');
  check('뽑은 후보는 꺼진 채로 들어옴', d.querySelectorAll('#filters .rule.off').length >= 1);

  // 지우기
  const x = d.querySelector('#filters .rx');
  x.click();
  await waitFor(() => calls.some((c) => c.body.action === 'delete'));
  post = calls.filter((c) => c.body.action === 'delete')[0];
  check('지우기가 규칙 번호를 보냄', post.body.action === 'delete' && typeof post.body.id === 'number', JSON.stringify(post.body));

  const note = d.querySelector('#fnote');
  check('무슨 일이 있었는지 알려 줌', !!note && note.textContent.length > 0, note ? note.textContent.trim().slice(0, 44) : '없음');

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
