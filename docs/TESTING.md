# OmniForum Testing

Use these checks before you ship a change or trust a deployment.

## Fast Local Checks

```bash
python3 -m py_compile app.py omniforum/*.py scripts/*.py tests/*.py
python3 -m ruff check .
for file in js/*.js; do node --check "$file"; done
scripts/generate_assets.py --check
scripts/check_frontend.py
scripts/production_readiness.py --json
scripts/security_check.py
python3 -m unittest discover -s tests -v
python3 -m pytest
```

## Full Release Gate

```bash
scripts/release_check.sh
```

The release gate runs Python compile/lint, JavaScript syntax, frontend asset checks, schema/operator checks, unit tests, browser tests when dependencies are available, restore verification, and clean package leak scanning.

## Real Browser Tests

Install Playwright and Chromium:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

Run the split browser suite:

```bash
python -m unittest discover -s tests -p 'test_browser_*.py' -v
```

The browser suite covers:

- login, registration, posting, replies, and uploads
- settings/profile update flows
- DMs, reports, moderation, and admin Operations
- plugin controls and section management
- accessibility shell and modal keyboard flow
- mobile overflow checks

## Restore Verification

```bash
scripts/verify_restore.sh
```

This creates a backup, restores into a temporary copy, boots the app, and checks `/api/health` plus `/api/home`.

## Offsite Restore Verification

```bash
OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD_FILE=/root/omniforum-backup-pass \
scripts/verify_offsite_restore.sh /srv/omniforum-offsite/omniforum-manual-YYYYMMDD-HHMMSS.tar.gz.enc /var/www/omniforum
```

## Staging Smoke

Only run staging smoke against a disposable staging instance. It creates users, content, reports, moderation actions, uploads, and a backup.

```bash
OMNIFORUM_STAGING_CONFIRM=yes scripts/staging_smoke.py https://staging.example.com
```

For an existing staging database:

```bash
OMNIFORUM_STAGING_CONFIRM=yes \
OMNIFORUM_STAGING_ADMIN_USER=owner_name \
OMNIFORUM_STAGING_ADMIN_PASSWORD='owner password' \
scripts/staging_smoke.py https://staging.example.com
```

## Operator Probes

```bash
python3 scripts/deploy_assistant.py --open
scripts/production_readiness.py --url https://staging.example.com
scripts/security_check.py
scripts/healthcheck.py https://staging.example.com
scripts/load_test.py https://staging.example.com --requests 80 --concurrency 8
scripts/migration_status.py --data-dir data
```

## Optional Email Probe

Email account features are hidden unless `OMNIFORUM_EMAIL_AUTH_ENABLED=1` and SMTP is configured. Probe SMTP only after intentionally enabling the feature:

```bash
OMNIFORUM_EMAIL_AUTH_ENABLED=1 scripts/probe_email_auth.py --env-file .env --to admin@example.com
```

## Clean Package Leak Scan

```bash
scripts/package_release.sh "$PWD" /tmp/omniforum-release
scripts/check_release_archive.py /tmp/omniforum-release/omniforum-source-*.tar.gz
```

## Current Coverage

- API auth, registration abuse controls, CSRF, persistent rate limits, posting, moderation, backups, and restore-guide flows
- FTS search index update hooks
- plugin enable/disable behavior and safe asset serving
- one-shot SSE stream verification
- public pages plus `robots.txt` and `sitemap.xml`
- Dockerfile/Compose static configuration
- operator scripts for readiness, security, health monitoring, load probing, deployment assistant behavior, offsite backup copy, and offsite restore rehearsal
- structure checks that keep large backend/frontend files split below the configured ceiling
