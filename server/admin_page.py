"""The two documents the collector answers /admin with.

The deployment serves its section pages from disk (`/news/*` is a file_server rule in front of the
collector), so an operator page placed among them would be readable by anyone. This module holds the
two things /admin can be instead, and the collector answers it only for a request that carries a
session:

  * `login_page()`    - a password box, nothing else. No dashboard markup at all, so the anonymous
                        response to /admin contains nothing to scrape.
  * `operator_page()` - the same dashboard the public sees, built with the operator panels and told
                        it has a session, so its writes carry the header the server wants and it can
                        offer a way out.

`operator_page` is the only place that needs the page builder, and it imports it inside the call:
the collector imports this module on the request path, and pulling the whole page builder in at
startup would make every run pay for a page most requests never ask for.
"""
from __future__ import annotations

LOGIN = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>(function(){try{var t=localStorage.getItem('tbn-theme');document.documentElement.dataset.theme=t==='dark'?'dark':'light'}catch(e){document.documentElement.dataset.theme='light'}})();</script>
<meta name="robots" content="noindex">
<title>관리자 로그인 · TeemoBKK</title>
<style>
:root{color-scheme:light;--bg:#fbfaf7;--surface:#fff;--text:#17181a;--muted:#454a50;
  --line:#e3ded4;--accent:#a02c22;--error:#8a5a12;--serif:"Noto Serif KR","Nanum Myeongjo","AppleMyungjo","Batang","바탕",Georgia,serif}
*{box-sizing:border-box}
html{background:var(--bg);color:var(--text)}
body{margin:0;min-height:100dvh;display:grid;place-items:center;padding:24px;
  font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",sans-serif}
form{width:100%;max-width:380px;background:var(--surface);border:1px solid var(--line);
  border-radius:4px;padding:28px}
.brand{display:block;margin-bottom:28px;font:700 26px/1.2 var(--serif);letter-spacing:-.035em}
.brand span{color:var(--accent)}
h1{margin:0 0 4px;font:700 26px/1.3 var(--serif);letter-spacing:-.045em}
p.note{margin:0 0 26px;color:var(--muted);font-size:13px}
label{display:block;font-size:13px;color:var(--text);font-weight:600;margin-bottom:8px}
input{width:100%;padding:11px 12px;border-radius:4px;border:1px solid var(--line);
  background:var(--surface);color:var(--text);font-size:15px}
input:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button{margin-top:16px;width:100%;min-height:44px;padding:10px;border:1px solid var(--accent);
  border-radius:4px;background:var(--accent);color:#f8f9f8;font-size:15px;font-weight:700;cursor:pointer}
button:hover{filter:brightness(.88)}
button[disabled]{opacity:.55;cursor:default}
#msg{margin-top:12px;font-size:13px;color:var(--error);min-height:18px}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#131417;--surface:#1b1d21;
  --text:#ececeb;--muted:#b9bcc0;--line:#2c2f34;--accent:#e0776c;--error:#d8ab5c}
  button{color:#17181a}}
html[data-theme="dark"]{color-scheme:dark;--bg:#131417;--surface:#1b1d21;--text:#ececeb;
  --muted:#b9bcc0;--line:#2c2f34;--accent:#e0776c;--error:#d8ab5c}
html[data-theme="dark"] button:not(.theme-toggle){color:#17181a}
html[data-theme="light"]{color-scheme:light;--bg:#fbfaf7;--surface:#fff;--text:#17181a;
  --muted:#454a50;--line:#e3ded4;--accent:#a02c22;--error:#8a5a12}
</style>
</head>
<body>
<form id="f">
  <span class="brand"><span>티모</span> 라이브뉴스</span>
  <h1>관리자 로그인</h1>
  <p class="note">TeemoBKK 라이브 뉴스 관리자 영역입니다.</p>
  <label for="pw">비밀번호</label>
  <input id="pw" type="password" autocomplete="current-password" autofocus>
  <button id="go" type="submit">로그인</button>
  <div id="msg" role="alert"></div>
</form>
<script>
const f=document.querySelector('#f'), pw=document.querySelector('#pw'),
      go=document.querySelector('#go'), msg=document.querySelector('#msg');
f.onsubmit=async ev=>{
  ev.preventDefault();
  if(!pw.value)return;
  go.disabled=true; msg.textContent='';
  try{
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({password:pw.value})});
    if(r.ok){location.replace('/admin/');return}
    msg.textContent=r.status===429?'시도가 너무 많습니다. 15분 뒤에 다시 시도해 주세요.':'비밀번호가 맞지 않습니다.';
  }catch(e){msg.textContent='연결할 수 없습니다.'}
  pw.value=''; go.disabled=false; pw.focus();
};
</script>
</body>
</html>
"""


def login_page(status_note: str = "") -> str:
    """The login document. `status_note` is set in the page, never echoed into the markup."""
    if not status_note:
        return LOGIN
    return LOGIN.replace("</body>", "<script>document.querySelector('#msg').textContent=%s;</script></body>"
                         % _js_string(status_note))


def _js_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("<", "\\u003c") + '"'


def operator_page() -> str:
    """The dashboard with the operator panels, told it has a session.

    The flag is what the script checks before it sends a write and before it offers the logout
    control; the session itself is the cookie, which this document never sees.
    """
    from pages.build import page_build

    html = page_build.admin_page(icon_prefix="/")
    if "<script>" in html:
        return html.replace("<script>", "<script>window.__ADMIN__=true;", 1)
    return html
