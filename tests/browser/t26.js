// Calendar specifics: the time-basis line and the Fed voter marks must reach the DOM.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';

const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => {
        const s = new URL(String(u), URL_).href;
        return fetch(s, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
      };
    },
  });
  const w = dom.window, d = w.document;
  await sleep(9000);

  d.querySelector('#tab-cal').click();
  await sleep(4000);

  const sum = (d.querySelector('#cal-sum') || {}).textContent || '';
  console.log('  cal-sum:', sum.slice(0, 130));
  console.log('  시간 기준 표시:', /시각 기준 KST/.test(sum) ? 'PASS' : 'FAIL');
  console.log('  방콕 시차 표시:', /방콕은 여기서 2시간/.test(sum) ? 'PASS' : 'FAIL');
  console.log('  연준 명단 기준:', /연준 인물 명단 2026년 기준/.test(sum) ? 'PASS' : 'FAIL');

  const rows = [...d.querySelectorAll('.cal-row.speech')];
  console.log('  연설 행 %d개', rows.length);
  let marked = 0;
  rows.forEach((r) => {
    const name = (r.querySelector('.cal-n') || {}).textContent || '';
    const val = (r.querySelector('.cal-v') || {}).textContent || '';
    if (val) marked++;
    console.log('     %-42s | %s', name.trim().slice(0, 42), val.trim() || '(없음)');
  });
  console.log('  발언권 표시된 행: %d → %s', marked, marked > 0 ? 'PASS' : '(연준 인물 없음 — 데이터에 따라 정상)');
  process.exit(0);
})();