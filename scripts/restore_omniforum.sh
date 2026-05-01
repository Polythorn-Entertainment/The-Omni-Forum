#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 /absolute/path/to/omniforum-backup-YYYYMMDD-HHMMSS.zip [/absolute/path/to/project]" >&2
  exit 1
fi

ARCHIVE_PATH="$1"
PROJECT_DIR="${2:-$(pwd)}"

if [ ! -f "$ARCHIVE_PATH" ]; then
  echo "Backup archive not found: $ARCHIVE_PATH" >&2
  exit 1
fi

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

DATA_DIR="$PROJECT_DIR/data"
TMP_DIR="$(mktemp -d)"
STAMP="$(date +%Y%m%d-%H%M%S)"
SNAPSHOT_DIR="$PROJECT_DIR/data-pre-restore-$STAMP"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Extracting $ARCHIVE_PATH into a temporary workspace..."
unzip -q "$ARCHIVE_PATH" -d "$TMP_DIR"

if [ ! -d "$TMP_DIR/data" ]; then
  echo "The archive does not contain a data/ directory." >&2
  exit 1
fi

if [ -d "$DATA_DIR" ]; then
  echo "Saving current data directory to $SNAPSHOT_DIR"
  mv "$DATA_DIR" "$SNAPSHOT_DIR"
fi

echo "Restoring backup data into $DATA_DIR"
mkdir -p "$DATA_DIR"
cp -R "$TMP_DIR/data/." "$DATA_DIR/"

echo
echo "Restore complete."
echo "Previous data snapshot: $SNAPSHOT_DIR"
echo "Next steps:"
echo "1. Start OmniForum again."
echo "2. Visit /api/health and the homepage."
echo "3. Sign in with an admin account and confirm the expected data is present."
