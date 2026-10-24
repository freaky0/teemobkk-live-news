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

## Google Cloud 설정

이 안내는 현재 제한된 미리보기 경로 `https://teemobkk.io/thai/` 전용입니다. 운영 승격이나 공개 배포 승인이 아닙니다.

1. Google Auth Platform의 Clients에서 **Web application** 유형 클라이언트를 만듭니다. 기존 Workspace Desktop 클라이언트나 개인 API 토큰은 재사용하지 않습니다.
2. Audience를 테스트용으로 유지하고, 로그인할 Google 계정을 Test users에 추가합니다. 공개 프로덕션 앱으로 게시하지 않습니다.
3. 다음 주소를 정확히 등록합니다.

| 항목 | 값 |
|---|---|
| Authorized JavaScript origin | `https://teemobkk.io` |
| Authorized redirect URI | `https://teemobkk.io/thai/accounts/google/login/callback/` |

앱은 `/thai` prefix로 마운트됩니다. callback URI 끝의 `/`를 포함하고, query/fragment는 붙이지 않습니다. 저장소의 `POST_SCRIPT_PREFIX=/thai`로 Django URL reversing을 확인하면 경로는 `/thai/accounts/google/login/callback/`입니다.

Google 동의 화면에 서비스 표시명과 연락 이메일을 설정하고, 테스트 모드의 Test users에 승인된 검토 계정을 추가합니다. 현재 코드가 요청하는 scope는 `openid`와 `email`뿐입니다. 이 로그인 기능에는 Drive, Gmail 등 다른 API scope가 필요하지 않습니다.

## 비밀 설정

Google Cloud에서 만든 **Web application Client ID**와 **Client secret**은 제한된 미리보기 서버의 보호된 비밀 설정에 각각 `POST_GOOGLE_CLIENT_ID`, `POST_GOOGLE_CLIENT_SECRET`으로 등록합니다. 이 저장소, 채팅, 티켓, 스크린샷, 일반 로그에는 넣지 않습니다. 값은 둘 다 있어야 Google 버튼이 활성화됩니다. 같은 제공자를 Django 관리자 `SocialApp`에도 중복 등록하지 않습니다.

운영자 보고에 따라 Google Client ID와 Client secret은 미리보기 전용 보호 환경에 설정됐고, 별도 승인된 서비스 재시작이 완료됐습니다. 로그인 요청은 앱의 계정 방식 확인 화면까지 도달했지만 Google 로그인 성공은 확인되지 않았습니다. 비밀값은 이 저장소에 두지 않습니다. 추가 설정은 검증된 미리보기 비밀 관리 절차로만 변경하고, 운영 설정·배포는 별도 승인 없이는 변경하지 않습니다.

## 기존 이메일 계정 정책

같은 이메일이라는 이유만으로 Google 계정을 기존 계정에 자동 연결하지 않습니다. 이메일로 이미 가입한 계정은 먼저 이메일 링크로 로그인한 뒤 내 계정의 **Google 계정 연결** 버튼을 사용해야 합니다. 연결은 Google 재인증을 거치고, Google이 검증한 주소가 기존 계정의 검증 이메일과 일치해야 합니다. 이 기능의 코드는 로컬 후보 브랜치에만 있으며 현재 공개 미리보기에는 아직 반영되지 않았습니다. 미리보기 반영 및 실계정 연결은 별도 검증이 필요합니다. 테스트 목적으로 실회원이나 기존 가입 데이터를 삭제하지 않습니다.

## 외부 검증 전 조건

Chrome 피싱 경고를 우회하지 않습니다. Google의 경고 검토와 OAuth 연결은 별개입니다. 제한 미리보기 실계정 callback 검증과 운영 승격은 별개의 절차이며, main 병합 및 운영 배포는 별도 승인이 필요합니다.

## 공식 근거

- https://docs.allauth.org/en/latest/socialaccount/providers/google.html
- https://docs.allauth.org/en/latest/socialaccount/adapter.html
- https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred
