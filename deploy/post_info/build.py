"""Build a form-free preview notice; no Django, DB, mail or OAuth runtime."""
from pathlib import Path
from html import escape
import argparse,hashlib,json,subprocess

REPO=Path(__file__).resolve().parents[2]
SERVE_ROOT='/opt/teemobkk-post-preview/info-only/notice-v1/public'
PATHS={'/':'index.html','/accounts/policy/terms/':'terms.html','/accounts/policy/privacy/':'privacy.html','/info-assets/style.css':'style.css','/info-assets/cat.webp':'cat.webp'}
CSS='''*{box-sizing:border-box}body{margin:0;background:#f4f9fd;color:#17395b;font-family:system-ui,-apple-system,"Noto Sans KR",sans-serif;font-size:16px;line-height:1.85}a{color:#174f82;text-underline-offset:4px;overflow-wrap:anywhere}a:focus-visible{outline:3px solid #ba7900;outline-offset:5px}header,main,footer{width:min(100% - 40px,760px);margin-inline:auto}header{display:flex;align-items:center;gap:14px;padding-block:28px;border-bottom:2px solid #17395b}header img{width:62px;height:62px;border-radius:50%;border:2px solid #efc145}header a{text-decoration:none;font-weight:800;line-height:1.2;font-size:21px}header small{display:block;font-size:13px;font-weight:500;margin-top:8px}main{padding-block:36px 48px}h1{font-size:clamp(28px,5vw,39px);line-height:1.4;letter-spacing:-.04em;margin:0 0 24px}h2{font-size:20px;line-height:1.5;margin:30px 0 12px}p{margin:12px 0}.status{background:#fff3cb;border-left:4px solid #d49b17;padding:18px 20px;margin:20px 0 28px}.status strong{display:block}.identity{padding-block:18px;border-block:1px solid #c9d9e7;margin-block:26px}.identity p{margin:6px 0}nav{display:flex;flex-wrap:wrap;gap:12px 24px}footer{border-top:1px solid #c9d9e7;padding-block:22px 35px;font-size:14px;color:#4d657d}.draft{font-weight:700;color:#735100}li{padding-left:4px;margin-block:6px}@media(max-width:420px){header,main,footer{width:calc(100% - 32px)}header{padding-block:22px}main{padding-top:28px}.status{padding:14px 16px}}'''
HOME='''<p>태국 소식과 생활 정보를 나누는 독립 커뮤니티의 개발 검토 사이트입니다.</p>
<h2>현재 제공하는 내용</h2><p>운영자와 문의 방법, 이용약관 초안, 개인정보 안내 초안만 공개합니다.</p>
<p>회원 가입, 이메일 인증, Google 로그인, 게시판과 API는 사용할 수 없습니다. 이 안내 페이지에는 개인정보를 입력하는 폼이 없습니다.</p>
<h2>보안 경고 안내</h2><p>사이트에 대한 보안 경고를 확인해 점검 중입니다. 경고 해제는 확인되지 않았습니다. 브라우저에 보안 경고가 표시되면 우회해 접속하지 마세요.</p>'''
TERMS='''<p class="draft">개발 검토용 초안입니다. 정식 운영 전에 운영자 검토와 문서 확정이 필요합니다.</p>
<h2>서비스 상태</h2><p>현재는 안내 페이지만 제공합니다. 회원·게시판 기능은 중단 상태입니다.</p>
<h2>서비스 이용 원칙</h2><p>개인정보 노출, 도배, 타인 사칭, 불법 게시물은 금지합니다. 이 문서는 가입이나 동의를 받는 화면이 아닙니다.</p>
<h2>확정이 필요한 항목</h2><p>법적 운영 주체, 적용 법률, 책임 범위, 신고·제재·이의 제기와 계정 삭제의 세부 절차를 정식 운영 전에 확정해야 합니다.</p>'''
PRIVACY='''<p class="draft">개발 검토용 초안입니다. 정식 운영 전에 운영자 검토와 문서 확정이 필요합니다.</p>
<h2>현재 안내 페이지</h2><p>이 페이지에는 입력 폼이나 회원 DB 연결이 없습니다. 가입·로그인 요청과 인증 메일 발송을 받지 않습니다. 기존 회원 데이터는 이번 안내 공개로 수정하지 않습니다.</p>
<p>접속 과정에서 IP 주소, 요청 경로와 시각, 응답 상태 등이 서버 기록에 남을 수 있습니다. 구체적인 처리 항목과 보관 기간은 최종 방침에서 확정해야 합니다.</p>
<h2>회원 기능에서 사용하는 정보 · 초안</h2><p>이메일 주소, 공개 닉네임, 로그인 제공자 식별자, 동의 버전과 시각을 계정 운영에 사용합니다. 이메일 주소는 인증 메일 발송과 계정 관리에 사용하며 다른 회원에게 공개하지 않습니다. 인증 링크는 유효기간과 사용 여부를 관리합니다. 현재 해당 기능은 중단 상태입니다.</p>
<h2>문의와 주의 사항</h2><p>문의 링크는 사용자의 이메일 앱을 엽니다. 메일 내용은 이용하는 이메일 서비스에서 처리합니다. 문의할 때 비밀번호·신분증 번호·금융정보나 인증 링크를 보내지 마세요.</p>
<h2>확정이 필요한 항목</h2><p>법적 운영 주체, 보관·파기 기간, 처리 위탁과 국외 이전, 사용자 권리 행사와 계정 삭제의 세부 절차를 정식 운영 전에 확정해야 합니다.</p>'''
def document(title,body):
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{escape(title)} · TEEMOBKK's POST</title><link rel="stylesheet" href="/info-assets/style.css"></head><body>
<header><img src="/info-assets/cat.webp" alt="" width="62" height="62"><a href="/">TEEMOBKK's POST<small>태국 커뮤니티 · 개발 검토 안내</small></a></header>
<main><h1>{escape(title)}</h1><div class="status"><strong>가입과 로그인은 중단되어 있습니다.</strong>현재는 안내 페이지만 제공합니다. 이메일 주소나 인증 정보를 입력하지 마세요.</div>{body}
<section class="identity" aria-label="운영자와 문의"><h2>운영자와 문의</h2><p>운영: TeemoBKK · <a href="https://teemobkk.io/about/">기존 사이트의 운영자 소개</a></p><p>문의: <a href="mailto:admin@teemobkk.io">admin@teemobkk.io</a></p></section>
<nav aria-label="안내 페이지"><a href="/">검토 안내</a><a href="/accounts/policy/terms/">이용약관</a><a href="/accounts/policy/privacy/">개인정보 안내</a></nav></main>
<footer>TEEMOBKK's POST · 안내 전용 페이지입니다. 로그인이나 회원 기능의 재개를 뜻하지 않습니다.</footer></body></html>'''
def config():
    blocks=[]
    for i,(path,filename) in enumerate(PATHS.items()):
        blocks.append(f'''    @notice{i} {{
        method GET HEAD
        path {path}
    }}
    handle @notice{i} {{
        root * {SERVE_ROOT}
        rewrite * /{filename}
        file_server
    }}''')
    return '''\n\n# Information-only isolated preview; no app proxy or credential collection.
post-dev.teemobkk.io {
    header {
        Cache-Control "no-store"
        X-Robots-Tag "noindex, nofollow, noarchive"
        X-Content-Type-Options nosniff
        Referrer-Policy no-referrer
        X-Frame-Options DENY
        Content-Security-Policy "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    }
'''+ '\n'.join(blocks)+'''
    handle {
        header Content-Type "text/plain; charset=utf-8"
        respond "로그인·인증·회원 기능은 중단 상태입니다. 현재는 안내 페이지만 제공합니다." 503
    }
}
'''
def build(out):
    out.mkdir(parents=True,exist_ok=False);public=out/'public';public.mkdir()
    files={'index.html':document('검토 사이트 안내',HOME).encode(),'terms.html':document('이용약관',TERMS).encode(),'privacy.html':document('개인정보 안내',PRIVACY).encode(),'style.css':CSS.encode(),'cat.webp':(REPO/'thai_platform/static/assets/original-cat.webp').read_bytes()}
    manifest={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'files':{}}
    for name,data in files.items():
        (public/name).write_bytes(data);manifest['files'][name]={'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    (out/'preview.caddy').write_text(config())
    manifest['caddy_sha256']=hashlib.sha256((out/'preview.caddy').read_bytes()).hexdigest()
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'source_commit':manifest['source_commit'],'public_files':len(files),'out':str(out)}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True,type=Path);build(parser.parse_args().out)
