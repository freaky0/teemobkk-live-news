# 작성자 확인 해결 상태

## 계약

- `Post.resolution`: `unresolved`(미해결), `resolved`(작성자 해결 확인). 기본값은 미해결이다. 답변 수·공개 상태와 별개다.
- 공개 목록·상세·게시글 API에 상태를 표시한다. 목록의 `resolution` 필터는 기존 검색·지역·주제·페이지 조건과 함께 동작한다.
- `POST /api/v1/posts/{id}/resolution/`: JSON `{ "resolution": "resolved" }` 또는 `unresolved`.
- `POST /community/{id}/resolution/`: CSRF 보호 폼. GET으로 변경하지 않는다.
- 활성 작성자 본인만 변경한다. 다른 회원과 관리자도 대리 변경할 수 없다. 가입 절차 미완료 계정은 기존 공통 권한 검사로 거부한다.
- 숨김·삭제·없는 글은 404. 잘못된 입력은 400. 일반 게시글 생성·수정 API로 해결 상태를 쓰려고 하면 400이다.
- 같은 상태를 반복 요청하면 감사 이벤트를 추가하지 않는다. 실제 전환은 `post.resolution` 이벤트로 이전·새 상태를 남긴다.
- Django 관리자에서는 이 필드를 읽기 전용으로 둔다. 운영자가 임의로 해결 확인을 대신하지 않는다.

## 변경·검증 경계

추가형 `0002_post_resolution`만 생성했다. 이전 마이그레이션은 수정하지 않았다. 테스트 DB에서 기존 본문·작성자·숨김 상태 보존과 적용/되돌리기를 검증했다. 되돌리면 새 해결 상태 컬럼은 사라진다. 운영 데이터의 마이그레이션은 실행하지 않았다.

기존 검사에 `community.tests_resolution`을 추가해 실행한다.

```sh
POST_LOCAL_DEVELOPMENT=1 POST_RUN_BROWSER_TESTS=1 \
POST_BROWSER_EXECUTABLE=/path/to/chromium \
python manage.py test members.tests members.tests_preview members.tests_disclosure \
  members.tests_google_preview members.tests_browser community.tests_api \
  community.tests_web community.tests_news community.tests_browser community.tests_resolution
```

검증 결과: 전체 81개 통과(기존 71개와 추가 10개). Django check, 마이그레이션 누락 검사, JavaScript 문법 검사, diff 공백 검사 통과. 추가 브라우저 검사는 작성자 전환→API 재조회→상태 필터→상세→목록 복귀를 320·390·768·1440 폭에서 확인했다.

개발·운영 서비스, 실제 회원 DB, 인증 설정, 검토 사이트 차단 상태는 변경하지 않았다. 외부 Google 로그인 성공이나 보안 경고 해제를 증명하는 검사가 아니다.
