# Google 로그인 연결 준비

## 구현과 검증 범위

Django 5.2.18 / django-allauth 65.19.7 기준이다.
Google 인증 시작 및 callback의 정확한 두 경로만 검토 환경 게이트에서 허용한다.
실제 로그인 처리는 allauth의 OAuth state 검증과 PKCE S256을 사용한다.
인증 시작 POST는 CSRF 보호를 유지한다. GET은 로그인 확인 화면만 표시한다.
초대 목록에 포함된 검증된 Google 이메일만 가입과 로그인 처리를 통과한다.
외부 계정 API나 메일/Drive 권한은 요청하지 않는다. 기본 신원 확인용 scope만 사용한다.

현재 검증은 개발 테스트 DB 및 가상 OAuth 자격 증명으로 수행했다.
실계정 로그인이나 배포 완료를 의미하지 않는다.

## 필요한 Google Cloud 설정

1. Google Auth Platform의 Clients에서 **Web application** 유형 클라이언트를 만든다.
   기존 Workspace용 Desktop 클라이언트나 토큰은 재사용하지 않는다.
2. 애플리케이션 이름과 지원 이메일을 설정한다. 외부 테스트 모드라면 허용할 테스트 사용자를 Audience에 추가한다.
3. 아래 값을 정확히 등록한다.

| 항목 | 값 |
|---|---|
| JavaScript origin | `https://post-dev.teemobkk.io` |
| Redirect URI | `https://post-dev.teemobkk.io/accounts/google/login/callback/` |

Redirect URI의 마지막 `/`를 포함한다. 실제 인증 토큰이나 query/fragment를 붙이지 않는다.
이 값은 검토 환경용이며, 운영 도메인의 callback을 임의로 등록하거나 배포하지 않는다.

Google Cloud에서 내려받은 웹용 클라이언트 JSON은 비공개 저장소에만 보관한다.
Client secret, access token, refresh token을 채팅·Git·스크린샷·일반 로그에 넣지 않는다.
설정 도구에는 JSON 파일 경로만 전달한다. OAuth client JSON을 일반 read_file로 출력하지 않는다.
웹 클라이언트 형식과 등록 callback을 값 비노출 방식으로 검사한 뒤, 승인된 검토 서버 환경에만 반영한다.
앱 환경변수는 `POST_GOOGLE_CLIENT_ID`와 `POST_GOOGLE_CLIENT_SECRET`이며 둘 다 필요하다.
현재는 실서비스에 설정하지 않았다.

## 기존 이메일 계정 정책

같은 이메일이라는 이유만으로 Google 계정을 기존 계정에 자동 연결하지 않는다.
이메일로 이미 가입한 계정에서 Google 신규 가입을 시도하면 현재 정책은 충돌로 거부한다.
이메일 로그인 후 별도 확인과 동의를 거치는 **명시적 Google 연결** 기능은 아직 구현 범위 밖이다.
같은 계정으로 두 로그인 방식을 사용하려면 이 절차를 별도로 승인·구현·검증해야 한다.
테스트 목적으로 실회원이나 기존 가입 데이터를 삭제하지 않는다.

## 외부 검증 전 조건

Chrome 피싱 경고를 우회하지 않는다. Google의 경고 검토와 OAuth 연결은 별개다.
웹용 자격 증명 준비, 기존 계정 연결 정책 결정, 검토 서버 적용 승인 후 실계정 callback을 검증한다.
초대되지 않은 계정 차단, 신규 Google 가입의 닉네임·동의, 기존 Google 계정 재로그인까지 확인한다.
main 병합과 운영 배포는 별도 승인 대상이다.

## 공식 근거

- https://docs.allauth.org/en/latest/socialaccount/providers/google.html
- https://docs.allauth.org/en/latest/socialaccount/adapter.html
- https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred
