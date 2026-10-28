# Community Feature Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add category-specific marketplace, job, and place details; per-member blocked-content filtering; near-live private-message unread updates; and a read-only external-backup readiness report.

**Architecture:** Extend the existing Django `Post` model and `PostForm`/DRF serializers with optional, category-scoped fields and additive migrations. Reuse `MemberBlock` and existing private-message read state; enforce member-specific visibility in shared web/API query services, and use one authenticated no-store count endpoint polled by a small same-origin script only while the tab is visible. Inspect backup operations read-only; do not transfer or alter the production database.

**Tech Stack:** Django 5.2, Django REST Framework, SQLite, server-rendered templates, small vanilla JavaScript module, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-27-community-expansion-design.md`

## Global Constraints

- Keep existing post/comment/member rows and the existing category behavior intact.
- New post-detail fields are nullable/blank and only accepted for their matching category.
- Keep current permissions, CSRF behavior, existing unread/read semantics and message-block behavior.
- The Google Maps link is an encoded search URL from user-entered place and region; do not invent coordinates or venue facts.
- External links allow only `http` and `https`; render user content escaped and external links with safe target attributes.
- Never expose another member’s private information or unread count.
- Do not deploy, change account privileges, restore/reset the live DB, transmit database copies, or modify `/opt/teemo-live-news`.
- Verify each slice with a failing test first, then targeted tests, regression tests, browser checks where applicable, and a small commit before the next slice.

## Review Focus

- Existing records and code from the deployed `4aa084d` release after additive migrations → migration test verifies rows and prior release insert/read compatibility.
- A user submits category-specific fields under a different category or through the API → reject or ignore them without storing them; test both web form and strict serializer.
- Malicious or international place names and `javascript:` external URLs → quote the search query and reject unsafe schemes; test encoded Unicode, query delimiters, and scheme rejection.
- A blocked member’s content is fetched by direct detail, search, API, nested replies, or an anonymous/unrelated viewer → apply per-viewer filtering consistently without changing public data; test each path and unblock.
- A polling request races with reading a message or the tab becomes hidden → return only the authenticated recipient’s current count, stop hidden-tab polling, and do not create duplicate timers; test endpoint privacy and browser lifecycle.

---

### Task 1: 중고게시판 정보

**Files:**
- Modify: `thai_platform/community/models.py` (`Post`)
- Modify: `thai_platform/community/forms.py` (`PostForm`)
- Modify: `thai_platform/community/serializers.py` (`PostInputSerializer`, `PostSerializer`)
- Modify: `thai_platform/community/services.py` (category-aware validation and persistence)
- Modify: `thai_platform/templates/community/fields.html`, `detail.html`, `list.html`
- Create: `thai_platform/community/migrations/<generated additive market-fields migration>.py`
- Create: `thai_platform/community/tests_market.py`
- Browser test: `thai_platform/community/tests_browser.py`

**Interfaces:**
- Consumes: existing `PostForm`, `PostInputSerializer`, `create_post`, `update_post`, and `Post.Category.MARKET`.
- Produces: optional `Post.market_kind` (`sell`/`buy`), `market_price` (nullable `DecimalField(max_digits=12, decimal_places=2)`, nonnegative and displayed in THB), `market_region` (existing region values), and `market_status` (`active`/`reserved`/`completed`). Fields are only editable for category `market` by the author or existing operator.

- [ ] **Step 1: Write failing tests** `MarketBoardTests.test_market_fields_save_and_render`, `test_market_price_rejects_negative_and_invalid_kind`, `test_non_market_payload_cannot_store_market_fields`, and `test_existing_post_rows_survive_market_migration`. Assert exact saved values and visible status/THB labels, no persistence of cross-category fields, and unchanged pre-migration author/title/body with all new optional fields empty.
- [ ] **Step 2: Verify RED**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_market --noinput`
Expected: expected missing-field/form behavior failures; no import/setup failures.

