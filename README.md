# OmniForum

OmniForum is a self-hosted forum application built on a lightweight Python backend with SQLite storage and a static HTML/CSS/JavaScript frontend.

It is designed for a single-instance deployment with persistent disk storage, role-based moderation, direct messages, real-time live updates, inline media, plugin-aware frontend extensions, and admin operations such as backups and cleanup.

## Highlights

- Real accounts with persistent sessions
- Signup abuse controls with invite-only mode, admin approval queue, registration throttles, and blocked username patterns
- Role-aware sections, posting permissions, and hidden restricted areas
- Threads, replies, quoting, reactions, likes, polls, bookmarks, follows, split/merge/move tools, staff notes, and featured/pinned/locked/solved states
- Inline image/GIF uploads in threads and replies
- Sensitive-media controls, per-user media quotas, and account-level media usage tracking
- Profile pictures, profile customization, signatures, and account settings
- Admin-editable branding, homepage copy, policy copy, support links, feature toggles, and default theme
- Full-site appearance themes with saved per-user color schemes
- Direct messages, polished unread notification filters, advanced search, and trending/related discovery
- Live `EventSource` updates for nav alerts, thread activity, and section changes
- Featured threads, status messages, and richer community spotlight cards
- Reports, appeals, staff inbox, and moderation history
- Email-free recovery with user recovery codes, Discord verification notes, expiring temporary passwords, and forced reset on login
- Admin tools for the first-run setup wizard, onboarding readiness, production install checks, backups, import/export previews, restore guidance, trash restore, logs, searchable audit events, analytics, search-term tracking, media cleanup, and plugin toggles
- Public discovery helpers such as `robots.txt`, `sitemap.xml`, and richer share metadata
- Automated Python smoke tests for API flows, admin operations, SSE, and public pages
- Optional Discord webhook notifications for reports, appeals, contact notices, backups, and restores

## Stack

- Backend: `app.py` using Python standard library HTTP tooling
- Storage: split SQLite databases under `data/`
- Frontend: static HTML pages plus shared `js/` and `css/`
- Media: uploaded avatars and post media served from `/media/...`

Pillow is the only runtime Python dependency and is used for image processing.

## Requirements

- Python `3.10+`
- Python dependencies from `requirements.txt`
- A host that supports a long-running Python process
- A persistent writable filesystem for `data/`
- A reverse proxy with HTTPS for production use

## Step-By-Step Local Setup

Follow these steps exactly if you want to run OmniForum on your own computer.

### 1. Make sure Python is installed

Open a terminal and run:

```bash
python3 --version
```

If Python is installed, you should see a version number such as `Python 3.11.x`.

If that command fails, install Python 3 first, then come back and run the command again.

### 2. Open the project folder in your terminal

Change into the OmniForum folder:

```bash
cd /path/to/forum
```

Example:

```bash
cd /Users/mizuhiki/Downloads/forum
```

Optional: copy the environment template if you want to customize the public URL, upload quotas, or Discord webhook before first run:

```bash
cp .env.example .env
```

### 3. Create a virtual environment and install dependencies

Run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

This installs Pillow, which OmniForum uses to process uploaded images, strip metadata, resize large images, and generate thumbnails.

### 4. Start the website

Run:

```bash
python app.py
```

When it starts correctly, you should see:

```text
OmniForum running at http://127.0.0.1:8000
```

### 5. Open the site in your browser

Open:

```text
http://127.0.0.1:8000
```

### 6. Create the first account

The first account created on a brand-new OmniForum install becomes the `Owner`.

That account has full control of the site.

### 7. Confirm the data folder was created

After the server starts, OmniForum creates and uses files inside `data/`, including:

- forum databases such as `users.db`, `threads.db`, and `posts.db`
- uploaded media folders
- logs and backup folders

If `data/` is writable, the site will create what it needs automatically.

If you need to return to a clean local install, stop the server and run:

```bash
OMNIFORUM_CONFIRM_RESET=yes scripts/reset_runtime_data.sh
```

This removes local SQLite databases, uploads, backups, and logs, then recreates the runtime folder structure.

### 8. Stop the server when you are done

In the terminal where OmniForum is running, press:

```text
Ctrl+C
```

