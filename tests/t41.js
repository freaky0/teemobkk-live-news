// Deterministic headline and cross-language trend contracts on generated documents.
const {spawnSync} = require('node:child_process');
const {JSDOM} = require('jsdom');
const assert = require('node:assert/strict');
const python = spawnSync('python', ['-c', `import page_build,sys
sys.stdout.write(page_build.render(public=True,datadir='',want_thai=sys.argv[2]=='thai',icon_prefix='',admin=sys.argv[1]=='admin',lang=sys.argv[1] if sys.argv[1]!='admin' else 'ko'))`, process.argv[2] || 'en', process.argv[3] || 'global'], {cwd: require('node:path').join(__dirname,'..'),encoding:'utf8'});
assert.equal(python.status, 0, python.stderr);
const dom = new JSDOM(python.stdout, {url:'http://localhost/',runScripts:'dangerously',beforeParse(w){
  w.fetch = async () => ({ok:true,json:async()=>({articles:[],hidden:[]})});
}});
const w = dom.window, d = w.document;
const title = 'Market & <policy> reut.rs/abc - Publisher';
const story = {title,link:'https://example.com/raw',source:'Example',published_at:new Date().toISOString()};
const article = w.eval('card')(story,false,false,false,false);
const node = new JSDOM(article).window.document;
assert.equal(node.querySelector('.title').textContent, 'Market & <policy>');
assert.equal(node.querySelector('.title a').getAttribute('href'), story.link);
if (process.argv[2] === 'admin') {
  assert.equal(node.querySelector('[data-hide]').dataset.title, title);
  assert.equal(node.querySelector('[data-picklink]').dataset.title, title);
  w.eval(`HIDE_UNDO=${JSON.stringify({link:story.link,title})}; renderUndo()`);
  assert.equal(d.querySelector('#undobar .utext').textContent, 'Market & <policy>');
  assert.equal(w.eval('HIDE_UNDO.title'), title);
  w.fetch = async u => ({ok:true,json:async()=>({hidden:[{link:story.link,title}]})});
  w.eval('loadHidden()');
  setTimeout(()=>{
    try {assert.equal(d.querySelector('#hidden .hidrow a').textContent,'Market & <policy>');
      assert.equal(d.querySelector('#hidden [data-unhide]').dataset.unhide,story.link);console.log('admin title OK');process.exit(0)}
    catch(e){console.error(e);process.exit(1)}
  },50);
} else {
  const thai = process.argv[3] === 'thai';
  const rows = [
    ...Array.from({length:3},(_,i)=>({title:'Trump meets leaders '+i,link:'https://example.com/en'+i})),
    ...Array.from({length:3},(_,i)=>({title:'트럼프 회담 '+i,link:'https://example.com/ko'+i})),
    ...Array.from({length:3},(_,i)=>({title:'ทรัมป์ พบผู้นำ '+i,link:'https://example.com/th'+i})),
    {title:'ทรัมป์ประกาศนโยบาย',link:'https://example.com/th-joined'},
    ...Array.from({length:3},(_,i)=>({title:'ตลาดหุ้นปรับตัวลดลง '+i,link:'https://example.com/raw'+i})),
    ...Array.from({length:3},(_,i)=>({title:'Trumpet concerts '+i,link:'https://example.com/unrelated'+i}))
  ];
  w.eval(`MEM[${JSON.stringify(thai?'태국':'글로벌')}]=${JSON.stringify(rows)};V.tab=${JSON.stringify(thai?'thai':'global')}`);
  const trends = w.eval('trends()');
  const trump = trends.filter(x=>x.t === 'trend:trump');
  assert.equal(trump.length,1,JSON.stringify(trends));
  assert.equal(trump[0].c,10,JSON.stringify(trends));
  assert.equal(trump[0].label,process.argv[2]==='ko'?'트럼프':'Trump');
  assert.ok(trends.some(x=>x.t.includes('ตลาดหุ้น') && x.label.includes(process.argv[2]==='ko'?'태국어':'Thai')),JSON.stringify(trends));
  assert.equal(w.eval('termMatch("Trump visits", "trend:trump")'),true);
  assert.equal(w.eval('termMatch("트럼프 방문", "trend:trump")'),true);
  assert.equal(w.eval('termMatch("ทรัมป์ พบ", "trend:trump")'),true);
  assert.equal(w.eval('termMatch("Trumpet concerts", "trend:trump")'),false);
  console.log(process.argv[2],process.argv[3],'trends OK');process.exit(0);
}
