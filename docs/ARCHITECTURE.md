# OmniForum Architecture

## Stack

- Backend: `app.py` using Python standard library HTTP tooling
- Storage: split SQLite databases under `data/`
- Frontend: static HTML pages plus shared `js/` and `css/`
- Media: uploaded avatars and post media served from `/media/...`
- Runtime dependency: Pillow for image processing

## Source Layout

```text
app.py                  Python HTTP server entrypoint
omniforum/              Backend modules for config, DB, schema, routing, API mixins, focused domain helpers, media, search, backups, plugins, and validation
index.html              Forum homepage
pages/                  Secondary site pages
js/                     Frontend application logic, with page modules plus shared UI/data/admin/thread bundles
css/                    Ordered stylesheet bundle plus focused style modules
data/                   Runtime databases, uploads, backups, logs
deploy/                 Deployment examples and Deployment Assistant static assets
docs/                   Focused setup, deployment, operations, testing, policy, and architecture notes
scripts/                Helper maintenance scripts
```

## Runtime Data Layout

- `users.db`: accounts, roles, recovery state/codes, site settings, registration controls, invite codes, preferences, saved site theme, and avatars
- `sessions.db`: login sessions, CSRF tokens, and session audit metadata
- `sections.db`: categories and sections
- `threads.db`: threads, poll data, bookmarks, follows
- `posts.db`: replies, likes, reactions, media, edit history
- `messages.db`: direct messages
- `notifications.db`: alerts and unread notifications
- `reports.db`: reports, appeals, report internal notes, and saved moderation macros
- `audit.db`: searchable admin audit trail plus lightweight search analytics and persistent rate-limit events
- `contact.db`: contact form submissions and staff inbox state
- `uploads/avatars/`: profile pictures
- `uploads/posts/`: thread/reply images and GIFs
- `uploads/thumbs/`: generated thumbnails for inline post media
- `exports/backups/`: admin-created backups
- `logs/server.log`: lightweight server log
- `logs/access.log`: request log mirror with request IDs
- `logs/app.jsonl`: structured JSONL runtime events, API requests, API exceptions, and media scanner outcomes

Only uploaded media and exported backups are meant to be web-served. The rest of `data/` is private application storage.

## Source And Runtime Hygiene

- Commit `data/README.md` and `.gitkeep` placeholders only.
- Do not commit `data/*.db`, `data/logs/*`, `data/uploads/*`, or `data/exports/*`.
- Use `scripts/reset_runtime_data.sh` to clear a local development instance before making a clean source package.
- Use `scripts/package_release.sh` to create a clean source archive that excludes runtime data.
- Use `scripts/check_release_archive.py` to verify a package excludes private/runtime state.
- Use `scripts/seed_demo.py` against a clean local server to create screenshot/QA/demo content without private data.
- Use `scripts/backup_omniforum.sh` or the admin Operations backup before deleting runtime data you may need again.
- Use `scripts/scrub_private_data.sh` when preparing a source handoff from a dirty local workspace.
- Use `scripts/clean_workspace.sh` to remove generated local clutter such as `__pycache__`, `.DS_Store`, coverage, and test caches.
- Mount `data/` as persistent storage in Docker, systemd, or VPS deployments.

## Privacy Posture

- Treat everything under `data/` except placeholders and `data/README.md` as private.
- Before publishing a copy of the source, run `scripts/package_release.sh` or reset local runtime data.
- If private runtime data was ever shared, rotate sessions by clearing `data/sessions.db`, issue new passwords or recovery codes as needed, and replace any exposed webhook URLs in `.env`.

## Backend Structure

The backend still starts from `app.py`, but shared foundations now live in `omniforum/`:

