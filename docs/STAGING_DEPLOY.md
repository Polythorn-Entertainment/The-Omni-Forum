# OmniForum Staging Deploy

Use staging as a disposable rehearsal before pointing real users at the forum.

## Staging Setup

- Run one writable OmniForum process behind nginx or Caddy with HTTPS.
- Keep `data/` on persistent disk, owned by the service user, and excluded from source packages.
- If staging runs with Docker Compose, keep the named `omniforum-data` volume persistent and include it in backup/restore rehearsal.
- Copy `deploy/staging.env.example` to the server as `.env` and set `OMNIFORUM_PUBLIC_URL` to the staging HTTPS origin.
- Copy `deploy/omniforum-remote-deploy.env.example` to `deploy/omniforum-remote-deploy.env` on your workstation if staging deploys should be pushed over SSH.
- Keep `OMNIFORUM_SECURE_COOKIES=1` behind HTTPS.
- Install `deploy/logrotate-omniforum.conf` or an equivalent host log policy for `data/logs/server.log`, `data/logs/access.log`, and `data/logs/app.jsonl`.
- Copy `deploy/omniforum-offsite-backup.env.example` to `deploy/omniforum-offsite-backup.env`, point it at a staging off-host target, and install `deploy/omniforum-offsite-backup.timer`.
- Copy `deploy/omniforum-healthcheck.env.example` to `deploy/omniforum-healthcheck.env`, then install `deploy/omniforum-healthcheck.timer` or wire `scripts/healthcheck.py` into the monitor you already use.
- Configure `OMNIFORUM_MEDIA_SCAN_COMMAND` before public upload testing if staging should mimic production scanning.
- Keep `OMNIFORUM_EMAIL_AUTH_ENABLED=0` unless SMTP is configured. When it is `0`, email fields and reset links stay hidden from normal users.

## Reverse Proxy

- Use `deploy/nginx-omniforum.conf` for nginx or `deploy/caddy-omniforum.conf` for Caddy.
- Let the proxy terminate TLS and forward to the Python app on `127.0.0.1:8000`.
- Set the proxy upload limit at least as high as `OMNIFORUM_MAX_REQUEST_BYTES`.
- Forward or generate `X-Request-ID` if you want proxy logs to correlate with OmniForum JSONL request logs.

## Smoke Rehearsal

Run the automated staging smoke only against a disposable staging instance. It creates users, a thread, an upload, a reply, a report, a moderation action, and a backup:

```bash
OMNIFORUM_STAGING_CONFIRM=yes scripts/staging_smoke.py https://staging.example.com
```

Run the production-readiness pass after the proxy is live:

```bash
python3 scripts/deploy_assistant.py --open
scripts/production_readiness.py --url https://staging.example.com
scripts/security_check.py
scripts/healthcheck.py https://staging.example.com
scripts/load_test.py https://staging.example.com --requests 80 --concurrency 8
scripts/migration_status.py --data-dir data
```

For SSH deploy rehearsal:

```bash
set -a
. deploy/omniforum-remote-deploy.env
set +a
OMNIFORUM_DEPLOY_CONFIRM=yes scripts/deploy_remote.sh
```

If email recovery is intentionally enabled on staging, probe SMTP before showing the feature to users:

```bash
OMNIFORUM_EMAIL_AUTH_ENABLED=1 scripts/probe_email_auth.py --env-file .env --to admin@example.com
```

For an existing staging database, provide admin credentials instead of relying on first-account owner creation:

```bash
OMNIFORUM_STAGING_CONFIRM=yes \
OMNIFORUM_STAGING_ADMIN_USER=owner_name \
OMNIFORUM_STAGING_ADMIN_PASSWORD='owner password' \
scripts/staging_smoke.py https://staging.example.com
```

## Manual Launch Rehearsal

1. Load `/api/health`, `/api/home`, `/robots.txt`, and `/sitemap.xml`.
2. Create or log in as the owner/admin.
3. Register a normal member and confirm the member cannot see admin Operations.
4. Create a thread with an image upload, reply, quote, reaction, bookmark, and follow.
5. Submit a report as the member and resolve it as staff.
6. Open Settings -> Operations and confirm install checks, queue counts, logs, media scanner state, email auth state, and schema migrations.
7. Create a backup, open the restore guide, download the archive, and run `scripts/verify_restore.sh` locally against a copied source tree.
8. Test mobile widths around 390px and 768px for menu, posting, modals, settings, and Operations.
9. Confirm `scripts/package_release.sh` excludes `.env`, databases, logs, uploads, backups, and caches.
10. Confirm `scripts/healthcheck.py` and `scripts/production_readiness.py` pass from outside the app process.
11. Run `scripts/offsite_backup.sh` and `scripts/verify_offsite_restore.sh` against the newest off-host backup artifact.
12. Re-run `scripts/deploy_remote.sh` once to confirm repeat deploys preserve `.env` and `data/`.
