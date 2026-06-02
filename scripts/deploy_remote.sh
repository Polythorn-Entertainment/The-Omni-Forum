#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
HOST="${OMNIFORUM_DEPLOY_HOST:-}"
USER="${OMNIFORUM_DEPLOY_USER:-}"
APP_DIR="${OMNIFORUM_DEPLOY_PATH:-/var/www/omniforum}"
SERVICE="${OMNIFORUM_DEPLOY_SERVICE:-omniforum}"
SSH_BIN="${OMNIFORUM_DEPLOY_SSH_BIN:-ssh}"
SCP_BIN="${OMNIFORUM_DEPLOY_SCP_BIN:-scp}"
SSH_OPTS="${OMNIFORUM_DEPLOY_SSH_OPTS:-}"
INSTALL_DEPS="${OMNIFORUM_DEPLOY_INSTALL_DEPS:-1}"
RESTART_SERVICE="${OMNIFORUM_DEPLOY_RESTART_SERVICE:-1}"
RUN_READINESS="${OMNIFORUM_DEPLOY_RUN_READINESS:-1}"
PUBLIC_URL="${OMNIFORUM_DEPLOY_PUBLIC_URL:-}"

if [ "${OMNIFORUM_DEPLOY_CONFIRM:-}" != "yes" ]; then
  cat >&2 <<'EOF'
Refusing to deploy without OMNIFORUM_DEPLOY_CONFIRM=yes.

Required:
  OMNIFORUM_DEPLOY_HOST=example.com

Recommended:
  OMNIFORUM_DEPLOY_USER=deploy
  OMNIFORUM_DEPLOY_PATH=/var/www/omniforum
  OMNIFORUM_DEPLOY_SERVICE=omniforum
  OMNIFORUM_DEPLOY_PUBLIC_URL=https://forum.example.com

This script uploads a clean source package, preserves remote data/ and .env,
installs Python dependencies, restarts the systemd service, and optionally
runs the public readiness probe.
EOF
  exit 2
fi

if [ -z "${HOST}" ]; then
  echo "OMNIFORUM_DEPLOY_HOST is required." >&2
  exit 2
fi

REMOTE="${HOST}"
if [ -n "${USER}" ]; then
  REMOTE="${USER}@${HOST}"
fi

OUT_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${OUT_DIR}"
}
trap cleanup EXIT

"${PROJECT_DIR}/scripts/package_release.sh" "${PROJECT_DIR}" "${OUT_DIR}"
ARCHIVE="$(ls -1 "${OUT_DIR}"/omniforum-source-*.tar.gz | tail -n 1)"
REMOTE_ARCHIVE="/tmp/$(basename "${ARCHIVE}")"

echo "Uploading clean package to ${REMOTE}:${REMOTE_ARCHIVE}"
# shellcheck disable=SC2086
"${SCP_BIN}" ${SSH_OPTS} "${ARCHIVE}" "${REMOTE}:${REMOTE_ARCHIVE}"

REMOTE_SCRIPT="$(mktemp)"
cat >"${REMOTE_SCRIPT}" <<'REMOTE_EOF'
set -euo pipefail

archive="$1"
app_dir="$2"
service="$3"
install_deps="$4"
restart_service="$5"

release_dir="$(mktemp -d)"
cleanup() {
  rm -rf "${release_dir}" "${archive}"
}
trap cleanup EXIT

mkdir -p "${app_dir}"
tar -xzf "${archive}" -C "${release_dir}"

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on the remote host for safe deploy sync." >&2
  exit 2
fi

rsync -a --delete \
  --exclude ".env" \
  --exclude "data/" \
  --exclude "deploy/omniforum-healthcheck.env" \
  --exclude "deploy/omniforum-offsite-backup.env" \
  "${release_dir}/" "${app_dir}/"

mkdir -p \
  "${app_dir}/data/logs" \
  "${app_dir}/data/exports" \
  "${app_dir}/data/uploads/avatars" \
  "${app_dir}/data/uploads/posts" \
  "${app_dir}/data/uploads/thumbs"
touch \
  "${app_dir}/data/logs/.gitkeep" \
  "${app_dir}/data/exports/.gitkeep" \
  "${app_dir}/data/uploads/avatars/.gitkeep" \
  "${app_dir}/data/uploads/posts/.gitkeep" \
  "${app_dir}/data/uploads/thumbs/.gitkeep"

if [ ! -f "${app_dir}/.env" ]; then
  echo "WARNING: ${app_dir}/.env does not exist. Copy .env.example and set production values before starting." >&2
fi

if [ "${install_deps}" = "1" ]; then
  python3 -m pip install -r "${app_dir}/requirements.txt"
fi

if [ "${restart_service}" = "1" ]; then
  sudo systemctl daemon-reload
  sudo systemctl restart "${service}"
  sudo systemctl --no-pager --full status "${service}" >/dev/null
fi

echo "Remote deploy sync complete: ${app_dir}"
REMOTE_EOF

echo "Applying package on remote host"
# shellcheck disable=SC2086
"${SSH_BIN}" ${SSH_OPTS} "${REMOTE}" "bash -s -- '${REMOTE_ARCHIVE}' '${APP_DIR}' '${SERVICE}' '${INSTALL_DEPS}' '${RESTART_SERVICE}'" <"${REMOTE_SCRIPT}"
rm -f "${REMOTE_SCRIPT}"

if [ "${RUN_READINESS}" = "1" ] && [ -n "${PUBLIC_URL}" ]; then
  echo "Running public readiness probe for ${PUBLIC_URL}"
  "${PROJECT_DIR}/scripts/production_readiness.py" --url "${PUBLIC_URL}"
  "${PROJECT_DIR}/scripts/healthcheck.py" "${PUBLIC_URL}"
fi

echo "Deploy completed for ${REMOTE}:${APP_DIR}"
