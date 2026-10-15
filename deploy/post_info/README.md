# 안내 전용 제한 공개

검토 사이트의 회원 앱을 시작하지 않고 Caddy가 정적 안내만 제공한다.
고양이 이미지와 파랑·노랑 브랜드를 유지한다. 외부 글꼴·스크립트·회원 DB를 사용하지 않는다.

## 공개 범위

GET·HEAD는 다음 정확한 경로에서만 허용한다.

- `/`: 운영자·문의·현재 중단 상태 안내
- `/accounts/policy/terms/`: 약관 초안
- `/accounts/policy/privacy/`: 개인정보 안내 초안
- `/info-assets/style.css`, `/info-assets/cat.webp`: 전용 스타일과 이미지

그 밖의 경로와 모든 쓰기 메서드는 503을 반환한다. 로그인·인증·회원·게시판·API를 프록시하지 않는다.
브라우저가 보안 경고를 표시하면 우회하지 않는다. 안내 공개는 Google 분류 해제를 의미하지 않는다.
정책의 보관 기간이나 법적 운영 주체가 확정된 것으로 표시하지 않는다.

## 빌드·검사

`python -m unittest discover -s deploy/post_info -p test_info.py -v`

`python deploy/post_info/build.py --out <새로운 출력 디렉터리>`

출력은 `public/` 파일 5개, 해시 명세, Caddy 호스트 블록이다. 빌드 출력을 Git에 추가하지 않는다.
기존 출력 디렉터리는 덮어쓰지 않는다. 실제 배포는 승인된 커밋의 결과만 사용한다.

## 배포 경계

기존 Caddy 설정을 비공개로 백업하고 검사한다. 운영 호스트 설정 부분을 바이트 단위로 보존한다.
Caddy 변환 결과의 기존 운영 라우팅도 비교하고 `caddy validate` 통과 후 reload한다.
공개 GET·HEAD와 차단 대상 GET·POST·PUT·DELETE를 독립적으로 검증한다.
입력 검사는 민감정보 없는 빈 본문만 사용하며 회원 앱은 계속 중지한다.
설치 실패 시 이전 Caddy 설정으로 복구한다. 회원 DB·앱 환경·서비스 설정은 변경하지 않는다.
Google 검토 요청은 실제 검증 결과로 초안만 작성하며 별도 승인 없이 제출하지 않는다.
