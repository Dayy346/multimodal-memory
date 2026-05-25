.PHONY: up down logs ps rebuild db-migrate api dev-frontend

# Start Postgres + API + web UI (one command, one browser URL)
up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

rebuild:
	docker compose up -d --build --force-recreate

db-migrate:
	docker compose run --rm api alembic upgrade head

# Local-only (no Docker) — prefer `make up` on the homelab
api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm install && npm run dev -- --host
