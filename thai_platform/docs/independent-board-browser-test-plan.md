# Independent board browser acceptance plan

Use a disposable Django test database and the built-in localhost-only live server; do not point to production services or a real news database. Browser requests to other origins are aborted. The browser tests use test-only authenticated sessions, not real authentication providers.

## Automated browser coverage

1. As staff for `notice` and a member for `free`, `market`, `jobs`, and `living`, select the category in the web editor, create, open and edit each post. Confirm each updated title on its detail page.
2. As an anonymous reader, use the category dropdown and Apply control for each board. Check the selected category and that only the corresponding marker appears.
3. As another member, confirm notice and another author's post do not expose edit links and direct edit URLs return 403. Attempt to create a notice as a member and check it is not saved.
4. As a second member on each board, add a helpful reaction, bookmark, and answer. Verify pressed states and that the answer survives reload.
5. Check for uncaught browser page errors. Exercise the mobile viewport (390 × 844).

Run from `thai_platform` with dependencies and a Chromium headless shell already installed, without network access:

```sh
POST_LOCAL_DEVELOPMENT=1 POST_SECRET_KEY=local-test-only-not-production \
POST_RUN_BROWSER_TESTS=1 PLAYWRIGHT_BROWSERS_PATH=/path/to/existing/browser/cache \
uv run --offline python manage.py test community.tests_independent_board_browser
```

`POST_BROWSER_EXECUTABLE` can instead select an installed browser. For physical table isolation, API/Web consistency and legacy interactions, also run `community.tests_independent_storage_acceptance`. Browser tests alone do not prove five separate physical tables. Run the existing news tests separately against their test fixtures to check regression; this plan neither changes nor accesses production news. Before release repeat against the integrated implementation, also testing desktop widths, cross-category moves and confirmation, guest write redirects, staff-to-staff notice editing, unauthorized direct POST/CSRF, per-user undo and isolation of reactions/bookmarks, comments/replies, pagination, and news unchanged. Record failures separately from environment/setup errors.
