OmniForum Operations

Running locally

- Start the server from the project root with `python3 app.py`.
- By default it binds to `127.0.0.1:8000`.
- Override runtime settings with:
  - `OMNIFORUM_HOST`
  - `OMNIFORUM_PORT`
  - `OMNIFORUM_MAX_REQUEST_BYTES`
  - `OMNIFORUM_BACKUP_ROTATION`
  - `OMNIFORUM_SECURE_COOKIES=1`

Data layout

- SQLite files live under `data/`.
- Uploaded media lives under `data/uploads/`.
- Admin-created backup archives are written to `data/exports/backups/`.
- Runtime request logs are appended to `data/logs/server.log`.

Backups

- Open Settings as an admin or owner and use `Operations` -> `Create Backup`.
- The server generates a zip archive containing:
  - all `data/*.db` files
  - `data/logs/server.log` if present
  - uploaded avatars and post media
- Backup rotation keeps the newest archives and removes older ones based on `OMNIFORUM_BACKUP_ROTATION`.

Restore process

1. Stop the OmniForum server.
2. Make a safety copy of the current `data/` folder.
3. Extract the chosen backup archive into the project root so its `data/` contents replace the current runtime files.
4. Start the server again with `python3 app.py`.
5. Load `/api/health`, `/api/home`, or the homepage to confirm the restored instance boots normally.

Media cleanup

- Admins can run orphaned media cleanup from `Operations`.
- This removes files in `data/uploads/` that are no longer referenced by post media or user avatars.
- It also clears orphaned post-media metadata and stale avatar references before sweeping files.
- Run a backup before cleanup if you want an easy rollback point.

Production notes

- Put OmniForum behind a reverse proxy such as nginx.
- Set `OMNIFORUM_SECURE_COOKIES=1` when traffic is served over HTTPS.
- Keep the app on a private loopback/private subnet binding and let the proxy handle TLS.
- Review the provided nginx example in `deploy/nginx-omniforum.conf`.

Moderation / support queues

- Reports, appeals, and staff inbox notices all surface in the top-right user menu for staff.
- Admin operations are intentionally hidden from moderators and below.
