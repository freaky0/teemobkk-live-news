// Local dashboard: does 더 보기 actually show more cards?
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';

const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
vc.on('error', (...a) => console.log('  [console.error]', ...a.map(String)));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (fn, ms = 25000, step = 300) => {
  const until = Date.now() + ms;
  while (Date.now() < until) { if (fn()) return true; await sleep(step); }
  return false;
};

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously',
    url: URL_,
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => {
        const s = new URL(String(u), URL_).href;
        return fetch(s, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
      };
    },
  });
  const w = dom.window, d = w.document;
  const cards = () => d.querySelectorAll('#feed .card').length;
  const more = () => d.querySelector('#more');
  const counts = () => (d.querySelector('#counts') || {}).textContent || '';

  await waitFor(() => cards() > 0);
  console.log('  초기        cards=%d | 더보기 숨김=%s | %s', cards(), more().hidden, counts().trim());

  const before = cards();
  more().click();
  await waitFor(() => cards() > before);
  console.log('  1회 클릭 후 cards=%d | 더보기 숨김=%s | %s', cards(), more().hidden, counts().trim());

  more().click();
  await sleep(7000);
  console.log('  2회 클릭 후 cards=%d | 더보기 숨김=%s | %s', cards(), more().hidden, counts().trim());

  more().click();
  await sleep(7000);
  console.log('  3회 클릭 후 cards=%d | 더보기 숨김=%s | %s', cards(), more().hidden, counts().trim());

  const links = [...d.querySelectorAll('#feed .card .title a')].map((a) => a.getAttribute('href'));
  const duplicateLinks = links.length - new Set(links).size;
  console.log('  중복 링크:', duplicateLinks);
  if (duplicateLinks) throw new Error('대시보드에 중복 원문 링크가 표시됨');
  console.log('  카드 표시:', cards() >= 100 ? 'PASS (100건 이상 표시)' : 'FAIL');
  process.exit(0);
})();
