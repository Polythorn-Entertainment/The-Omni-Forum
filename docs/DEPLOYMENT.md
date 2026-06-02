# OmniForum Deployment Guide

This is the production path for a VPS, dedicated server, or container host where you control one long-running OmniForum process and persistent disk storage.

## Production Layout

A normal install looks like this:

- One writable OmniForum instance
- nginx, Caddy, or another reverse proxy in front of it
- HTTPS terminated at the proxy
- `data/` on persistent private storage
- `.env`, monitor env files, databases, logs, uploads, and backups kept out of source packages
- Backups copied off the server

## Step-By-Step Hosting Setup

1. Copy the project to the server, usually:

```text
/var/www/omniforum
```

2. SSH into the server:

```bash
ssh your-user@your-server-ip
```

3. Move into the project folder:

```bash
cd /var/www/omniforum
```

4. Create your environment file:

```bash
cp .env.example .env
```

Use [ENVIRONMENT.md](ENVIRONMENT.md) for a full fill-out guide.

Set at least:

- `OMNIFORUM_PUBLIC_URL=https://forum.example.com`
- `OMNIFORUM_SECURE_COOKIES=1`
- `OMNIFORUM_DISCORD_WEBHOOK_URL` if you want Discord staff notifications

Keep `OMNIFORUM_EMAIL_AUTH_ENABLED=0` unless SMTP is configured and tested. When disabled, email fields and reset links are hidden from normal users and email reset APIs reject use.

5. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

6. Ensure the app can write runtime storage:

```bash
sudo chown -R www-data:www-data /var/www/omniforum/data
```

The service user needs write access to `data/`, `data/uploads/`, `data/logs/`, and `data/exports/`.

7. Test-run the app directly:

```bash
source .venv/bin/activate
python app.py
```

Press `Ctrl+C` after confirming the app boots.

## Systemd

An example service is included at `deploy/omniforum.service`.

Typical install:

```bash
sudo cp deploy/omniforum.service /etc/systemd/system/omniforum.service
sudo systemctl daemon-reload
sudo systemctl enable omniforum
sudo systemctl start omniforum
sudo systemctl status omniforum
```

## Reverse Proxy

Use one of the included examples:

- `deploy/nginx-omniforum.conf`
- `deploy/caddy-omniforum.conf`

For nginx:

```bash
sudo cp deploy/nginx-omniforum.conf /etc/nginx/sites-available/omniforum
sudo nano /etc/nginx/sites-available/omniforum
sudo ln -s /etc/nginx/sites-available/omniforum /etc/nginx/sites-enabled/omniforum
sudo nginx -t
sudo systemctl reload nginx
```

The proxy should:

- Terminate TLS.
- Forward to the Python app on `127.0.0.1:8000`.
- Set upload limits at least as high as `OMNIFORUM_MAX_REQUEST_BYTES`.
- Forward or generate `X-Request-ID` for log correlation.

## Launch Checklist

- Point DNS at the server.
- Enable HTTPS.
- Set `OMNIFORUM_PUBLIC_URL` to the real HTTPS origin.
- Set `OMNIFORUM_SECURE_COOKIES=1`.
- Keep `OMNIFORUM_HOST=127.0.0.1` unless the app runs inside a private container network.
- Confirm `data/` is persistent and writable.
- Configure log rotation with `deploy/logrotate-omniforum.conf`.
- Configure off-host backups with `deploy/omniforum-offsite-backup.env.example`.
- Configure health monitoring with `deploy/omniforum-healthcheck.env.example`.
- Configure `OMNIFORUM_MEDIA_SCAN_COMMAND` if public uploads need external malware/quarantine scanning.
- Create the first owner account.
- Configure signup controls.
- Create an initial backup from `Settings -> Operations`.

## Operator Commands

Run readiness:

```bash
scripts/production_readiness.py --url https://forum.example.com
scripts/security_check.py
scripts/healthcheck.py https://forum.example.com
```

Run load probe after the proxy is live:

```bash
scripts/load_test.py https://forum.example.com --requests 80 --concurrency 8
```

Check migrations:

```bash
scripts/migration_status.py --data-dir data
```

## SSH Clean Deploy

Copy the example deploy env:

