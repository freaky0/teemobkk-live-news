// Load the LIVE page with the LIVE data (no fetch stubbing) and watch two refresh cycles.
const { JSDOM } = require('jsdom');

const URL_ = process.argv[2] || 'https://freaky0.github.io/teemobkk-live-news/';


const header = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) jsdom' };

async function grab(url) {
  const r = await fetch(url, { headers: header, cache: 'no-cache' });
  return { status: r.status, body: await r.text() };
}

(async () => {
  const page = await grab(URL_ + '?probe=' + Date.now());
  console.log('page:', page.status, page.body.length, 'bytes');
  const style = /<script>([\s\S]*)<\/script>/.exec(page.body);
  if (!style) { console.log('no script found'); process.exit(1); }

  const dom2 = new JSDOM(page.body, {
    runScripts: 'dangerously',
    url: URL_,
    pretendToBeVisual: true,
    beforeParse(w) {
      w.fetch = async (u, o) => {
        const s = String(u);
        const r = await fetch(s, { headers: header, cache: (o && o.cache) || 'default' });
        const text = await r.text();
        console.log('   fetch', s.replace(URL_, ''), '->', r.status, text.length + 'B');
        return { ok: r.ok, status: r.status, text: async () => text, json: async () => JSON.parse(text) };
      };
      w.setInterval = (fn, ms) => { console.log('   setInterval', ms); return 0; };
      w.scrollTo = () => { };
      w.addEventListener('error', (e) => console.log('   JS ERROR', e.message));
    }
  });
  const errors = [];
  dom2.window.addEventListener('error', (e) => errors.push(e.message));
  dom2.virtualConsole.on('jsdomError', (e) => errors.push('jsdomError: ' + e.message));

  setTimeout(() => {
    const d = dom2.window.document;
    console.log('--- after 6s ---');
    console.log('  header #updated :', d.querySelector('#updated') ? d.querySelector('#updated').textContent : 'MISSING');
    console.log('  stale badge    :', d.querySelector('#stale') ? d.querySelector('#stale').dataset.show : 'MISSING');
    console.log('  cards          :', d.querySelectorAll('#feed .card').length);
    console.log('  first title    :', d.querySelector('#feed .card .title') ? d.querySelector('#feed .card .title').textContent.slice(0, 50) : 'none');
    console.log('  counts         :', d.querySelector('#counts') ? d.querySelector('#counts').textContent : 'MISSING');
    console.log('  pill count text:', Array.from(d.querySelectorAll('.pill')).slice(0, 3).map(p => p.textContent).join(' | '));
    console.log('  sections       :', d.querySelectorAll('#feed .sec').length);
    console.log('  errors         :', errors.slice(0, 5));
    process.exit(0);
  }, 6000);
})();
