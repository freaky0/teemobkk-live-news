// Economic-calendar priority and country filters run entirely against a deterministic fixture.
const {spawnSync} = require('node:child_process');
const {JSDOM} = require('jsdom');
const assert = require('node:assert/strict');
const path = require('node:path');
const PY = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const lang = process.argv[2] || 'ko';
const python = spawnSync(PY, ['-c', `import page_build,sys
sys.stdout.write(page_build.render(public=True,datadir='',want_thai=False,icon_prefix='/',admin=False,lang=sys.argv[1]))`, lang], {
  cwd: path.join(__dirname, '..', '..', 'pages', 'build'), encoding: 'utf8',
  env: {...process.env, PYTHONIOENCODING:'utf-8'}
});
assert.equal(python.status, 0, python.stderr);
const fixture = {updated_at_kst:'2026-10-29 09:00',fed_roster_as_of:'2026-10-01',days:[{
  date:'2026-10-29',label:'Thursday',weekday:'Thu',events:[
    {kst:'10:00',country:'United States',country_code:'US',name:'CPI',name_ko:'물가 지표',importance:5,kind:'econ',released:false,passed:false},
    {kst:'09:00',country:'Thailand',country_code:'TH',name:'GDP',name_ko:'태국 GDP',importance:3,kind:'econ',released:false,passed:false},
    {kst:'11:00',country:'Thailand',country_code:'TH',name:'Rate decision',name_ko:'금리 결정',importance:4,kind:'econ',released:false,passed:false},
    {kst:'12:00',country:'Thailand',country_code:'TH',name:'Trade balance',name_ko:'무역 수지',importance:2,kind:'econ',released:false,passed:false}
  ]
}]};
const dom = new JSDOM(python.stdout, {url:'http://localhost/',runScripts:'dangerously',pretendToBeVisual:true,beforeParse(w){
  w.fetch = async u => String(u).includes('/api/calendar')
    ? {ok:true,json:async()=>fixture}
    : {ok:true,json:async()=>({articles:[],hidden:[]})};
}});
const {window:w} = dom, d = w.document;
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
(async()=>{
  d.querySelector('#tab-cal').click();
  await wait(40);
  const rows = () => [...d.querySelectorAll('#cal-body .cal-row')];
  assert.deepEqual(rows().map(row=>['i5','i4','i3','i2'].find(level=>row.classList.contains(level))), ['i5','i4','i3','i2']);
  const country = d.querySelector('#cal-country'), importance = d.querySelector('#cal-importance');
  assert.deepEqual([...country.options].map(option=>option.value), ['', 'TH', 'US']);
  country.value='TH';country.dispatchEvent(new w.Event('change'));
  assert.equal(rows().length, 3);
  importance.value='4';importance.dispatchEvent(new w.Event('change'));
  assert.equal(rows().length, 1);
  assert.match(rows()[0].textContent, /금리 결정|Rate decision/);
  importance.value='5';importance.dispatchEvent(new w.Event('change'));
  assert.equal(rows().length, 0);
  assert.match(d.querySelector('.cal-no-matches').textContent, /조건에 맞는 일정|match these filters/);
  console.log('calendar priority and filter behavior OK ('+lang+')');
  w.close();
})().catch(error=>{console.error(error);process.exitCode=1;w.close()});