By default the server binds to `127.0.0.1:8000`.

## Step-By-Step Hosting Setup

Use this if you want to run OmniForum on a VPS or traditional hosting server where you control a long-running Python process.

### 1. Copy the project to the server

Upload the full OmniForum folder to your server.

Example target path:

```text
/var/www/omniforum
```

### 2. SSH into the server

Example:

```bash
ssh your-user@your-server-ip
```

### 3. Move into the project folder

```bash
cd /var/www/omniforum
```

### 4. Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `OMNIFORUM_PUBLIC_URL`
- `OMNIFORUM_SECURE_COOKIES=1`
- `OMNIFORUM_DISCORD_WEBHOOK_URL` if you want Discord staff notifications
### 5. Confirm Python is available

```bash
python3 --version
```

If Python is not installed, install Python 3 through your server's package manager first.

### 6. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Keep using this virtual environment for direct test runs and for your production service command.

### 7. Make sure the app can write to `data/`

OmniForum must be able to write inside the project folder, especially:

- `data/`
- `data/uploads/`
- `data/logs/`
- `data/exports/`

If needed, fix ownership and permissions for the account that will run the app.

### 8. Test-run the app directly

From the project root, run:

```bash
source .venv/bin/activate
python app.py
```

If it starts, open the server locally or through your tunnel/proxy and make sure the homepage loads.

Press `Ctrl+C` to stop it after testing.

### 9. Create a systemd service so the site stays running

Create:

```text
/etc/systemd/system/omniforum.service
```

Use this example and adjust paths/usernames as needed:

```ini
[Unit]
Description=OmniForum
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/omniforum
Environment=OMNIFORUM_HOST=127.0.0.1
Environment=OMNIFORUM_PORT=8000
Environment=OMNIFORUM_SECURE_COOKIES=1
ExecStart=/var/www/omniforum/.venv/bin/python /var/www/omniforum/app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable omniforum
sudo systemctl start omniforum
sudo systemctl status omniforum
```

### 10. Put nginx in front of OmniForum

Copy the example config from:

```text
deploy/nginx-omniforum.conf
```

Place it in your nginx sites configuration, adjust the domain, then reload nginx.

Typical steps:

```bash
sudo cp deploy/nginx-omniforum.conf /etc/nginx/sites-available/omniforum
sudo nano /etc/nginx/sites-available/omniforum
sudo ln -s /etc/nginx/sites-available/omniforum /etc/nginx/sites-enabled/omniforum
sudo nginx -t
sudo systemctl reload nginx
```

### 11. Point your domain to the server

Update your DNS so your domain points to your server's IP address.

Then set that domain name in your nginx config.

### 12. Enable HTTPS

Set up SSL/TLS in nginx or your preferred reverse proxy.

When serving OmniForum over HTTPS, keep:

```text
OMNIFORUM_SECURE_COOKIES=1
```

### 13. Open the website and create the first account

Visit your domain in the browser.

If this is a fresh install, the first account created becomes the `Owner`.

### 14. Create a backup after initial setup

After logging in as admin/owner, open:

```text
Settings -> Operations -> Create Backup
```

This gives you a clean starting backup right after deployment.

## Configuration

OmniForum reads a small set of environment variables at startup:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OMNIFORUM_HOST` | `127.0.0.1` | Bind address for the Python server |
| `OMNIFORUM_PORT` | `8000` | Port for the Python server |
| `OMNIFORUM_SECURE_COOKIES` | `0` | Set to `1` behind HTTPS so session cookies use the secure flag |
| `OMNIFORUM_PUBLIC_URL` | `http://127.0.0.1:8000` | Public base URL used in staff links and Discord webhook notices |
| `OMNIFORUM_MAX_REQUEST_BYTES` | `50331648` | Max request body size in bytes |
| `OMNIFORUM_BACKUP_ROTATION` | `8` | Number of backup archives to keep |
| `OMNIFORUM_LIVE_INTERVAL_SECONDS` | `5` | SSE refresh cadence for live updates |
| `OMNIFORUM_USER_MEDIA_LIMIT_BYTES` | `67108864` | Per-account media quota in bytes |
| `OMNIFORUM_USER_MEDIA_LIMIT_FILES` | `80` | Per-account media file quota |
| `OMNIFORUM_DISCORD_WEBHOOK_URL` | empty | Optional Discord webhook for staff-facing event notifications |

