(function(){
'use strict';
var ticker=document.getElementById('ticker'),tickerInner=document.getElementById('ticker-inner'),
    stateBox=document.getElementById('ticker-state'),stateText=document.getElementById('ticker-state-text'),
    ageText=document.getElementById('ticker-age');
if(!ticker||!tickerInner||!stateBox||!stateText||!ageText)return;

/* MEXC spot miniTicker, official protobuf wrapper:
   PushDataV3ApiWrapper.publicMiniTicker = field 309, and inside it
   symbol = 1, price = 2, zonedRate = 4. The @24H subscription makes
   zonedRate the rolling 24-hour change. */
var SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','BNBUSDT','DOGEUSDT','ADAUSDT','LINKUSDT'];
var LABELS={BTCUSDT:'BTC/USDT',ETHUSDT:'ETH/USDT',SOLUSDT:'SOL/USDT',XRPUSDT:'XRP/USDT',
            BNBUSDT:'BNB/USDT',DOGEUSDT:'DOGE/USDT',ADAUSDT:'ADA/USDT',LINKUSDT:'LINK/USDT'};
var ALLOW=Object.create(null);
SYMBOLS.forEach(function(symbol){ALLOW[symbol]=LABELS[symbol];});
var WS_URL='wss://wbs-api.mexc.com/ws';
var MACRO_URL='https://stooq.com/q/l/?s=%5Endq,%5Espx,xauusd,dx.f,%5Etnx,cl.f&f=sd2t2ohlcv&h&e=csv';
var MACRO_NAMES={'^ndq':'NASDAQ','^spx':'S&P 500','xauusd':'GOLD','dx.f':'DXY','^tnx':'US 10Y','cl.f':'WTI'};
var STALE_MS=45000,UI_MS=5000,PING_MS=25000,RETRY_BASE=2000,RETRY_MAX=60000,
    ROTATE_MS=23*60*60*1000+50*60*1000;
var cryptoRows=Object.create(null),macroRows=[],ws=null,reconnectTimer=null,pingTimer=null,
    rotateTimer=null,lastValidAt=0,openedAt=0,retryAttempt=0;
var decoder=typeof TextDecoder!=='undefined'?new TextDecoder('utf-8'):null;

function decodeUtf8(bytes){
  if(decoder)return decoder.decode(bytes);
  var text='';
  for(var i=0;i<bytes.length;i++)text+=String.fromCharCode(bytes[i]);
  return text;
}
function readVarint(bytes,state){
  var value=0,mult=1,b;
  do{
    if(state.i>=bytes.length)throw new Error('varint');
    b=bytes[state.i++];
    value+=(b&0x7f)*mult;
    mult*=128;
    if(mult>9007199254740992)throw new Error('varint');
  }while(b&0x80);
  return value;
}
function parseFields(bytes){
  var fields=Object.create(null),state={i:0};
  while(state.i<bytes.length){
    var tag=readVarint(bytes,state),field=Math.floor(tag/8),wire=tag&7;
    if(!field)throw new Error('field');
    if(wire===0){fields[field]={wire:0,value:readVarint(bytes,state)};}
    else if(wire===1){
      if(state.i+8>bytes.length)throw new Error('fixed64');
      state.i+=8;
    }else if(wire===2){
      var length=readVarint(bytes,state);
      if(length<0||state.i+length>bytes.length)throw new Error('length');
      fields[field]={wire:2,value:bytes.subarray(state.i,state.i+length)};
      state.i+=length;
    }else if(wire===5){
      if(state.i+4>bytes.length)throw new Error('fixed32');
      state.i+=4;
    }else{
      throw new Error('wire');
    }
  }
  return fields;
}
function decimalField(entry,min,max){
  if(!entry||entry.wire!==2)return null;
  var raw=decodeUtf8(entry.value).trim();
  if(!raw||raw.length>32||!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw))return null;
  var value=Number(raw);
  if(!isFinite(value)||value<min||value>max)return null;
  return value;
}
function groupFixed(value,digits){
  var parts=value.toFixed(digits).split('.');
  parts[0]=parts[0].replace(/\B(?=(\d{3})+(?!\d))/g,',');
  return parts.join('.');
}
function formatPrice(value){
  if(value>=1)return groupFixed(value,2);
  if(value>=0.01)return groupFixed(value,4);
  return groupFixed(value,8);
}
function formatChange(value){
  if(Math.abs(value)<0.005)return '0.00%';
  var sign=value>0?'+':(value<0?'':'');
  var abs=Math.abs(value);
  return sign+value.toFixed(abs>=100?0:(abs>=10?1:2))+'%';
}
function formatAge(ms){
  if(ms<8000)return '방금';
  var seconds=Math.round(ms/1000);
  if(seconds<90)return seconds+'초 전';
  var minutes=Math.round(seconds/60);
  return minutes+'분 전';
}
function setState(kind,text){
  if(stateBox.getAttribute('data-state')!==kind)stateBox.setAttribute('data-state',kind);
  if(stateText.textContent!==text)stateText.textContent=text;
}
function makeTick(label,price,change,kind){
  var row=document.createElement('span');row.className='tick';
  var name=document.createElement('b');name.textContent=label;
  var value=document.createElement('span');value.textContent=formatPrice(price);
  var rate=document.createElement('span');rate.className=change>0?'up':(change<0?'dn':'flat');
  rate.textContent=formatChange(change);
  row.title=label+(kind==='crypto'?' · 24시간 변동':' · 당일 변동');
  row.append(name,document.createTextNode(' '),value,document.createTextNode(' '),rate);
  return row;
}
function renderTicker(){
  var sequence=document.createElement('span');sequence.className='ticker-seq';
  SYMBOLS.forEach(function(symbol){
    var row=cryptoRows[symbol];
    if(row)sequence.append(makeTick(ALLOW[symbol],row.price,row.change,'crypto'));
  });
  macroRows.forEach(function(row){
    sequence.append(makeTick(row.label,row.price,row.change,'macro'));
  });
  if(!sequence.childNodes.length){tickerInner.replaceChildren();return;}
  var duplicate=sequence.cloneNode(true);duplicate.setAttribute('aria-hidden','true');
  tickerInner.replaceChildren(sequence,duplicate);
}
function readMiniTicker(buffer){
  try{
    var wrapper=parseFields(new Uint8Array(buffer)),body=wrapper[309];
    if(!body||body.wire!==2)return;
    var item=parseFields(body.value);
    var symbol=item[1]&&item[1].wire===2?decodeUtf8(item[1].value).trim().toUpperCase():'';
    if(!symbol&&wrapper[3]&&wrapper[3].wire===2)symbol=decodeUtf8(wrapper[3].value).trim().toUpperCase();
    if(!ALLOW[symbol])return;
    var price=decimalField(item[2],0,1000000000000);
    var change=decimalField(item[4],-1,1000);
    if(price===null||price<=0||change===null)return;
    /* MEXC returns zonedRate as a fraction (0.0766 is 7.66%), so convert once. */
    cryptoRows[symbol]={price:price,change:change*100};
    lastValidAt=Date.now();retryAttempt=0;
    renderTicker();updateFreshness();
  }catch(error){}
}
function handleText(data){
  var message;
  try{message=JSON.parse(data);}catch(error){return;}
  if(!message||typeof message!=='object')return;
  if(message.msg==='PONG')return;
}
function handleMessage(data){
  if(typeof data==='string'){handleText(data);return;}
  if(data instanceof ArrayBuffer){readMiniTicker(data);return;}
  if(typeof Blob!=='undefined'&&data instanceof Blob){
    try{data.arrayBuffer().then(readMiniTicker).catch(function(){});}catch(error){}
  }
}
function updateFreshness(){
  var now=Date.now();
  if(lastValidAt)ageText.textContent='· '+formatAge(now-lastValidAt);
  else ageText.textContent='';
  if(!ws||ws.readyState!==1)return;
  if(lastValidAt&&now-lastValidAt>STALE_MS){setState('stale','MEXC 지연 · 24시간 변동');}
  else if(lastValidAt){setState('live','MEXC 실시간 · 24시간 변동');}
  else if(openedAt&&now-openedAt>STALE_MS){setState('stale','MEXC 연결됨 · 시세 대기');}
}
function clearSocketTimers(){
  if(pingTimer){clearInterval(pingTimer);pingTimer=null;}
  if(rotateTimer){clearTimeout(rotateTimer);rotateTimer=null;}
}
function closeSocket(){
  clearSocketTimers();
  if(ws){
    ws.onopen=ws.onmessage=ws.onerror=ws.onclose=null;
    try{ws.close();}catch(error){}
    ws=null;
  }
}
function scheduleRetry(){
  clearSocketTimers();
  retryAttempt+=1;
  var delay=Math.min(RETRY_MAX,RETRY_BASE*Math.pow(1.8,retryAttempt-1));
  delay=Math.round(delay*(0.85+Math.random()*0.3));
  setState('reconnecting','MEXC 재연결 중');
  if(reconnectTimer){clearTimeout(reconnectTimer);}
  reconnectTimer=setTimeout(connect,delay);
}
function connect(){
  closeSocket();
  if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}
  lastValidAt=0;openedAt=0;
  setState('connecting',retryAttempt?'MEXC 재연결 중':'MEXC 연결 중');
  if(typeof WebSocket==='undefined'){setState('unsupported','MEXC 실시간 미지원');return;}
  var socket;
  try{socket=new WebSocket(WS_URL);}catch(error){scheduleRetry();return;}
  ws=socket;socket.binaryType='arraybuffer';
  socket.onopen=function(){
    if(ws!==socket)return;
    openedAt=Date.now();
    setState('connecting','MEXC 구독 중');
    try{
      socket.send(JSON.stringify({
        method:'SUBSCRIPTION',
        params:SYMBOLS.map(function(symbol){
          return 'spot@public.miniTicker.v3.api.pb@'+symbol+'@24H';
        })
      }));
    }catch(error){}
    pingTimer=setInterval(function(){
      if(ws===socket&&socket.readyState===1){try{socket.send('{"method":"PING"}');}catch(error){}}
    },PING_MS);
    /* The documented connection limit is 24 hours. Rotate at 23h50m so the
       ticker reconnects before the server closes it. */
    rotateTimer=setTimeout(function(){if(ws===socket)connect();},ROTATE_MS);
  };
  socket.onmessage=function(event){if(ws===socket)handleMessage(event.data);};
  socket.onerror=function(){if(ws!==socket)return;try{socket.close();}catch(error){}};
  socket.onclose=function(){
    if(ws!==socket)return;
    ws=null;clearSocketTimers();lastValidAt=0;openedAt=0;ageText.textContent='';
    scheduleRetry();
  };
}
async function loadMacro(){
  try{
    var controller=new AbortController(),timeout=setTimeout(function(){controller.abort();},8000);
    var response=await fetch(MACRO_URL,{signal:controller.signal,cache:'no-store'});
    clearTimeout(timeout);
    if(!response.ok)return;
    var text=await response.text(),lines=text.trim().split(/\r?\n/).slice(1),rows=[];
    for(var i=0;i<lines.length;i++){
      var cells=lines[i].split(',');
      if(cells.length<7)continue;
      var symbol=String(cells[0]||'').toLowerCase(),close=Number(cells[6]),open=Number(cells[3]);
      if(!isFinite(close)||!isFinite(open)||open<=0||close<=0)continue;
      var change=(close-open)/open*100;
      if(!isFinite(change))continue;
      rows.push({label:MACRO_NAMES[symbol]||symbol.toUpperCase(),price:close,change:change});
    }
    if(rows.length){macroRows=rows;renderTicker();}
  }catch(error){}
}
ticker.hidden=false;
renderTicker();
connect();
updateFreshness();
loadMacro();
setInterval(updateFreshness,UI_MS);
setInterval(function(){if(!document.hidden)loadMacro();},300000);
window.addEventListener('online',function(){
  if(!ws||ws.readyState>1){if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}connect();}
});
document.addEventListener('visibilitychange',function(){
  if(document.hidden)return;
  updateFreshness();
  if(!ws||ws.readyState>1){if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}connect();}
});
window.addEventListener('pagehide',function(){closeSocket();if(reconnectTimer){clearTimeout(reconnectTimer);reconnectTimer=null;}});
window.addEventListener('pageshow',function(event){if(event.persisted)connect();});
})();
