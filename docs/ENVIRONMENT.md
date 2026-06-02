# OmniForum Environment Setup

This page explains what to put in `.env` and which settings should stay off until you are ready for them.

## What `.env` Is

- `.env` contains runtime configuration for the machine that runs OmniForum.
- `.env` may contain secrets such as SMTP passwords and webhook URLs.
- `.env` is ignored by Git, Docker image builds, and clean release packages.
- Keep `.env` on the server or local machine only.

## Create The File

From the project root:

```bash
cp .env.example .env
chmod 600 .env
```

You can also use the Deployment Assistant:

```bash
python3 scripts/deploy_assistant.py --open
```

Then open:

```text
http://127.0.0.1:8787
```

The assistant can write `.env` for you after you fill in the form.

## Local Development Values

Use these for running on your own machine:

```bash
OMNIFORUM_HOST=127.0.0.1
OMNIFORUM_PORT=8000
OMNIFORUM_PUBLIC_URL=http://127.0.0.1:8000
OMNIFORUM_SECURE_COOKIES=0
```

Start the app:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

## Production Values

Use these behind nginx, Caddy, or another HTTPS reverse proxy:

```bash
OMNIFORUM_HOST=127.0.0.1
OMNIFORUM_PORT=8000
OMNIFORUM_PUBLIC_URL=https://forum.example.com
OMNIFORUM_SECURE_COOKIES=1
```

Replace `https://forum.example.com` with the real public origin.

Keep `OMNIFORUM_HOST=127.0.0.1` unless the app runs inside a private container network. Let the proxy handle HTTPS and public traffic.

## Required Core Settings

| Variable | Local example | Production example | Notes |
| --- | --- | --- | --- |
| `OMNIFORUM_HOST` | `127.0.0.1` | `127.0.0.1` | Bind address for the Python process |
| `OMNIFORUM_PORT` | `8000` | `8000` | Port for the Python process |
| `OMNIFORUM_PUBLIC_URL` | `http://127.0.0.1:8000` | `https://forum.example.com` | Public base URL for links, metadata, and notices |
| `OMNIFORUM_SECURE_COOKIES` | `0` | `1` | Must be `1` when served over HTTPS |

## Runtime Limits

These defaults are fine for most first installs:

```bash
OMNIFORUM_MAX_REQUEST_BYTES=50331648
OMNIFORUM_BACKUP_ROTATION=8
OMNIFORUM_BACKUP_STALE_HOURS=168
OMNIFORUM_LIVE_INTERVAL_SECONDS=5
OMNIFORUM_USER_MEDIA_LIMIT_BYTES=67108864
OMNIFORUM_USER_MEDIA_LIMIT_FILES=80
```

### What They Control

| Variable | Purpose |
| --- | --- |
| `OMNIFORUM_MAX_REQUEST_BYTES` | Max request/upload body size in bytes |
| `OMNIFORUM_BACKUP_ROTATION` | Number of local backup archives to keep |
| `OMNIFORUM_BACKUP_STALE_HOURS` | Age before the Operations dashboard marks a backup stale |
| `OMNIFORUM_LIVE_INTERVAL_SECONDS` | Server-Sent Events update interval |
| `OMNIFORUM_USER_MEDIA_LIMIT_BYTES` | Per-account media quota |
| `OMNIFORUM_USER_MEDIA_LIMIT_FILES` | Per-account media file count limit |

If you raise `OMNIFORUM_MAX_REQUEST_BYTES`, also raise the reverse proxy upload limit.

## Upload Scanner

Leave scanning disabled for basic local testing:

```bash
OMNIFORUM_MEDIA_SCAN_COMMAND=
OMNIFORUM_MEDIA_SCAN_REQUIRED=0
OMNIFORUM_MEDIA_SCAN_TIMEOUT_SECONDS=20
```

For production, you can run an external scanner before uploads are committed:

```bash
OMNIFORUM_MEDIA_SCAN_COMMAND=clamdscan --no-summary {path}
OMNIFORUM_MEDIA_SCAN_REQUIRED=1
OMNIFORUM_MEDIA_SCAN_TIMEOUT_SECONDS=20
```

