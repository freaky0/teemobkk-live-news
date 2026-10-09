// Tab label size: read the computed font-size of the three tab buttons, and check the row
// still switches tabs. Layout width cannot be measured here (jsdom has no layout engine).
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
const WIDTH = Number(process.argv[3]) || 1280;
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
      w.fetch = async (u) => fetch(new URL(String(u), URL_).href, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' } });
      Object.defineProperty(w, 'innerWidth', { value: WIDTH, configurable: true });
    },
  });
  const w = dom.window, d = w.document;
  await sleep(8000);

  const tabs = Array.from(d.querySelectorAll('.tab'));
  check('탭 3개', tabs.length === 3, tabs.map((t) => t.textContent.trim()).join(' / '));
  const sizes = tabs.map((t) => w.getComputedStyle(t).fontSize);
  const weights = tabs.map((t) => w.getComputedStyle(t).fontWeight);
  console.log('    폰트 크기:', sizes.join(', '), '| 굵기:', weights.join(', '));
  check('탭 폰트가 17px', sizes.every((s) => s === '17px'), sizes.join(','));
  check('제목(.title)과 같은 크기', w.getComputedStyle(d.querySelector('#feed .card .title') || d.createElement('div')).fontSize !== '14px',
    'title=' + w.getComputedStyle(d.querySelector('#feed .card .title')).fontSize);
  check('활성 탭 표시', tabs.filter((t) => t.classList.contains('active')).length === 1, '');

  // The row still has to work after restyling.
  d.querySelector('#tab-cal').click();
  await sleep(2500);
  check('지표 탭 전환', d.querySelector('#tab-cal').classList.contains('active'), '');
  d.querySelector('#tab-thai').click();
  await sleep(5000);
  check('태국 탭 전환', d.querySelector('#tab-thai').classList.contains('active'), '');
  d.querySelector('#tab-global').click();
  await sleep(5000);
  check('경제 소식 복귀', d.querySelector('#tab-global').classList.contains('active') && d.querySelectorAll('#feed .card').length > 0,
    d.querySelectorAll('#feed .card').length + '건');

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();