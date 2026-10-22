# 태국 커뮤니티 preview 배포 절차

## 범위

이 절차는 병합된 `thai_platform`을 기존 개발용 미리보기에만 배포한다.

- 공개 경로: `https://teemobkk.io/thai/`
- 서비스: `teemobkk-post-preview.service` (`teemo-post-preview` 사용자)
- 릴리스 루트: `/opt/teemobkk-post-preview/releases/<commit>/thai_platform`
- 별도 커뮤니티 DB: `/var/lib/teemobkk-post-preview/community.sqlite3`
- 뉴스 데이터는 별도 읽기 전용 연결이다. 커뮤니티 DB·마이그레이션 대상으로 사용하지 않는다.

이 앱은 현재 개발용 preview로 표시되며 Google 로그인이 연결되지 않았다. 사용자는 이 `/thai/` 서비스를 계속 사용할 대상으로 지정했다. 이 절차는 이 preview만 대상으로 하며 다른 운영 서비스로 전환하거나 Google OAuth·메일·정책 환경값을 바꾸지 않는다. `POST_RESTRICTED_PREVIEW`와 허용 목록은 유지한다.

`/opt/teemo-live-news`, 해당 체크아웃, 그 안의 DB와 파일은 배포 대상이 아니다. `deploy/scripts/vps_update.sh`는 실행하지 않는다. `community/management/commands/apply_report_retention`도 배포 중 실행하지 않는다.

## 확인한 라우팅

Caddy가 `/thai/static/*`을 릴리스의 `staticfiles`에서 제공하고, `/thai/*`의 나머지 요청을 `127.0.0.1:8871`의 Django 서비스로 전달한다. Django의 `POST_SCRIPT_PREFIX`는 `/thai`다. `/thai/news/*`는 앞선 별도 규칙으로 기존 뉴스 파일을 제공하므로 이 규칙과 원본 경로를 보존한다.

배포 전에 현재 설정을 다시 읽어 이 경로 순서와 대상을 확인한다. HTTP 200만으로 성공 판정하지 말고, 앱 홈·커뮤니티·뉴스룸과 기존 `/thai/news/*` 경로를 각각 검사한다.

## 중단 조건

다음 중 하나라도 맞으면 파일 전송·설정 변경·마이그레이션·재시작을 하지 않는다.

1. 배포할 커밋이 `origin/main`의 승인된 병합 커밋과 다르거나, `thai_platform` 원본 트리가 깨끗하지 않다.
2. 릴리스 패키지와 파일별 SHA-256·크기·모드 manifest가 일치하지 않거나 허용 경로 밖의 파일이 들어 있다.
3. 실행 중인 서비스, Caddy 경로, 서비스 계정, 별도 DB 경로가 이 문서의 대상과 달라졌다.
4. 새 코드가 요구하는 패키지가 실행 환경에 없거나 `pip check`·`manage.py check --deploy`가 실패한다. 공유 preview 가상환경을 `uv sync`로 덮어쓰거나 서버에 `uv`를 새로 설치하지 않는다. 이번 변경에는 새 직접 런타임 의존성이 없고 `pip check`는 통과했지만, lockfile과 `certifi` 버전 차이는 기록한다.
5. DB·Caddy 설정·systemd drop-in에 필요한 새 보호 백업을 만들 권한이 없다. 사용자가 기존 백업을 보호하라고 한 경우, 별도 승인을 받기 전에는 백업 파일을 만들거나 바꾸지 않는다.
6. 서비스 재시작으로 생기는 정상적인 새 systemd journal 항목까지 금지된 로그 변경에 포함되는지 불명확하다. 기존 로그를 편집·삭제·비우지 않는다.
7. `caddy validate`, `manage.py check --deploy`, `manage.py migrate --plan` 중 하나라도 실패한다.
8. 아카이브·manifest·검증기·백업기·활성화 도구가 정확한 배포 커밋과 일치하지 않는다. 이전 성공 배포에서 릴리스별 아카이브/manifest, `install_thai_release.py`, `verify_thai_release.py`, 제한된 DB·systemd 백업, `systemd-run` 점검, 원자적 drop-in 전환과 자동 복구 절차를 사용했다. 현재 호스트의 이전 스크립트는 `274c566`에 고정되어 있으므로 그대로 실행하지 말고, 같은 검증 절차로 이번 커밋 전용 파일을 만든다.

## 배포 전

