# TEEMOBKK POST — 독립 커뮤니티 개발 서비스

A 고양이 뉴스룸의 Django 웹·공통 API 첫 개발 묶음입니다. 운영 사이트 배포본이 아닙니다.

## 개발 환경 실행

```sh
cd thai_platform
uv sync --locked
# 아래 명령은 로컬에서 실행하세요. 생성된 비밀값을 채팅·로그에 출력하지 마세요.
uv run python -c "import os,secrets; fd=os.open('.dev-secret',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,secrets.token_urlsafe(64).encode());os.close(fd)"
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py migrate
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py runserver 127.0.0.1:8870 --insecure
```

`.dev-secret`이 이미 있으면 생성 명령은 실패합니다. 기존 값을 덮어쓰지 마세요.
DB는 기본적으로 `thai_platform/var/community.sqlite3`입니다. 개발 설정은 이 디렉터리 밖의 DB 연결을 거부합니다.
기존 `/opt/teemo-live-news/news.db`와 운영 파일은 수정하지 않습니다.
개발 서버는 로컬 바인딩으로만 실행합니다. 운영에는 Django 개발 서버를 쓰지 마세요.
`POST_LOCAL_DEVELOPMENT=1`은 로컬에서만 사용하세요. 운영 설정은 외부 비밀키·허용 호스트·HTTPS가 필요합니다.

## 실제 구현 범위

- 별도 DB 마이그레이션, Django 회원·세션 기반 게시판.
- 공개 목록·상세, 로그인 후 작성·댓글·신고, 작성자/운영자 수정·삭제 권한.
- 서버 렌더 A안 홈·게시판·상세·글쓰기.
- 웹과 미래 앱이 공유할 `/api/v1/` 게시글·댓글·신고 API.
- 신고 비공개·운영자 처리·작업 이력. 게시글 관리의 운영자는 공지 관리와 같이 활성 staff 계정이며 슈퍼유저 권한은 필요하지 않습니다. 신고 처리 권한은 별도 `Report moderators` 그룹 정책을 따릅니다.
- 필터·페이지의 URL 보존, 목록 스크롤 복원.
- 로그인한 계정별 브라우저 텍스트 초안. 민감한 내용은 입력하지 마세요.

## 뉴스 읽기 전용 연결

`POST_NEWS_DB`에 기존 SQLite 파일의 절대 경로를 지정합니다. 미설정이면 뉴스 경로는 503을 반환하고 홈은 뉴스 조회 안내와 커뮤니티를 표시합니다.

```sh
POST_LOCAL_DEVELOPMENT=1 POST_NEWS_DB=/opt/teemo-live-news/news.db uv run python manage.py runserver 127.0.0.1:8870 --insecure
```

`--insecure`는 DEBUG가 꺼진 로컬 개발 서버에서 정적 자산을 표시하기 위한 옵션입니다. 운영용 설정이 아닙니다.
운영 뉴스 DB는 Django ORM·마이그레이션 대상이 아닙니다. 별도 `sqlite3` 연결의 `mode=ro`와 `PRAGMA query_only=ON`으로 읽습니다. 번역 함수·수집기·원문 네트워크 요청은 실행하지 않습니다.