`{path}` is replaced with the temporary upload file path. `{storage_path}` is replaced with the final relative storage path. If neither placeholder is present, OmniForum appends the uploaded file path as the final argument.

Set `OMNIFORUM_MEDIA_SCAN_REQUIRED=1` only after confirming the scanner command works. Required mode rejects uploads if the scanner is missing or fails.

## Email Account Features

Email account features are off by default:

```bash
OMNIFORUM_EMAIL_AUTH_ENABLED=0
OMNIFORUM_EMAIL_FROM=
OMNIFORUM_SMTP_HOST=
OMNIFORUM_SMTP_PORT=587
OMNIFORUM_SMTP_USERNAME=
OMNIFORUM_SMTP_PASSWORD=
OMNIFORUM_SMTP_STARTTLS=1
```

When `OMNIFORUM_EMAIL_AUTH_ENABLED=0`, normal users do not see email fields or password reset links, and email reset APIs reject use.

Enable email only after SMTP is configured and tested:

```bash
OMNIFORUM_EMAIL_AUTH_ENABLED=1
OMNIFORUM_EMAIL_FROM=Forum <no-reply@example.com>
OMNIFORUM_SMTP_HOST=smtp.example.com
OMNIFORUM_SMTP_PORT=587
OMNIFORUM_SMTP_USERNAME=no-reply@example.com
OMNIFORUM_SMTP_PASSWORD=replace-with-real-password
OMNIFORUM_SMTP_STARTTLS=1
```

Probe SMTP before launch:

```bash
OMNIFORUM_EMAIL_AUTH_ENABLED=1 scripts/probe_email_auth.py --env-file .env --to admin@example.com
```

## Staff Notifications

Leave Discord/webhook notices blank unless you want staff-facing alerts:

```bash
OMNIFORUM_DISCORD_WEBHOOK_URL=
```

If configured, OmniForum can send notifications for reports, appeals, contact notices, backups, and restore-guide events.

## Docker Compose

Docker Compose reads values from `.env` for interpolation. The file is not copied into the image.

For production-like Compose:

```bash
OMNIFORUM_PUBLIC_URL=https://forum.example.com
OMNIFORUM_SECURE_COOKIES=1
```

Then run:

```bash
docker compose up -d --build
```

## Remote Deploy Env Files

The root `.env` configures the app itself. These deploy/monitor files are separate and should also stay private:

- `deploy/omniforum-remote-deploy.env`
- `deploy/omniforum-healthcheck.env`
- `deploy/omniforum-offsite-backup.env`

Create them from their examples only when needed:

```bash
cp deploy/omniforum-remote-deploy.env.example deploy/omniforum-remote-deploy.env
cp deploy/omniforum-healthcheck.env.example deploy/omniforum-healthcheck.env
cp deploy/omniforum-offsite-backup.env.example deploy/omniforum-offsite-backup.env
chmod 600 deploy/*.env
```

## Validate `.env`

Run:

```bash
scripts/production_readiness.py --json
scripts/security_check.py
```

On a production host, also pass the public URL:

```bash
scripts/production_readiness.py --url https://forum.example.com
scripts/healthcheck.py https://forum.example.com
```

## Expected Warnings

- A local `.env` will trigger a readiness warning because it is private runtime state.
- `OMNIFORUM_PUBLIC_URL=http://127.0.0.1:8000` with `OMNIFORUM_SECURE_COOKIES=0` is correct for local development.
- `OMNIFORUM_PUBLIC_URL=https://...` should use `OMNIFORUM_SECURE_COOKIES=1`.
- No remote health check runs unless you provide `--url`.

## Before Sharing Source

Do not include `.env` in handoff archives. Use:

```bash
scripts/package_release.sh "$PWD" /tmp/omniforum-release
scripts/check_release_archive.py /tmp/omniforum-release/omniforum-source-*.tar.gz
```

If private data may have been created locally:

```bash
OMNIFORUM_CONFIRM_SCRUB=yes scripts/scrub_private_data.sh "$PWD"
scripts/clean_workspace.sh
```
