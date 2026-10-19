# 가입·로그인 개발 계약

## 구현한 방식

- 이메일 인증 링크 또는 Google OAuth 중 하나를 선택합니다. 이메일 가입에는 비밀번호가 없습니다.
- 이메일 링크는 django-sesame 3.2.5를 사용합니다. 10분 만료, 한 번 사용, 전용 scope를 적용합니다.
- 링크의 token과 challenge ID는 URL fragment에 둡니다. fragment는 HTTP 요청 URL과 접근 로그에 보내지 않습니다.
- 확인 화면에서 fragment를 즉시 지우고, 사용자가 누르는 CSRF 보호 POST로만 인증을 소비합니다. 메일 링크 검사기의 GET만으로 로그인되지 않습니다.
- 신청 브라우저의 세션 nonce에 묶습니다. 다른 브라우저에서 열면 새 인증 메일을 요청해야 합니다. 이메일 본문과 화면에 이를 안내합니다.
- DB에는 원문 인증 토큰이 아니라 digest·만료 시각·사용 시각·세션 digest를 저장합니다. 조건부 UPDATE로 사용을 선점합니다. SQLite의 SELECT FOR UPDATE만을 믿지 않습니다.
- 이메일 주소별/IP별 요청 제한을 적용합니다. 존재·미존재·Google 전용·요청 제한의 응답은 구분하지 않습니다. 전송 실패 토큰은 무효화합니다.
- 인증 뒤 닉네임과 약관·개인정보 동의를 받아 서버의 문서 버전과 동의 시각을 저장합니다. 완료 전에는 게시글·댓글·신고 쓰기를 거부합니다.
- 이메일은 내 계정과 본인용 `/api/v1/me/`에서만 표시합니다. 공개 게시글·댓글 serializer에는 넣지 않습니다. 계정 화면과 본인 API는 캐시를 금지합니다.
- Google OIDC 검증과 세션 처리는 django-allauth 65.19.7이 담당합니다. provider 계정 ID를 사용하며 이메일 기반 인증·자동 연결 설정을 끕니다.
- Google 신규 가입에는 제공자가 검증한 이메일 하나가 필요합니다. 같은 이메일의 기존 계정이 있으면 자동 연결하지 않고 중단합니다.
- Google 전용 계정에 이메일 로그인 자격을 자동 부여하지 않습니다. 명시적 계정 연결·재인증·이메일 변경·실제 영구 삭제는 범위 밖입니다. 계정 비활성화와 운영자 삭제 검토 요청은 `CLOSURE-DESIGN.md`의 제한된 절차로만 지원합니다. 이메일·Google 계정 접근 복구는 제공자 복구 절차만 안내합니다.
- 일반 계정 비밀번호 로그인·비밀번호 재설정·소셜 연결 관리 경로는 열지 않습니다. 관리자 인증 경로는 별도입니다.

## 실제 운영과 개발의 구분

현재 Google 실계정 OAuth와 실제 SMTP 전송을 완료한 상태가 아닙니다. 테스트는 in-memory mail backend와 합성 회원을 사용합니다. 화면에 가짜 외부 인증 성공을 표시하지 않습니다.

확인한 로컬 환경 변수 이름과 `/opt/data/.env`, 현재 저장소 문서에서는 필요한 OAuth·SMTP 설정을 발견하지 못했습니다. VPS에는 SSH 읽기 전용 조회를 수행했습니다. 확인한 `/root/docs`, `/opt/docs`, `/opt/teemo-live-news/docs`에서 관련 문서가 나오지 않았고, 지정한 프로젝트 `.env` 경로도 발견되지 않았습니다. 서버 전체에 자격 증명이 없다는 뜻은 아닙니다. 다른 위치에 있으면 경로를 확인해야 합니다. 비밀값은 출력하거나 이 문서에 저장하지 않았습니다.

## 설정 변수

실제 값을 채팅·소스·일반 로그에 넣지 마세요. 서버 secret store 또는 읽기 제한된 환경 설정으로 주입합니다.

