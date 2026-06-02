# OmniForum

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite&logoColor=white)
![Pillow 12.2+](https://img.shields.io/badge/Pillow-12.2%2B-5A67D8)
![Docker Ready](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)
![License: MOSL](https://img.shields.io/badge/License-MOSL_1.0-green)

OmniForum is a self-hosted community forum built for people who want to own the whole stack: accounts, discussions, moderation, uploads, backups, operations, and the data itself.

It is intentionally simple to host. The app runs as one Python process, stores forum data in SQLite files under `data/`, and serves a static HTML/CSS/JavaScript frontend. Put it behind HTTPS, keep `data/` persistent, and the first account on a fresh install becomes the `Owner`.

## What It Does

- Forum sections, threads, replies, quoting, reactions, polls, bookmarks, follows, pinned/locked/featured/solved states, and search
- User accounts with roles, persistent sessions, profile pictures, signatures, themes, settings, direct messages, and notifications
- Inline image/GIF uploads with server-side processing, thumbnails, quotas, and optional external media scanning
- Staff tools for reports, appeals, contact inbox, moderation notes, warnings, bans, mutes, role changes, audit logs, and moderation analytics
- Admin Operations for setup, branding, signup controls, import/export previews, backups, restore guidance, logs, health checks, plugins, and orphaned media cleanup
- Production helpers for Docker, nginx, Caddy, systemd, logrotate, health monitoring, offsite backups, SSH deploys, clean source packages, and release checks

## Open-Source Resources Used

OmniForum keeps its dependency list short. The core app is mostly Python standard library plus browser-native frontend code.

| Area | Resource | Used For |
| --- | --- | --- |
| Backend runtime | Python standard library | HTTP server, routing, cookies, JSON, files, subprocesses, and utility code |
| Storage | SQLite | Accounts, sessions, sections, threads, posts, messages, reports, audit logs, settings, rate limits, and search index data |
| Image processing | Pillow `>=12.2.0,<13` | Upload validation, resizing, metadata stripping, GIF handling, and thumbnails |
| Frontend | HTML, CSS, JavaScript | Browser UI without a bundled frontend framework |
| Browser APIs | `EventSource`, `fetch`, `localStorage`, DOM APIs | Live updates, API calls, drafts, settings, and interactive UI |
| Containers | Docker / Docker Compose | Local and production-style container runs with persistent `data/` storage |
| Reverse proxy examples | nginx, Caddy | HTTPS termination, upload limits, and proxying to the Python process |
| Service management examples | systemd, logrotate | Long-running service setup and log rotation |
| Testing | Python `unittest`, Playwright | API, page, browser, upload, admin, moderation, accessibility, and mobile smoke checks |
| Linting | Ruff | Python source checks |
| CI example | GitHub Actions | Compile, lint, frontend checks, tests, restore verification, and package leak scan |

## Project Shape

```text
app.py                  Python HTTP server entrypoint
omniforum/              Backend modules for config, DB, schema, APIs, media, search, backups, plugins, and validation
index.html              Forum homepage
pages/                  Secondary site pages
js/                     Frontend application logic
css/                    Stylesheets
data/                   Runtime databases, uploads, backups, and logs; private except placeholders
deploy/                 Deployment examples and Deployment Assistant assets
docs/                   Setup, deployment, operations, testing, resources, and architecture notes
scripts/                Maintenance, release, backup, restore, deploy, and verification scripts
```

## Docs

| Topic | Doc |
| --- | --- |
| Start here: setup through launch | [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) |
| Local setup, Docker, and Deployment Assistant | [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) |
| `.env` setup and runtime configuration | [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) |
| Production deploy, backups, restore, and launch checklist | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| Staging rehearsal | [docs/STAGING_DEPLOY.md](docs/STAGING_DEPLOY.md) |
| Operations dashboard, moderation queues, plugins, recovery, and maintenance | [docs/OPERATIONS.md](docs/OPERATIONS.md) |
| Tests, browser automation, release gate, and restore verification | [docs/TESTING.md](docs/TESTING.md) |
| Requirements, resource files, manifests, and deploy assets | [docs/RESOURCES.md](docs/RESOURCES.md) |
| Feature inventory and roles | [docs/FEATURES.md](docs/FEATURES.md) |
| Backend/frontend structure, data layout, and source hygiene | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Privacy, retention, handoff, and incident-response notes | [docs/DATA_POLICY.md](docs/DATA_POLICY.md) |

## Quick Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:8000
```

## Release Check

```bash
scripts/release_check.sh
```

That gate runs compile/lint checks, frontend checks, schema and operator checks, unit/browser tests, restore verification, and a clean package leak scan.

## Clean Source Packages

Do not upload live runtime data to a public repo. Use the package helper when sharing source:

```bash
scripts/package_release.sh "$PWD" /tmp/omniforum-release
scripts/check_release_archive.py /tmp/omniforum-release/omniforum-source-*.tar.gz
```

Clean packages exclude `.env`, SQLite databases, sessions, logs, uploads, backups, caches, and local operator env files.

## License

OmniForum is released under the Mizuhiki Open Source License v1.0. See [LICENSE](LICENSE).
