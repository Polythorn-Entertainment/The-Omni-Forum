# OmniForum Local Setup

This is the local setup path for trying the forum, making changes, or doing a quick smoke test before deployment.

## Requirements

- Python `3.10+`
- Python dependencies from `requirements.txt`
- A writable local `data/` directory
- Optional: Docker Compose for containerized local runs

## Step-By-Step Setup

1. Check Python:

```bash
python3 --version
```

2. Open the project folder:

```bash
cd /path/to/forum
```

3. Optional: copy the environment template:

```bash
cp .env.example .env
```

For a full `.env` fill-out guide, see [ENVIRONMENT.md](ENVIRONMENT.md).

4. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

5. Start the website:

```bash
python app.py
```

The default local URL is:

```text
http://127.0.0.1:8000
```

6. Create the first account.

On a brand-new runtime, the first account becomes the `Owner`.

7. Confirm `data/` was created.

OmniForum creates runtime SQLite databases, uploaded media folders, logs, and backup directories under `data/`. The folder must be writable by the process running the app.

## Reset Local Runtime Data

Stop the server, then run:

```bash
OMNIFORUM_CONFIRM_RESET=yes scripts/reset_runtime_data.sh
```

This removes local SQLite databases, uploads, backups, and logs, then recreates the runtime folder structure.

## Docker

The Docker setup mirrors the split app layout and keeps runtime state out of the image.

Run locally:

```bash
docker compose up --build
```

Then open:

```text
http://127.0.0.1:8000
```

Compose uses a named volume, `omniforum-data`, mounted at `/app/data` so SQLite databases, uploads, logs, and backups persist across container restarts without writing private state into the source tree.

Change the host port:

```bash
OMNIFORUM_DOCKER_PORT=8080 docker compose up --build
```

For HTTPS behind a proxy, set production environment values before starting:

```bash
OMNIFORUM_PUBLIC_URL=https://forum.example.com \
OMNIFORUM_SECURE_COOKIES=1 \
docker compose up -d --build
```

The container healthcheck probes `/api/health`. Optional email, media scanner, Discord, and backup settings can be provided through Compose environment interpolation from a local `.env`; `.env` is ignored and never copied into the image.

## Deployment Assistant

OmniForum includes a local browser assistant for deployment setup. It can write the local `.env`, remote deploy env, healthcheck env, and offsite backup env; run readiness/security/health/load checks; build a clean package; show the exact SSH deploy command; and scrub runtime data with explicit confirmation.

Run:

```bash
python3 scripts/deploy_assistant.py --open
```

Then open:

```text
http://127.0.0.1:8787
```

The assistant binds to localhost by default and refuses non-localhost binding unless you pass `--allow-remote`. It writes secret-bearing env files only when you click the matching write button. The UI assets live in `deploy/assistant/`.

## Stop The Server

In the terminal where OmniForum is running, press:

```text
Ctrl+C
```
