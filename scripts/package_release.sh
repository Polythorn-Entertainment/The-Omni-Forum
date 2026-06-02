#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
OUT_DIR="${2:-${PROJECT_DIR}/dist}"
VERSION="${OMNIFORUM_RELEASE_VERSION:-$(date -u +"%Y%m%d-%H%M%S")}"
ARCHIVE="${OUT_DIR}/omniforum-source-${VERSION}.tar.gz"

mkdir -p "${OUT_DIR}"

tar -czf "${ARCHIVE}" -C "${PROJECT_DIR}" \
  --exclude="./.env" \
  --exclude="./deploy/omniforum-healthcheck.env" \
  --exclude="./deploy/omniforum-offsite-backup.env" \
  --exclude="./deploy/omniforum-remote-deploy.env" \
  --exclude="./.venv" \
  --exclude="./venv" \
  --exclude="./dist" \
  --exclude="./__pycache__" \
  --exclude="./__pycache__/*" \
  --exclude="*/__pycache__" \
  --exclude="*/__pycache__/*" \
  --exclude="*.pyc" \
  --exclude=".DS_Store" \
  --exclude="./data/*.db" \
  --exclude="./data/*.db-*" \
  --exclude="./data/logs/*" \
  --exclude="./data/exports/*" \
  --exclude="./data/uploads/avatars/*" \
  --exclude="./data/uploads/posts/*" \
  --exclude="./data/uploads/thumbs/*" \
  --exclude="./data-pre-restore-*" \
  .

echo "Created clean source package: ${ARCHIVE}"
echo "Runtime data, local env files, caches, uploads, logs, and backups were excluded."
