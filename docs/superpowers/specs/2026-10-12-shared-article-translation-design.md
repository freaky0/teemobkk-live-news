# Shared Article Translation Design

## Status

Draft for user review. This document describes the approved design direction. It does not authorize production deployment, service restart, or changes to the live collector configuration.

## Goal

Use one persisted Korean translation for an article across the website and Telegram news posts. The article title and summary must not be independently translated by separate delivery paths.

## Current behavior

- The website collector invokes `pipeline/translate_ko.py`, which stores translations in `articles.title_ko` and `articles.summary_ko` in the collector's `news.db`.
- The website API and page seed select those fields and fall back to the original title or summary when a Korean value is empty.
- The Telegram posting path has a separate editorial generation step (`deploy/tg_push.py`'s `brief` path) that can generate translated title/body plus channel-specific note and tags. This can produce text that differs from the persisted website translation.
- A newest-first backfill is already running against the live `news.db`. It must continue without being restarted or having its existing translations overwritten.

## Proposed source of truth and flow

1. `pipeline/translate_ko.py` remains the single component that translates an article's title and summary into Korean.
2. It persists the result to `articles.title_ko` and `articles.summary_ko`, keyed by the article's canonical `link`.
3. Website reads continue to use the stored fields and original-text fallback.
4. Every Telegram article publisher reads the same stored translation for that article link. It uses `title_ko` and `summary_ko` for the corresponding post title and translated body.
5. If a Telegram candidate has no stored Korean fields, the publisher invokes the shared translation component for that specific link and reads back the persisted result. It must not invoke its own translation prompt or another translation provider.
6. If translation fails, preserve the existing fail-open posting policy by using the original source text. Do not silently create a second translation.
7. Channel-only editorial fields, such as `TeemoBKK's Note` and tags, remain channel-specific. Their generation must receive the already translated title and summary and must not regenerate or rewrite those fields.

## Identity and consistency

- Use the exact article `link` primary key used by the collector. Confirm link normalization and resolution behavior for each Telegram publisher before implementation.
- Read title and summary translation fields as one logical pair. Do not mix a translated title with an unrelated or stale summary.
- Existing non-empty translations are preserved. The backfill and ordinary collector must not be made to overwrite them as part of this change.
- No schema change is planned.

## Error handling

- A missing translation may be filled through the shared translator once, then re-read from the database.
- A provider error, invalid output, or database write failure must not trigger a second independent translation path.
- On failure, log the article identifier and error category without logging credentials or full sensitive request data. Telegram posting may use the original text under the existing fail-open policy.

## Testing and acceptance criteria

- Unit tests prove the Telegram translation path reads `title_ko` and `summary_ko` by article link and does not call its independent title/body translation prompt.
- Missing-field tests prove the shared translator is invoked for the same link and the persisted fields are read back.
- Failure tests prove no second translator is called and the configured original-text fallback remains intact.
- Integration tests compare the website API's Korean title/summary with the Telegram post's corresponding title/body for the same database row; those strings must match exactly before channel-only formatting is added.
- Tests cover missing, partial, invalid, and already-translated rows, as well as alternate publisher paths and canonical-link cases.
- Verify new collector writes and Telegram posts use the shared fields after deployment. Verify the active backfill independently; do not treat it as proof of deployment.

## Scope and rollout

- Change only the translation-to-publisher boundary and its focused tests. Do not change article selection, posting cadence, channel filters, note/tag policy, model credentials, or the live website API contract.
- Inspect every production Telegram publishing path, including scheduled posts and the VPS-agent outbox path, before implementation. All paths that publish article translations must use the same stored fields.
- Implement and verify locally first. Production push, file replacement, service restart, or deployment requires separate explicit approval.
- The existing live backfill remains a separate data operation. Do not pause or restart it for this code change unless it fails or the user directs otherwise.
