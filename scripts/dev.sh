#!/bin/sh
# EduGuardian AI dev helper.
# Usage: scripts/dev.sh [up|down|logs|migrate|seed|test|psql|prod-up|prod-down|config]
set -eu

cd "$(dirname "$0")/.."

DEV="docker compose -f docker-compose.yml -f docker-compose.dev.yml"

[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example"; }

cmd="${1:-up}"
shift 2>/dev/null || true

case "$cmd" in
    up)        $DEV up --build "$@" ;;
    down)      $DEV down "$@" ;;
    logs)      $DEV logs -f "$@" ;;
    migrate)   $DEV exec backend alembic upgrade head ;;
    seed)      $DEV exec backend python -m app.seed "$@" ;;
    test)      $DEV run --rm -e SKIP_MIGRATIONS=1 backend pytest --cov=app "$@" ;;
    psql)      $DEV exec db psql -U edu -d eduguardian ;;
    prod-up)   docker compose up -d --build "$@" ;;
    prod-down) docker compose down "$@" ;;
    config)    docker compose config -q && $DEV config -q && echo "compose config OK" ;;
    *)         echo "Unknown command: $cmd" >&2; exit 1 ;;
esac
