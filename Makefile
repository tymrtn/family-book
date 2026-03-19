.PHONY: dev test seed migrate build clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Start dev server with auto-reload
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test: ## Run the test suite
	uv run pytest

test-v: ## Run tests with verbose output
	uv run pytest -v

seed: ## Load demo family data
	uv run python -m app.seed

migrate: ## Run database migrations (alembic upgrade head)
	uv run alembic upgrade head

migration: ## Create a new migration (usage: make migration m="description")
	uv run alembic revision --autogenerate -m "$(m)"

rollback: ## Rollback last migration
	uv run alembic downgrade -1

build: ## Build Docker image
	docker build -t family-book .

up: ## Start with Docker Compose
	docker compose up -d

down: ## Stop Docker Compose
	docker compose down

logs: ## Tail Docker Compose logs
	docker compose logs -f familybook

setup: ## First-time setup: copy .env, install deps, create DB, seed
	@test -f .env || cp .env.example .env
	uv sync
	uv run alembic upgrade head
	@echo ""
	@echo "✅ Setup complete. Edit .env with your SECRET_KEY and FERNET_KEY, then run: make dev"

clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache htmlcov .coverage
