// The English page: language declaration, switcher, translated interface, and -- the part that
// can break -- category pills that show English labels while still filtering on the stored
// Korean value.
const { JSDOM, VirtualConsole } = require('jsdom');
const PAGE = process.argv[2];
const URL_ = process.argv[3] || 'https://freaky0.github.io/teemobkk-live-news/';
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
  const fs = require('fs');
  // The page to inspect: a local file when the same document is served both ways, otherwise the
  // live page itself. Passing "-" (or nothing) fetches it, which is what a server-rendered page
  // needs: its document is not the published static one, so the two cannot stand in for each other.
  const page = (PAGE && PAGE !== '-') ? fs.readFileSync(PAGE, 'utf8') : await (await fetch(URL_)).text();

  // --- static checks ---
  const stat = new JSDOM(page);
  const sd = stat.window.document;
  check('문서 언어 en', sd.documentElement.lang === 'en', sd.documentElement.lang);
  const bar = sd.querySelector('.langbar');
  check('상단에 언어 전환기', !!bar, bar ? bar.textContent.trim() : 'none');
  check('현재 언어가 English로 표시', !!sd.querySelector('.langbar b'), sd.querySelector('.langbar b')?.textContent);
  const link = sd.querySelector('.langbar a');
  check('한국어 링크가 ko 페이지를 가리킴', !!link && link.getAttribute('href').indexOf('ko') >= 0,
    link ? link.getAttribute('href') : 'none');
  const tabs = Array.from(sd.querySelectorAll('.tab')).map((t) => t.textContent.trim());
  check('탭이 영어', tabs.join('/') === 'Markets/Indicators/Thailand', tabs.join('/'));
  const seeds = sd.querySelectorAll('#feed .card.seed').length;
  check('시드 카드 실려 있음', seeds >= 20, seeds + '개');
  const koreanUi = ['더 보기', ' 위로', '경제 소식', '연결 중', '지금 뜨는', '원문 열기', '펼쳐보기'];
  const left = koreanUi.filter((w) => page.indexOf(w) >= 0);
  check('한국어 UI가 남아 있지 않음', left.length === 0, left.join(', ') || 'none');

  // --- live checks ---
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u) => fetch(new URL(String(u), URL_).href, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' } });
    },
  });
  const w = dom.window, d = w.document;
  // the deployed page answers through a proxy: wait for the render, not for a clock
await waitFor(() => d.querySelectorAll('#filters-global button[data-cat]').length > 0
  && d.querySelectorAll('#feed .card').length > 0);

  const HANGUL = /[\uAC00-\uD7A3]/;
  const pills = Array.from(d.querySelectorAll('#filters-global button[data-cat]'));
  const labels = pills.map((b) => b.textContent.replace(/\d+$/, '').trim());
  // The contract is "the stored value stays the Korean name, the label is translated", so the test
  // picks a real pill and checks both halves of it. Naming a category here instead would be the
  // one string most likely to be wrong after a taxonomy change, and it would then "prove" the page
  // correct against a name this test invented.
  const pick = pills.find((b) => HANGUL.test(b.dataset.cat) && !HANGUL.test(b.textContent));
  check('분류 알약 라벨이 영어', !!pick, labels.slice(1, 4).join(' / '));
  const pickLabel = pick ? pick.textContent.replace(/\d+$/, '').trim() : '';
  const pickValue = pick ? pick.dataset.cat : '';
  check('분류 값은 저장값(한국어) 유지', !!pick && HANGUL.test(pickValue), pickValue);

  const cards = () => Array.from(d.querySelectorAll('#feed .card'));
  // A story can carry several labels, and the clicked one need not be the first of them.
  const labelsOf = (c) => Array.from(c.querySelectorAll('.chip.tap:not(.src)')).map((e) => e.textContent.trim());
  const hasLabel = (c) => labelsOf(c).indexOf(pickLabel) >= 0;
  pick.click();
  await waitFor(() => {
    const c = cards();
    return c.length > 0 && c.every(hasLabel);
  });
  const after = cards();
  check('영어 알약이 실제로 걸러냄', after.length > 0 && after.every(hasLabel),
    after.length + '건 · ' + Array.from(new Set(after.flatMap(labelsOf))).join(', '));
  check('분류 칩도 영어 라벨로 표시',
    after.length > 0 && hasLabel(after[0]) && !HANGUL.test(labelsOf(after[0]).join(' ')),
    after.length ? labelsOf(after[0]).join(' + ') : '(없음)');

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();