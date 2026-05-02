#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${PROJECT_DIR}/data"
BACKUP_DIR="${DATA_DIR}/exports/backups"
ROTATION="${OMNIFORUM_BACKUP_ROTATION:-8}"

mkdir -p "${BACKUP_DIR}"

STAMP="$(date -u +"%Y%m%d-%H%M%S")"
ARCHIVE="${BACKUP_DIR}/omniforum-manual-${STAMP}.tar.gz"
TMP_ARCHIVE="$(mktemp "${PROJECT_DIR}/omniforum-manual-${STAMP}.XXXXXX.tar.gz")"

tar -czf "${TMP_ARCHIVE}" -C "${PROJECT_DIR}" \
  --exclude="data/exports/backups/*" \
  data
mv "${TMP_ARCHIVE}" "${ARCHIVE}"

ls -1t "${BACKUP_DIR}"/omniforum-manual-*.tar.gz 2>/dev/null | tail -n +"$((ROTATION + 1))" | while read -r old; do
  rm -f "${old}"
done

echo "Created ${ARCHIVE}"
