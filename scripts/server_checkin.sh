#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${CHECKIN_ENV_FILE:-$ROOT_DIR/.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

STATE_DIR="${CHECKIN_STATE_DIR:-$ROOT_DIR/.checkin-state}"
LOG_DIR="${CHECKIN_LOG_DIR:-$ROOT_DIR/logs}"
VENV_DIR="${CHECKIN_VENV_DIR:-$ROOT_DIR/.venv-server}"
TZ_NAME="${CHECKIN_TIMEZONE:-Asia/Shanghai}"
WINDOW_START="${CHECKIN_WINDOW_START:-19:31}"
WINDOW_END="${CHECKIN_WINDOW_END:-23:55}"

mkdir -p "$STATE_DIR" "$LOG_DIR"

today="$(TZ="$TZ_NAME" date +%F)"
now_hm="$(TZ="$TZ_NAME" date +%H:%M)"
log_file="$LOG_DIR/server-checkin-$today.log"
success_file="$STATE_DIR/success-$today"
lock_dir="$STATE_DIR/lock"

exec > >(tee -a "$log_file") 2>&1

echo "[$(TZ="$TZ_NAME" date '+%F %T %Z')] 652 check-in script started"

if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "Another check-in process is running; skip."
  exit 0
fi
trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT

if [ -f "$success_file" ]; then
  echo "Already succeeded on $today; skip."
  exit 0
fi

if [ "${CHECKIN_IGNORE_WINDOW:-false}" != "true" ]; then
  if [[ "$now_hm" < "$WINDOW_START" || "$now_hm" > "$WINDOW_END" ]]; then
    echo "Current Beijing time $now_hm is outside $WINDOW_START-$WINDOW_END; skip."
    exit 0
  fi
fi

if [ -z "${QFHY_SESSION:-}" ] && [ -z "${CHECKIN_ACCOUNTS_JSON:-}" ]; then
  echo "Missing QFHY_SESSION or CHECKIN_ACCOUNTS_JSON. Put it in $ENV_FILE."
  exit 2
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install -q --disable-pip-version-check -r requirements-action.txt

export CHECKIN_TIMEZONE="$TZ_NAME"
export TZ="$TZ_NAME"

set +e
"$VENV_DIR/bin/python" -m app.cli.checkin_once "$@"
code=$?
set -e

if [ "$code" -eq 0 ]; then
  {
    echo "date=$today"
    echo "time=$now_hm"
    echo "timezone=$TZ_NAME"
  } > "$success_file"
  echo "Check-in completed successfully; wrote $success_file."
else
  echo "Check-in failed with exit code $code."
fi

exit "$code"