- `omniforum/config.py` contains paths, environment-backed settings, roles, constants, and table-name mappings.
- `omniforum/api_routes.py` owns the declarative API route table that maps methods and paths to handler methods.
- `omniforum/api_*.py` modules own the domain-specific `ForumHandler` API mixins for auth, public data, messages, moderation, users, content, and admin operations.
- Large content, moderation, and admin groups are split further into focused section/thread/post/reaction/report/appeal/user moderation/admin operation mixins.
- `omniforum/domain.py` is a compatibility facade over focused `domain_*.py` modules for users, threads, messages, notifications, moderation, search, and live/home payloads.
- Thread-specific work is split further into `domain_thread_membership.py`, `domain_sections.py`, `domain_thread_records.py`, `domain_thread_lists.py`, and `domain_posts.py`.
- Cross-domain calls use explicit local imports in focused modules instead of facade-level peer injection.
- `omniforum/db.py` owns SQLite attachment, SQL qualification, and runtime directory creation.
- `omniforum/core.py` owns time helpers, role checks, password hashing, and recovery-code helpers.
- `omniforum/errors.py` contains the shared API exception type.
- `omniforum/schema.py` is a compatibility facade over focused schema modules: `schema_core.py`, `schema_maintenance.py`, `schema_defaults.py`, `schema_search.py`, and `schema_seed.py`.
- `omniforum/migrations.py` owns legacy import plus schema migration history in `schema_migrations`.
- `omniforum/validation.py` is a compatibility facade over focused validation modules for text, registration/invites, site settings, profile/account fields, content/moderation fields, pagination, and trust-limit calculations.
- `omniforum/audit.py` owns audit-event logging, filtering, serialization, and summary query helpers.
- `omniforum/account_state.py` owns account trust, restrictions, cooldowns, XP promotion, and participation guards.
- `omniforum/sessions.py` owns cookie session lookup, session creation, session refresh, and revocation helpers.
- `omniforum/content_state.py` owns soft-delete/restore behavior, shadow visibility, reaction summaries, and poll helpers.
- `omniforum/site_settings.py` owns site settings update persistence and related audit events.
- `omniforum/admin_health.py` owns admin health, queue counters, onboarding checks, install checks, and operations analytics.
- `omniforum/admin_export.py` owns admin export generation and import-preview helpers.
- `omniforum/seo.py` owns `robots.txt` and `sitemap.xml` generation.
- `omniforum/media.py` is a compatibility facade over focused media modules: `media_paths.py`, `media_quota.py`, `media_images.py`, `media_store.py`, and `media_posts.py`.
- `omniforum/search.py` owns FTS schema usage, index refresh/update hooks, and search analytics logging.
- `omniforum/runtime_logging.py` owns server/app log writing and recent-log parsing.
- `omniforum/backups.py` owns backup archive creation and inspection.
- `omniforum/storage.py` owns storage/media usage and orphan cleanup helpers.
- `omniforum/plugins.py` owns plugin manifests, client asset allowlisting, and plugin summaries.
- `omniforum/integrations.py` owns external notices such as Discord webhooks.

`app.py` is intentionally small now: stdlib server startup, request parsing, static/private asset serving, CSRF and rate-limit enforcement, cookies, JSON responses, and route dispatch. Domain service logic and route handler groups live in `omniforum/`, so new behavior should usually land there instead of growing the entrypoint again.

## Frontend Structure

The shared frontend UI is split by domain. `js/api.js`, `js/ui.js`, `js/data.js`, `js/layout-ui.js`, `js/admin-ui.js`, `js/admin-ops-ui.js`, `js/profile-ui.js`, `js/page-section.js`, `js/page-thread.js`, and `js/page-settings.js` are compatibility/bundle markers.

Focused files such as `api-content-client.js`, `layout-nav-ui.js`, `layout-sidebar-ui.js`, `data-media.js`, `admin-ops-audit.js`, `profile-card-ui.js`, `page-section-composer.js`, `page-thread-render.js`, and `page-settings-content.js` carry the actual behavior.

`css/main.css` and `css/forum.css` are ordered stylesheet bundles that import focused files for base, navigation, forum hero/sidebar/sections/posts, modals, pages, components, and responsive overrides.

Frontend asset order is owned by `assets/manifest.json`.

```bash
scripts/generate_assets.py
scripts/generate_assets.py --check
scripts/build_assets.py /tmp/omniforum-assets
```

## Security And Growth Posture

- Account recovery is email-free by default.
- Optional email password reset is available only when `OMNIFORUM_EMAIL_AUTH_ENABLED=1` and SMTP is configured.
- Uploaded media is type-checked and reprocessed with Pillow.
- `OMNIFORUM_MEDIA_SCAN_COMMAND` can run an external scanner/quarantine command before uploads are committed.
- Browser CSP keeps scripts and styles under `script-src 'self'` and `style-src 'self'`.
- API responses include `X-Request-ID`.
- API requests, failures, exceptions, and media scanner outcomes are written to `data/logs/app.jsonl`.
- Schema upgrades use additive repair plus an ordered checksum-recorded migration registry.
- External monitoring can call `scripts/healthcheck.py https://forum.example.com`.

## Important Constraints

- OmniForum uses SQLite and local file storage, so treat it as a single-node app.
- Production should always run behind HTTPS.
- Only `/media/...` and `/exports/...` should be exposed through the app.
- The rest of `data/` should never be served directly.
