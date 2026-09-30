# Agent Mailbox Protocol (Muse ↔ Hermes)

비동기 파일 기반 에이전트 간 작업 전달 프로토콜. Phase 1.

## 디렉터리

```
mailbox/
  inbox/      # Muse → Hermes 작업 파일
  outbox/     # Hermes → Muse 결과 파일
  archive/    # 처리 완료된 파일 이동
  PROTOCOL.md # 이 문서
```

## 작업 파일 (inbox/{id}.json) — Muse가 작성

```json
{
  "id": "20261001-001",
  "from": "muse",
  "to": "hermes",
  "type": "task",
  "title": "짧은 제목",
  "body": "작업 내용 (마크다운 가능)",
  "created_at": "2026-10-01T05:20:00+07:00"
}
```

## 결과 파일 (outbox/{id}.json) — Hermes가 작성

```json
{
  "id": "20261001-001",
  "from": "hermes",
  "to": "muse",
  "type": "result",
  "status": "done",
  "summary": "한 줄 요약",
  "body": "결과 내용 (마크다운 가능)",
  "created_at": "2026-10-01T05:35:00+07:00"
}
```

- `id`: `{YYYYMMDD}-{순번}` 형식. 예: `20261001-001`. 중복 시 뒤에 `-2`를 붙인다.
- `status`: `done` / `failed` / `working` 중 하나. `failed`면 body에 실패 원인을 적는다.

## Hermes 동작

1. `mailbox/inbox/`를 감시한다 (git pull 주기적 감시 또는 파일시스템 watch).
2. 새 작업 파일을 발견하면 처리한다.
3. 결과를 `mailbox/outbox/{id}.json`에 쓰고 커밋·푸시한다.
4. 처리한 inbox 파일을 `mailbox/archive/`로 이동한다.
5. 처리 중 에러가 나도 멈추지 않는다. 해당 작업은 `failed`로 결과를 남기고 다음 작업을 계속 처리한다.

## Muse 동작

1. 작업을 `mailbox/inbox/{id}.json`으로 커밋·푸시한다.
2. `mailbox/outbox/{id}.json`이 생길 때까지 git pull로 확인한다.

## 제한 (중요)

- 이 저장소는 공개 저장소다. 작업·결과 파일의 내용은 GitHub에서 누구나 볼 수 있다.
- 비밀값(API 키, 토큰, 비밀번호 등)은 절대 넣지 않는다.
- 공개되면 안 되는 내용(비공개 계획, 개인정보 등)도 넣지 않는다.
- 필드명을 바꾸지 않는다. 스키마 변경이 필요하면 양쪽이 먼저 합의한다.

## Phase 2 (미정)

실시간 HTTP 엔드포인트 (`POST /agent/tasks`, `GET /agent/tasks/{id}`).
필요해지면 별도로 합의 후 추가한다.
