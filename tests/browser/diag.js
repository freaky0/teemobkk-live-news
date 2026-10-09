// Diagnose the deployed section page: does the API call succeed, and do the pills appear?
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2];
const WAIT = Number(process.argv[3]) || 12000;
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message.slice(0, 160)));

(async () => {
  const page = await (await fetch(URL_)).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => {
        const full = new URL(String(u), URL_).href;
        try {
          const r = await fetch(full, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' } });
          console.log('  fetch %s -> %s', full.replace('https://teemobkk.io', ''), r.status);
          return r;
        } catch (e) {
          console.log('  fetch %s -> ERROR %s', full, e.message);
          throw e;
        }
      };
    },
  });
  const d = dom.window.document;
  await new Promise((r) => setTimeout(r, WAIT));
  console.log('  카드: %d (시드 %d)',
    d.querySelectorAll('#feed .card').length, d.querySelectorAll('#feed .card.seed').length);
  console.log('  알약: %d 개 → %s', d.querySelectorAll('#filters-global button').length,
    Array.from(d.querySelectorAll('#filters-global button')).map((b) => b.textContent.trim()).slice(0, 4).join(' / '));
  console.log('  상태문구: %s', (d.querySelector('#conn, .status, #status') || {}).textContent?.trim().slice(0, 60));
  process.exit(0);
})();