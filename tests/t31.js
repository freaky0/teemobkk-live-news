// The deployed /thai/ page: the tab must be selected at runtime, the cards must be Thailand
// sources, and the language switcher must point at the Korean copy.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'https://teemobkk.io/thai/news/';
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pass = [];
const check = (n, ok, d) => { pass.push(ok); console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', n, d ? '  (' + d + ')' : ''); };

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u) => fetch(new URL(String(u), URL_).href,
        { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' } });
    },
  });
  const d = dom.window.document;
  await sleep(10000);

  const cards = Array.from(d.querySelectorAll('#feed .card'));
  const sources = Array.from(new Set(cards.map((c) => {
    const e = c.querySelector('.chip.src'); return e ? e.textContent.trim() : '';
  })));
  check('태국 탭이 런타임에 선택됨', d.querySelector('#tab-thai').classList.contains('active'), '');
  check('경제 소식 탭은 해제', !d.querySelector('#tab-global').classList.contains('active'), '');
  check('카드가 렌더됨', cards.length > 0, cards.length + '건');
  const thaiSources = sources.filter((s) => /Matichon|Thairath|Bangkok|Khaosod|태국|방콕|Thai/i.test(s));
  check('태국 소스가 올라옴', thaiSources.length > 0, sources.slice(0, 4).join(' · '));
  check('언어 전환기가 한국어 사본을 가리킴',
    (d.querySelector('.langbar a') || {}).getAttribute?.('href') === 'ko/index.html',
    (d.querySelector('.langbar a') || {}).getAttribute?.('href'));
  check('분류 값은 저장값 유지', Array.from(d.querySelectorAll('#filters-thai button[data-cat]'))
    .some((b) => b.dataset.cat === '사고·재난'),
    Array.from(d.querySelectorAll('#filters-thai button[data-cat]')).map((b) => b.dataset.cat).slice(0, 3).join('/'));

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();