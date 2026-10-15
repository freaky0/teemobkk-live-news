# TEEMOBKK POST — 독립 커뮤니티 개발 서비스

A 고양이 뉴스룸의 Django 웹·공통 API 첫 개발 묶음입니다. 운영 사이트 배포본이 아닙니다.

## 개발 환경 실행

```sh
cd thai_platform
uv sync --locked
# 아래 명령은 로컬에서 실행하세요. 생성된 비밀값을 채팅·로그에 출력하지 마세요.
uv run python -c "import os,secrets; fd=os.open('.dev-secret',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,secrets.token_urlsafe(64).encode());os.close(fd)"
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py migrate
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py runserver 127.0.0.1:8870
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
- 신고 비공개·운영자 처리·작업 이력.
- 필터·페이지의 URL 보존, 목록 스크롤 복원.
- 로그인한 계정별 브라우저 텍스트 초안. 민감한 내용은 입력하지 마세요.

## 인증 경계

실제 Google 로그인은 `POST_GOOGLE_CLIENT_ID`와 `POST_GOOGLE_CLIENT_SECRET`을 안전한 서버 환경에 설정한 뒤 사용할 수 있습니다.
값을 채팅·소스·일반 로그에 넣지 마세요. Google OAuth 동의 화면과 정확한 리디렉션 URI 설정이 필요합니다.
콜백은 최종 서비스 원점의 `/accounts/google/login/callback/`입니다. 설정 전에는 Google 로그인 경로를 503으로 닫습니다.
일반 비밀번호 회원가입은 열지 않았습니다. 화면에 가짜 로그인·테스트 계정 선택기를 제공하지 않습니다.
Google 이메일만으로 기존 계정을 자동 연결하지 않습니다. 제공자 계정 식별자 기반 연결을 사용합니다.
테스트는 Django의 테스트 전용 세션과 임시 회원으로 권한을 검증합니다. 실제 Google 계정 로그인을 성공했다는 의미가 아닙니다.

웹 API는 현재 세션 쿠키·CSRF 인증입니다. 네이티브 앱용 OIDC/PKCE·토큰 발급/갱신·기기별 로그아웃은 후속 범위입니다.
공통 API가 있다는 이유로 앱 인증까지 구현됐다고 보지 마세요. 브라우저 인증 쿠키를 앱 토큰으로 재사용하지 마세요.

## API 초안

- `GET/POST /api/v1/posts/`
- `GET/PATCH/DELETE /api/v1/posts/{id}/`
- `GET/POST /api/v1/posts/{id}/comments/`
- `POST /api/v1/posts/{id}/reports/`
- 운영자: `GET /api/v1/reports/`, `GET/PATCH /api/v1/reports/{id}/`

익명 읽기는 공개 상태만 제공합니다. 쓰기는 로그인과 CSRF가 필요합니다.
작성자·상태·권한을 클라이언트가 임의로 바꿀 수 없어야 합니다.
API에서 요청을 반복 전송하면 중복 생성될 수 있습니다. 멱등성 키는 아직 구현하지 않았으므로 자동 쓰기 재시도를 하지 마세요.
목록 API는 페이지 구분을 사용합니다. 서버 측 제한이 적용됩니다.
현재 개발용 요청 제한은 프로세스 로컬 캐시 기준입니다. 다중 프로세스 운영 전에 공용 캐시·프록시 신뢰 정책이 필요합니다.

## 검사

```sh
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py check
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py makemigrations --check --dry-run
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_api community.tests_web
uv run pip-audit --local --progress-spinner off
node --check static/service.js
uv run playwright install chromium
POST_LOCAL_DEVELOPMENT=1 POST_RUN_BROWSER_TESTS=1 uv run python manage.py test community.tests_browser
```

이미 설치된 Chromium을 사용하려면 `POST_BROWSER_EXECUTABLE`에 실행 파일 경로를 설정하세요.
브라우저 검사 결과와 화면은 무시되는 `var/browser/`에 저장합니다. 실제 서비스 DB가 아닌 테스트 DB에서 실행합니다.

## 아직 미완료

Google 실계정 인증 확인, 약관·개인정보 동의 온보딩, 탈퇴·계정 복구, 이미지 서버 업로드, 가이드 CMS, 기존 뉴스 DB 공개 기준 연결, 앱용 인증, 푸시, 백업 복구 실습, 운영 인프라·도메인·배포.
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
