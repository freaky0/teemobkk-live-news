(() => {
'use strict';
const dialog=document.querySelector('#report-dialog');let trigger;
document.querySelector('[data-open-report]')?.addEventListener('click',e=>{trigger=e.currentTarget;dialog.showModal();document.querySelector('#report-title').focus();});
document.querySelector('[data-close-report]')?.addEventListener('click',()=>dialog.close());
dialog?.addEventListener('close',()=>trigger?.focus());
document.querySelectorAll('form[data-confirm]').forEach(f=>f.addEventListener('submit',e=>{if(!confirm(f.dataset.confirm))e.preventDefault();}));
function removeFailedNewsImage(image){if(!(image instanceof HTMLImageElement)||!image.classList.contains('news-image'))return;const item=image.closest('.news-item');const thumbnail=image.closest('.news-thumbnail');image.remove();if(item?.classList.contains('has-video'))thumbnail?.classList.add('no-poster');else{thumbnail?.remove();item?.classList.remove('has-image');}}
document.addEventListener('error',e=>removeFailedNewsImage(e.target),true);
document.querySelectorAll('img.news-image').forEach(image=>{if(image.complete&&image.naturalWidth===0)removeFailedNewsImage(image);});
const shareButton=document.querySelector('[data-share-article]');
shareButton?.addEventListener('click',async()=>{
const status=document.querySelector('[data-share-status]');
if(status)status.textContent='';
try{
if(typeof navigator.share==='function'){await navigator.share({title:shareButton.dataset.shareTitle||document.title,url:location.href});return;}
if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(location.href);if(status)status.textContent='기사 링크를 복사했습니다.';return;}
if(status)status.textContent='공유 기능을 사용할 수 없습니다. 주소 표시줄에서 링크를 복사해 주세요.';
}catch(error){if(error?.name!=='AbortError'&&status)status.textContent='공유하지 못했습니다. 주소 표시줄에서 링크를 복사해 주세요.';}
});
const scriptPrefix=(document.body.dataset.scriptPrefix||'').replace(/\/+$/,'');const listPage=[`${scriptPrefix}/`,`${scriptPrefix}/community/`,`${scriptPrefix}/newsroom/`].includes(location.pathname);const scrollKey='post-scroll:'+location.pathname+location.search;
function remember(){if(listPage)try{sessionStorage.setItem(scrollKey,String(scrollY));}catch{}}
window.addEventListener('pagehide',remember);document.addEventListener('click',e=>{if(e.target.closest('a[href]'))remember();});
window.addEventListener('pageshow',e=>{if(listPage&&!e.persisted)try{requestAnimationFrame(()=>scrollTo(0,Number(sessionStorage.getItem(scrollKey)||0)));}catch{}});
const user=document.body.dataset.userId,keyPrefix='post-draft:'+user+':';
try{const pending=sessionStorage.getItem('post-submitted:'+user);if(pending&&document.querySelector('[data-message-tags~="post-saved"]')){localStorage.removeItem(pending);sessionStorage.removeItem('post-submitted:'+user);}}catch{}
const form=document.querySelector('[data-editor]');if(!form)return;
const key=keyPrefix+form.dataset.draftKey,status=document.querySelector('#draft-status');let timer,dirty=false,submitting=false;
function read(){try{return JSON.parse(localStorage.getItem(key)||'null');}catch{return null;}}
function save(){const data={};for(const name of ['title','body','region','category'])data[name]=form.elements[name].value;try{localStorage.setItem(key,JSON.stringify(data));status.textContent='텍스트 초안을 이 브라우저에 자동 저장했습니다.';return true;}catch{status.textContent='초안 자동 저장 실패. 내용을 복사한 뒤 브라우저 저장소 설정을 확인하세요.';return false;}}
const stored=read();if(stored&&!form.hasAttribute('data-bound')){for(const name of ['title','body','region','category'])if(typeof stored[name]==='string')form.elements[name].value=stored[name];status.textContent='저장한 초안을 불러왔습니다. 서버에 등록하려면 아래 등록 버튼을 누르세요.';}
form.addEventListener('input',()=>{dirty=true;clearTimeout(timer);timer=setTimeout(save,300);});
form.addEventListener('change',()=>{dirty=true;save();});
form.addEventListener('submit',()=>{clearTimeout(timer);save();submitting=true;try{sessionStorage.setItem('post-submitted:'+user,key);}catch{}});
document.addEventListener('click',e=>{const a=e.target.closest('a[href]');if(a&&dirty&&!e.ctrlKey&&!e.metaKey&&!e.shiftKey){if(!confirm('작성 화면을 나갈까요? 텍스트 초안은 이 브라우저에 보관합니다.')){e.preventDefault();return;}save();dirty=false;}});
window.addEventListener('beforeunload',e=>{if(dirty&&!submitting){save();e.preventDefault();e.returnValue='';}});
})();