- [ ] **Step 3: Implement the minimal additive model, form, serializer and service validation**; generate the migration with Django, defaulting old rows to empty optional values. Render only non-empty market information.
- [ ] **Step 4: Verify GREEN and regressions**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_market community.tests_boards community.tests_api community.tests_web --noinput`
Expected: all pass; `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py makemigrations --check --dry-run` reports no model drift.

- [ ] **Step 5: Browser verify** create/edit/list/detail at 320, 390 and 1440px; verify no overflow and status/price are labeled. Commit `feat: add structured secondhand board details`.

### Task 2: 구인구직 정보

**Files:**
- Modify: `thai_platform/community/models.py`, `forms.py`, `serializers.py`, `services.py`
- Modify: `thai_platform/templates/community/fields.html`, `detail.html`, `list.html`
- Create: `thai_platform/community/migrations/<generated additive job-fields migration>.py`
- Create: `thai_platform/community/tests_jobs.py`
- Browser test: `thai_platform/community/tests_browser.py`

**Interfaces:**
- Consumes: existing category-scoped post form/service and common region choices.
- Produces: optional `Post.job_kind` (`hiring`/`seeking`), `job_region`, `job_compensation` (maximum 200 characters), and `job_status` (`open`/`closed`). Only category `jobs` accepts or renders these values; writes remain author/operator-only.

- [ ] **Step 1: Write failing tests** `JobBoardTests.test_hiring_and_seeking_details_render`, `test_compensation_length_and_status_validation`, and `test_non_job_payload_cannot_store_job_fields`. Assert hiring/seeking labels, region/status/optional compensation, 201/invalid-form behavior per the current create API, and no persisted job details outside `jobs`.
- [ ] **Step 2: Verify RED**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_jobs --noinput`
Expected: field and validation assertions fail for the intended missing behavior.

- [ ] **Step 3: Add optional job fields, server validation and category-specific form/detail/list rendering**; generate the next additive migration.
- [ ] **Step 4: Verify GREEN and regressions**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_jobs community.tests_market community.tests_boards community.tests_api --noinput`
Expected: all pass and market workflow remains unchanged.

- [ ] **Step 5: Browser verify** hiring/seeking create and status update at mobile and desktop widths. Commit `feat: add structured job board details`.

### Task 3: 맛집·여행지와 Google Maps 링크

**Files:**
- Create: `thai_platform/community/places.py` with `build_google_maps_search_url(place_name: str, region: str) -> str` and `validate_external_place_url(value: str) -> str`
- Modify: `thai_platform/community/models.py`, `forms.py`, `serializers.py`, `services.py`
- Modify: `thai_platform/templates/community/fields.html`, `detail.html`, `list.html`
- Create: `thai_platform/community/migrations/<generated additive place-fields migration>.py`
- Create: `thai_platform/community/tests_foodtravel.py`
- Browser test: `thai_platform/community/tests_browser.py`

**Interfaces:**
- Consumes: category-scoped form/service, common `Post.region`, and URL-safe encoding.
- Produces: optional `Post.place_name`, `place_region`, `place_note`, and `place_url`. For `foodtravel`, display the explicit validated URL when present plus an automatically generated Google Maps search link from the place name and region. The generated link is derived, not stored as a guessed venue.

- [ ] **Step 1: Write failing tests** `FoodTravelTests.test_google_maps_search_url_encodes_unicode_and_reserved_chars`, `test_rejects_non_http_external_scheme`, `test_place_details_only_apply_to_foodtravel`, and `test_maps_link_renders_as_safe_external_link`. Pin the URL to `https://www.google.com/maps/search/?api=1&query=<urlencoded place-and-region>` and assert Unicode/reserved characters round-trip; reject `javascript:`/protocol-relative URLs; ensure rendered anchors use `rel="noopener noreferrer"`.
- [ ] **Step 2: Verify RED**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_foodtravel --noinput`
Expected: URL builder/validation and template assertions fail for absent implementation.

- [ ] **Step 3: Implement URL encoding with `urllib.parse.urlencode`, strict `http`/`https` validation for user-supplied links, category-limited persistence, and escaped safe link rendering**; generate the additive migration.
- [ ] **Step 4: Verify GREEN and regressions**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_foodtravel community.tests_market community.tests_jobs community.tests_api community.tests_web --noinput`
Expected: all pass; malformed schemes and cross-category payloads never persist.

