#!/bin/zsh

set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h}"
DEFAULT_ENV_FILE="${REPO_ROOT}/ops/codex/local-dispatch.env"
ENV_FILE="${LOCAL_DISPATCH_ENV_FILE:-${DEFAULT_ENV_FILE}}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  source "${ENV_FILE}"
  set +a
fi

: "${NEWSLETTER_PYTHON_BIN:=python3}"
: "${NEWSLETTER_BUILD_ARCHIVE:=0}"
: "${NEWSLETTER_STATE_DIR:=${REPO_ROOT}/tmp/codex}"
: "${NEWSLETTER_DISPATCH_ORIGIN:=mac-studio-launchd}"

mkdir -p "${NEWSLETTER_STATE_DIR}"

LOCK_DIR="${NEWSLETTER_STATE_DIR}/local-dispatch.lock"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] another local dispatch run is still active; skipping"
  exit 0
fi

cleanup() {
  rmdir "${LOCK_DIR}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

cd "${REPO_ROOT}"
export NEWSLETTER_DISPATCH_ORIGIN
"${NEWSLETTER_PYTHON_BIN}" "${REPO_ROOT}/scripts/fetch_and_send.py"

if [[ "${NEWSLETTER_BUILD_ARCHIVE}" == "1" ]]; then
  "${NEWSLETTER_PYTHON_BIN}" "${REPO_ROOT}/scripts/build_archive_site.py"
fi
