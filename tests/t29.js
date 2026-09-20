// The seed: does the page ship headlines in its own HTML, and does the script replace them
// (not append a second copy)?
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pass = [];
const check = (n, ok, d) => { pass.push(ok); console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', n, d ? '  (' + d + ')' : ''); };

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();

  // 1. Static check: the seed is in the HTML that leaves the server, with no script run.
  const stat = new JSDOM(page);
  const sd = stat.window.document;
  const seeds = sd.querySelectorAll('#feed .card.seed');
  const langCount = sd.querySelectorAll('#feed [lang]').length;
  const feedText = (sd.querySelector('#feed') || { textContent: '' }).textContent;
  const korean = (feedText.match(/[\uac00-\ud7a3]/g) || []).length;
  const letters = (feedText.match(/[A-Za-z\uac00-\ud7a3\u0e00-\u0e7f]/g) || []).length;
  check('HTML에 시드 카드가 실려 있음', seeds.length >= 20, seeds.length + '개');
  check('제목에 lang 속성이 붙음', langCount >= 20, langCount + '개');
  check('시드 글자의 한국어 비중 < 35%', letters > 0 && korean / letters < 0.35,
    (korean / Math.max(letters, 1) * 100).toFixed(1) + '% (한국어 ' + korean + '/' + letters + ')');
  const seedTitles = Array.from(seeds).map((c) => c.querySelector('.title').textContent.trim());
  console.log('    예시:', seedTitles.slice(0, 2).join(' | ').slice(0, 110));

  // 2. Live check: after the script runs, the seed is gone and the feed is normal.
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u) => fetch(new URL(String(u), URL_).href,
        { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' } });
    },
  });
  const d = dom.window.document;
  await sleep(9000);
  const cards = d.querySelectorAll('#feed .card').length;
  const left = d.querySelectorAll('#feed .card.seed').length;
  const titles = Array.from(d.querySelectorAll('#feed .card .title')).map((t) => t.textContent.trim());
  check('스크립트가 시드를 대체함', left === 0, '남은 시드 ' + left + '개');
  const links = Array.from(d.querySelectorAll('#feed .card .title a')).map((a) => a.getAttribute('href'));
  check('카드가 중복되지 않음', cards === 25, cards + '건');
  // Links are the dedup key, not titles: one Decrypt story legitimately arrives twice (the
  // site's own feed and a Bluesky post about it) with the same headline and different URLs.
  check('링크 중복 없음', new Set(links).size === links.length, links.length + '개 중 ' + new Set(links).size + '고유');

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();