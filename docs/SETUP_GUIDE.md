# OmniForum Setup And Launch Guide

Start here if you are setting up OmniForum from scratch. This guide follows the order most people will actually use: prepare the source, fill out `.env`, test locally, rehearse on staging, then launch behind HTTPS.

## The Short Version

OmniForum runs as one writable Python process. SQLite databases, uploads, logs, and backups live under `data/`. In production, put it behind HTTPS and keep `data/` on persistent private storage.

## Setup Paths

Pick the path that matches what you are doing right now:

| Path | Use When | Main Docs |
| --- | --- | --- |
| Local development | You want to try or customize the forum on your machine | [LOCAL_SETUP.md](LOCAL_SETUP.md), [ENVIRONMENT.md](ENVIRONMENT.md) |
| Staging rehearsal | You want a disposable production-like test before launch | [STAGING_DEPLOY.md](STAGING_DEPLOY.md), [TESTING.md](TESTING.md) |
| Production launch | You are putting the site behind a real domain and HTTPS | [DEPLOYMENT.md](DEPLOYMENT.md), [OPERATIONS.md](OPERATIONS.md), [DATA_POLICY.md](DATA_POLICY.md) |
| Requirements/resources lookup | You need to know what a file is for | [RESOURCES.md](RESOURCES.md) |

## Before You Start

You need:

- Python `3.10+`
- A writable persistent `data/` directory
- A domain name for production
- A reverse proxy such as nginx or Caddy for HTTPS
- A backup location outside the app server
- Optional: Docker Compose, SMTP, Discord webhook, upload scanner

The one rule to keep in mind:

- Keep `.env`, databases, sessions, logs, uploaded media, backups, and monitor/offsite env files private.
- Use clean packages when you share the source or hand it to a server.

## 1. Prepare The Source

From the project root, install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the release gate before deploying changes:

```bash
scripts/release_check.sh
```

Create a clean source package:

```bash
scripts/package_release.sh "$PWD" /tmp/omniforum-release
scripts/check_release_archive.py /tmp/omniforum-release/omniforum-source-*.tar.gz
```

That archive leaves out `.env`, databases, logs, uploads, backups, and caches.

## 2. Create `.env`

Create the runtime config:

```bash
cp .env.example .env
chmod 600 .env
```

For local development:

```bash
OMNIFORUM_PUBLIC_URL=http://127.0.0.1:8000
OMNIFORUM_SECURE_COOKIES=0
OMNIFORUM_EMAIL_AUTH_ENABLED=0
```

For production behind HTTPS:

```bash
OMNIFORUM_PUBLIC_URL=https://forum.example.com
OMNIFORUM_SECURE_COOKIES=1
OMNIFORUM_EMAIL_AUTH_ENABLED=0
```

Leave email account features disabled until SMTP is configured and tested. See [ENVIRONMENT.md](ENVIRONMENT.md) for every variable and optional integrations.

## 3. Run Locally First

Start the app:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

On a fresh runtime, the first registered account becomes the `Owner`.

Local smoke checklist:

- Home page loads.
- First account can register and log in.
- A thread can be created.
- An image upload works if Pillow is installed.
- `Settings -> Operations` opens for the owner.
- `/api/health` returns healthy JSON.

## 4. Deploy To Staging

Use staging as a dress rehearsal before production. It should be close enough to production to catch proxy, cookie, upload, backup, and mobile issues.

Minimum staging setup:

- One writable OmniForum process
- Persistent `data/`
- HTTPS through nginx or Caddy
- Log rotation
- Healthcheck
- Backup and restore rehearsal

Run staging smoke only against a disposable staging instance:

```bash
OMNIFORUM_STAGING_CONFIRM=yes scripts/staging_smoke.py https://staging.example.com
```

Then run:

```bash
scripts/production_readiness.py --url https://staging.example.com
scripts/security_check.py
scripts/healthcheck.py https://staging.example.com
scripts/load_test.py https://staging.example.com --requests 80 --concurrency 8
```

See [STAGING_DEPLOY.md](STAGING_DEPLOY.md) for the full rehearsal checklist.

## 5. Deploy To Production

A solid production install looks like this:

- Copy the clean package to `/var/www/omniforum`.
- Keep `data/` persistent and writable by the service user.
- Run the Python process under systemd or Docker Compose.
- Put nginx or Caddy in front of it.
- Terminate HTTPS at the proxy.
- Set `OMNIFORUM_PUBLIC_URL` and `OMNIFORUM_SECURE_COOKIES=1`.
- Keep `.env` and monitor/offsite env files private.

