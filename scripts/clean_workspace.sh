#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"

find "$ROOT" \
  \( -name "__pycache__" -type d -prune -exec rm -rf {} + \) -o \
  \( -name ".DS_Store" -type f -delete \) -o \
  \( -name "*.pyc" -type f -delete \)

find "$ROOT" -maxdepth 1 -type d -name "data-pre-restore-*" -exec rm -rf {} +
rm -rf "$ROOT/.pytest_cache" "$ROOT/.mypy_cache" "$ROOT/.ruff_cache" "$ROOT/htmlcov"
rm -f "$ROOT/.coverage"

echo "Workspace cleanup complete."
