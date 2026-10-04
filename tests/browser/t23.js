// P1 check: does the verification chip appear on exactly the official/social cards?
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';

const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  let api = null;
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => {
        const s = new URL(String(u), URL_).href;
        if (s.includes('/api/news')) {
          const r = await fetch(s, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' } });
          const t = await r.text();
          try { api = JSON.parse(t); } catch (e) { console.log('  [json]', e.message); }
          return { ok: r.ok, status: r.status, headers: r.headers, json: async () => JSON.parse(t), text: async () => t };
        }
        return fetch(s, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
      };
    },
  });
  const d = dom.window.document;
  await sleep(11000);

  const cards = [...d.querySelectorAll('#feed .card')];
  console.log('  카드:', cards.length, '| API:', api ? api.articles.length + '건' : '(없음)');

  let off = 0, sns = 0, other = 0;
  const wrong = [];
  cards.forEach((c, i) => {
    const v = c.querySelector('.chip.verif');
    const label = v ? v.textContent.trim() : '';
    const src = (c.querySelector('.chip.src') || {}).textContent || '';
    if (label === '공식') off++;
    else if (label === 'SNS') sns++;
    else other++;
    if (v) console.log('    card%02d %-4s %s (%s)', i, label, src.trim().slice(0, 22), (v.title || '').slice(0, 20));
  });
  console.log('  라벨: 공식 %d · SNS %d · 없음 %d', off, sns, other);

  // Cross-check against the API payload so the label is not applied by accident.
  if (api) {
    const inView = api.articles.slice(0, cards.length);
    const wantOff = inView.filter((a) => a.source_type === 'official').length;
    const wantSns = inView.filter((a) => a.source_type === 'social').length;
    console.log('  기대: 공식 %d · SNS %d  →  %s',
      wantOff, wantSns, (wantOff === off && wantSns === sns) ? 'PASS' : 'FAIL');
  }
  process.exit(0);
})();