- [ ] **Step 5: Browser verify** enter Korean/Thai place names, click the generated link, inspect target attributes, test at 320/390/1440px and check for console errors. Commit `feat: add map links to food and travel posts`.

### Task 4: 차단 회원 게시글·댓글 개인별 숨김

**Files:**
- Modify: `thai_platform/community/services.py` (viewer-aware post/comment/notification query helpers and reply validation)
- Modify: `thai_platform/community/web.py` (home/list/detail/search, public-member, activity, and notification views)
- Modify: `thai_platform/community/api.py` (post list/detail/comments and notification querysets)
- Modify: `thai_platform/templates/community/block_list.html`, `member_menu.html` (describe viewer-specific post/comment hiding)
- Create: `thai_platform/community/tests_blocked_visibility.py`
- Browser test: `thai_platform/community/tests_browser.py`

**Interfaces:**
- Consumes: existing `MemberBlock(blocker, blocked)`, published status constraints, and existing public web/API endpoints.
- Produces: `blocked_member_ids(user)`, `visible_posts(user)`, `visible_comments(user, post)`, and `visible_notifications(user)` query helpers. For authenticated viewers, exclude blocked members’ posts, comments, replies, profile, and related reply notifications; anonymous and unrelated viewers keep current visibility. Omit blocked records entirely without placeholders or existence hints. Existing operator-hidden state remains globally authoritative.

- [ ] **Step 1: Write failing tests** `BlockedContentVisibilityTests.test_block_hides_target_posts_only_for_blocker`, `test_block_hides_comments_and_replies_in_detail_and_api`, `test_block_hides_profile_activity_and_notification_hints`, `test_direct_post_and_comment_routes_do_not_leak_blocked_content`, `test_unblock_restores_unchanged_content`, and `test_operator_hidden_content_remains_hidden_for_every_viewer`. Assert blocker sees neither body nor author identity or notification hint; anonymous/unrelated viewers retain visibility; nested replies to hidden comments are omitted; unblocking restores the same rows.
- [ ] **Step 2: Verify RED**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_blocked_visibility --noinput`
Expected: visibility assertions fail only for the blocker; baseline visibility for others remains asserted.

- [ ] **Step 3: Route all relevant web/API query paths through shared viewer-aware query helpers**. Preserve original database rows and ensure queryset filtering occurs before pagination/counts.
- [ ] **Step 4: Verify GREEN and regressions**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_blocked_visibility community.tests_member_menu community.tests_private_messages community.tests_comment_likes community.tests_notifications community.tests_operator_posts community.tests_replies community.tests_api --noinput`
Expected: all pass, with no effect on other viewers or historical rows.

- [ ] **Step 5: Browser verify** block/unblock and verify own, anonymous, unrelated, and blocker views on list/detail/comments at 320, 390 and 1440px. Commit `feat: hide blocked members content per viewer`.

### Task 5: 쪽지 수신 배지 주기 갱신

**Files:**
- Modify: `thai_platform/community/private_messages.py` (authenticated unread-count endpoint)
- Modify: `thai_platform/config/urls.py` (same-origin route)
- Modify: `thai_platform/templates/base.html` (data attributes and initial server count)
- Create: `thai_platform/static/message-unread.js`
- Modify: `thai_platform/members/tests_header_footer.py`
- Create: `thai_platform/community/tests_message_poll.py`
- Browser test: `thai_platform/community/tests_browser.py`

**Interfaces:**
- Produces: named same-origin route `community-unread-count` in `config/urls.py`, resolved in the template through Django `{% url %}` so `/thai/` script-prefix deployments work; `GET` returns `{"count": <integer>}` with `Cache-Control: private, no-store`. Only authenticated active members may receive their own recipient-scoped count.
- Client polls every 30 seconds while `document.visibilityState === "visible"`, pauses while hidden, refreshes immediately on `visibilitychange`, prevents overlapping requests, and leaves the last good count unchanged on network/server errors. Zero removes the numeric badge but retains the accessible message link; count changes update a stable `role="status"` announcement only when the count changes.

