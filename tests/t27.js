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
  // The first number in the summary line, e.g. "총 758건, 25건 표시, 보관 13245건" -> 758.
  const totalOf = (t) => { const m = String(t).match(/\d[\d,]*/); return m ? parseInt(m[0].replace(/,/g, ''), 10) : -1; };
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

  // --- 3. source pills, and how the two axes combine ---
  const srclist = Array.from(d.querySelectorAll('#filters-global button[data-src]')).map((b) => b.dataset.src);
  check('③ 소스 알약에 Whale Alert 있음', srclist.indexOf('Whale Alert') >= 0, srclist.join(' · '));
  // Clear the category first: this check is about the source filter on its own.
  g('button[data-cat="전체"]').click();
  await sleep(WAIT);
  g('button[data-src="Whale Alert"]').click();
  await sleep(WAIT);
  cl = cards();
  check('③ Whale Alert 알약 → 고래 알림만', same(cl.map(srcOf), 'Whale Alert') && cl.length > 0, cl.length + '건');
  check('③ 소스 알약 aria-pressed', g('button[data-src="Whale Alert"]').getAttribute('aria-pressed') === 'true',
    'aria=' + g('button[data-src="Whale Alert"]').getAttribute('aria-pressed'));

  // The axes compose: selecting a category next to a source keeps both and returns the
  // intersection, which can only narrow the list. This used to release one of them, because two
  // conditions sent together were ANDed on the server and usually returned nothing.
  const srcOnly = totalOf(counts());
  g('button[data-cat="지정학"]').click();
  await sleep(WAIT);
  const bothAxes = totalOf(counts());
  check('③ 두 축이 교차함 (분류 + 소스)',
    g('button[data-cat="지정학"]').classList.contains('active') && srcOnly >= 0 && bothAxes >= 0
      && bothAxes <= srcOnly,
    '소스만 ' + srcOnly + ' → 둘 다 ' + bothAxes);

  // --- 4. 전체 restores the baseline ---
  g('button[data-cat="전체"]').click();
  await sleep(WAIT);
  const back = Array.from(new Set(cards().map(catOf)));
  check('④ 전체 → 원복', cards().length === base && back.length > 1,
    cards().length + '건 vs ' + base + ' · 분류 ' + back.length + '종');

  // --- 5. the Thai tab has its own category row ---
  d.querySelector('#tab-thai').click();
  await sleep(WAIT + 3000);
  // The Thai category is read off a card on screen instead of being named here. Naming 비자·이민
  // made this check depend on the data: it is a rare axis and the window has held zero of them
  // (measured: 0 rows in 24 hours, last one 25 hours old), which failed the check for a reason that
  // had nothing to do with the filter.
  const thCards = cards();
  const thTotalBefore = totalOf(counts());
  // Pick the label that appears on the fewest cards: that is a real category rather than the
  // generic one every story falls back to, and the filter then has to prove it narrows the list.
  const freq = {};
  thCards.forEach((c) => labelsOf(c).forEach((l) => { freq[l] = (freq[l] || 0) + 1; }));
  const thFirst = Object.keys(freq).sort((a, b) => freq[a] - freq[b] || a.localeCompare(b))[0] || '';
  // Matched by the pill's text, not by data-cat: on the Thai tab a chip shows a short label
  // (생활·교통·날씨) while the stored value is the longer full name, so a label cannot be looked up
  // as a stored value. On the global tab those two happen to be identical, which is why the same
  // lookup works a few lines above.
  const thPill = Array.from(d.querySelectorAll('#filters-thai button[data-cat]'))
    .find((b) => b.textContent.replace(/\d+$/, '').trim() === thFirst);
  check('⑤ 태국 탭에 카드가 있음', thCards.length > 0, thCards.length + '건');
  check('⑤ 그 분류의 알약이 있음', !!thPill, thFirst || '(없음)');
  if (thPill) { thPill.click(); await sleep(WAIT + 3000); }
  const th = cards();
  const thTotalAfter = totalOf(counts());
  // Compared on the reported total, not on the number of cards drawn: the list draws at most one
  // page (25), so a category holding more rows than that shows 25 cards before and after and only
  // the total moves.
  check('⑤ 태국 탭 분류 알약 → 그 분류가 남고 총계가 줄어듦',
    !!thPill && allHave(th, thFirst) && thTotalAfter >= 0 && thTotalAfter < thTotalBefore,
    thFirst + ' · ' + th.length + '건 표시 · 총 ' + thTotalAfter + ' (전 ' + thTotalBefore + ') · 표본 ' + (freq[thFirst] || 0) + '건');

  // --- 6. a story that matched two axes shows both labels ---
  // Which story carries two labels is a property of the day's news, not of the page. The newest 25
  // can all be single-label - measured when the finance wires were added: the newest 25 were 0
  // multi-label while the newest 300 held 41 - and asking the first 25 for one made this check fail
  // on the data rather than on the rendering. So the story is found in the stored window first, and
  // the page is then asked to show it.
  d.querySelector('#tab-global').click();
  await sleep(WAIT + 3000);
  g('button[data-cat="전체"]').click();
  await sleep(WAIT);
  let multiSource = null;
  try {
    // The global tab, because that is the tab being tested: the first multi-label story in the whole
    // stored window was a Thailand one, and a Thailand story never appears in this tab's list, so
    // the search below could not have found it.
    const listed = await (await fetch(URL_ + 'api/news?limit=300&region=' + encodeURIComponent('글로벌'),
      { cache: 'no-cache' })).json();
    multiSource = ((listed && listed.articles) || listed || [])
      .find((a) => (a.categories || []).length > 1) || null;
  } catch (e) { /* reported by the check below */ }
  check('⑥ 창 안에 두 축에 걸린 기사가 있음', !!multiSource,
    multiSource ? multiSource.title.slice(0, 38) + ' · ' + multiSource.categories.join(' + ')
                : '없음 - 분류가 겹치는 기사를 하나도 만들지 못했습니다');
  if (multiSource) {
    // The label order is the taxonomy's, so the page is asked for the whole set, not for one name.
    const wanted = multiSource.categories.slice().sort().join(' + ');
    // The search box matches the typed words as one phrase, so a made-up phrase from four title
    // words finds nothing (measured: "Forecast Fed" 0 rows while "Fed" finds 12). Words are tried
    // longest first instead, which is also how a reader would hunt for one story.
    const tries = Array.from(new Set(String(multiSource.title)
      .replace(/[^\w\s\uac00-\ud7a3]/g, ' ').split(/\s+/)
      .filter((x) => x.length > 5))).sort((a, b) => b.length - a.length).slice(0, 3);
    let hit = null;
    const attempts = [];
    for (const word of tries) {
      q.value = word;
      q.oninput();
      await sleep(WAIT + 2000);
      const shown = cards();
      hit = shown.find((c) => {
        const a = c.querySelector('.title a');
        return a && a.getAttribute('href') === multiSource.link;
      }) || null;
      attempts.push(word + '=' + shown.length);
      if (hit) break;
    }
    check('⑥ 두 축에 걸린 카드는 알약을 두 개 보여줌',
      !!hit && labelsOf(hit).slice().sort().join(' + ') === wanted,
      hit ? labelsOf(hit).join(' + ') + ' (기대 ' + wanted + ')'
          : '검색으로 그 카드를 찾지 못함 (' + attempts.join(', ') + ')');
    q.value = '';
    q.oninput();
    await sleep(WAIT);
  }

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
