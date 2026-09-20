// Teemo's Pick on the page: the badge a reader sees, the pill that filters, and the operator's
// toggle with its optional phrase.
//
// The API is simulated here rather than exercised: the pick has to be visible without a real pick
// existing in the archive, and a check must not edit the data it is inspecting. The stub marks the
// first story as picked on every feed answer and claims exactly one pick when the pill is on, so
// the badge, the count and the filtering can all be seen.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
const vc = new VirtualConsole();
vc.on('jsdomError', (e) => console.log('  [jsdomError]', e.message));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const waitFor = async (fn, ms = 20000, step = 300) => {
  const until = Date.now() + ms;
  while (Date.now() < until) { if (fn()) return true; await sleep(step); }
  return false;
};
const pass = [];
const check = (n, ok, d) => { pass.push(ok); console.log('  %s %s%s', ok ? 'PASS' : 'FAIL', n, d ? '  (' + d + ')' : ''); };

const NOTE = '직접 확인한 내용';
let writes = [];

function stubFetch(realFetch) {
  return async (u, o) => {
    const url = new URL(String(u), URL_);
    const method = ((o && o.method) || 'GET').toUpperCase();
    if (/^\/api\/(pick|unpick)$/.test(url.pathname)) {
      writes.push({ path: url.pathname, body: JSON.parse((o && o.body) || '{}') });
      return { ok: true, json: async () => ({ ok: true, picked_total: 1 }) };
    }
    if (url.pathname === '/api/hidden') {
      return { ok: true, json: async () => ({ hidden: [], total: 0 }) };
    }
    const picked = url.searchParams.get('picked') === '1';
    // The stub owns the pick state, so it asks the real server for the unfiltered list and applies
    // the pick itself. Letting the server filter would be asking the real archive about a pick that
    // only exists here - and the answer would be "none", which is what this check saw once the
    // server learned the parameter.
    const ask = new URL(url.href);
    ask.searchParams.delete('picked');
    const real = await realFetch(ask.href, { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: 'no-store' });
    if (url.pathname !== '/api/news') return { ok: real.ok, json: async () => real.json() };
    const payload = await real.json();
    if (picked) {
      payload.articles = (payload.articles || []).slice(0, 1);
      payload.total = payload.articles.length;
    }
    // The first story is the picked one in this simulated feed, and it stays marked when the pill
    // filters down to it - the server marks every row it returns, filtered or not.
    if (payload.articles && payload.articles.length) {
      payload.articles = payload.articles.map((a, i) => (i === 0
        ? Object.assign({}, a, { picked: true, pick_note: NOTE }) : Object.assign({}, a, { picked: false })));
    }
    return { ok: real.ok, json: async () => payload };
  };
}

(async () => {
  const page = await (await fetch(URL_ + '?p=' + Date.now())).text();
  const dom = new JSDOM(page, {
    runScripts: 'dangerously', url: URL_, pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = stubFetch(fetch);
      w.prompt = () => NOTE;   // the phrase prompt, answered here
    },
  });
  const w = dom.window, d = w.document;
  await waitFor(() => d.querySelectorAll('#feed .card').length > 0);
  await sleep(1200);

  const cards = () => Array.from(d.querySelectorAll('#feed .card'));
  const badges = () => Array.from(d.querySelectorAll('#feed .card .pickbadge'));
  const pickPill = () => d.querySelector('.pills button[data-pick]');
  const chipTexts = () => Array.from(d.querySelectorAll('#conds [data-cond-off]')).map((b) => b.textContent);

  check('Teemo\'s Pick 알약이 있음', !!pickPill() && /Teemo's Pick/.test(pickPill().textContent),
    pickPill() ? pickPill().textContent : '없음');
  check('Pick 알약은 기본으로 꺼져 있음', pickPill().getAttribute('aria-pressed') === 'false');

  check('골라낸 카드에 배지가 붙음', badges().length === 1, badges().length + '개');
  check('배지에 버섯과 문구가 함께 있음',
    badges().length > 0 && /\ud83c\udf44/.test(badges()[0].textContent) && badges()[0].textContent.indexOf(NOTE) >= 0,
    badges().length ? badges()[0].textContent.trim().slice(0, 46) : '없음');
  check('카드에 언어가 지정됨', !!cards()[0].querySelector('.title[lang]'),
    (cards()[0].querySelector('.title') || {}).getAttribute ? cards()[0].querySelector('.title').getAttribute('lang') : '없음');
  check('배지가 제목 위에 옴', badges().length > 0
    && badges()[0].compareDocumentPosition(cards()[0].querySelector('.title'))
      & w.Node.DOCUMENT_POSITION_FOLLOWING,
    'ok');

  // The pill narrows the feed and, like every other selection, turns into a condition with a count.
  pickPill().click();
  await sleep(2500);
  check('알약을 누르면 조건 칩이 생김',
    chipTexts().some((t) => t.indexOf("Teemo's Pick") >= 0), chipTexts().join(' / ') || '없음');
  check('칩에 그 조건의 건수가 붙음',
    (d.querySelector('#conds [data-cond-off] .n') || {}).textContent === '1',
    (d.querySelector('#conds [data-cond-off] .n') || {}).textContent || '없음');
  check('골라낸 기사만 남음', cards().length === 1 && badges().length === 1,
    cards().length + '장 / 배지 ' + badges().length);
  check('알약이 켜진 상태가 됨', pickPill().getAttribute('aria-pressed') === 'true');

  // Releasing the condition puts the list back, from the same row as every other condition.
  d.querySelector('#conds [data-cond-off]').click();
  await sleep(2500);
  check('칩을 풀면 알약도 꺼짐', pickPill().getAttribute('aria-pressed') === 'false');
  check('칩이 사라짐', !chipTexts().some((t) => t.indexOf("Teemo's Pick") >= 0), chipTexts().join(' / ') || '없음');
  check('목록이 다시 넓어짐', cards().length > 1, cards().length + '장');

  // The operator's toggle: the second card is not picked, so the click picks it and sends the phrase.
  const plain = cards().find((c) => !c.querySelector('.pickbadge'));
  const btn = plain && plain.querySelector('[data-picklink]');
  check('카드에 Pick 컨트롤이 있음', !!btn, btn ? btn.textContent.trim() : '없음');
  if (btn) {
    check('Pick 버튼의 상태가 꺼짐으로 표시됨', btn.dataset.picked === '0', btn.dataset.picked);
    btn.click();
    await sleep(1500);
    const call = writes.filter((x) => x.path === '/api/pick')[0];
    check('Pick이 링크와 문구를 보냄', !!call && call.body.link === btn.dataset.picklink
      && call.body.note === NOTE, call ? call.body.note : '호출 없음');
  }

  // And the picked card offers the way back.
  const onBadge = badges()[0];
  const onCard = onBadge && onBadge.closest('.card');
  const onBtn = onCard && onCard.querySelector('[data-picklink]');
  check('골라낸 카드의 컨트롤이 해제로 표시됨', !!onBtn && onBtn.dataset.picked === '1',
    onBtn ? onBtn.textContent.trim() : '없음');
  if (onBtn) {
    onBtn.click();
    await sleep(1500);
    check('해제가 그 링크를 보냄', writes.some((x) => x.path === '/api/unpick'
      && x.body.link === onBtn.dataset.picklink), writes.length + '회 호출');
  }

  const bad = pass.filter((x) => !x).length;
  console.log('\n  %d/%d', pass.length - bad, pass.length);
  process.exit(bad ? 1 : 0);
})().catch((e) => { console.log('  [error]', e.message); process.exit(1); });
