# OmniForum Resources And Requirements

This page lists the files that matter when you install, deploy, package, or hand off OmniForum.

## Python Requirements

Runtime dependencies live in [../requirements.txt](../requirements.txt).

Current runtime dependency:

- `Pillow>=12.2.0,<13`: image validation, resizing, metadata stripping, GIF frame handling, and thumbnail generation. The 12.2.0 floor avoids the PDF trailer loop DoS fixed in Pillow 12.2.0.

Development and test dependencies live in [../requirements-dev.txt](../requirements-dev.txt).

Current development dependencies:

- `ruff`: Python lint checks used by `scripts/release_check.sh` and CI
- `playwright`: real browser coverage for auth, uploads, settings, moderation, admin Operations, accessibility shell checks, and mobile layout checks
- `pytest`: optional test runner for GitHub and local collection compatibility; the suite also runs with `unittest`

Install runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

Install development/test dependencies:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

No Node package install is required. Node is used only as a local/CI executable for JavaScript syntax checks:

```bash
for file in js/*.js; do node --check "$file"; done
```

## Runtime Configuration Files

- `.env.example`: safe template for the private root `.env`
- `.env`: local or server runtime config; private and excluded from packages
- `deploy/staging.env.example`: staging-oriented `.env` template
- `deploy/omniforum-remote-deploy.env.example`: SSH deploy helper template
- `deploy/omniforum-healthcheck.env.example`: healthcheck timer/monitor template
- `deploy/omniforum-offsite-backup.env.example`: offsite backup template

The private versions of these files are ignored and excluded from clean packages:

- `.env`
- `deploy/omniforum-remote-deploy.env`
- `deploy/omniforum-healthcheck.env`
- `deploy/omniforum-offsite-backup.env`

See [ENVIRONMENT.md](ENVIRONMENT.md) before filling them out.

## Runtime Data

Runtime data lives under `data/`. Only placeholders and [../data/README.md](../data/README.md) belong in source.

Private runtime files include:

- SQLite databases
- session state
- uploaded avatars and post media
- thumbnails
- logs
- backup archives
- restore snapshots

Before sharing source, build a clean package:

```bash
scripts/package_release.sh "$PWD" /tmp/omniforum-release
scripts/check_release_archive.py /tmp/omniforum-release/omniforum-source-*.tar.gz
```

## Frontend Assets

Frontend page/script ordering is declared in [../assets/manifest.json](../assets/manifest.json).

Useful commands:

```bash
scripts/generate_assets.py --check
scripts/build_assets.py /tmp/omniforum-assets
scripts/check_frontend.py
```

When adding or removing frontend files, update the manifest through the existing asset scripts instead of editing generated page tags by hand.

## Deployment Resources

Deployment examples live in `deploy/`:

- `nginx-omniforum.conf`
- `caddy-omniforum.conf`
- `omniforum.service`
- `logrotate-omniforum.conf`
- `omniforum-healthcheck.service`
- `omniforum-healthcheck.timer`
- `omniforum-offsite-backup.service`
- `omniforum-offsite-backup.timer`
- `assistant/` for the local Deployment Assistant UI

Container resources:

- [../Dockerfile](../Dockerfile)
- [../docker-compose.yml](../docker-compose.yml)
- [../.dockerignore](../.dockerignore)

## Plugin Resources

Plugins live under `plugins/<plugin-id>/` and are described in [../plugins/README.md](../plugins/README.md).

Each plugin needs a `plugin.json` manifest. Only enabled plugins and manifest-declared client assets are served to the browser.

## Test And Release Resources

The main release command is:

```bash
scripts/release_check.sh
```

It runs compile/lint checks, frontend checks, schema/operator checks, unit and browser tests, restore verification, and clean package leak scanning.

Other useful checks:

```bash
scripts/production_readiness.py --json
scripts/security_check.py
scripts/verify_restore.sh
scripts/healthcheck.py https://forum.example.com
```
