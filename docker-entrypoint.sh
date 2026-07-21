#!/usr/bin/env sh
set -eu

PYTHON="/opt/venv/bin/python"
PAYROLLCTL="/opt/venv/bin/payrollctl"
DRAMATIQ="/opt/venv/bin/dramatiq"

is_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|on|ON)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

if [ ! -x "$PYTHON" ]; then
  echo "[entrypoint] ERROR: python not found at $PYTHON" >&2
  exit 1
fi

if [ ! -x "$PAYROLLCTL" ]; then
  echo "[entrypoint] ERROR: payrollctl not found at $PAYROLLCTL" >&2
  exit 1
fi

if [ ! -x "$DRAMATIQ" ]; then
  echo "[entrypoint] ERROR: dramatiq not found at $DRAMATIQ" >&2
  exit 1
fi

# Determine process role
# Options: web (only app), worker (only Dramatiq), all (app + worker in same container)
PROCESS_ROLE="${PROCESS_ROLE:-all}"

echo "[entrypoint] Process role: $PROCESS_ROLE"

# Database initialization only for web or all roles
if [ "$PROCESS_ROLE" = "web" ] || [ "$PROCESS_ROLE" = "all" ]; then
  echo "[entrypoint] Initializing database: payrollctl database init"
  $PAYROLLCTL database init || true

  echo "[entrypoint] Running migrations: payrollctl database migrate"
  $PAYROLLCTL database migrate || true
fi

# Worker configuration
QUEUE_ENABLED="${QUEUE_ENABLED:-1}"
REDIS_URL="${REDIS_URL:-${CACHE_REDIS_URL:-}}"
WORKER_THREADS="${DRAMATIQ_WORKER_THREADS:-8}"
WORKER_PROCESSES="${DRAMATIQ_WORKER_PROCESSES:-2}"

# Start Dramatiq worker based on role
if [ "$PROCESS_ROLE" = "worker" ]; then
  # Dedicated worker mode: only run Dramatiq worker
  if is_true "$QUEUE_ENABLED" && [ -n "$REDIS_URL" ]; then
    echo "[entrypoint] Starting Dramatiq worker (dedicated mode, threads=$WORKER_THREADS, processes=$WORKER_PROCESSES)"
    exec "$DRAMATIQ" coati_payroll.queue.tasks --threads "$WORKER_THREADS" --processes "$WORKER_PROCESSES"
  else
    echo "[entrypoint] ERROR: Worker role requires QUEUE_ENABLED=1 and REDIS_URL to be configured" >&2
    exit 1
  fi
elif [ "$PROCESS_ROLE" = "all" ]; then
  # All-in-one mode: worker in background + app (for development or small deployments)
  if is_true "$QUEUE_ENABLED" && [ -n "$REDIS_URL" ]; then
    echo "[entrypoint] Starting Dramatiq worker in background (all-in-one mode, threads=$WORKER_THREADS, processes=$WORKER_PROCESSES)"
    "$DRAMATIQ" coati_payroll.queue.tasks --threads "$WORKER_THREADS" --processes "$WORKER_PROCESSES" &
  else
    echo "[entrypoint] Dramatiq worker not started (QUEUE_ENABLED=$QUEUE_ENABLED, REDIS_URL configured=$([ -n "$REDIS_URL" ] && echo yes || echo no))"
  fi
  echo "[entrypoint] Starting app: $*"
  exec "$PYTHON" app.py
elif [ "$PROCESS_ROLE" = "web" ]; then
  # Web-only mode: no worker (worker runs in separate container)
  echo "[entrypoint] Starting app in web-only mode (no worker): $*"
  exec "$PYTHON" app.py
else
  echo "[entrypoint] ERROR: Invalid PROCESS_ROLE='$PROCESS_ROLE'. Valid options: web, worker, all" >&2
  exit 1
fi