# 검토 환경 인증 전 안내

## 변경 범위

- 제한된 검토 환경에서 `/accounts/policy/terms/`와 `/accounts/policy/privacy/`의 GET·HEAD만 인증 없이 허용한다.
- 계정 경로 전체나 정책 경로의 하위 경로는 공개하지 않는다. 게시판·뉴스·관리자·API의 기존 제한을 유지한다.
- 로그인 방식 선택 및 이메일 제출 전에 운영자 소개, 문의 주소, 약관·개인정보 링크와 이메일 이용 목적을 표시한다.
- 운영자 브랜드와 문의 주소는 기존 운영 사이트의 공개 소개 페이지 `https://teemobkk.io/about/`에서 확인한 정보를 재사용한다. 새 운영 법인이나 연락처를 가정하지 않는다.
- 이메일 인증에 필요한 실제 이메일과 입력하지 말아야 할 비밀번호·신분증 번호·금융정보를 구분한다.
- 약관·개인정보 문서는 여전히 검토용 초안이다. 보관·파기 기간 등 미확정 사항을 확정된 것처럼 기재하지 않는다.

## 검증

정책 페이지가 기존 코드에서 302를 반환하는 실패를 먼저 재현했다. 정책 링크 누락과 기존 문구 충돌도 테스트 실패로 확인했다.
수정 후 제한 경계 검사와 안내 검사는 통과했다.
로컬 실제 브라우저에서 320·390·1440 너비로 링크 이동과 이메일 화면 복귀, 가로 넘침 및 콘솔 오류를 검사했다.
브라우저는 테스트 DB를 사용했다. 외부 메일이나 Google 인증 요청은 수행하지 않았다.

통합 실행: `members.tests_google_preview members.tests members.tests_preview members.tests_disclosure members.tests_browser community.tests_news community.tests_api community.tests_web community.tests_browser` — 71개 통과.
`makemigrations --check --dry-run`은 변경 없음을 확인했다.

## 배포 경계

이 변경은 개발 브랜치 전용이다. 운영 배포, 검토 사이트 재개, Google 검토 요청을 포함하지 않는다.
로컬 테스트 통과가 Google 경고 해제나 오탐을 증명하지 않는다.
