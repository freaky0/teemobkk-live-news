// Does a two-keyword selection actually show the union, and does the header say what is applied?
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

(async () => {
  const page = await (await fetch(URL_)).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => fetch(new URL(String(u), URL_).href,
        { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
    },
  });
  const d = dom.window.document;
  const btn = (i) => Array.from(d.querySelectorAll('#trend .tbtn[data-trend]'))[i];
  const stamp = () => (d.querySelector('#stamp') || {}).textContent || (d.body.textContent.match(/키워드[^\n]*/) || [''])[0];

  await waitFor(() => d.querySelectorAll('#trend .tbtn[data-trend]').length > 0);
  const terms = [btn(0).dataset.trend, btn(1).dataset.trend];
  btn(0).click();
  await sleep(2500);
  btn(1).click();
  await waitFor(() => d.querySelectorAll('#feed .card').length > 0 ? true : false, 30000);
  await sleep(2500);

  const cards = Array.from(d.querySelectorAll('#feed .card'));
  const titles = cards.map((c) => (c.querySelector('.title') || {}).textContent || '').join(' | ');
  const hits = cards.filter((c) => {
    const t = ((c.querySelector('.title') || {}).textContent || '') + ' ' +
              ((c.querySelector('.summary') || {}).textContent || '');
    return terms.some((x) => t.toLowerCase().indexOf(x.toLowerCase()) >= 0);
  });
  console.log('  선택한 낱말: %s', terms.join(' + '));
  console.log('  카드 %d건 · 그중 낱말을 포함한 카드 %d건', cards.length, hits.length);
  console.log('  상태줄: %s', stamp().trim().slice(0, 90));
  console.log('  예시: %s', titles.slice(0, 110));
  const ok = cards.length > 0 && hits.length === cards.length;
  console.log('\n  %s', ok ? 'PASS 병합 결과가 모두 선택한 낱말과 관련됨' : 'FAIL 관련 없는 카드가 섞임');
  process.exit(ok ? 0 : 1);
})();