For systemd:

```bash
sudo cp deploy/omniforum.service /etc/systemd/system/omniforum.service
sudo systemctl daemon-reload
sudo systemctl enable omniforum
sudo systemctl start omniforum
sudo systemctl status omniforum
```

For nginx:

```bash
sudo cp deploy/nginx-omniforum.conf /etc/nginx/sites-available/omniforum
sudo nano /etc/nginx/sites-available/omniforum
sudo ln -s /etc/nginx/sites-available/omniforum /etc/nginx/sites-enabled/omniforum
sudo nginx -t
sudo systemctl reload nginx
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full production deploy guide.

## 6. Complete First-Run Admin Setup

After production boots:

1. Visit the public HTTPS URL.
2. Create the first account; it becomes `Owner`.
3. Open `Settings -> Operations`.
4. Run the setup wizard.
5. Configure site name, branding, policy copy, support links, sections, default theme, and signup controls.
6. Create the first backup.
7. Save recovery codes for the owner account.

Recommended signup settings for launch:

- Start with invite-only or approval-required registration.
- Add blocked username patterns for staff/system names.
- Keep persistent throttles enabled.
- Open public registration only after moderation and backups are verified.

## 7. Configure Backups And Monitoring

Local backups are useful, but production needs off-host backups.

Create offsite backup config:

```bash
cp deploy/omniforum-offsite-backup.env.example deploy/omniforum-offsite-backup.env
chmod 600 deploy/omniforum-offsite-backup.env
```

Install or adapt:

- `deploy/omniforum-offsite-backup.service`
- `deploy/omniforum-offsite-backup.timer`
- `deploy/omniforum-healthcheck.service`
- `deploy/omniforum-healthcheck.timer`
- `deploy/logrotate-omniforum.conf`

Verify restore:

```bash
scripts/verify_restore.sh
scripts/verify_offsite_restore.sh /path/to/offsite-backup.tar.gz.enc /var/www/omniforum
```

See [OPERATIONS.md](OPERATIONS.md) and [DATA_POLICY.md](DATA_POLICY.md) for day-to-day operations, retention, and privacy notes.

## 8. Final Launch Verification

Run these from outside the app process:

```bash
scripts/production_readiness.py --url https://forum.example.com
scripts/security_check.py
scripts/healthcheck.py https://forum.example.com
```

Manual launch checklist:

- Home page loads over HTTPS.
- `/api/health`, `/api/home`, `/robots.txt`, and `/sitemap.xml` load.
- Owner login works.
- Normal member registration works according to signup settings.
- Posting, replies, image upload, DMs, reports, and moderation work.
- `Settings -> Operations` shows expected health, backup, log, plugin, and migration state.
- Backup restore has been tested.
- Mobile widths around 390px and 768px are usable.
- `.env`, databases, uploads, logs, and backups are not in source packages.

## 9. Optional Features

Enable only when ready:

- SMTP/email reset: set `OMNIFORUM_EMAIL_AUTH_ENABLED=1` only after running `scripts/probe_email_auth.py`.
- Upload scanner: set `OMNIFORUM_MEDIA_SCAN_COMMAND` and then `OMNIFORUM_MEDIA_SCAN_REQUIRED=1` only after scanner testing.
- Discord notifications: set `OMNIFORUM_DISCORD_WEBHOOK_URL`.
- SSH deploy helper: create `deploy/omniforum-remote-deploy.env` from its example and run `scripts/deploy_remote.sh`.

## Troubleshooting Map

| Problem | Start Here |
| --- | --- |
| App does not boot | [LOCAL_SETUP.md](LOCAL_SETUP.md), [ENVIRONMENT.md](ENVIRONMENT.md) |
| HTTPS/cookies are wrong | [ENVIRONMENT.md](ENVIRONMENT.md), [DEPLOYMENT.md](DEPLOYMENT.md) |
| Browser tests or release gate fail | [TESTING.md](TESTING.md) |
| Backups or restores are unclear | [DEPLOYMENT.md](DEPLOYMENT.md), [OPERATIONS.md](OPERATIONS.md) |
| Runtime/private files may be exposed | [DATA_POLICY.md](DATA_POLICY.md), [ARCHITECTURE.md](ARCHITECTURE.md) |
| Need feature inventory or roles | [FEATURES.md](FEATURES.md) |