Example:

```bash
OMNIFORUM_HOST=127.0.0.1 \
OMNIFORUM_PORT=8000 \
OMNIFORUM_SECURE_COOKIES=1 \
python app.py
```

## Data Layout

Runtime data is stored under `data/`:

- `users.db`: accounts, roles, recovery state/codes, site settings, registration controls, invite codes, preferences, saved site theme, and avatars
- `sessions.db`: login sessions, CSRF tokens, and session audit metadata
- `sections.db`: categories and sections
- `threads.db`: threads, poll data, bookmarks, follows
- `posts.db`: replies, likes, reactions, media, edit history
- `messages.db`: direct messages
- `notifications.db`: alerts and unread notifications
- `reports.db`: reports, appeals, report internal notes, and saved moderation macros
- `audit.db`: searchable admin audit trail plus lightweight search analytics for moderation, signup, content, section, plugin, and operations actions
- `contact.db`: contact form submissions and staff inbox state
- `uploads/avatars/`: profile pictures
- `uploads/posts/`: thread/reply images and GIFs
- `uploads/thumbs/`: generated thumbnails for inline post media
- `exports/backups/`: admin-created backups
- `logs/server.log`: lightweight request and operations log

Only uploaded media and exported backups are meant to be web-served. The rest of `data/` is private application storage.

## Source And Runtime Hygiene

Keep source files and private runtime state separate:

- Commit `data/README.md` and `.gitkeep` placeholders only.
- Do not commit `data/*.db`, `data/logs/*`, `data/uploads/*`, or `data/exports/*`.
- Use `scripts/reset_runtime_data.sh` to clear a local development instance before making a clean source package.
- Use `scripts/package_release.sh` to create a clean source archive that excludes runtime data.
- Use `scripts/seed_demo.py` against a clean local server to create screenshot/QA/demo content without private data.
- Use `scripts/backup_omniforum.sh` or the admin Operations backup before deleting runtime data you may need again.
- Use `scripts/scrub_private_data.sh` when preparing a source handoff from a dirty local workspace.
- Mount `data/` as persistent storage in Docker, systemd, or VPS deployments.

Privacy posture:

- Treat everything under `data/` except placeholders and `data/README.md` as private.
- Before publishing a copy of the source, run `scripts/package_release.sh` or reset local runtime data.
- If private runtime data was ever shared, rotate sessions by clearing `data/sessions.db`, issue new passwords or recovery codes as needed, and replace any exposed webhook URLs in `.env`.

## Hosting Notes

OmniForum is best suited to:

- a VPS
- a dedicated server
- a container host with a persistent mounted volume
- a private internal app behind nginx or Caddy

It is not a good fit for:

- serverless platforms
- ephemeral filesystems
- multi-instance horizontal scaling without redesigning storage

Important production expectations:

- Keep OmniForum as a single writable app instance
- Put it behind a reverse proxy that handles HTTPS
- Keep `data/` on persistent disk
- Make off-host backups regularly
- Increase proxy upload limits if you allow image/GIF uploads

An example nginx config is included at `deploy/nginx-omniforum.conf`.

## Recommended Production Setup

1. Copy the project to the server.
2. Ensure the project directory and `data/` are writable by the app user.
3. Start OmniForum with Python and keep it running under a process manager such as `systemd`, `supervisord`, or another long-lived service manager.
4. Put nginx or another reverse proxy in front of it.
5. Set `OMNIFORUM_SECURE_COOKIES=1` when serving over HTTPS.
6. Point the proxy at the local OmniForum process and allow `/`, `/media/`, and `/exports/`.
7. Verify the homepage or `/api/health` after deployment.
8. Check `/robots.txt` and `/sitemap.xml` once your public URL is set.

## Production Checklist

