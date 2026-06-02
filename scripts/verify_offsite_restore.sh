#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-${OMNIFORUM_OFFSITE_RESTORE_SOURCE:-}}"
PROJECT_DIR="${2:-$(cd "$(dirname "$0")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${OMNIFORUM_VERIFY_HOST:-127.0.0.1}"
PORT="${OMNIFORUM_VERIFY_PORT:-8766}"
PASSWORD="${OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD:-}"
PASSWORD_FILE="${OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD_FILE:-}"
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

if [ -z "${SOURCE}" ]; then
  echo "Usage: $0 /path/to/offsite-backup.tar.gz-or.enc [/absolute/path/to/project]" >&2
  echo "       or set OMNIFORUM_OFFSITE_RESTORE_SOURCE." >&2
  exit 2
fi

if [ -n "${PASSWORD_FILE}" ]; then
  if [ ! -f "${PASSWORD_FILE}" ]; then
    echo "Password file not found: ${PASSWORD_FILE}" >&2
    exit 2
  fi
  PASSWORD="$(cat "${PASSWORD_FILE}")"
fi

fetch_source() {
  local source="$1"
  local output_dir="$2"
  case "${source}" in
    local:*)
      cp "${source#local:}" "${output_dir}/"
      if [ -f "${source#local:}.sha256" ]; then
        cp "${source#local:}.sha256" "${output_dir}/"
      fi
      ;;
    rclone:*)
      command -v rclone >/dev/null 2>&1 || {
        echo "rclone source requested but rclone is not installed." >&2
        exit 2
      }
      rclone copyto "${source#rclone:}" "${output_dir}/$(basename "${source#rclone:}")"
      ;;
    s3://*)
      command -v aws >/dev/null 2>&1 || {
        echo "s3 source requested but aws CLI is not installed." >&2
        exit 2
      }
      aws s3 cp "${source}" "${output_dir}/$(basename "${source}")"
      ;;
    rsync:*)
      command -v rsync >/dev/null 2>&1 || {
        echo "rsync source requested but rsync is not installed." >&2
        exit 2
      }
      rsync -av "${source#rsync:}" "${output_dir}/"
      ;;
    *)
      cp "${source}" "${output_dir}/"
      if [ -f "${source}.sha256" ]; then
        cp "${source}.sha256" "${output_dir}/"
      fi
      ;;
  esac
}

fetch_source "${SOURCE}" "${TMP_DIR}"
ARTIFACT="$(find "${TMP_DIR}" -maxdepth 1 -type f ! -name '*.sha256' | head -n 1)"
if [ -z "${ARTIFACT}" ] || [ ! -f "${ARTIFACT}" ]; then
  echo "Could not fetch offsite backup artifact: ${SOURCE}" >&2
  exit 1
fi

CHECKSUM_FILE="${ARTIFACT}.sha256"
if [ -f "${CHECKSUM_FILE}" ]; then
  if command -v shasum >/dev/null 2>&1; then
    (cd "$(dirname "${ARTIFACT}")" && shasum -a 256 -c "$(basename "${CHECKSUM_FILE}")")
  elif command -v sha256sum >/dev/null 2>&1; then
    (cd "$(dirname "${ARTIFACT}")" && sha256sum -c "$(basename "${CHECKSUM_FILE}")")
  else
    echo "No SHA-256 tool found for checksum verification." >&2
    exit 2
  fi
fi

RESTORE_ARCHIVE="${ARTIFACT}"
case "${ARTIFACT}" in
  *.enc)
    if [ -z "${PASSWORD}" ]; then
      echo "Encrypted offsite backup requires OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD or _FILE." >&2
      exit 2
    fi
    command -v openssl >/dev/null 2>&1 || {
      echo "openssl is required to decrypt this backup." >&2
      exit 2
    }
    RESTORE_ARCHIVE="${TMP_DIR}/decrypted-omniforum-backup.tar.gz"
    printf '%s' "${PASSWORD}" | openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
      -pass stdin -in "${ARTIFACT}" -out "${RESTORE_ARCHIVE}"
    ;;
esac

RESTORE_TARGET="${TMP_DIR}/omniforum-offsite-restore-check"
mkdir -p "${RESTORE_TARGET}"

echo "Copying source into offsite restore target..."
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

echo "Restoring offsite backup ${ARTIFACT} into ${RESTORE_TARGET}..."
"${RESTORE_TARGET}/scripts/restore_omniforum.sh" "${RESTORE_ARCHIVE}" "${RESTORE_TARGET}"

echo "Starting offsite-restored OmniForum on http://${HOST}:${PORT}..."
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
            print("Offsite restore verification passed.")
            raise SystemExit(0)
    except Exception as exc:
        last_error = str(exc)
    time.sleep(0.25)
raise SystemExit(f"Offsite restore verification failed: {last_error}")
PY
