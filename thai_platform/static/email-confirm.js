(() => {
'use strict';
const params=new URLSearchParams(location.hash.slice(1));
const challenge=params.get('id')||'',token=params.get('token')||'';
// Remove the bearer token before any further navigation. Never persist it.
history.replaceState(null,'',location.pathname);
if(/^[0-9a-f-]{36}$/i.test(challenge)&&token.length>0&&token.length<=500){
 document.querySelector('#email-challenge').value=challenge;
 document.querySelector('#email-token').value=token;
 document.querySelector('#email-confirm-button').disabled=false;
 document.querySelector('#email-confirm-status').textContent='직접 요청한 인증 링크인지 확인한 뒤 계속하세요.';
}
})();
