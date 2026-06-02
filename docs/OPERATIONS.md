# OmniForum Operations

## Running Locally

- Create a virtual environment with `python3 -m venv .venv`, activate it, and install dependencies with `python -m pip install -r requirements.txt`.
- Copy `.env.example` to `.env` if you want persistent local overrides.
- Start the server from the project root with `python app.py`.
- By default it binds to `127.0.0.1:8000`.
- Override runtime settings with:
  - `OMNIFORUM_HOST`
  - `OMNIFORUM_PORT`
  - `OMNIFORUM_PUBLIC_URL`
  - `OMNIFORUM_MAX_REQUEST_BYTES`
  - `OMNIFORUM_BACKUP_ROTATION`
  - `OMNIFORUM_BACKUP_STALE_HOURS`
  - `OMNIFORUM_LIVE_INTERVAL_SECONDS`
  - `OMNIFORUM_USER_MEDIA_LIMIT_BYTES`
  - `OMNIFORUM_USER_MEDIA_LIMIT_FILES`
  - `OMNIFORUM_MEDIA_SCAN_COMMAND`
  - `OMNIFORUM_MEDIA_SCAN_REQUIRED`
  - `OMNIFORUM_MEDIA_SCAN_TIMEOUT_SECONDS`
  - `OMNIFORUM_EMAIL_AUTH_ENABLED`
  - `OMNIFORUM_EMAIL_FROM`
  - `OMNIFORUM_SMTP_HOST`
  - `OMNIFORUM_SMTP_PORT`
  - `OMNIFORUM_SMTP_USERNAME`
  - `OMNIFORUM_SMTP_PASSWORD`
  - `OMNIFORUM_SMTP_STARTTLS`
  - `OMNIFORUM_DISCORD_WEBHOOK_URL`
  - `OMNIFORUM_SECURE_COOKIES=1`

## Data Layout

- SQLite files live under `data/`.
- Uploaded media lives under `data/uploads/`.
- Pillow processes uploads when installed from `requirements.txt`: large images are resized, metadata is stripped during re-encoding, and post images receive generated thumbnails under `data/uploads/thumbs/`.
- Searchable admin audit events are stored in `data/audit.db`.
- Site configuration, branding, recovery codes, and signup controls are stored in `data/users.db`.
- Report internal notes, SLA/escalation state, and saved moderation macros are stored in `data/reports.db`.
- Admin-created backup archives are written to `data/exports/backups/`.
- Runtime request logs are appended to `data/logs/server.log`.
- Access logs are mirrored to `data/logs/access.log`; structured app events, API request outcomes, API exceptions, and media scanner outcomes are written as JSON lines to `data/logs/app.jsonl`.
- Source packages should include `data/README.md` and `.gitkeep` placeholders, not live `*.db`, session, upload, backup, or log files.
- Use `OMNIFORUM_CONFIRM_RESET=yes scripts/reset_runtime_data.sh` to clean local runtime state after stopping the server.
- Use `scripts/package_release.sh` to build a clean source archive without private runtime state.
- Use `scripts/seed_demo.py http://127.0.0.1:8000` against a clean local server to create demo users/content for screenshots and QA.

## Backups

- Open Settings as an admin or owner and use `Operations` -> `Create Backup`.
- The server generates a zip archive containing:
  - all `data/*.db` files
  - `data/logs/server.log` if present
  - uploaded avatars and post media
- Backup rotation keeps the newest archives and removes older ones based on `OMNIFORUM_BACKUP_ROTATION`.
- The Operations dashboard marks the latest archive as stale after `OMNIFORUM_BACKUP_STALE_HOURS` hours. The default is 168 hours.

## Production Health Dashboard

- Admins and the owner can open `Settings -> Operations` to view the production health snapshot.
- The dashboard shows total SQLite database size, individual database file sizes, media usage by upload bucket, orphaned media counts, backup status, recent failed requests/runtime errors, queue counts, plugin status, media scanner state, onboarding readiness, production install checks, forum analytics, and recovery readiness.
- Recovery readiness validates the latest backup archive, confirms the restore script exists and is executable, and shows the last logged backup and restore-guide check.
- The dashboard is read-only except for the explicit actions: setup wizard, import/export tools, staff workflow tools, create backup, cleanup orphan media, signup controls, plugin manager, trash restore, and backup restore guide.

## First-Run Setup And Site Settings

- Admins and the owner can open `Settings -> Operations -> Setup Wizard`.
- The wizard saves site name, logo text/mark, hero copy, footer links, policy intros, support links, SEO defaults, upload policy, feature toggles, and default theme into the persistent site settings table.
- Use the same wizard to jump to signup controls, section management, and first backup creation during launch setup.

## Import/Export Tools