- [ ] **Step 1: Write failing tests** `MessagePollTests.test_count_is_only_for_authenticated_recipient`, `test_count_changes_when_message_becomes_read`, `test_response_is_private_no_store`, `test_named_route_resolves_under_thai_mount_prefix`, and browser test `test_unread_badge_refreshes_and_pauses_in_hidden_tab`. Assert anonymous access cannot get a count, recipients see only their own unread count, reading decrements it, response has `private` and `no-store`, and reversing under `SCRIPT_NAME="/thai"` stays under that prefix.
- [ ] **Step 2: Verify RED**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_message_poll --noinput`
Expected: endpoint/auth/privacy assertions fail because the poll endpoint is absent.

- [ ] **Step 3: Implement the recipient-scoped count endpoint and a single lifecycle-aware vanilla-JS timer**. Do not create WebSocket infrastructure or change when a message becomes read.
- [ ] **Step 4: Verify GREEN and regressions**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_message_poll community.tests_private_messages community.tests_notifications members.tests_header_footer --noinput`
Expected: private count, read transition, and existing messaging/notifications pass.

- [ ] **Step 5: Browser verify** mock or deliver a test message while the page is open; assert badge update, hidden-tab pause/resume, one timer, no console errors and 320/390/768/1440px layout. Commit `feat: refresh unread message badge while active`.

### Task 6: 읽기 전용 백업 상태 점검 보고

**Files:**
- Create: `docs/operations/community-db-backup-readiness.md` (evidence-backed report; no secrets, user data, or credential values)
- No production code or server state changes.

**Interfaces:**
- Report only metadata: backup scheduler existence and last run result, backup file permissions/ownership and same-host/off-host status, last integrity/restore verification evidence, and remaining gaps. Do not copy or upload database files.

- [ ] **Step 1: Define report assertions** source timestamp, evidence for each claim, explicit `unknown` when absent.
- [ ] **Step 2: Read-only inventory** approved SSH route; inspect only named service/timers/backup paths and metadata; never dump environment contents or database rows.
- [ ] **Step 3: Write the report** and verify it contains no secret values, user data or unsupported claims.
- [ ] **Step 4: Review** that no remote file, service, timer, database, backup, or news path changed. Commit `docs: record community backup readiness`.

### Task 7: Integrated verification and handoff

**Files:**
- Test the full changed surface in the same isolated worktree.

**Interfaces:**
- Consumes: all completed tasks and their committed migrations.
- Produces: tested non-deployed candidate branch based on the approved spec.

- [ ] **Step 1: Run project checks**

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py check` and `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py makemigrations --check --dry-run`
Expected: no system issues and no migration drift.

- [ ] **Step 2: Run focused combined suite** all new `tests_market`, `tests_jobs`, `tests_foodtravel`, `tests_blocked_visibility`, `tests_message_poll` plus existing `tests_boards`, `tests_api`, `tests_web`, `tests_private_messages`, `tests_notifications`, `tests_comment_likes`, `tests_replies`, `tests_operator_posts`.

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test community.tests_market community.tests_jobs community.tests_foodtravel community.tests_blocked_visibility community.tests_message_poll community.tests_boards community.tests_api community.tests_web community.tests_private_messages community.tests_notifications community.tests_comment_likes community.tests_replies community.tests_operator_posts --noinput`
Expected: all applicable tests pass; report skips exactly.

- [ ] **Step 3: Run the README-documented Django, dependency-audit, JavaScript and browser checks**; keep baseline failures separate.

Run: `POST_LOCAL_DEVELOPMENT=1 uv run python manage.py test members.tests community.tests_api community.tests_web community.tests_news --noinput`

Run: `uv run pip-audit --local --progress-spinner off`

Run: `node --check static/service.js`

Run: `POST_LOCAL_DEVELOPMENT=1 POST_RUN_BROWSER_TESTS=1 uv run python manage.py test members.tests_browser community.tests_browser --noinput`

- [ ] **Step 4: Review diff, security boundaries, migration graph and historical compatibility**; refresh Graft after substantial implementation.
- [ ] **Step 5: Finish with a concise verification handoff** listing commit SHA, test counts/skips, migration/data-compatibility evidence, backup audit findings and unresolved gaps. Keep the candidate non-deployed and request separate production approval. Do not create a verification-only commit unless the repository's release convention requires a committed report.
