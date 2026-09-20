// Does a two-keyword selection show only stories carrying BOTH, and does the condition row say so?
//
// This check used to assert the union - every card carrying at least one of the terms - which was
// the old behaviour and the opposite of what selecting several things should do. Both outcomes are
// passable here: an intersection can legitimately be empty in a 24-hour window, and then the row has
// to explain itself instead of leaving a blank feed.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (fn, ms = 30000, step = 400) => {
  const until = Date.now() + ms;
  while (Date.now() < until) { if (fn()) return true; await sleep(step); }
  return false;
};
const pass = [];
const check = (n, ok, d) => { pass.push(ok); console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', n, d ? '  (' + d + ')' : ''); };

(async () => {
  const page = await (await fetch(URL_)).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => fetch(new URL(String(u), URL_).href,
        { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
    },
  });
  const w = dom.window, d = w.document;
  const btn = (i) => Array.from(d.querySelectorAll('#trend .tbtn[data-trend]'))[i];
  const cards = () => Array.from(d.querySelectorAll('#feed .card'));
  const textOf = (c) => ((c.querySelector('.title') || {}).textContent || '') + ' '
    + ((c.querySelector('.summary') || {}).textContent || '');
  const conds = () => (d.querySelector('#conds') || {});
  const condText = () => ((conds().textContent) || '').replace(/\s+/g, ' ').trim();

  await waitFor(() => d.querySelectorAll('#trend .tbtn[data-trend]').length > 0);
  const terms = [btn(0).dataset.trend, btn(1).dataset.trend];
  btn(0).click();
  await sleep(2500);
  btn(1).click();
  await sleep(6000);

  const list = cards();
  const both = list.filter((c) => terms.every((x) => w.termMatch(textOf(c), x)));
  console.log('  선택한 낱말: %s', terms.join(' + '));
  console.log('  카드 %d건 · 그중 둘 다 포함 %d건', list.length, both.length);
  console.log('  조건 줄: %s', condText().slice(0, 120));

  const row = conds();
  check('조건 줄이 두 낱말을 보여줌',
    !row.hidden && terms.every((x) => condText().indexOf(x) >= 0), condText().slice(0, 80));

  if (list.length) {
    check('보이는 카드가 선택한 낱말을 모두 포함', both.length === list.length,
      list.length + '건 중 ' + both.length + '건');
  } else {
    // An empty intersection is a legitimate answer; what must not happen is an unexplained blank.
    check('0건이면 조건 줄과 넓히기 버튼으로 설명함',
      !!row.querySelector('[data-cond-wide]') && condText().indexOf('\u2192 0') >= 0,
      condText().slice(0, 80));
  }

  // Releasing one condition must widen the result, which is what makes the row useful.
  const before = (d.querySelector('#counts') || {}).textContent || '';
  const off = row.querySelector('[data-cond-off]');
  if (off) {
    off.click();
    await sleep(6000);
    const after = (d.querySelector('#counts') || {}).textContent || '';
    check('조건 하나를 풀면 결과가 넓어짐', after !== before, before.trim() + '  ->  ' + after.trim());
  } else {
    check('조건을 풀 버튼이 있음', false, 'none');
  }

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
