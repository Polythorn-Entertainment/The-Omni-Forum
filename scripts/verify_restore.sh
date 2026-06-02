#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${OMNIFORUM_VERIFY_HOST:-127.0.0.1}"
PORT="${OMNIFORUM_VERIFY_PORT:-8765}"
TMP_DIR="$(mktemp -d)"
SERVER_PID=""

cleanup() {
  if [ -n "${SERVER_PID}" ] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "Creating backup from ${PROJECT_DIR}..."
BACKUP_OUTPUT="$(OMNIFORUM_BACKUP_ROTATION=99 "${PROJECT_DIR}/scripts/backup_omniforum.sh" "${PROJECT_DIR}")"
ARCHIVE="$(printf '%s\n' "${BACKUP_OUTPUT}" | awk '/Created / {print $2}' | tail -n 1)"

if [ ! -f "${ARCHIVE}" ]; then
  echo "Could not find backup archive from output:" >&2
  printf '%s\n' "${BACKUP_OUTPUT}" >&2
  exit 1
fi

RESTORE_TARGET="${TMP_DIR}/omniforum-restore-check"
mkdir -p "${RESTORE_TARGET}"

echo "Copying source into restore target..."
tar -czf "${TMP_DIR}/source.tar.gz" -C "${PROJECT_DIR}" \
  --exclude="./.env" \
  --exclude="./.venv" \
  --exclude="./venv" \
  --exclude="./dist" \
  --exclude="*/__pycache__" \
  --exclude="*.pyc" \
  --exclude=".DS_Store" \
  --exclude="./data-pre-restore-*" \
  .
tar -xzf "${TMP_DIR}/source.tar.gz" -C "${RESTORE_TARGET}"

echo "Restoring ${ARCHIVE} into ${RESTORE_TARGET}..."
"${RESTORE_TARGET}/scripts/restore_omniforum.sh" "${ARCHIVE}" "${RESTORE_TARGET}"

echo "Starting restored OmniForum on http://${HOST}:${PORT}..."
(
  cd "${RESTORE_TARGET}"
  OMNIFORUM_HOST="${HOST}" \
  OMNIFORUM_PORT="${PORT}" \
  OMNIFORUM_PUBLIC_URL="http://${HOST}:${PORT}" \
  PYTHONUNBUFFERED=1 \
  "${PYTHON_BIN}" app.py
) >"${TMP_DIR}/server.log" 2>&1 &
SERVER_PID="$!"

"${PYTHON_BIN}" - <<PY
import json
import time
import urllib.request

base = "http://${HOST}:${PORT}"
deadline = time.time() + 30
last_error = ""
while time.time() < deadline:
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=2) as response:
            health = json.loads(response.read().decode("utf-8"))
        with urllib.request.urlopen(base + "/api/home", timeout=5) as response:
            home = json.loads(response.read().decode("utf-8"))
        if health.get("ok") and home.get("categories"):
            print("Restore verification passed.")
            raise SystemExit(0)
    except Exception as exc:
        last_error = str(exc)
    time.sleep(0.25)
raise SystemExit(f"Restore verification failed: {last_error}")
PY
