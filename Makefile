# EduGuardian AI convenience targets (requires GNU make + docker compose v2).
DEV = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: help env config up down logs build dev dev-down dev-logs migrate shell psql test lint clean

help:
	@echo "env       - create .env from .env.example (if missing)"
	@echo "config    - validate compose files"
	@echo "up        - build + start prod-like stack (frontend :3000, backend :8000)"
	@echo "down      - stop prod-like stack"
	@echo "dev       - start dev stack with hot reload (frontend :5173, backend :8000, db :5433)"
	@echo "dev-down  - stop dev stack"
	@echo "migrate   - run alembic upgrade head in backend container"
	@echo "test      - run backend pytest in dev backend container"
	@echo "clean     - stop everything and delete volumes (DESTROYS DATA)"

env:
	@test -f .env || cp .env.example .env

config:
	docker compose config -q
	$(DEV) config -q

up: env
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend

build:
	docker compose build

dev: env
	$(DEV) up --build

dev-down:
	$(DEV) down

dev-logs:
	$(DEV) logs -f

migrate:
	docker compose exec backend alembic upgrade head

shell:
	docker compose exec backend sh

psql:
	docker compose exec db psql -U edu -d eduguardian

test:
	$(DEV) run --rm -e SKIP_MIGRATIONS=1 backend pytest --cov=app

lint:
	$(DEV) run --rm -e SKIP_MIGRATIONS=1 backend ruff check .

clean:
	docker compose down -v
	$(DEV) down -v
