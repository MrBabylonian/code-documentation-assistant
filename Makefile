.PHONY: up down test-backend test-integration test-frontend lint eval e2e

up:
	docker compose up --build -d

down:
	docker compose down

test-backend:
	cd backend && uv run pytest tests/unit -v

test-integration:
	cd backend && uv run pytest -m integration -v

test-frontend:
	cd frontend && npm run test

lint:
	cd backend && uv run ruff check src tests && uv run mypy
	cd frontend && npm run lint && npm run typecheck

eval:
	cd backend && uv run python -m codedoc.evals.eval_runner --mode both

e2e:
	cd e2e && npm ci && npx playwright test
