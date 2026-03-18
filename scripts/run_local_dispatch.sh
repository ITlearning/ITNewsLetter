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
: "${NEWSLETTER_GIT_PUSH_AFTER_RUN:=0}"
: "${NEWSLETTER_GIT_REMOTE:=origin}"
: "${NEWSLETTER_GIT_BRANCH:=main}"
: "${NEWSLETTER_GIT_AUTHOR_NAME:=ITNewsLetter Bot}"
: "${NEWSLETTER_GIT_AUTHOR_EMAIL:=41898282+github-actions[bot]@users.noreply.github.com}"
: "${NEWSLETTER_GIT_COMMIT_MESSAGE:=chore: update newsletter state}"

mkdir -p "${NEWSLETTER_STATE_DIR}"

LOCK_DIR="${NEWSLETTER_STATE_DIR}/local-dispatch.lock"
LOCK_PID_FILE="${LOCK_DIR}/pid"
TMP_WORKTREE_PARENT=""
TMP_WORKTREE=""
STATE_FILES=(
  "data/state.json"
  "data/news.json"
  "data/last_run.json"
)

acquire_lock() {
  if mkdir "${LOCK_DIR}" 2>/dev/null; then
    print -r -- "$$" > "${LOCK_PID_FILE}"
    return 0
  fi

  local existing_pid=""
  if [[ -f "${LOCK_PID_FILE}" ]]; then
    existing_pid="$(<"${LOCK_PID_FILE}")"
  fi

  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] another local dispatch run is still active; skipping"
    return 1
  fi

  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] removing stale local dispatch lock"
  rm -f "${LOCK_PID_FILE}" >/dev/null 2>&1 || true
  rmdir "${LOCK_DIR}" 2>/dev/null || true

  if mkdir "${LOCK_DIR}" 2>/dev/null; then
    print -r -- "$$" > "${LOCK_PID_FILE}"
    return 0
  fi

  print -u2 -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] failed to acquire local dispatch lock"
  return 1
}

if ! acquire_lock; then
  exit 0
fi

cleanup() {
  if [[ -n "${TMP_WORKTREE}" && -d "${TMP_WORKTREE}" ]]; then
    (
      cd "${REPO_ROOT}"
      git worktree remove --force "${TMP_WORKTREE}"
    ) >/dev/null 2>&1 || rm -rf "${TMP_WORKTREE}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${TMP_WORKTREE_PARENT}" && -d "${TMP_WORKTREE_PARENT}" ]]; then
    rm -rf "${TMP_WORKTREE_PARENT}" >/dev/null 2>&1 || true
  fi
  rm -f "${LOCK_PID_FILE}" >/dev/null 2>&1 || true
  rmdir "${LOCK_DIR}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

cd "${REPO_ROOT}"
export NEWSLETTER_DISPATCH_ORIGIN
"${NEWSLETTER_PYTHON_BIN}" "${REPO_ROOT}/scripts/fetch_and_send.py"

if [[ "${NEWSLETTER_BUILD_ARCHIVE}" == "1" ]]; then
  "${NEWSLETTER_PYTHON_BIN}" "${REPO_ROOT}/scripts/build_archive_site.py"
fi

if [[ "${NEWSLETTER_GIT_PUSH_AFTER_RUN}" == "1" ]]; then
  if ! command -v git >/dev/null 2>&1; then
    print -u2 -r -- "git was not found on PATH"
    exit 127
  fi

  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] syncing newsletter state to ${NEWSLETTER_GIT_REMOTE}/${NEWSLETTER_GIT_BRANCH}"
  git -C "${REPO_ROOT}" fetch "${NEWSLETTER_GIT_REMOTE}" "${NEWSLETTER_GIT_BRANCH}"

  TMP_WORKTREE_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/itnewsletter-sync.XXXXXX")"
  TMP_WORKTREE="${TMP_WORKTREE_PARENT}/repo"
  git -C "${REPO_ROOT}" worktree add --detach "${TMP_WORKTREE}" "${NEWSLETTER_GIT_REMOTE}/${NEWSLETTER_GIT_BRANCH}"

  for relative_path in "${STATE_FILES[@]}"; do
    if [[ ! -f "${REPO_ROOT}/${relative_path}" ]]; then
      print -u2 -r -- "expected state file missing: ${relative_path}"
      exit 1
    fi
    mkdir -p "${TMP_WORKTREE}/${relative_path:h}"
    cp "${REPO_ROOT}/${relative_path}" "${TMP_WORKTREE}/${relative_path}"
  done

  if [[ -n "$(git -C "${TMP_WORKTREE}" status --porcelain -- "${STATE_FILES[@]}")" ]]; then
    git -C "${TMP_WORKTREE}" config user.name "${NEWSLETTER_GIT_AUTHOR_NAME}"
    git -C "${TMP_WORKTREE}" config user.email "${NEWSLETTER_GIT_AUTHOR_EMAIL}"
    git -C "${TMP_WORKTREE}" add -- "${STATE_FILES[@]}"
    git -C "${TMP_WORKTREE}" commit -m "${NEWSLETTER_GIT_COMMIT_MESSAGE}"
    git -C "${TMP_WORKTREE}" push "${NEWSLETTER_GIT_REMOTE}" "HEAD:${NEWSLETTER_GIT_BRANCH}"
  else
    print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] no state changes to push"
  fi
fi
