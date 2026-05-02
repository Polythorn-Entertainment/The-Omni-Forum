#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${PROJECT_DIR}/data"

if [ ! -d "${DATA_DIR}" ]; then
  echo "Data directory not found: ${DATA_DIR}" >&2
  exit 1
fi

if [ "${OMNIFORUM_CONFIRM_RESET:-}" != "yes" ]; then
  cat >&2 <<EOF
This removes local OmniForum runtime state:
  - data/*.db and SQLite sidecar files
  - data/logs/*
  - data/exports/*
  - data/uploads/{avatars,posts,thumbs}/*

It keeps data/README.md and recreates the runtime directories.

Run again with:
  OMNIFORUM_CONFIRM_RESET=yes $0 ${PROJECT_DIR}
EOF
  exit 2
fi

find "${DATA_DIR}" -maxdepth 1 -type f \( -name "*.db" -o -name "*.db-*" \) -delete

for folder in logs exports uploads/avatars uploads/posts uploads/thumbs; do
  rm -rf "${DATA_DIR:?}/${folder}"
  mkdir -p "${DATA_DIR}/${folder}"
  touch "${DATA_DIR}/${folder}/.gitkeep"
done

echo "Runtime data reset in ${DATA_DIR}"
echo "Start OmniForum to recreate empty SQLite databases and seeded sections."