1. 원격 `main`에서 앱 코드의 정확한 병합 커밋 SHA를 확인하고 `git archive --format=tar <commit> thai_platform` 방식으로 아카이브를 만든다. `--prefix=thai_platform/`와 `thai_platform` 경로 인자를 함께 쓰지 않는다. 그러면 경로가 `thai_platform/thai_platform/...`으로 중복된다. gzip은 고정 timestamp로 만든다. `.env`, `.dev-secret`, `var/`, `.venv/`, 미추적 파일은 포함하지 않는다.
2. manifest에 아카이브 SHA-256, 모든 파일의 상대 경로·SHA-256·크기·모드를 기록한다. 심볼릭 링크, 중복 경로, `..`, `thai_platform/` 바깥의 항목은 거부한다.
3. 승인된 배포 인증과 이미 신뢰된 SSH host key를 사용해 아카이브·manifest·검증 스크립트만 전송한다. 비밀값, 인증 파일, 개인키는 저장소나 아카이브에 넣지 않는다.
4. 호스트에서는 새 커밋 전용 릴리스 디렉터리에 먼저 추출한다. manifest와 모든 파일 메타데이터를 검증하고 `/opt/teemobkk-post-preview/releases/<commit>/thai_platform/manage.py`가 있는지 확인한다. 중복된 `thai_platform/thai_platform/` 구조면 중단한다. 완료 전까지 실행 중인 Caddy·systemd 경로를 바꾸지 않는다.
5. 전용 커뮤니티 DB가 계속 `/var/lib/teemobkk-post-preview/community.sqlite3`인지 확인한다. 실제 `POST_DB_PATH`가 `/opt/teemo-live-news/news.db`이거나 그 DB와 같으면 즉시 중단한다.
6. `manage.py showmigrations --plan` 및 `check --deploy`를 운영 서비스와 동일한 비밀 환경을 출력 없이 사용해 실행한다. `--plan`에서 의도된 변경만 확인한다. 환경값을 명령 출력·저장소·로그에 노출하지 않는다.
7. 사전 DB 보호가 별도 승인된 뒤에만 SQLite online backup API로 커뮤니티 DB를 복사하고, 그 복사본의 `PRAGMA integrity_check`, 테이블·행 수와 애플리케이션 조회를 검증한다. 실행 중인 SQLite DB를 `cp`하지 않는다. 기존 뉴스 DB는 백업하거나 변경하지 않는다.
8. 정적 파일 변경이 있을 때만 새 릴리스 안에서 수집하고 Caddy 정적 경로의 읽기를 확인한다. 변경이 없으면 Caddy의 현재 정적 root를 그대로 둔다. 이번 변경에는 `thai_platform/static/` 파일 차이가 없어 기존 정적 자산 경로는 유지한다.

## 적용 순서

1. 백업된 현재 Caddyfile과 systemd drop-in의 SHA-256을 확인한다.
2. systemd의 `WorkingDirectory`만 새 릴리스로 바꾼다. 정적 파일 변경이 확인된 경우에만 Caddy의 `/thai/static/*` root를 함께 바꾼다. `/thai/news/*`, 다른 호스트·경로, 환경 파일, 인증 설정은 수정하지 않는다.
3. `caddy validate`를 통과시킨 뒤 Caddy를 reload한다. systemd drop-in만 바뀌었다면 `daemon-reload` 후 `teemobkk-post-preview.service`를 재시작한다. 서비스 실행은 정상 journal 항목을 추가할 수 있다.
4. 서비스 환경을 그대로 사용해 `manage.py migrate --plan`을 다시 확인하고, 별도 커뮤니티 DB에만 `manage.py migrate --noinput`을 적용한다. 현재 릴리스에서 예상되는 신규 변경은 nullable `community.Report.closed_at` 필드 추가다. 다른 앱·DB 변경이 나타나면 중단한다.
5. 이전 릴리스 디렉터리는 롤백 확인이 끝날 때까지 삭제하지 않는다. `makemigrations`, 데이터 정리, 계정 삭제, 신고 보존 purge를 실행하지 않는다.

## 확인과 롤백

- 서비스가 `active`이고 새 `WorkingDirectory`를 사용하는지 확인한다. 새 프로세스가 응답할 때까지 대기한 뒤 loopback health와 공개 HTTPS를 각각 검사한다.
- `https://teemobkk.io/thai/`, `/thai/community/`, `/thai/newsroom/`, `/thai/static/...`를 확인한다. HTML 링크·폼·정적 자산이 `/thai/` 접두사를 유지하는지 확인한다.
- 기존 `/thai/news/*`, `/thai/news/`, 루트 뉴스 페이지를 독립적으로 검사한다. 해당 응답·정적 root가 달라졌으면 실패로 처리한다.
- 릴리스 디렉터리의 manifest를 다시 읽고 파일 수·경로·SHA-256·모드·소유자를 확인한다. 현재 서비스와 Caddy가 실제로 새 릴리스를 가리키는지 확인한다.
- 검증 실패 시 승인된 사전 백업과 기록된 이전 값만 사용해 Caddyfile과 systemd drop-in을 복원하고, Caddy validate/reload 및 서비스 복구를 확인한다. 코드 롤백 뒤에도 additive `closed_at` 열은 남겨 둔다. 마이그레이션 역적용이나 DB 복원은 별도 검토 없이 하지 않는다.

## 현재 호스트 확인 메모

2026-10-22 배포 전 읽기 전용 점검에서 `/thai/`는 `teemobkk-post-preview.service`로 연결되고, 활성 릴리스는 `6cb2195e5e6e713f216edc71217e2014bc03868d`였다. 커뮤니티 DB는 `/var/lib/teemobkk-post-preview/community.sqlite3`이며 뉴스 DB와 분리되어 있다. 배포할 앱 코드는 `70d85b8c3fc5d06c8e3937e3726fd3322d717b66`이며 runbook 문서 변경은 `2c4c82ad144e424843b2dcd9bbcc022e62c8b5bc`에 있다. 앱 아카이브는 136개 파일이고 활성 릴리스에는 125개 파일이 있어 트리가 다르므로 배포가 필요하다. `thai_platform/static/`은 변경되지 않았고 `/thai/news/*`는 별도 규칙으로 유지된다. 활성 릴리스의 기존 `check --deploy`는 종료 코드 0이었고 `security.W021`(HSTS preload 미사용) 경고가 남았다. 새 릴리스는 배포 전 다시 점검한다. 이 경고를 없애려고 preload를 켜지 않는다.

현재 호스트 PATH에는 `uv`가 없고 공유 preview 가상환경의 `certifi`는 `uv.lock`보다 오래됐지만, 새 코드에는 직접 의존성 추가가 없으며 호스트 `pip check`는 `No broken requirements found`를 반환했다. 공유 가상환경을 변경하지 않고 기존의 성공한 릴리스 절차를 사용한다. 새 코드 점검이나 import 검사가 실패하면 배포를 중단한다.