```bash
cp deploy/omniforum-remote-deploy.env.example deploy/omniforum-remote-deploy.env
```

Edit the host/user/path values, then run:

```bash
set -a
. deploy/omniforum-remote-deploy.env
set +a
OMNIFORUM_DEPLOY_CONFIRM=yes scripts/deploy_remote.sh
```

The deploy script uploads a clean package, preserves remote `.env` and `data/`, restarts systemd, and runs public readiness checks when `OMNIFORUM_DEPLOY_PUBLIC_URL` is set.

## Backups And Restore

Admins can create backups from:

```text
Settings -> Operations -> Create Backup
```

Each backup archive includes runtime SQLite databases, uploaded media, and logs when present.

Verify a local restore:

```bash
scripts/verify_restore.sh
```

Run offsite backup and restore rehearsal:

```bash
OMNIFORUM_OFFSITE_BACKUP_TARGET=local:/srv/omniforum-offsite \
OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD_FILE=/root/omniforum-backup-pass \
scripts/offsite_backup.sh /var/www/omniforum

OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD_FILE=/root/omniforum-backup-pass \
scripts/verify_offsite_restore.sh /srv/omniforum-offsite/omniforum-manual-YYYYMMDD-HHMMSS.tar.gz.enc /var/www/omniforum
```

Manual restore flow:

1. Stop OmniForum.
2. Open `Settings -> Operations` and use `Restore Guide` on the archive you want.
3. Run `scripts/restore_omniforum.sh /absolute/path/to/archive.zip /absolute/path/to/project`.
4. Start OmniForum again.
5. Verify the homepage, `/api/health`, and an admin login.

## Configuration Reference

| Variable | Default | Purpose |
| --- | --- | --- |
| `OMNIFORUM_HOST` | `127.0.0.1` | Bind address for the Python server |
| `OMNIFORUM_PORT` | `8000` | Port for the Python server |
| `OMNIFORUM_SECURE_COOKIES` | `0` | Set to `1` behind HTTPS so session cookies use the secure flag |
| `OMNIFORUM_PUBLIC_URL` | `http://127.0.0.1:8000` | Public base URL used in staff links and Discord webhook notices |
| `OMNIFORUM_MAX_REQUEST_BYTES` | `50331648` | Max request body size in bytes |
| `OMNIFORUM_BACKUP_ROTATION` | `8` | Number of backup archives to keep |
| `OMNIFORUM_BACKUP_STALE_HOURS` | `168` | Age before the dashboard marks latest backup stale |
| `OMNIFORUM_LIVE_INTERVAL_SECONDS` | `5` | SSE refresh cadence for live updates |
| `OMNIFORUM_USER_MEDIA_LIMIT_BYTES` | `67108864` | Per-account media quota in bytes |
| `OMNIFORUM_USER_MEDIA_LIMIT_FILES` | `80` | Per-account media file quota |
| `OMNIFORUM_MEDIA_SCAN_COMMAND` | empty | Optional upload scanner command; supports `{path}` and `{storage_path}` placeholders |
| `OMNIFORUM_MEDIA_SCAN_REQUIRED` | `0` | Set to `1` to reject uploads when no scanner is configured |
| `OMNIFORUM_MEDIA_SCAN_TIMEOUT_SECONDS` | `20` | Max seconds to wait for the upload scanner |
| `OMNIFORUM_EMAIL_AUTH_ENABLED` | `0` | Enables user-visible email account features only when set to `1` |
| `OMNIFORUM_EMAIL_FROM` | empty | Sender address for optional email password reset |
| `OMNIFORUM_SMTP_HOST` | empty | SMTP host for optional email account features |
| `OMNIFORUM_SMTP_PORT` | `587` | SMTP port |
| `OMNIFORUM_SMTP_USERNAME` | empty | SMTP username |
| `OMNIFORUM_SMTP_PASSWORD` | empty | SMTP password |
| `OMNIFORUM_SMTP_STARTTLS` | `1` | Set to `0` to skip SMTP STARTTLS |
| `OMNIFORUM_DISCORD_WEBHOOK_URL` | empty | Optional Discord webhook for staff-facing event notifications |

## Staging

Use [STAGING_DEPLOY.md](STAGING_DEPLOY.md) for a disposable launch rehearsal before pointing real users at the forum.
