OmniForum Operations

Running locally

- Create a virtual environment with `python3 -m venv .venv`, activate it, and install dependencies with `python -m pip install -r requirements.txt`.
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
  - `OMNIFORUM_DISCORD_WEBHOOK_URL`
  - `OMNIFORUM_SECURE_COOKIES=1`

Data layout

- SQLite files live under `data/`.
- Uploaded media lives under `data/uploads/`.
- Pillow processes uploads when installed from `requirements.txt`: large images are resized, metadata is stripped during re-encoding, and post images receive generated thumbnails under `data/uploads/thumbs/`.
- Searchable admin audit events are stored in `data/audit.db`.
- Site configuration, branding, recovery codes, and signup controls are stored in `data/users.db`.
- Report internal notes, SLA/escalation state, and saved moderation macros are stored in `data/reports.db`.
- Admin-created backup archives are written to `data/exports/backups/`.
- Runtime request logs are appended to `data/logs/server.log`.

Backups

- Open Settings as an admin or owner and use `Operations` -> `Create Backup`.
- The server generates a zip archive containing:
  - all `data/*.db` files
  - `data/logs/server.log` if present
  - uploaded avatars and post media
- Backup rotation keeps the newest archives and removes older ones based on `OMNIFORUM_BACKUP_ROTATION`.
- The Operations dashboard marks the latest archive as stale after `OMNIFORUM_BACKUP_STALE_HOURS` hours. The default is 168 hours.

Production health dashboard

- Admins and the owner can open `Settings -> Operations` to view the production health snapshot.
- The dashboard shows total SQLite database size, individual database file sizes, media usage by upload bucket, orphaned media counts, backup status, recent failed requests/runtime errors, queue counts, plugin status, onboarding readiness, production install checks, forum analytics, and recovery readiness.
- Recovery readiness validates the latest backup archive, confirms the restore script exists and is executable, and shows the last logged backup and restore-guide check.
- The dashboard is read-only except for the explicit actions: setup wizard, import/export tools, staff workflow tools, create backup, cleanup orphan media, signup controls, plugin manager, trash restore, and backup restore guide.

First-run setup and site settings

- Admins and the owner can open `Settings -> Operations -> Setup Wizard`.
- The wizard saves site name, logo text/mark, hero copy, footer links, policy intros, support links, SEO defaults, upload policy, feature toggles, and default theme into the persistent site settings table.
- Use the same wizard to jump to signup controls, section management, and first backup creation during launch setup.

Import/export tools

- Admins and the owner can open `Settings -> Operations -> Import / Export`.
- JSON and CSV exports are available for users, threads, posts, reports, moderation logs, and settings.
- Import preview accepts JSON exports and reports detected counts without writing live data. Treat it as a restore-planning tool, not a live importer.

Audit log

- Admins and the owner can open `Settings -> Operations -> Audit Log`.
- Audit events are searchable and filterable by category, actor, target type, exact action, date range, and text query.
- Events are written for user moderation, report/appeal/contact triage, section changes, plugin toggles, backup and restore-guide activity, media cleanup, signup settings, invite codes, registration approvals, staff content actions, thread splits, and staff thread notes.
- Events are also written for site setting changes, admin exports, import previews, moderation macros, report internal notes, recovery-code regeneration, and recovery-code login.
- Raw request logs stay in `data/logs/server.log`; the audit log is the structured history stored in `data/audit.db`.

Restore process

1. Stop the OmniForum server.
2. In `Settings -> Operations`, open `Restore Guide` for the archive you want and confirm the checklist.
3. Run `scripts/restore_omniforum.sh /absolute/path/to/archive.zip /absolute/path/to/project`.
4. Start the server again with `python app.py`.
5. Load `/api/health`, `/api/home`, or the homepage to confirm the restored instance boots normally.

Soft-delete recovery

- Admins can also restore soft-deleted threads and replies from `Settings -> Operations`.
- Restore a deleted thread before restoring individual replies that belong to it.
- The recovery panel is meant for recent moderation mistakes; full-instance rollback should still use backup restore.

Plugins

- Installed plugins live under `plugins/<plugin-name>/`.
- Each plugin needs a `plugin.json` manifest.
- Only enabled plugins are served to clients.
- Only manifest-declared `client.styles`, `client.scripts`, and `client.assets` files are publicly served.
- Admins can toggle plugin state from `Settings -> Operations -> Manage Plugins`.

Media cleanup

- Admins can run orphaned media cleanup from `Operations`.
- This removes files in `data/uploads/` that are no longer referenced by post media, generated thumbnails, or user avatars.
- It also clears orphaned post-media metadata and stale avatar references before sweeping files.
- Run a backup before cleanup if you want an easy rollback point.

Signup controls

- Admins and the owner can open `Settings -> Operations -> Signup Controls`.
- Public registration can be left open, closed, switched to invite-only mode, or combined with admin approval.
- Approval-required accounts are created in a pending state and cannot log in until an admin approves them.
- Invite codes can be created, copied, disabled, limited by use count, and optionally expired after a number of days.
- Blocked username patterns are one per line. Wildcards such as `admin*` are supported, and plain words block usernames containing that word.
- Registration throttling is enforced in memory per client IP to slow repeated signup attempts.
- Captcha support is not wired in yet; use invite-only mode, approval review, throttling, and username blocks before allowing public traffic.

Production notes

- Put OmniForum behind a reverse proxy such as nginx.
- Set `OMNIFORUM_SECURE_COOKIES=1` when traffic is served over HTTPS.
- Keep the app on a private loopback/private subnet binding and let the proxy handle TLS.
- Review the provided nginx example in `deploy/nginx-omniforum.conf`.
- Check `/robots.txt` and `/sitemap.xml` after setting `OMNIFORUM_PUBLIC_URL`.
- If you use Discord for staff operations, set `OMNIFORUM_DISCORD_WEBHOOK_URL` so reports, appeals, contact notices, backups, and restores can fan out there.

Moderation / support queues

- Reports, appeals, and staff inbox notices all surface in the top-right user menu for staff.
- Report cards support saved macros, internal staff discussion notes, assignment, priority/category, SLA due dates, and escalation notes.
- Saved macros live under `Settings -> Operations -> Staff Workflows`.
- Pending signup approvals surface in Operations for admins and the owner.
- Admin operations are intentionally hidden from moderators and below.

Email-free account recovery

- Users can generate one-time recovery codes from Settings.
- A recovery code can be entered on the login form instead of a password and forces an immediate password reset.
- Users can save a Discord username in Settings so admins have a verification note for recovery requests.
- Admin-issued temporary passwords expire and force a password reset on login.

Testing

- Run `python3 -m unittest discover -s tests -v` from the project root.
- The smoke suite covers API auth/posting/moderation flows, SSE, plugin toggles, backups, and public discovery endpoints.
- For real browser coverage, create a virtual environment, install Playwright with `python -m pip install -r requirements-dev.txt`, install Chromium with `python -m playwright install chromium`, then run `python -m unittest tests.test_browser_smoke -v`.
- The browser suite covers login, posting, image uploads, replies, notification filters, DMs, reports, moderation actions, settings, admin operations panels, plugin controls, section management, and a mobile overflow check.
