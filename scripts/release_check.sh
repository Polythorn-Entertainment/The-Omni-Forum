#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
NODE_BIN="${NODE_BIN:-node}"
OUT_DIR="${OMNIFORUM_RELEASE_CHECK_OUT:-/tmp/omniforum-release-check}"

cd "${PROJECT_DIR}"

echo "== Python compile =="
"${PYTHON_BIN}" -m py_compile app.py omniforum/*.py scripts/*.py tests/*.py

echo "== Python lint =="
"${PYTHON_BIN}" -m ruff check .

echo "== JavaScript syntax =="
for file in js/*.js; do
  "${NODE_BIN}" --check "$file"
done

echo "== Frontend assets =="
scripts/generate_assets.py --check
scripts/check_frontend.py
scripts/build_assets.py "${OUT_DIR}/assets"

echo "== Schema and operator checks =="
scripts/check_migrations.py
scripts/migration_status.py --allow-pending
scripts/security_check.py
scripts/production_readiness.py

echo "== Shell syntax =="
bash -n scripts/*.sh

echo "== Tests =="
"${PYTHON_BIN}" -m unittest discover -s tests -v

echo "== Restore verification =="
scripts/verify_restore.sh

echo "== Clean package leak scan =="
scripts/package_release.sh "${PROJECT_DIR}" "${OUT_DIR}/release"
archive="$(ls -1 "${OUT_DIR}"/release/omniforum-source-*.tar.gz | tail -n 1)"
scripts/check_release_archive.py "$archive"

echo "Release check passed: ${archive}"
