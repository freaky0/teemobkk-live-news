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
<meta name="robots" content="noindex">
<title>관리자 로그인 · TeemoBKK</title>
<style>
html{background:#05070d;color:#e8eefc}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;
  font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif}
form{width:100%;max-width:340px;background:#0b1120;border:1px solid #1e2a45;border-radius:14px;padding:22px}
h1{margin:0 0 4px;font-size:16px;letter-spacing:-.01em}
p.note{margin:0 0 16px;color:#8b9bbd;font-size:13px}
label{display:block;font-size:12px;color:#8b9bbd;margin-bottom:6px}
input{width:100%;box-sizing:border-box;padding:11px 12px;border-radius:9px;border:1px solid #1e2a45;
  background:#070c16;color:#e8eefc;font-size:15px}
input:focus{outline:none;border-color:#2f7fd8}
button{margin-top:14px;width:100%;padding:11px;border:0;border-radius:9px;background:#2f7fd8;color:#fff;
  font-size:15px;font-weight:600;cursor:pointer}
button[disabled]{opacity:.55;cursor:default}
#msg{margin-top:12px;font-size:13px;color:#ff9d9d;min-height:18px}
</style>
</head>
<body>
<form id="f">
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
    return LOGIN.replace("</script>", "document.querySelector('#msg').textContent=%s;</script>"
                         % _js_string(status_note))


def _js_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("<", "\\u003c") + '"'


def operator_page() -> str:
    """The dashboard with the operator panels, told it has a session.

    The flag is what the script checks before it sends a write and before it offers the logout
    control; the session itself is the cookie, which this document never sees.
    """
    import page_build

    html = page_build.admin_page(icon_prefix="/")
    if "<script>" in html:
        return html.replace("<script>", "<script>window.__ADMIN__=true;", 1)
    return html