- Copy `.env.example` to `.env` and set `OMNIFORUM_PUBLIC_URL` to the real HTTPS origin.
- Set `OMNIFORUM_SECURE_COOKIES=1` behind HTTPS.
- Keep `OMNIFORUM_HOST=127.0.0.1` unless the app is inside a private container network.
- Make `data/`, `data/uploads/`, `data/exports/`, and `data/logs/` writable by the service user.
- Keep `data/` on persistent disk and back it up off-host.
- Configure nginx or another proxy with an upload limit at least as large as `OMNIFORUM_MAX_REQUEST_BYTES`.
- Rotate `data/logs/server.log`, `data/logs/access.log`, and `data/logs/app.jsonl` with the platform log rotation tool. A sample config is included at `deploy/logrotate-omniforum.conf`.
- OmniForum stores persistent rate-limit events in `data/audit.db` so active abuse windows survive process restarts. Proxy-level request limiting for `/api/login`, `/api/register`, `/api/contact`, and upload-heavy routes is still recommended as an outer layer.
- Create the first owner account, configure signup controls, and make an initial backup from Settings -> Operations.

Example logrotate config:

```text
/var/www/omniforum/data/logs/server.log
/var/www/omniforum/data/logs/access.log
/var/www/omniforum/data/logs/app.jsonl {
    weekly
    rotate 8
    compress
    missingok
    notifempty
    copytruncate
    create 0640 www-data www-data
}
```

## Testing

Run the backend/API smoke suite:

```bash
python3 -m unittest discover -s tests -v
```