- Admins and the owner can open `Settings -> Operations -> Import / Export`.
- JSON and CSV exports are available for users, threads, posts, reports, moderation logs, and settings.
- Import preview accepts JSON exports and reports detected counts without writing live data. Treat it as a restore-planning tool, not a live importer.

## Audit Log

- Admins and the owner can open `Settings -> Operations -> Audit Log`.
- Audit events are searchable and filterable by category, actor, target type, exact action, date range, and text query.
- Events are written for user moderation, report/appeal/contact triage, section changes, plugin toggles, backup and restore-guide activity, media cleanup, signup settings, invite codes, registration approvals, staff content actions, thread splits, and staff thread notes.
- Events are also written for site setting changes, admin exports, import previews, moderation macros, report internal notes, recovery-code regeneration, and recovery-code login.
- Raw request logs stay in `data/logs/server.log`; the audit log is the structured history stored in `data/audit.db`.

## Restore Process

1. Stop the OmniForum server.
2. In `Settings -> Operations`, open `Restore Guide` for the archive you want and confirm the checklist.
3. Run `scripts/restore_omniforum.sh /absolute/path/to/archive.zip /absolute/path/to/project`.
4. Start the server again with `python app.py`.
5. Load `/api/health`, `/api/home`, or the homepage to confirm the restored instance boots normally.

## Soft-Delete Recovery

- Admins can also restore soft-deleted threads and replies from `Settings -> Operations`.
- Restore a deleted thread before restoring individual replies that belong to it.
- The recovery panel is meant for recent moderation mistakes; full-instance rollback should still use backup restore.

## Plugins

- Installed plugins live under `plugins/<plugin-name>/`.
- Each plugin needs a `plugin.json` manifest.
- Only enabled plugins are served to clients.
- Only manifest-declared `client.styles`, `client.scripts`, and `client.assets` files are publicly served.
- Admins can toggle plugin state from `Settings -> Operations -> Manage Plugins`.

## Media Cleanup

- Admins can run orphaned media cleanup from `Operations`.
- This removes files in `data/uploads/` that are no longer referenced by post media, generated thumbnails, or user avatars.
- It also clears orphaned post-media metadata and stale avatar references before sweeping files.
- Run a backup before cleanup if you want an easy rollback point.

## Signup Controls

- Admins and the owner can open `Settings -> Operations -> Signup Controls`.
- Public registration can be left open, closed, switched to invite-only mode, or combined with admin approval.
- Approval-required accounts are created in a pending state and cannot log in until an admin approves them.
- Invite codes can be created, copied, disabled, limited by use count, and optionally expired after a number of days.
- Blocked username patterns are one per line. Wildcards such as `admin*` are supported, and plain words block usernames containing that word.
- Registration throttling is persisted in `data/audit.db` per client IP so active abuse windows survive process restarts.
- Captcha support is not wired in yet; use invite-only mode, approval review, throttling, and username blocks before allowing public traffic.

## Production Notes

- Put OmniForum behind a reverse proxy such as nginx.
- Set `OMNIFORUM_SECURE_COOKIES=1` when traffic is served over HTTPS.
- Keep the app on a private loopback/private subnet binding and let the proxy handle TLS.
- Keep `data/` on persistent storage and writable by the service user.
- Docker Compose uses a named `omniforum-data` volume mounted at `/app/data`; back up that volume the same way you would back up a host `data/` directory.
- Rotate `data/logs/server.log`, `data/logs/access.log`, and `data/logs/app.jsonl` with logrotate or the host's log management tool.
- A ready-to-copy logrotate example is available at `deploy/logrotate-omniforum.conf`.
- Keep backups off-host; local backup archives are useful but not enough if the disk is lost.
- Review the provided nginx example in `deploy/nginx-omniforum.conf`.
- Check `/robots.txt` and `/sitemap.xml` after setting `OMNIFORUM_PUBLIC_URL`.
- Forward or generate `X-Request-ID` at the proxy if you want to correlate proxy logs with OmniForum logs. OmniForum returns a request ID on every response and generates one when the header is missing.
- Set `OMNIFORUM_MEDIA_SCAN_COMMAND` when public uploads need an external scanner. The command may include `{path}` and `{storage_path}` placeholders, or OmniForum appends the uploaded file path as the final argument.
- Keep `OMNIFORUM_EMAIL_AUTH_ENABLED=0` unless SMTP is configured and tested. When disabled, email recovery UI stays hidden from normal users and email reset APIs reject use.
- If you use Discord for staff operations, set `OMNIFORUM_DISCORD_WEBHOOK_URL` so reports, appeals, contact notices, backups, and restores can fan out there.
- Built-in abuse throttles are persisted in `data/audit.db` so restarts do not clear active windows. For public sites, add proxy-level request limiting for `/api/login`, `/api/register`, `/api/contact`, and upload-heavy routes before requests reach Python.
- Copy `deploy/omniforum-offsite-backup.env.example` to `deploy/omniforum-offsite-backup.env`, set `OMNIFORUM_OFFSITE_BACKUP_TARGET`, enable backup encryption, and schedule `deploy/omniforum-offsite-backup.timer`.
- Copy `deploy/omniforum-remote-deploy.env.example` to `deploy/omniforum-remote-deploy.env` on the operator machine when you want SSH deploys with `scripts/deploy_remote.sh`; keep that env file out of source.
- Run `python3 scripts/deploy_assistant.py --open` for a localhost browser workflow that generates env files, runs checks, builds a package, and shows the deploy command.
- Run `scripts/production_readiness.py --url https://forum.example.com` before launch, then copy `deploy/omniforum-healthcheck.env.example` to `deploy/omniforum-healthcheck.env` and schedule `scripts/healthcheck.py` with `deploy/omniforum-healthcheck.timer` or an external monitor.
- Use `scripts/probe_email_auth.py --env-file .env --to admin@example.com` to test SMTP only after intentionally enabling `OMNIFORUM_EMAIL_AUTH_ENABLED=1`.
- Use `scripts/security_check.py` before handoff and `scripts/load_test.py https://forum.example.com` after the proxy is live.

