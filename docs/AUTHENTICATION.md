# 저장소·배포 인증 운영

이 문서는 TeemoBKK 저장소 작업에 필요한 인증 경로와 안전한 사용법을 기록한다. 비밀값은 문서, 코드, 채팅, 로그, 커밋에 저장하지 않는다.

## 인증 경로 구분

| 목적 | 인증 경로 | 사용법 |
| --- | --- | --- |
| `freaky0/teemobkk-live-news` GitHub 접근 | 전용 SSH deploy key: `/opt/data/.ssh/teemobkk-live-news-deploy-20261003` | `git@github.com:freaky0/teemobkk-live-news.git` 원격에 사용한다. 현재 실행 환경에서 `ssh -i <키 경로> -o IdentitiesOnly=yes -o BatchMode=yes -T git@github.com`이 저장소 계정으로 인증되는 것을 확인했다. |
| TeemoBKK VPS 접속 | `/opt/data/.ssh/teemobkk-deploy` | `root@72.62.64.195` 접속용이다. GitHub deploy key와 별개이며 서로 바꿔 쓰지 않는다. |
| 다른 서비스의 API·봇 인증 | 환경변수, 전용 비밀 저장소 또는 서비스별 secret store | 실제 토큰·비밀번호는 해당 시스템에서 읽고, 이 문서에는 변수명이나 안전한 조회 절차만 기록한다. |

이 경로들은 현재 운영 환경에서 확인된 위치다. 다른 컨테이너나 세션에서 같은 경로가 보인다고 가정하지 말고, 파일의 존재·읽기 권한과 해당 서비스 인증을 비밀값을 출력하지 않는 방식으로 확인한다.

## GitHub 사용

HTTPS 원격은 비대화형 실행에서 사용자 인증 프롬프트를 띄울 수 있다. 이 경우 토큰을 원격 주소에 넣거나 채팅으로 요청하지 않는다. 승인된 SSH 키를 지정해 접근한다.

```bash
GIT_SSH_COMMAND='ssh -i /opt/data/.ssh/teemobkk-live-news-deploy-20261003 -o IdentitiesOnly=yes -o BatchMode=yes' \
  git ls-remote git@github.com:freaky0/teemobkk-live-news.git refs/heads/main
```

푸시 전에는 작업 트리, 브랜치와 원격 기준점, 스테이징 파일을 확인한다. 필요한 파일만 추가한다. 공개 저장소에는 비밀값이 포함된 파일이나 설정을 올리지 않는다. `ssh -T` 성공은 인증 확인일 뿐, 저장소 쓰기 권한이나 푸시 성공을 보증하지 않는다. 쓰기 권한은 실제 승인된 푸시의 결과로 확인한다.

## VPS 배포

`/opt/data/.ssh/teemobkk-deploy`는 VPS SSH 경로다. GitHub 저장소 접근 키와 별도다. 서버 내부에서 작업한다는 이유만으로 호스트 권한이 생기는 것은 아니다. 실행 환경, 사용자, 실제 대상 경로와 권한을 확인한 뒤 작업한다.

`deploy/scripts/vps_update.sh`는 VPS 체크아웃에서 `git reset --hard origin/main`을 실행한다. 운영 체크아웃에 수정 파일이나 추적되지 않은 파일이 있으면 이를 덮어쓰거나 삭제할 수 있다. 배포 전에 운영 작업 트리의 상태를 조사하고 변경을 보존·조정한다. 안전한 복구 방안이 없는 상태에서는 이 스크립트를 실행하지 않는다. GitHub 푸시와 VPS 배포는 별도 단계이며, 둘 다 완료 여부를 각각 읽어 확인한다.

## 비밀값 취급 규칙

- 비밀번호, 개인 키 내용, 토큰, 쿠키, 인증 코드, `.env` 값을 채팅이나 문서에 붙여 넣지 않는다.
- 비밀값을 일반 출력·스크린샷·로그에 노출하지 않는다. 인증 확인은 성공/실패와 계정 식별 결과만 기록한다.
- 비밀값을 Git remote URL, 명령행 인자, 소스 코드, 테스트 fixture, 커밋 메시지에 넣지 않는다.
- 권한이 없으면 사용 가능한 승인된 자격 증명 경로를 확인한다. 임의로 새 토큰을 만들거나 자격 증명을 요청하지 않는다.
- 이 문서에는 확인한 인증 수단의 목적과 경로만 기록한다. 키 내용이나 토큰 값은 기록하지 않는다.