- 대상: `region=태국`, 최근 30일, 발행 시각이 현재보다 1분 넘게 미래가 아닌 기사.
- 상태: `ready` 또는 기존 `legacy` 중 한국어 제목과 필요한 한국어 요약이 있는 기사. `pending`·미확인 상태는 제외합니다.
- 제외: `hidden_links`, 활성 `filter_rules`의 `filter_hits` 중 `filter_keeps`에 없는 기사, `settings.hidden_sources`의 매체.
- 정책 테이블 누락·차단 매체 설정 파싱 실패·DB 오류는 뉴스 표시를 차단합니다. 원문이나 전체 DB로 대체하지 않습니다.
- 홈·목록·상세·API는 같은 공개 조건 함수를 사용합니다. 공개 응답에는 내부 상태·운영 메모·인증 설정을 넣지 않습니다.
- 목록과 검색은 최신 발행순, 페이지당 20개입니다. 뉴스 상세는 링크의 SHA-256 기반 고유 주소입니다. 공개 조건은 상세 재조회 때도 적용합니다.
- 한국어 제목과 요약을 그대로 재사용합니다. 사실 재검증이나 새 번역을 수행한 결과가 아닙니다. 뉴스 상세에 원문 링크와 요약임을 표시합니다.
- 기사 대표 이미지는 원 발행사의 HTTPS 이미지 주소를 그대로 사용합니다. 후보 앱은 이미지를 내려받아 자체 저장하지 않으며, 브라우저가 발행사 서버에 직접 요청합니다. 공개 `/thai/`에서 확인한 외부 이미지 호스트는 `assets.aseannow.com`, `www.matichon.co.th`, `mpics2.mgronline.com`입니다. 이미지 표시를 유지하며, 실제 권리·처리 지역은 공개 전 별도 확인이 필요합니다.

웹 경로는 `/newsroom/`, `/newsroom/{id}/`입니다. `/thai/news/`와 `/thai/news/ko/`의 기존 운영 페이지와 겹치지 않도록 분리했습니다. 앱 공통 API는 `GET /api/v1/news/`, `GET /api/v1/news/{id}/`입니다.

## 링크 공유 미리보기

메신저·SNS 미리보기 메타데이터는 `base.html`의 `social_meta` 블록에서 한 번만 출력합니다.

- 홈·목록·커뮤니티·로그인 등 일반 페이지: 항상 같은 대표 이미지 `https://teemobkk.io/thai/static/assets/share-home-v1.jpg` (1200×630 JPEG). 첫 기사 썸네일이 대표 이미지로 쓰이지 않습니다.
- 뉴스 상세 `/newsroom/{id}/`: `og:type=article`과 기사 제목·요약, 기사 대표 이미지(발행사 HTTPS URL)를 사용합니다. 기사 이미지가 없으면 같은 대표 이미지로 대체합니다.
- `canonical`·`og:url`은 쿼리 없는 절대 HTTPS 주소(`config/context.py`의 `PUBLIC_ORIGIN`+`/thai`+path)입니다. `POST_SCRIPT_PREFIX`와 무관하게 `/thai/` 접두사를 유지합니다.
- 대표 이미지는 자체 보유 자산(`static/assets/cat-hero.webp`)으로 생성합니다. `uv run python scripts/generate_share_image.py`. 내용이 바뀌면 파일명 접미사(`v1`)와 `config/context.py`의 경로를 함께 올려 캐시를 우회합니다.
- 정적 파일이므로 배포 시 `collectstatic` 결과를 `/thai/static/` 경로에서 제공해야 합니다. Caddy 정적 root를 바꾸지 않으면 새 이미지가 404가 되므로 `PREVIEW_DEPLOYMENT.md`의 정적 자산 절차를 함께 확인합니다.

경로 접두사 아래에 배포할 때는 `POST_SCRIPT_PREFIX=/thai`를 서버 환경에 설정합니다. 프록시는 접두사만 제거한 요청 경로를 Django로 전달하고, Django의 `FORCE_SCRIPT_NAME`과 상대 `STATIC_URL`이 브라우저 경로를 다시 `/thai/` 아래로 만듭니다. 운영 프록시 설정은 별도 검증 후 적용해야 하며, 이 문서는 현재 라이브 설정이 변경됐다는 뜻이 아닙니다.
목록 매개변수는 `q`(최대 200자)와 `page`(1~10000)입니다. 응답은 `count`, `page`, `page_size`, `has_next`, `results`입니다.
각 기사는 `id`, `title`, `summary`, `source`, `category`, `published_at`, `source_url`을 제공합니다. POST·PATCH·DELETE는 허용하지 않습니다.
DB 권한·접근 방식은 실제 운영 배포 전에 별도로 검토해야 합니다. 이번 연결은 로컬 개발 서버에서만 실행합니다.

