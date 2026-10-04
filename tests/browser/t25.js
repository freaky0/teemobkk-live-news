// P2 check: print the trend strip the page computes, then click one and count results.
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
  await sleep(10000);

  const strip = () => d.querySelector('#trend');
  const show = (label) => {
    const btns = [...strip().querySelectorAll('[data-trend]')];
    console.log('  %s (숨김=%s, %d개)', label, strip().hidden, btns.length);
    btns.forEach((b) => {
      const n = (b.querySelector('.n') || {}).textContent || '';
      console.log('     %-22s %s', b.dataset.trend, n);
    });
    return btns;
  };

  console.log('탭:', d.querySelector('.tab.active').textContent);
  const btns = show('경제 소식');

  // Clicking a trend must behave like typing it in the search box.
  if (btns.length) {
    const want = btns[0].dataset.trend;
    btns[0].click();
    await sleep(4500);
    const q = d.querySelector('#q').value;
    const countText = (d.querySelector('#counts') || {}).textContent || '';
    console.log('  클릭: "%s" → 검색어 "%s" | %s', want, q, countText.trim());
    const cards = d.querySelectorAll('#feed .card').length;
    console.log('  결과 카드 %d → %s', cards, cards > 0 ? 'PASS (0건 아님)' : 'FAIL (0건)');
  }

  // Switching to the calendar tab must hide the strip.
  d.querySelector('#tab-thai').click();
  await sleep(5000);
  const th = show('태국 소식');
  if (th.length) {
    th[0].click();
    await sleep(4500);
    console.log('  태국 클릭: "%s" → %s', th[0].dataset.trend, ((d.querySelector('#counts') || {}).textContent || '').trim());
    console.log('  태국 결과 카드 %d → %s', d.querySelectorAll('#feed .card').length,
      d.querySelectorAll('#feed .card').length > 0 ? 'PASS' : 'FAIL');
    d.querySelector('#q').value = ''; d.querySelector('#q').oninput(); await sleep(3000);
  }

  d.querySelector('#tab-cal').click();
  await sleep(1800);
  const hiddenOnCal = strip().hidden || getComputedStyle_(w, strip());
  console.log('  지표 탭에서 숨김: %s', hiddenOnCal ? 'PASS' : 'FAIL');
  d.querySelector('#tab-global').click();
  await sleep(1200);
  console.log('  복귀 후 표시: %s', !strip().hidden ? 'PASS' : 'FAIL');

  function getComputedStyle_(win, el) {
    const cs = win.getComputedStyle(el);
    return cs.display === 'none';
  }
  process.exit(0);
})();