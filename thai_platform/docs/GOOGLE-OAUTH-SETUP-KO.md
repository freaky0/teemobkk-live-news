# Google 로그인 연결 안내

현재 서비스 코드에는 django-allauth Google OAuth 경로, CSRF 보호 로그인 시작, PKCE, 신규 계정 정책 검사가 구현되어 있습니다. 실제 Google 로그인은 OAuth 앱 자격 증명이 서버 환경에 설정되어야 합니다. 이 저장소에는 실제 자격 증명을 넣지 않습니다.

## Google Cloud 설정

1. Google Cloud Console에서 OAuth 클라이언트 ID를 만들고 애플리케이션 유형은 웹 애플리케이션으로 설정합니다.[6]
2. 승인된 JavaScript 원본에는 최종 서비스 HTTPS 원점을 등록합니다. 예: `https://community.example.com`.
3. 승인된 리디렉션 URI에는 아래 주소를 정확히 등록합니다. `example.com`은 실제 공개 호스트명으로 바꿉니다.[6]

   `https://community.example.com/accounts/google/login/callback/`

4. OAuth 동의 화면에 서비스 표시명과 연락 이메일을 설정하고, 앱 검증·테스트 사용자 등 Google이 요구하는 절차를 완료합니다.[6]
5. 현재 코드에서 요청하는 범위는 `openid`와 `email`뿐이며 `profile`은 요청하지 않습니다. `openid`는 Google 계정의 안정적인 `sub` 식별자를 받고, `email`은 검증된 이메일 주소를 받는 데 사용합니다.[12] 앱은 이메일만으로 기존 계정을 자동 연결하지 않습니다.

## 서버 설정

서버의 보호된 비밀 설정에 다음 값을 주입합니다. 값을 소스 코드, 저장소, 브라우저, 티켓, 일반 로그에 기록하지 마세요.

- `POST_GOOGLE_CLIENT_ID`
- `POST_GOOGLE_CLIENT_SECRET`
- `POST_PUBLIC_ORIGIN` — 최종 서비스의 `https://` 원점
- `POST_ALLOWED_HOSTS` — 실제 호스트명
- 정책을 승인한 뒤에만 `POST_POLICY_APPROVED=1`, 정책 파일 경로와 비초안 버전 설정

현재 설정은 `POST_GOOGLE_CLIENT_ID`와 `POST_GOOGLE_CLIENT_SECRET`이 모두 있을 때만 Google 버튼을 활성화합니다. 미설정이면 버튼은 비활성 상태이며 OAuth 요청을 시작하지 않습니다. 운영 가입도 승인된 약관·개인정보 처리방침이 있어야 열립니다. 정책 승인 값만 올리고 사업자 연락처나 탈퇴·파기 절차를 비워두지 마세요.

django-allauth 설정은 `settings.py`의 환경변수 방식입니다. 같은 Google 제공자를 Django 관리자 `SocialApp`에도 중복 등록하지 마세요. allauth 문서는 환경 설정과 관리자 등록을 대체 가능한 별도 방식으로 설명하며 둘을 중복하면 제공자 선택이 모호해질 수 있다고 경고합니다.[7]

## 확인 순서

1. 자격 증명을 설정한 서버에서 비밀값을 출력하지 않는 상태 확인으로 Google 설정 여부만 확인합니다.
2. TLS가 적용된 최종 호스트에서 로그인 화면의 Google 버튼이 활성화되는지 확인합니다.
3. Google 계정으로 로그인 시작을 눌렀을 때 승인 화면으로 이동하고, 동의 뒤 정확한 callback으로 돌아오는지 테스트 계정으로 확인합니다.
4. 새 계정 생성, 같은 이메일의 기존 계정 자동 연결 거부, 초대 제한이 켜진 경우 초대되지 않은 계정 거부를 확인합니다.
5. 문제를 해결할 때 `client_secret`, 인증 코드, ID token, 세션 쿠키를 로그나 대화에 복사하지 않습니다.

이 작업 환경에서는 실제 Google 자격 증명 또는 Google Cloud 콘솔 설정을 확인·변경하지 않았습니다. 자동화된 테스트는 합성 자격 증명으로 OAuth 시작 요청과 PKCE·callback URL을 검증할 뿐, 실제 Google 인증 왕복을 증명하지 않습니다.

## 공식 문서

- Google provider 등록 및 callback 안내: https://docs.allauth.org/en/latest/socialaccount/providers/google.html
- 설정 기반 또는 관리자 `SocialApp` 기반 제공자 설정: https://docs.allauth.org/en/latest/socialaccount/provider_configuration.html
- OpenID Connect scope, Google `sub`, email claims: https://developers.google.com/identity/openid-connect/reference

## Sources

[6] https://docs.allauth.org/en/latest/socialaccount/providers/google.html
[7] https://docs.allauth.org/en/latest/socialaccount/provider_configuration.html
[12] https://developers.google.com/identity/openid-connect/reference — Google OpenID Connect API Reference
