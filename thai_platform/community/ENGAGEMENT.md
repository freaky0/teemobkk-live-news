# 도움 반응 · 비공개 스크랩 · 내 활동

## 동작 계약

- 반응은 게시글의 ‘도움됐어요’ 한 종류다. 점수·등급·정확성 인증을 의미하지 않는다.
- Helpful과 Bookmark는 각각 DB에 `(user, post)` 유니크 제약을 갖는다. 같은 요청을 반복해도 행을 중복 생성하지 않는다.
- 요청마다 토글하는 대신 원하는 상태 `active: true/false`를 명시한다. 같은 요청의 재전송이 상태를 뒤집지 않는다.
- 반응자 목록과 스크랩한 사람 목록은 공개하지 않는다. 공개 API의 `helpful_active`, `bookmarked`는 요청자 본인의 값뿐이며 익명에게는 false다.
- 스크랩 기록은 일반 모더레이션 감사 로그에 복사하지 않는다. 도움 반응의 실제 변경만 기존 감사 구조로 기록한다.
- 활성·가입 완료 계정만 변경한다. 다른 계정 ID를 넣어 조작하지 못한다. 새 API는 알 수 없는 입력 필드를 거부한다.
- 숨김·삭제 글은 변경 대상과 내 활동 결과에서 제외한다. 삭제·숨김 댓글 및 숨김·삭제된 부모 글의 댓글도 내 활동에서 제외한다.
- 상세 HTML, 게시글 API, 내 활동 응답은 개인 상태가 공용 캐시에 남지 않도록 캐시를 차단한다.

## 웹과 API

- `POST /api/v1/posts/{id}/helpful/` — `{ "active": true }` 또는 false. 응답은 본인 상태와 반응 수.
- `POST /api/v1/posts/{id}/bookmark/` — 같은 입력. 응답은 본인 상태만.
- `GET /api/v1/activity/?kind=posts|comments|helpful|bookmarks&page=1` — 본인 결과만, 기본 페이지 크기 20. 다른 사람의 ID를 받는 경로는 없다.
- `POST /community/{id}/helpful/`, `/bookmark/` — CSRF 보호 폼.
- `GET /community/activity/?kind=...` — 내 질문·답변·반응·비공개 스크랩 네 가지 탭. 본인 것만 표시한다.
- 비회원에게는 로그인 안내만 표시한다. 가입이나 반응이 성공한 것처럼 위장하지 않는다.

## 저장소 경계

두 추가형 마이그레이션 `0003_helpful`, `0004_bookmark`를 생성했다. 기존 마이그레이션은 수정하지 않았다. 이전 해결 상태 마이그레이션 회귀 검사는 종료 시 모든 최신 마이그레이션으로 복원하도록 고쳤다. 이전처럼 0002까지만 복원하면 새 기능의 브라우저 검사에서 테이블이 사라지기 때문이다.

새 의존성, 알림, 네이티브 앱 인증, 계정 연결은 추가하지 않았다. 운영·검토 서버와 실제 회원·뉴스 DB는 수정하지 않는다. 기존 개발 브랜치에 병합하지 않고 격리 브랜치에서 검증한다.

## 검증 명령

기존 브라우저 포함 검사에 `community.tests_engagement`를 추가한다.

```sh
POST_LOCAL_DEVELOPMENT=1 POST_RUN_BROWSER_TESTS=1 \
POST_BROWSER_EXECUTABLE=/path/to/chromium \
python manage.py test members.tests members.tests_preview members.tests_disclosure \
  members.tests_google_preview members.tests_browser community.tests_api \
  community.tests_web community.tests_news community.tests_browser \
  community.tests_resolution community.tests_engagement
```

추가 검사: DB 중복 제약, 반복 요청, 권한·CSRF, 본인별 상태 분리, 비공개 목록 차단, 숨김 콘텐츠 제외, 페이지 구분, 게시글 수 증가 시 쿼리 수 유지, 수정·해결 처리 후 응답 상태 일치. 브라우저는 실제 폼 제출 후 API 재조회와 320·390·768·1440 폭에서 내 활동→상세를 확인한다. 동시 프로세스 부하 시험을 수행했다는 뜻은 아니다.
