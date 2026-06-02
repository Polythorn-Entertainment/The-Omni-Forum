# OmniForum Data Policy Notes

This is a practical starting point for privacy and retention decisions. It is not legal advice; adjust the retention windows and request handling to match your community rules and legal obligations before launch.

## Data Classes

- Account data: username, password hash, role, profile fields, preferences, recovery codes, optional email fields when email auth is enabled.
- Community content: sections, threads, posts, polls, reactions, bookmarks, subscriptions, uploads, and generated thumbnails.
- Private/community support data: direct messages, reports, appeals, contact submissions, staff notes, audit events, rate-limit events, sessions, and operational logs.
- Backups: compressed copies of `data/`, including databases, uploads, logs, and exports unless separately scrubbed.

## Default Retention

- Sessions: expire through normal session handling; clear `data/sessions.db` if session rotation is needed after exposure.
- Logs: rotate with `deploy/logrotate-omniforum.conf`; keep only as long as needed for abuse response and debugging.
- Local backups: rotate with `OMNIFORUM_BACKUP_ROTATION`; keep off-host copies on a documented schedule.
- Rate-limit events: retained in `data/audit.db` so active abuse windows survive restarts.
- Staff audit records: keep long enough to explain moderation decisions and administrative changes.
- Uploads: remove through moderation/admin cleanup when content is deleted or ruled unsafe.

## User Requests

- Export: use admin export tools for users, threads, posts, reports, moderation, settings, or all data. Review exports before sharing because they may include staff-only context.
- Deletion: remove or anonymize public content according to the community policy, then clear profile fields, sessions, recovery codes, optional email data, and related private messages where required.
- Correction: let users update profile/settings directly where possible; staff can document exceptional corrections in audit notes.
- Account recovery: recovery codes are available without email. Optional email reset remains hidden until `OMNIFORUM_EMAIL_AUTH_ENABLED=1` and SMTP are configured.

## Incident Response

1. Stop public access or disable risky features if data exposure is ongoing.
2. Preserve a backup for investigation if legally appropriate.
3. Rotate `.env` secrets, webhook URLs, SMTP credentials, and clear `data/sessions.db` if sessions may be exposed.
4. Run `scripts/scrub_private_data.sh` before any source handoff.
5. Rebuild a clean package with `scripts/package_release.sh` and verify the leak scan.

## Production Handoff Checklist

- `.env` and monitor/offsite env files stay out of source packages.
- `data/*.db`, uploads, logs, and backup archives stay on persistent private storage.
- `scripts/production_readiness.py`, `scripts/security_check.py`, `scripts/healthcheck.py`, and `scripts/verify_offsite_restore.sh` are part of launch rehearsal.
- Off-host backup encryption is enabled, and a restore from the off-host artifact has been tested.
