#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
TARGET="${OMNIFORUM_OFFSITE_BACKUP_TARGET:-}"
PASSWORD="${OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD:-}"
PASSWORD_FILE="${OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD_FILE:-}"

if [ -z "${TARGET}" ]; then
  cat >&2 <<'EOF'
Set OMNIFORUM_OFFSITE_BACKUP_TARGET before running.

Supported targets:
  local:/absolute/path
  rclone:remote:path
  s3://bucket/prefix
  rsync:user@host:/absolute/path

Set OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD or OMNIFORUM_BACKUP_ENCRYPTION_PASSWORD_FILE
to encrypt the offsite artifact before upload.
EOF
  exit 2
fi

if [ -n "${PASSWORD_FILE}" ]; then
  if [ ! -f "${PASSWORD_FILE}" ]; then
    echo "Password file not found: ${PASSWORD_FILE}" >&2
    exit 2
  fi
  PASSWORD="$(cat "${PASSWORD_FILE}")"
fi

BACKUP_OUTPUT="$(OMNIFORUM_BACKUP_ROTATION="${OMNIFORUM_BACKUP_ROTATION:-99}" "${PROJECT_DIR}/scripts/backup_omniforum.sh" "${PROJECT_DIR}")"
ARCHIVE="$(printf '%s\n' "${BACKUP_OUTPUT}" | awk '/Created / {print $2}' | tail -n 1)"

if [ ! -f "${ARCHIVE}" ]; then
  echo "Could not find local backup archive from output:" >&2
  printf '%s\n' "${BACKUP_OUTPUT}" >&2
  exit 1
fi

ARTIFACT="${ARCHIVE}"
if [ -n "${PASSWORD}" ]; then
  command -v openssl >/dev/null 2>&1 || {
    echo "openssl is required for encrypted offsite backups." >&2
    exit 2
  }
  ARTIFACT="${ARCHIVE}.enc"
  printf '%s' "${PASSWORD}" | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
    -pass stdin -in "${ARCHIVE}" -out "${ARTIFACT}"
fi

CHECKSUM_FILE="${ARTIFACT}.sha256"
if command -v shasum >/dev/null 2>&1; then
  (cd "$(dirname "${ARTIFACT}")" && shasum -a 256 "$(basename "${ARTIFACT}")" >"$(basename "${CHECKSUM_FILE}")")
elif command -v sha256sum >/dev/null 2>&1; then
  (cd "$(dirname "${ARTIFACT}")" && sha256sum "$(basename "${ARTIFACT}")" >"$(basename "${CHECKSUM_FILE}")")
else
  echo "No SHA-256 tool found." >&2
  exit 2
fi

copy_local() {
  local destination="${1}"
  mkdir -p "${destination}"
  cp "${ARTIFACT}" "${CHECKSUM_FILE}" "${destination}/"
  echo "Copied offsite backup to local:${destination}/$(basename "${ARTIFACT}")"
}

case "${TARGET}" in
  local:*)
    copy_local "${TARGET#local:}"
    ;;
  rclone:*)
    command -v rclone >/dev/null 2>&1 || {
      echo "rclone target requested but rclone is not installed." >&2
      exit 2
    }
    rclone copy "${ARTIFACT}" "${CHECKSUM_FILE}" "${TARGET#rclone:}"
    echo "Copied offsite backup with rclone to ${TARGET#rclone:}"
    ;;
  s3://*)
    command -v aws >/dev/null 2>&1 || {
      echo "s3 target requested but aws CLI is not installed." >&2
      exit 2
    }
    aws s3 cp "${ARTIFACT}" "${TARGET%/}/$(basename "${ARTIFACT}")"
    aws s3 cp "${CHECKSUM_FILE}" "${TARGET%/}/$(basename "${CHECKSUM_FILE}")"
    echo "Copied offsite backup to ${TARGET%/}/$(basename "${ARTIFACT}")"
    ;;
  rsync:*)
    command -v rsync >/dev/null 2>&1 || {
      echo "rsync target requested but rsync is not installed." >&2
      exit 2
    }
    rsync -av "${ARTIFACT}" "${CHECKSUM_FILE}" "${TARGET#rsync:}/"
    echo "Copied offsite backup with rsync to ${TARGET#rsync:}/$(basename "${ARTIFACT}")"
    ;;
  *)
    echo "Unsupported OMNIFORUM_OFFSITE_BACKUP_TARGET: ${TARGET}" >&2
    exit 2
    ;;
esac

echo "Offsite backup artifact: ${ARTIFACT}"
echo "Offsite backup checksum: ${CHECKSUM_FILE}"
