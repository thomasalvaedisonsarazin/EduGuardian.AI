#!/bin/sh
# EduGuardian AI backend entrypoint:
#   1. ensure data dirs exist
#   2. run Alembic migrations (skip with SKIP_MIGRATIONS=1)
#   3. exec the container CMD (uvicorn by default)
set -eu

mkdir -p "${REPORTS_DIR:-/data/reports}" "${UPLOADS_DIR:-/data/uploads}"

if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
    echo "[entrypoint] Running database migrations (alembic upgrade head)..."
    attempt=1
    max_attempts="${MIGRATION_MAX_ATTEMPTS:-10}"
    until alembic upgrade head; do
        if [ "$attempt" -ge "$max_attempts" ]; then
            echo "[entrypoint] Migrations failed after ${attempt} attempts; exiting." >&2
            exit 1
        fi
        echo "[entrypoint] Migration attempt ${attempt} failed; retrying in 3s..." >&2
        attempt=$((attempt + 1))
        sleep 3
    done
    echo "[entrypoint] Migrations complete."
fi

if [ "$#" -eq 0 ]; then
    set -- uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

echo "[entrypoint] Starting: $*"
exec "$@"