실제 개발 서버를 실행한 뒤 `uv run python scripts/check_news_preview.py`로 뉴스 목록·상세·검색·뒤로가기와 5개 화면 폭을 검사할 수 있습니다.
이는 실제 공개 조건을 충족한 DB 기사를 읽는 검사입니다. 테스트 픽스처를 실제 뉴스라고 표시하지 않습니다. 결과와 캡처는 `var/news-preview/`에만 저장합니다.

## 인증 경계

이메일 인증 링크 또는 Google 인증을 선택합니다. 이메일 링크는 10분·1회·신청 브라우저 세션에 제한합니다. 인증 뒤 닉네임과 문서 동의를 완료해야 게시할 수 있습니다. 이메일은 본인 계정에서만 표시합니다.

상세 계약·준비 상태·검사와 공식 근거는 [members/AUTH-DESIGN.md](members/AUTH-DESIGN.md)에 있습니다. Google Console 설정은 [docs/GOOGLE-OAUTH-SETUP-KO.md](docs/GOOGLE-OAUTH-SETUP-KO.md)를 참고하세요. 이메일 인증 링크와 Google 로그인 흐름은 코드에 구현되어 있으나, 실제 Google 자격 증명과 SMTP 발송은 아직 연결·검증되지 않았습니다. 이용약관·개인정보 처리방침은 [docs/policy-draft/](docs/policy-draft/)의 검토용 초안입니다. 사용자 확인에 따라 책임자와 문의·삭제 요청 담당은 Teemobkk로 반영했으며, 실제 데이터 삭제·파기 방식과 보유 기간이 확정될 때까지 공개 승인하지 마세요.

실제 Google 로그인은 `POST_GOOGLE_CLIENT_ID`와 `POST_GOOGLE_CLIENT_SECRET`을 안전한 서버 환경에 설정한 뒤 사용할 수 있습니다.
값을 채팅·소스·일반 로그에 넣지 마세요. Google OAuth 동의 화면과 정확한 리디렉션 URI 설정이 필요합니다.
콜백은 최종 서비스 원점의 `/accounts/google/login/callback/`입니다. 설정 전에는 Google 로그인 경로를 503으로 닫습니다.
일반 비밀번호 회원가입은 열지 않았습니다. 화면에 가짜 로그인·테스트 계정 선택기를 제공하지 않습니다.
Google 이메일만으로 기존 계정을 자동 연결하지 않습니다. 제공자 계정 식별자 기반 연결을 사용합니다.
테스트는 Django의 테스트 전용 세션과 임시 회원으로 권한을 검증합니다. 실제 Google 계정 로그인을 성공했다는 의미가 아닙니다.

웹 API는 현재 세션 쿠키·CSRF 인증입니다. 네이티브 앱용 OIDC/PKCE·토큰 발급/갱신·기기별 로그아웃은 후속 범위입니다.
공통 API가 있다는 이유로 앱 인증까지 구현됐다고 보지 마세요. 브라우저 인증 쿠키를 앱 토큰으로 재사용하지 마세요.

## 프로필 사진

완료된 회원은 PNG/JPEG 사진(입력 최대 1MiB, 너비·높이 각 4096px 및 총 400만 픽셀 이하)을 올릴 수 있습니다. 서버는 내용을 디코딩해 최대 256px RGB PNG로 재인코딩하며 메타데이터를 제거하고 회원 DB에 저장합니다. 사진은 본인 계정 화면에서만 로그인 세션으로 볼 수 있으며 공개 프로필이나 게시물에는 표시되지 않습니다. 사진 삭제 또는 기본 아이콘 저장 시 사진 데이터는 DB에서 제거됩니다(기존 백업의 보존 정책은 별도). 운영 전 DB 백업·용량, 개인정보 고지, 프록시의 요청 크기 제한 및 다중 프로세스 업로드 속도 제한을 검토하세요. 배포 시 잠금 파일의 Pillow 설치와 members 마이그레이션이 필요합니다.

