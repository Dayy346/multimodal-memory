.PHONY: up down logs ps rebuild db-migrate api dev-frontend backfill-thumbs mark-job-completed

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

# Regenerate JPEG thumbnails for an existing job (HEIC fix). JOB_ID=uuid make backfill-thumbs
backfill-thumbs:
	docker compose exec api python scripts/backfill_thumbnails.py --job-id $(JOB_ID)

# Stop a stuck job in Postgres (works when API has no /cancel route). JOB_ID=uuid make mark-job-completed
mark-job-completed:
	docker compose exec db psql -U mm -d multimodal_memory -c \
		"UPDATE jobs SET status='completed', step='done', message='Stopped manually', error=NULL, updated_at=NOW() WHERE id='$(JOB_ID)';"

# Local-only (no Docker) — prefer `make up` on the homelab
api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm install && npm run dev -- --host
