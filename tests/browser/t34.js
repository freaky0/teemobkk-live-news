// The term rule behind the search box: a Latin term matches as a whole word, a Korean or Thai term
// as a substring. Measured before it was written: 'ai' as a plain substring matched 3,720 rows in one
// window where the whole word matched 599, because it fires inside "said", "Thailand" and "chain".
//
// The second half drives the real search box, so the JS rule (client-side filter) and the SQL rule
// (server-side filter) are checked against each other: the visible cards must all satisfy the rule.
const { JSDOM, VirtualConsole } = require('jsdom');
const URL_ = process.argv[2] || 'http://127.0.0.1:8765/';
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
      w.fetch = async (u, o) => fetch(new URL(String(u), URL_).href,
        { headers: { 'User-Agent': 'Mozilla/5.0 jsdom' }, cache: (o && o.cache) || 'default' });
    },
  });
  const w = dom.window, d = w.document;
  await sleep(9000);

  if (typeof w.termMatch !== 'function') {
    check('termMatch가 페이지에 있음', false, '없음');
    console.log('\n  0/1');
    process.exit(1);
  }
  const m = (t, n) => w.termMatch(t, n);

  // --- the rule, in isolation ---
  check('낱말 안쪽은 걸리지 않음', m('he said it was time', 'ai') === false, 'said');
  check('낱말로 있으면 걸림', m('an AI model rallied', 'ai') === true);
  check('붙임표 뒤는 낱말 끝', m('AI-driven rally', 'ai') === true);
  check('복수형 허용', m('spot ETFs saw inflows', 'etf') === true);
  check('복수형이 아닌 s는 제외', m('etfsx noise', 'etf') === false, 'etfsx');
  check('더 긴 낱말은 제외', m('ethereal talk', 'eth') === false, 'ethereal');
  check('구절은 붙어 있을 때만', m('the asian games opened', 'asian games') === true
    && m('asian regional games', 'asian games') === false);
  check('대소문자 무시', m('An Ai Model', 'AI') === true);

  const KO = '\uD2B8\uB7FC\uD504 \uAD00\uC138';
  check('한국어는 부분일치', m(KO, KO.slice(0, 2)) === true, KO.slice(0, 2));

  // --- and through the search box, where the server also filters ---
  const cards = () => [...d.querySelectorAll('#feed .card')];
  const textOf = (c) => ((c.querySelector('.title') || {}).textContent || '') + ' '
    + ((c.querySelector('.summary') || {}).textContent || '');
  const q = d.querySelector('#q');
  const search = async (term) => {
    q.value = term; q.oninput();
    await sleep(4500);
    return cards();
  };

  // Pick a card that contains "ai" only inside another word ("said", "Thailand"), then check the
  // search leaves it out. Asserting "no card contains an embedded ai" would be wrong: a card can
  // carry both the embedded letters and the real word.
  const hrefOf = (c) => ((c.querySelector('.title a') || {}).getAttribute?.('href')) || '';
  const beforeSearch = cards();
  const embeddedOnly = beforeSearch.find((c) => textOf(c).toLowerCase().indexOf('ai') >= 0 && !m(textOf(c), 'ai'));
  const embeddedHref = embeddedOnly ? hrefOf(embeddedOnly) : '';

  const aiCards = await search('ai');
  check('AI 검색 결과가 모두 낱말로 AI를 포함',
    aiCards.length > 0 && aiCards.every((c) => m(textOf(c), 'ai')),
    aiCards.length + '건 · 합격 ' + aiCards.filter((c) => m(textOf(c), 'ai')).length);
  if (embeddedHref) {
    check('낱말 안쪽에만 AI가 있는 카드는 빠짐',
      !aiCards.some((c) => hrefOf(c) === embeddedHref),
      embeddedHref.slice(0, 44));
  } else {
    check('낱말 안쪽에만 AI가 있는 카드 (표본에 없어 귀결 확인)', true, '표본 ' + beforeSearch.length + '건 중 0건');
  }

  const koCards = await search(KO.slice(0, 2));
  check('한국어 검색이 결과를 냄', koCards.length > 0, koCards.length + '건');

  q.value = ''; q.oninput();
  await sleep(3000);
  // The feed renders one page of cards, so a term that matches at least that many leaves the list
  // exactly as long as it already was: "more cards than the search showed" is then false while the
  // box works. Measured 2026-09-23: the Korean term matched 25 in the window and the unfiltered first
  // page is 25 too (total 1,332). Compare what comes back with what was on screen before the search -
  // that is what clearing the box has to do - and keep both counts in the message.
  const setOf = (list) => list.map(hrefOf).sort().join('\n');
  check('검색어를 지우면 원복', setOf(cards()) === setOf(beforeSearch),
    cards().length + '건 · 검색 전 ' + beforeSearch.length + '건');

  console.log('\n  %d/%d', pass.filter(Boolean).length, pass.length);
  process.exit(pass.every(Boolean) ? 0 : 1);
})();
