#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA_DIR="${PROJECT_DIR}/data"

cat <<EOF
This scrub prepares a source handoff by deleting private runtime state:
  - sessions and all SQLite databases
  - logs and local backup archives
  - uploaded avatars, post media, and thumbnails
  - restore snapshots named data-pre-restore-*

It does not delete .env, because secrets should be reviewed manually.
If .env contains real secrets or webhook URLs, rotate them before sharing.
EOF

if [ "${OMNIFORUM_CONFIRM_SCRUB:-}" != "yes" ]; then
  echo
  echo "Run again with:"
  echo "  OMNIFORUM_CONFIRM_SCRUB=yes $0 ${PROJECT_DIR}"
  exit 2
fi

OMNIFORUM_CONFIRM_RESET=yes "${PROJECT_DIR}/scripts/reset_runtime_data.sh" "${PROJECT_DIR}"
find "${PROJECT_DIR}" -maxdepth 1 -type d -name "data-pre-restore-*" -exec rm -rf {} +

echo "Private runtime data scrubbed. Review .env manually before sharing."
