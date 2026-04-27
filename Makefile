.PHONY: up down db-migrate api dev-frontend

up:
	docker compose up -d

down:
	docker compose down

db-migrate:
	alembic upgrade head

api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm install && npm run dev