## API 초안

- `GET/POST /api/v1/posts/`
- `GET/PATCH/DELETE /api/v1/posts/{id}/`
- `GET/POST /api/v1/posts/{id}/comments/`
- `POST /api/v1/posts/{id}/reports/`
- 운영자: `GET /api/v1/reports/`, `GET/PATCH /api/v1/reports/{id}/`

익명 읽기는 공개 상태만 제공합니다. 쓰기는 로그인과 CSRF가 필요합니다.
작성자·상태·권한을 클라이언트가 임의로 바꿀 수 없어야 합니다.
게시판별 정보가 있는 게시글의 게시판을 변경하려면 최신 게시글 GET 응답의 `board_data_version`과 `confirm_board_data_removal: true`를 PATCH에 함께 보내야 합니다. 정보나 게시판이 바뀐 뒤의 오래된 확인은 거부됩니다. 다시 GET하여 최신 정보를 확인하고 재동의해야 합니다.
API에서 요청을 반복 전송하면 중복 생성될 수 있습니다. 멱등성 키는 아직 구현하지 않았으므로 자동 쓰기 재시도를 하지 마세요.
목록 API는 페이지 구분을 사용합니다. 서버 측 제한이 적용됩니다.
현재 개발용 요청 제한은 프로세스 로컬 캐시 기준입니다. 다중 프로세스 운영 전에 공용 캐시·프록시 신뢰 정책이 필요합니다.

## 검사

```sh
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py check
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py makemigrations --check --dry-run
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test members.tests community.tests_api community.tests_web community.tests_news
uv run pip-audit --local --progress-spinner off
node --check static/service.js
uv run playwright install chromium
POST_LOCAL_DEVELOPMENT=1 POST_RUN_BROWSER_TESTS=1 uv run python manage.py test members.tests_browser community.tests_browser
```

이미 설치된 Chromium을 사용하려면 `POST_BROWSER_EXECUTABLE`에 실행 파일 경로를 설정하세요.
브라우저 검사 결과와 화면은 무시되는 `var/browser/`에 저장합니다. 실제 서비스 DB가 아닌 테스트 DB에서 실행합니다.

## 아직 미완료

Google 실계정 인증 확인, 실제 SMTP 발송, 약관·개인정보 문서 확정, 외부 HTTPS 검토 주소, 탈퇴·계정 복구, 이미지 서버 업로드, 가이드 CMS, 앱용 인증, 푸시, 백업 복구 실습, 운영 인프라·도메인·배포.

개발용 preview 경로 배포 절차는 [PREVIEW_DEPLOYMENT.md](PREVIEW_DEPLOYMENT.md)를 참고하세요. 이 절차는 `/thai/` preview 전용이며 운영 배포 승인이 아닙니다.
기존 기사·회원 데이터를 자동으로 가져오지 않습니다. 예시 회원·글을 개발 DB에 자동 생성하지 않습니다.
브라우저 로컬 저장소 초안은 같은 기기·원점에서만 복구됩니다. 동시 편집 충돌·초안 서버 동기화는 후속 범위입니다.
Django 관리자 화면은 기반 관리 도구입니다. 별도 A안 운영자 대시보드 전체를 구현한 것은 아닙니다.
소프트웨어는 무료 오픈소스를 사용하지만 서버·개발·API·스토어 등록 등 전체 비용이 무료라는 의미는 아닙니다.

## 자산

고양이 배너는 제공 캐릭터 참고 AI 재구성입니다. 작은 고양이는 제공 이미지 크롭입니다.
배포 전 이미지 사용권과 WantedSans 폰트 라이선스를 확인해야 합니다.

## 공식 문서

- Django 인증: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- DRF 인증: https://www.django-rest-framework.org/api-guide/authentication/
- django-allauth: https://docs.allauth.org/en/latest/socialaccount/providers/google.html
