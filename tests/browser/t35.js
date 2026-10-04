// The condition row: every selected filter in one place, each with its own count, and what all of
// them together return. This is the part a reader needs when the answer is 0 - which condition
// caused it - and it is where a typed word can become a condition, which is the only way to filter
// by something the trend strip never offers (it drops Latin words shorter than three letters, so
// "AI" never appears there).
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

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => fetch(new URL(String(u), URL_).href,
        { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
    },
  });
  const w = dom.window, d = w.document;
  await waitFor(() => d.querySelectorAll('#feed .card').length > 0);

  const box = d.querySelector('#q');
  const addBtn = d.querySelector('#qadd');
  const conds = () => d.querySelector('#conds') || {};
  const condText = () => (conds().textContent || '').replace(/\s+/g, ' ').trim();
  const chips = () => Array.from(conds().querySelectorAll('[data-cond-off]'));
  const chipCount = (el) => { const n = el.querySelector('.n'); return n ? Number(n.textContent) : -1; };
  const cards = () => Array.from(d.querySelectorAll('#feed .card'));
  const textOf = (c) => ((c.querySelector('.title') || {}).textContent || '') + ' '
    + ((c.querySelector('.summary') || {}).textContent || '');
  const totOf = (t) => { const m = String(t).match(/\d[\d,]*/); return m ? parseInt(m[0].replace(/,/g, ''), 10) : -1; };

  const addCondition = async (word) => {
    box.value = word; box.oninput();
    await sleep(1200);
    addBtn.click();
    await sleep(4000);
  };

  // --- a typed two-letter word becomes a condition ---
  await addCondition('ai');
  check('+ 조건 추가로 칩이 생김', chips().length === 1 && condText().indexOf('ai') >= 0, condText().slice(0, 60));
  check('칩을 만든 뒤 검색창이 비어 있음', box.value === '', 'value=' + JSON.stringify(box.value));
  const aiCards = cards();
  check('그 조건의 기사만 남음', aiCards.length > 0 && aiCards.every((c) => w.termMatch(textOf(c), 'ai')),
    aiCards.length + '건');

  // --- each chip carries its own count, and the total is not larger than the narrowest ---
  await sleep(2500);
  const counts = chips().map(chipCount);
  check('칩마다 개별 건수가 붙음', counts.length > 0 && counts.every((n) => n >= 0), counts.join(' · '));
  const shown = totOf(condText().replace(/^.*\u2192/, ''));
  check('조건 줄의 합계가 개별 건수 이하', shown >= 0 && counts.every((n) => n < 0 || shown <= n),
    '합계 ' + shown + ' · 개별 ' + counts.join('/'));

  // --- an impossible condition explains itself instead of blanking the feed ---
  await addCondition('zzzznotanarticle');
  check('두 조건이 모두 조건 줄에 있음', chips().length === 2, condText().slice(0, 80));
  check('0건이면 그 사실을 말함 (합계 0)', condText().indexOf('\u2192 0') >= 0, condText().slice(0, 90));
  check('가장 좁은 조건을 짚음', condText().indexOf('가장 좁은 조건') >= 0, condText().slice(0, 90));
  check('빈 목록 안내가 조건을 가리킴',
    (d.querySelector('#feed .empty') || {}).textContent?.indexOf('조건') >= 0,
    ((d.querySelector('#feed .empty') || {}).textContent || '').slice(0, 60));

  const wide = conds().querySelector('[data-cond-wide]');
  check('더 긴 기간 버튼이 있음', !!wide, wide ? wide.textContent.trim() : 'none');
  if (wide) {
    wide.click();
    await sleep(5000);
    const sel = d.querySelector('#hours');
    // The stamp lives in #updated inside .stamp; the first version of this check read a #stamp
    // element that does not exist and so read an empty string.
    const stampText = (d.querySelector('#updated') || {}).textContent || '';
    check('버튼이 기간을 전체로 바꿈', sel.value === '2160' && stampText.indexOf('전체 기간') >= 0,
      'hours=' + sel.value + ' · ' + stampText.trim().slice(0, 60));
  }

  // --- releasing the impossible condition brings the list back ---
  const offTargets = chips().filter((c) => c.dataset.condOff.indexOf('zzzznotanarticle') >= 0);
  if (offTargets.length) {
    offTargets[0].click();
    await sleep(5000);
    check('조건을 풀면 결과가 돌아옴', cards().length > 0 && chips().length === 1,
      cards().length + '건 · 칩 ' + chips().length + '개');
  } else {
    check('조건 해제 버튼을 찾음', false, JSON.stringify(chips().map((c) => c.dataset.condOff)));
  }

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