## Auth, Media, And Migration Posture

- Account recovery is email-free by default. Optional email password reset is available only when `OMNIFORUM_EMAIL_AUTH_ENABLED=1` and SMTP is configured.
- Uploaded images are type-checked, geometry-checked, resized, and re-encoded when Pillow is installed. `OMNIFORUM_MEDIA_SCAN_COMMAND` can run an external scanner/quarantine command before uploads are committed; set `OMNIFORUM_MEDIA_SCAN_REQUIRED=1` to fail closed when no scanner is configured.
- Browser scripts and styles are constrained to `script-src 'self'` and `style-src 'self'`; inline event handlers are blocked by CSP and bridged through delegated actions.
- Schema management combines additive repair with an ordered checksum-recorded migration registry. Run `scripts/check_migrations.py` before deploying schema changes and `scripts/migration_status.py --data-dir data` on a running instance to inspect what has applied.
- Data retention, deletion/export handling, and incident-response notes are documented in [DATA_POLICY.md](DATA_POLICY.md).

## Deployment Smoke Checks

1. Load `/api/health` and confirm `{"ok": true}`.
2. Load `/api/home` and confirm seeded sections appear.
3. Create the owner account on a fresh instance.
4. Create a test thread, reply, and backup.
5. Open Settings -> Operations and confirm production install checks are green or intentionally acknowledged.
6. Download a backup and verify the restore guide opens for that file.
7. Run `scripts/verify_restore.sh` to restore a backup into a temporary copy and boot-check `/api/health` plus `/api/home`.
8. Run `scripts/healthcheck.py https://forum.example.com` from outside the host network.
9. Run `scripts/verify_offsite_restore.sh` against the newest off-host backup artifact.
10. If deploying by SSH, run `OMNIFORUM_DEPLOY_CONFIRM=yes scripts/deploy_remote.sh` after sourcing the local deploy env.
11. If you prefer a guided flow, run `python3 scripts/deploy_assistant.py --open` from your operator machine.

## Moderation / Support Queues

- Reports, appeals, and staff inbox notices all surface in the top-right user menu for staff.
- Report cards support saved macros, internal staff discussion notes, assignment, priority/category, SLA due dates, and escalation notes.
- Saved macros live under `Settings -> Operations -> Staff Workflows`.
- Pending signup approvals surface in Operations for admins and the owner.
- Admin operations are intentionally hidden from moderators and below.

## Account Recovery

- Users can generate one-time recovery codes from Settings.
- A recovery code can be entered on the login form instead of a password and forces an immediate password reset.
- Users can save a Discord username in Settings so admins have a verification note for recovery requests.
- Admin-issued temporary passwords expire and force a password reset on login.
- Optional email password reset remains invisible unless `OMNIFORUM_EMAIL_AUTH_ENABLED=1`.

## Testing

- Run `python3 -m unittest discover -s tests -v` from the project root.
- The smoke suite covers API auth/posting/moderation flows, SSE, plugin toggles, backups, and public discovery endpoints.
- For real browser coverage, create a virtual environment, install Playwright with `python -m pip install -r requirements-dev.txt`, install Chromium with `python -m playwright install chromium`, then run `python -m unittest discover -s tests -p 'test_browser_*.py' -v`.
- The browser suite covers login, posting, image uploads, replies, notification filters, DMs, reports, moderation actions, settings, admin operations panels, plugin controls, section management, and a mobile overflow check.
