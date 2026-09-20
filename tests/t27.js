// The filter row: card chips, category pills, source pills, exclusivity, search box reset.
// Usage: node t27.js <url> [sleepMs]
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
const WAIT = Number(process.argv[3]) || 5000;

const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
vc.on('console.error', (...a) => console.log('  [console.error]', ...a.map(String)));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pass = [];
const check = (name, ok, detail) => {
  pass.push(ok);
  console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', name, detail ? '  (' + detail + ')' : '');
};

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  let seeded = false;
  const dom = new JSDOM(page, {
    runScripts: 'dangerously',
    url: URL_,
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => fetch(new URL(String(u), URL_).href,
        { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'no-cache' });
      // The old build restored the last query from this key on every load.
      try { w.localStorage.setItem('teemo-live-q', 'iran'); seeded = true; } catch (e) {}
    },
  });
  const w = dom.window, d = w.document;
  const cards = () => Array.from(d.querySelectorAll('#feed .card'));
  const counts = () => (d.querySelector('#counts') || {}).textContent || '';
  const srcOf = (c) => { const e = c.querySelector('.chip.src'); return e ? e.textContent.trim() : ''; };
  const catOf = (c) => { const e = c.querySelector('.chip.tap:not(.src)'); return e ? e.textContent.trim() : ''; };
  // A story can carry more than one axis, so a card can show several labels and the one that was
  // clicked is not necessarily the first. Every check about a category filter asks "does the card
  // carry this label", not "is this its only label".
  const labelsOf = (c) => Array.from(c.querySelectorAll('.chip.tap:not(.src)')).map((e) => e.textContent.trim());
  const allHave = (arr, v) => arr.length > 0 && arr.every((c) => labelsOf(c).indexOf(v) >= 0);
  const same = (arr, v) => arr.length > 0 && arr.every((x) => x === v);
  // renderPills() rewrites the row, so pills are looked up again after every click.
  const g = (sel) => d.querySelector('#filters-global ' + sel);
  const t = (sel) => d.querySelector('#filters-thai ' + sel);

  await sleep(WAIT + 4000);
  const base = cards().length;
  console.log('  로드 cards=%d | %s', base, counts().trim());

  // --- the search box must start empty, with the list unfiltered ---
  const q = d.querySelector('#q');
  check('③ 검색창 비어 있음', q.value === '', 'value=' + JSON.stringify(q.value) + ' seeded=' + seeded);
  check('③ 전체 목록이 걸러지지 않음', base >= 20, base + '건 · ' + counts().trim());

  // --- card chips ---
  const firstSrc = srcOf(cards()[0]);
  cards()[0].querySelector('.chip.src').click();
  await sleep(WAIT);
  let cl = cards();
  check('① 카드 소스 칩 → 그 소스만', same(cl.map(srcOf), firstSrc), firstSrc + ' · ' + cl.length + '건');
  check('① 클릭한 칩이 눌린 상태', cl.length > 0 && cl[0].querySelector('.chip.src').classList.contains('on'), '');

  cards()[0].querySelector('.chip.src').click();
  await sleep(WAIT);
  check('① 다시 클릭 → 해제', cards().length === base, cards().length + '건 vs ' + base);

  const firstCat = catOf(cards()[0]);
  cards()[0].querySelector('.chip.tap:not(.src)').click();
  await sleep(WAIT);
  cl = cards();
  check('① 분류 칩 클릭 → 그 분류를 가진 카드', allHave(cl, firstCat), firstCat + ' · ' + cl.length + '건');
  const clr = d.querySelector('#clrtag');
  if (clr) { clr.click(); await sleep(WAIT); }
  check('① 해제 알약 → 원복', cards().length === base, cards().length + '건 vs ' + base);

  // --- 2. the category pills (the reported failure) ---
  const cats = Array.from(d.querySelectorAll('#filters-global button[data-cat]')).map((b) => b.dataset.cat);
  check('② 분류 알약 목록', cats.length >= 14 && cats[0] === '전체', cats.length + '개 · ' + cats.slice(0, 3).join('/') + '…');
  g('button[data-cat="지정학"]').click();
  await sleep(WAIT);
  cl = cards();
  check('② 지정학 알약 → 그 분류를 가진 카드', allHave(cl, '지정학'),
    Array.from(new Set(cl.flatMap(labelsOf))).join(', ') || '(없음)');
  check('② 지정학 알약 active', g('button[data-cat="지정학"]').classList.contains('active'), '');
  check('② 지정학 건수가 줄어듦', cl.length <= base && counts().indexOf('전체 목록') < 0, counts().trim());

  // --- 3. source pills, and exclusivity between the two axes ---
  const srclist = Array.from(d.querySelectorAll('#filters-global button[data-src]')).map((b) => b.dataset.src);
  check('③ 소스 알약에 Whale Alert 있음', srclist.indexOf('Whale Alert') >= 0, srclist.join(' · '));
  g('button[data-src="Whale Alert"]').click();
  await sleep(WAIT);
  cl = cards();
  check('③ Whale Alert 알약 → 고래 알림만', same(cl.map(srcOf), 'Whale Alert') && cl.length > 0, cl.length + '건');
  check('③ 소스 알약 aria-pressed', g('button[data-src="Whale Alert"]').getAttribute('aria-pressed') === 'true',
    'aria=' + g('button[data-src="Whale Alert"]').getAttribute('aria-pressed'));
  check('③ 분류 알약이 풀림', !g('button[data-cat="지정학"]').classList.contains('active'),
    'active=' + g('button[data-cat="지정학"]').classList.contains('active'));

  // --- 4. 전체 restores the baseline ---
  g('button[data-cat="전체"]').click();
  await sleep(WAIT);
  const back = Array.from(new Set(cards().map(catOf)));
  check('④ 전체 → 원복', cards().length === base && back.length > 1,
    cards().length + '건 vs ' + base + ' · 분류 ' + back.length + '종');

  // --- 5. the Thai tab has its own category row ---
  d.querySelector('#tab-thai').click();
  await sleep(WAIT + 3000);
  t('button[data-cat="비자·이민"]').click();
  await sleep(WAIT + 3000);
  const th = cards();
  check('⑤ 태국 탭 비자·이민 → 그 분류를 가진 카드', allHave(th, '비자·이민'),
    Array.from(new Set(th.flatMap(labelsOf))).join(', ') || '(없음)');

  // --- 6. a story that matched two axes shows both labels ---
  d.querySelector('#tab-global').click();
  await sleep(WAIT + 3000);
  g('button[data-cat="전체"]').click();
  await sleep(WAIT);
  const multi = cards().filter((c) => labelsOf(c).length > 1);
  check('⑥ 두 축에 걸린 카드는 알약을 두 개 보여줌', multi.length > 0,
    multi.length + '건 · ' + (multi[0] ? labelsOf(multi[0]).join(' + ') : 'none'));

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