- `POST_GOOGLE_CLIENT_ID`, `POST_GOOGLE_CLIENT_SECRET`: Google OAuth 앱.
- `POST_PUBLIC_ORIGIN`: 가입 링크의 명시적 HTTPS 원점. 요청 Host 값을 사용하지 않습니다. LOCAL_DEVELOPMENT에서는 loopback HTTP만 예외입니다.
- `POST_MAIL_ENABLED=1`, `POST_EMAIL_HOST`, `POST_EMAIL_PORT`, `POST_EMAIL_HOST_USER`, `POST_EMAIL_HOST_PASSWORD`, `POST_EMAIL_USE_TLS`, `POST_DEFAULT_FROM_EMAIL`: 메일 연결.
- `POST_POLICY_APPROVED=1`, `POST_POLICY_DIR`, `POST_TERMS_VERSION`, `POST_PRIVACY_VERSION`: 운영자가 승인한 정책.
- 승인된 정책 디렉터리는 비어 있지 않은 `terms.txt`와 `privacy.txt`를 포함해야 합니다. 문서 버전은 `draft`로 시작할 수 없습니다. 단순 플래그만으로 초안을 확정본처럼 바꾸지 않습니다.

메일 발송은 명시적 설정과 발신자·호스트·원점이 있어야 활성화합니다. 기본 로컬 서버에서는 메일 요청을 503으로 닫습니다. 테스트에서는 별도의 override_settings로 in-memory mail만 활성화합니다.
실제 공개 가입은 승인된 약관·개인정보 안내가 있어야 합니다. 동기 SMTP 요청의 처리 시간 차이는 계정 추측에 이용될 수 있으므로 외부 공개 전에 비동기 발송 큐와 공용 요청 제한을 추가 검토해야 합니다. LOCAL_DEVELOPMENT의 동의 화면은 개발 검토용 초안으로 표시합니다.
Google callback은 최종 원점의 `/accounts/google/login/callback/`입니다. Google Console의 정확한 redirect URI·동의 화면·테스트 사용자 설정은 별도 확인이 필요합니다.

## 공개 전 중단 조건

외부 검토 주소와 접근 대상을 승인받기 전에는 공개하지 않습니다. 개발 서버는 loopback에만 바인딩합니다.
외부에서는 LOCAL_DEVELOPMENT 설정이나 Django runserver를 사용하지 않습니다. HTTPS reverse proxy·정식 WSGI 서버·공용 rate-limit cache·메일 발신 도메인 인증·보관/파기 정책·백업과 복구를 검토해야 합니다.
메일/SMS/API를 새 서비스에 연결하거나 유료 서비스를 구매하지 않았습니다. DNS·reverse proxy·운영 service를 수정하지 않았습니다.
기존 운영 뉴스 DB는 여전히 읽기 전용입니다. 새 회원 테이블의 마이그레이션 대상은 개발 DB뿐입니다.

## 검사

```sh
POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test members.tests community.tests_api community.tests_web community.tests_news
POST_LOCAL_DEVELOPMENT=1 POST_RUN_BROWSER_TESTS=1 uv run python manage.py test members.tests_browser community.tests_browser
```

브라우저 실행 파일을 지정하려면 `POST_BROWSER_EXECUTABLE`을 사용합니다. 가입 화면·동의·내 계정 캡처와 결과는 `var/auth-browser/`에 저장합니다. 테스트 메일의 링크는 테스트 코드 안에서만 읽고 출력하지 않습니다.
브라우저 검사에는 실제 폼 CSRF 검사를 유지합니다. 인증 페이지에 `Referrer-Policy: no-referrer`를 적용하면 정상 POST도 거부될 수 있으므로 `same-origin`을 사용합니다. 토큰은 fragment로 보내고 즉시 제거하여 보호합니다.

## 공식 근거

- https://django-sesame.readthedocs.io/en/stable/howto.html
- https://django-sesame.readthedocs.io/en/stable/reference.html
- https://docs.allauth.org/en/latest/account/configuration.html
- https://docs.allauth.org/en/latest/socialaccount/adapter.html
- https://docs.djangoproject.com/en/5.2/topics/email/
- https://docs.djangoproject.com/en/5.2/ref/csrf/
