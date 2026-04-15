# OmniForum

OmniForum is a self-hosted forum application built on a lightweight Python backend with SQLite storage and a static HTML/CSS/JavaScript frontend.

It is designed for a single-instance deployment with persistent disk storage, role-based moderation, direct messages, staff tooling, inline media, and admin operations such as backups and cleanup.

## Highlights

- Real accounts with persistent sessions
- Role-aware sections, posting permissions, and hidden restricted areas
- Threads, replies, quoting, reactions, likes, polls, bookmarks, and follows
- Inline image/GIF uploads in threads and replies
- Profile pictures, profile customization, signatures, and account settings
- Full-site appearance themes with saved per-user color schemes
- Direct messages, notifications, search, and trending/related discovery
- Reports, appeals, staff inbox, and moderation history
- Temp-password recovery flow with forced reset on login
- Admin tools for backups, logs, health checks, and media cleanup

## Stack

- Backend: `app.py` using Python standard library HTTP tooling
- Storage: split SQLite databases under `data/`
- Frontend: static HTML pages plus shared `js/` and `css/`
- Media: uploaded avatars and post media served from `/media/...`

No third-party Python packages are required by the current app.

## Requirements

- Python `3.10+`
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

### 3. Start the website

Run:

```bash
python3 app.py
```

When it starts correctly, you should see:

```text
OmniForum running at http://127.0.0.1:8000
```

### 4. Open the site in your browser

Open:

```text
http://127.0.0.1:8000
```

### 5. Create the first account

The first account created on a brand-new OmniForum install becomes the `Owner`.

That account has full control of the site.

### 6. Confirm the data folder was created

After the server starts, OmniForum creates and uses files inside `data/`, including:

- forum databases such as `users.db`, `threads.db`, and `posts.db`
- uploaded media folders
- logs and backup folders

If `data/` is writable, the site will create what it needs automatically.

### 7. Stop the server when you are done

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

### 4. Confirm Python is available

```bash
python3 --version
```

If Python is not installed, install Python 3 through your server's package manager first.

### 5. Make sure the app can write to `data/`

OmniForum must be able to write inside the project folder, especially:

- `data/`
- `data/uploads/`
- `data/logs/`
- `data/exports/`

If needed, fix ownership and permissions for the account that will run the app.

### 6. Test-run the app directly

From the project root, run:

```bash
python3 app.py
```

If it starts, open the server locally or through your tunnel/proxy and make sure the homepage loads.

Press `Ctrl+C` to stop it after testing.

### 7. Create a systemd service so the site stays running

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
ExecStart=/usr/bin/python3 /var/www/omniforum/app.py
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

### 8. Put nginx in front of OmniForum

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

### 9. Point your domain to the server

Update your DNS so your domain points to your server's IP address.

Then set that domain name in your nginx config.

### 10. Enable HTTPS

Set up SSL/TLS in nginx or your preferred reverse proxy.

When serving OmniForum over HTTPS, keep:

```text
OMNIFORUM_SECURE_COOKIES=1
```

### 11. Open the website and create the first account

Visit your domain in the browser.

If this is a fresh install, the first account created becomes the `Owner`.

### 12. Create a backup after initial setup

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
| `OMNIFORUM_MAX_REQUEST_BYTES` | `50331648` | Max request body size in bytes |
| `OMNIFORUM_BACKUP_ROTATION` | `8` | Number of backup archives to keep |

Example:

```bash
OMNIFORUM_HOST=127.0.0.1 \
OMNIFORUM_PORT=8000 \
OMNIFORUM_SECURE_COOKIES=1 \
python3 app.py
```

## Data Layout

Runtime data is stored under `data/`:

- `users.db`: accounts, roles, recovery state, preferences, saved site theme, and avatars
- `sessions.db`: login sessions and session audit metadata
- `sections.db`: categories and sections
- `threads.db`: threads, poll data, bookmarks, follows
- `posts.db`: replies, likes, reactions, media, edit history
- `messages.db`: direct messages
- `notifications.db`: alerts and unread notifications
- `reports.db`: reports and appeals
- `contact.db`: contact form submissions and staff inbox state
- `uploads/avatars/`: profile pictures
- `uploads/posts/`: thread/reply images and GIFs
- `exports/backups/`: admin-created backups
- `logs/server.log`: lightweight request and operations log

Only uploaded media and exported backups are meant to be web-served. The rest of `data/` is private application storage.

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

## Features

### Forum and Community

- Category/section forum layout
- Threads and replies
- Post quoting
- Rich post formatting with markdown-style and BBCode-style content
- Image/GIF uploads in new threads and replies
- Polls inside threads
- Saved threads and thread follows
- Related threads and trending threads
- Search across content

### Accounts and Profiles

- Registration and login
- Persistent cookie sessions
- Profile pictures
- Signatures
- Profile badge and accent customization
- Saved site theme preference in Settings
- Password change and temporary-password reset flow
- Session review and sign-out-other-sessions tools
- DM privacy and notification preferences

### Appearance and Personalization

- Full-site theme switching from Settings
- 15 preset color schemes built into the forum
- Live theme preview before saving
- Theme preference saved per account and re-applied after login/refresh

### Messaging and Alerts

- Direct messages
- Unread counts
- Notifications for replies, likes, mentions, DMs, reports, and staff actions

### Moderation and Staff Tools

- Reports queue
- Appeals queue
- Staff inbox for contact form submissions
- Warnings, notes, XP adjustments, timeouts, bans, mutes, and shadow mutes
- Role changes with audit history
- Thread moderation, lock/pin/solve controls, and section permissions

### Admin Operations

- Backup archive creation
- Request and storage health view
- Runtime logs view
- Orphaned media cleanup
- Section management

## Roles

- `Owner`: first registered account, full control
- `Admin`: full site administration and operations access
- `Mod`: moderation tools, staff inbox, report/appeal handling
- `Veteran`, `Member`, `New`: community roles used for section read/write permissioning

Sections can be hidden entirely from users who do not meet the section read role.

## Recovery and Contact

- There is no email stack in the current build
- Admins and the owner can issue a temporary password for account recovery
- Temporary passwords force the user to reset their password after login
- The contact form supports an optional Discord username so staff have an off-site handle to reference

## Backups and Restore

Admins can create backups from `Settings -> Operations -> Create Backup`.

Each backup archive includes:

- all runtime SQLite databases
- uploaded media
- the request/operations log when present

Basic restore flow:

1. Stop the server.
2. Make a safety copy of the current `data/` folder.
3. Extract the chosen backup so its `data/` contents replace the current runtime files.
4. Start OmniForum again.
5. Verify the homepage or `/api/health`.

## Operations and Maintenance

- Runtime logs: `data/logs/server.log`
- Media cleanup: `Settings -> Operations -> Media Cleanup`
- Backups: `data/exports/backups/`
- Private uploads: `data/uploads/`

For more detailed operational notes, see `docs/OPERATIONS.md`.

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
```

## Important Notes

- OmniForum currently uses SQLite and local file storage, so treat it as a single-node app
- Backups should be copied off the server if the forum matters to you
- Production should always run behind HTTPS
- Only `/media/...` and `/exports/...` should be exposed through the app
- The rest of `data/` should never be served directly
