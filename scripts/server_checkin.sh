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
WINDOW_START="${CHECKIN_WINDOW_START:-19:05}"
WINDOW_END="${CHECKIN_WINDOW_END:-22:35}"

mkdir -p "$STATE_DIR" "$LOG_DIR"

today="$(TZ="$TZ_NAME" date +%F)"
now_hm="$(TZ="$TZ_NAME" date +%H:%M)"
log_file="$LOG_DIR/server-checkin-$today.log"
success_file="$STATE_DIR/success-$today"
lock_dir="$STATE_DIR/lock"
dry_run=false
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    dry_run=true
  fi
done

exec > >(tee -a "$log_file") 2>&1

echo "[$(TZ="$TZ_NAME" date '+%F %T %Z')] 652 check-in script started"

if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "Another check-in process is running; skip."
  exit 0
fi
trap 'rmdir "$lock_dir" 2>/dev/null || true' EXIT

if [ -f "$success_file" ] && [ "$dry_run" != "true" ]; then
  echo "Already succeeded on $today; skip."
  exit 0
fi

if [ "${CHECKIN_IGNORE_WINDOW:-false}" != "true" ]; then
  if [[ "$now_hm" < "$WINDOW_START" || "$now_hm" > "$WINDOW_END" ]]; then
    echo "Current Beijing time $now_hm is outside $WINDOW_START-$WINDOW_END; skip."
    exit 0
  fi
fi

if [ -z "${QFHY_SESSION:-}" ] && [ -z "${CHECKIN_ACCOUNTS_JSON:-}" ] && [ -z "${CHECKIN_ACCOUNTS_FILE:-}" ]; then
  echo "Missing QFHY_SESSION, CHECKIN_ACCOUNTS_JSON, or CHECKIN_ACCOUNTS_FILE. Put it in $ENV_FILE."
  exit 2
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  python_bin="${CHECKIN_PYTHON:-}"
  if [ -z "$python_bin" ]; then
    if command -v python3 >/dev/null 2>&1; then
      python_bin="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
      python_bin="$(command -v python)"
    else
      echo "No python interpreter found. Set CHECKIN_PYTHON in $ENV_FILE."
      exit 2
    fi
  fi
  echo "Creating virtual environment with $python_bin"
  if ! "$python_bin" -m venv "$VENV_DIR"; then
    echo "Failed to create venv with $python_bin. Install python3-venv, or set CHECKIN_PYTHON to a Python that supports venv, for example a Conda Python."
    exit 2
  fi
fi

"$VENV_DIR/bin/python" -m pip install -q --disable-pip-version-check -r requirements-action.txt

export CHECKIN_TIMEZONE="$TZ_NAME"
export TZ="$TZ_NAME"

set +e
"$VENV_DIR/bin/python" -m app.cli.checkin_once --retry-on-no-task "$@"
code=$?
set -e

if [ "$code" -eq 0 ] && [ "$dry_run" != "true" ]; then
  {
    echo "date=$today"
    echo "time=$now_hm"
    echo "timezone=$TZ_NAME"
  } > "$success_file"
  echo "Check-in completed successfully; wrote $success_file."
elif [ "$code" -eq 0 ]; then
  echo "Dry-run completed successfully; success marker was not written."
elif [ "$code" -eq 3 ]; then
  echo "No pending check-in task yet; will retry at the next cron time."
  exit 0
else
  echo "Check-in failed with exit code $code."
fi

exit "$code"