Run the browser smoke suite:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest tests.test_browser_smoke -v
```

Verify backup restore into a temporary copy:

```bash
scripts/verify_restore.sh
```

## Security And Growth Notes

- Account recovery is email-free by default. For larger public communities, consider adding optional SMTP, magic-link login, or OAuth before opening registration broadly.
- Uploaded media is type-checked and reprocessed with Pillow, but OmniForum does not currently run malware scanning. High-trust deployments should place uploads behind a scanning/quarantine hook or restrict uploads to trusted roles.
- Schema upgrades are handled with additive table/column checks. For multi-version production upgrades, move toward explicit schema versions and migration records.

## Features

### Forum and Community

- Category/section forum layout
- Threads and replies
- Post quoting
- Rich post formatting with markdown-style and BBCode-style content
- Image/GIF uploads in new threads and replies
- Server-side media processing with resize/compression, metadata stripping, and generated thumbnails
- Polls inside threads
- Saved threads and thread follows
- Related threads and trending threads
- Featured threads and community spotlight surfaces
- Search across content
- Optional SQLite FTS5-backed search index with LIKE fallback

### Accounts and Profiles

- Registration and login
- Invite-only registration, admin approval review, throttling, and blocked username patterns
- Persistent cookie sessions
- Profile pictures
- Signatures
- Profile badge and accent customization
- Saved site theme preference in Settings
- Password change and temporary-password reset flow
- One-time recovery codes for email-free account recovery
- Optional recovery Discord username for admin verification notes
- Session review and sign-out-other-sessions tools
- DM privacy and notification preferences
- Draft recovery for locally saved thread and reply drafts
- Account data export from Settings
- Ignored-content and blocked-DM member controls
- Sensitive-media, compact-layout, and ignored-content presentation toggles

### Appearance and Personalization

- Full-site theme switching from Settings
- 15 preset color schemes built into the forum
- Live theme preview before saving
- Theme preference saved per account and re-applied after login/refresh
- Admin branding editor for site name, logo text/mark, hero copy, footer links, SEO defaults, policy intros, upload policy, feature toggles, and default theme

### Messaging and Alerts

- Direct messages
- Unread counts
- Filtered notifications for replies, likes, mentions, DMs, reports, appeals, contact notices, signups, and staff actions
- Live updates over Server-Sent Events for alerts, section activity, and thread replies

### Moderation and Staff Tools

- Reports queue
- Appeals queue
- Staff inbox for contact form submissions
- Saved moderation macros for consistent report triage notes
- Report internal discussion notes, private staff assignments, SLA labels, and escalation tracking
- Warnings, notes, XP adjustments, timeouts, bans, mutes, and shadow mutes
- Role changes with audit history
- Thread moderation, lock/pin/feature/solve controls, split/merge/move tools, staff-only thread notes, and section permissions
- Moderation analytics in Operations
- Trash/recovery view for soft-deleted threads and replies
- Optional Discord webhook notifications for new staff-facing events

### Admin Operations

- Signup Controls for public/open, invite-only, closed, and approval-queue registration modes
- First-run setup wizard for site name, branding, policy copy, registration mode, section layout, theme default, and first backup
- Admin import/export tools for users, threads, posts, reports, moderation logs, and settings as JSON/CSV with no-write import previews
- Backup archive creation
- Downloadable backup inventory in Operations
- Guided restore checklist and copyable restore command in Operations
- Production health dashboard with database size, media usage, backup status, latest errors, queue counts, plugin status, onboarding checklist, production install checks, analytics, and recovery readiness
- Searchable Audit Log in Operations for moderation, signup, content, section, plugin, and operations actions
- Runtime logs view
- Orphaned media cleanup
- Section management
- Plugin enable/disable controls with manifest-declared asset loading rules
- Recovery/restore controls for soft-deleted content

## Roles

- `Owner`: first registered account, full control
- `Admin`: full site administration and operations access
- `Mod`: moderation tools, staff inbox, report/appeal handling
- `Veteran`, `Member`, `New`: community roles used for section read/write permissioning

Sections can be hidden entirely from users who do not meet the section read role.

## Recovery and Contact

- There is no email stack in the current build
- Admins and the owner can issue a temporary password for account recovery
- Temporary passwords expire, force the user to reset their password after login, and create an audit trail
- Users can generate one-time recovery codes from Settings and use them from the login form if they forget their password
- Users can save a Discord username in Settings for admin verification notes
- The contact form supports an optional Discord username so staff have an off-site handle to reference

## Backups and Restore

Admins can create backups from `Settings -> Operations -> Create Backup`.

Each backup archive includes:

- all runtime SQLite databases
- uploaded media
- the request/operations log when present

Guided restore flow:

1. Stop the server.
2. Open `Settings -> Operations` and use `Restore Guide` on the archive you want.
3. Run `scripts/restore_omniforum.sh /absolute/path/to/archive.zip /absolute/path/to/project`.
4. Start OmniForum again.
5. Verify the homepage, `/api/health`, and an admin login.

## Operations and Maintenance

- Runtime logs: `data/logs/server.log`, `data/logs/access.log`, and `data/logs/app.jsonl`
- First-run setup wizard: `Settings -> Operations -> Setup Wizard`
- Import/export and preview tools: `Settings -> Operations -> Import / Export`
- Staff workflow macros: `Settings -> Operations -> Staff Workflows`
- Media cleanup: `Settings -> Operations -> Media Cleanup`
- Backups: `data/exports/backups/`
- Private uploads: `data/uploads/`
- Restore script: `scripts/restore_omniforum.sh`
- Production health dashboard: `Settings -> Operations`

For more detailed operational notes, see `docs/OPERATIONS.md`.

## Tests

Run the backend smoke suite from the project root:

```bash
python3 -m unittest discover -s tests -v
```

Run the browser smoke suite with Playwright:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest tests.test_browser_smoke -v
```

Current coverage includes:

- registration, login, profile/settings update, posting, moderation, backups, and restore-guide APIs
- plugin enable/disable behavior and safe asset serving
- one-shot SSE stream verification
- public page availability plus `robots.txt` and `sitemap.xml`
- browser automation for login, posting, uploads, replies, DMs, reports, moderation, settings, admin operations, plugin controls, section management, and mobile overflow checks

## Project Layout

```text
app.py                  Python server and API
index.html              Forum homepage
pages/                  Secondary site pages
js/                     Frontend application logic
css/                    Shared styles
data/                   Runtime databases, uploads, backups, logs
deploy/                 Deployment examples
docs/                   Extra operational notes
scripts/                Helper maintenance scripts
```

## Important Notes

- OmniForum currently uses SQLite and local file storage, so treat it as a single-node app
- Backups should be copied off the server if the forum matters to you
- Production should always run behind HTTPS
- Only `/media/...` and `/exports/...` should be exposed through the app
- The rest of `data/` should never be served directly
- Example deployment files are included: `.env.example`, `Dockerfile`, `docker-compose.yml`, `deploy/omniforum.service`, `deploy/nginx-omniforum.conf`, and `scripts/backup_omniforum.sh`
