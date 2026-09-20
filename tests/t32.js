// Keyword multi-select on the dashboard: several keywords at once, a click that releases, and
// 전체 actually clearing the keyword filter (it used to leave the list stuck until the search box
// was cleared by hand).
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (fn, ms = 25000, step = 300) => {
  const until = Date.now() + ms;
  while (Date.now() < until) { if (fn()) return true; await sleep(step); }
  return false;
};
const pass = [];
const check = (n, ok, d) => { pass.push(ok); console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', n, d ? '  (' + d + ')' : ''); };

(async () => {
  const queries = [];
  const page = await (await fetch(URL_)).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => {
        const full = new URL(String(u), URL_).href;
        if (full.indexOf('/api/news?') >= 0) queries.push(full);
        return fetch(full, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
      };
    },
  });
  const d = dom.window.document;

  const row = () => d.querySelector('#trend');
  const btns = () => Array.from(d.querySelectorAll('#trend .tbtn[data-trend]'));
  const selected = () => btns().filter((b) => b.classList.contains('on')).map((b) => b.dataset.trend);
  // a query string encodes a space as +, and decodeURIComponent does not turn it back
  const dec = (s) => decodeURIComponent(String(s).replace(/\+/g, ' '));
  const lastQ = () => { const u = queries[queries.length - 1] || ''; const m = u.match(/[?&]q=([^&]*)/); return m ? dec(m[1]) : ''; };

  await waitFor(() => btns().length > 0);
  check('추천 키워드 줄이 있음', btns().length > 0, btns().length + '개');

  // the row scrolls sideways on a phone instead of wrapping onto lines, and the label sits outside
  // that scroller so buttons can never be painted over it
  const track = d.querySelector('#trend .ttrack');
  const css = dom.window.getComputedStyle(track);
  check('줄이 옆으로 흐름 (wrap 없음)', css.overflowX === 'auto' && css.flexWrap !== 'wrap', css.overflowX + '/' + css.flexWrap);
  check('라벨이 스크롤 상자 밖', !!d.querySelector('#trend > .tlabel') && track.parentElement === d.querySelector('#trend'));

  const a = btns()[0].dataset.trend, b = btns()[1].dataset.trend;
  btns()[0].click();
  await waitFor(() => lastQ() === a);
  check('키워드를 누르면 그 낱말로 걸림', selected().length === 1 && selected()[0] === a, selected().join(','));
  check('검색창에는 들어가지 않음 (별개 상태)', d.querySelector('#q').value === '', JSON.stringify(d.querySelector('#q').value));
  check('선택 표시가 눌림 상태', d.querySelector('#trend .tbtn.on').getAttribute('aria-pressed') === 'true');
  // jsdom does not resolve var(), so the accent fill cannot be read here - the browser check
  // (tools/diag_keywords2.py) reads the painted colour. What is visible from here is the tick.
  check('선택한 낱말에 체크 표시', d.querySelector('#trend .tbtn.on').textContent.indexOf('✓') >= 0,
    d.querySelector('#trend .tbtn.on').textContent.trim());

  queries.length = 0;
  btns()[1].click();
  await waitFor(() => queries.filter((u) => /[?&]q=/.test(u)).length >= 2);
  const asked = queries.filter((u) => /[?&]q=/.test(u)).map((u) => dec((u.match(/[?&]q=([^&]*)/) || [])[1]));
  check('두 낱말을 함께 걸 수 있음', selected().length === 2 && selected().indexOf(a) >= 0 && selected().indexOf(b) >= 0, selected().join(' + '));
  check('두 낱말을 각각 조회함', asked.indexOf(a) >= 0 && asked.indexOf(b) >= 0, asked.join(','));

  btns()[0].click();
  await waitFor(() => selected().length === 1);
  check('같은 낱말을 다시 누르면 풀림', selected().length === 1 && selected()[0] === b, selected().join(','));

  // the pill row of whichever tab is open: the Thailand dashboard keeps its categories in its own row
  const catRow = () => (d.querySelector('#filters-thai') && !d.querySelector('#filters-thai').hidden
    ? d.querySelector('#filters-thai') : d.querySelector('#filters-global'));
  queries.length = 0;
  const all = Array.from(catRow().querySelectorAll('button[data-cat]')).find((x) => x.dataset.cat === '전체');
  all.click();
  await waitFor(() => queries.filter((u) => /\/api\/news\?/.test(u)).length > 0);
  await sleep(1200);
  check('전체를 누르면 키워드가 풀림', selected().length === 0, selected().join(',') || '없음');
  check('전체 뒤 조회에 q 가 없음', lastQ() === '', lastQ() || '없음');
  check('해제 버튼도 사라짐', !d.querySelector('[data-trend-clear]'));

  // and the release button works
  btns()[0].click();
  await waitFor(() => selected().length === 1);
  const clear = d.querySelector('[data-trend-clear]');
  check('선택하면 해제 버튼이 나타남', !!clear, clear ? clear.textContent.trim() : '없음');
  clear.click();
  await waitFor(() => selected().length === 0);
  check('해제 버튼이 바로 풀어 줌', selected().length === 0 && !d.querySelector('[data-trend-clear]'));

  // typing in the box releases the keywords, so the two text filters never fight
  btns()[0].click();
  await waitFor(() => selected().length === 1);
  const q = d.querySelector('#q');
  q.value = '금리';
  q.oninput();
  await sleep(900);
  check('검색어를 입력하면 키워드가 풀림', selected().length === 0, selected().join(',') || '없음');

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
