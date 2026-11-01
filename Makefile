.PHONY: help setup lint format typecheck test check clean \
        docker-build docker-run docker-stop \
        up down reset logs ps smoke

.DEFAULT_GOAL := help

NAME      := docagent-api
IMAGE     := $(NAME):dev
CONTAINER := $(NAME)
COMPOSE   := docker compose
SERVICE   ?=

help:  ## Show available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

# --- Development ------------------------------------------------------------

setup:  ## Install dependencies and git hooks
	uv sync
	uv run pre-commit install

lint:  ## Check code style
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-fix code style
	uv run ruff check --fix .
	uv run ruff format .

typecheck:  ## Run mypy
	uv run mypy

test:  ## Run tests with coverage
	uv run pytest --cov --cov-report=term-missing -m "not gpu"

check: lint typecheck test  ## Everything CI runs

clean:  ## Remove caches
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov

# --- Single container (API only) --------------------------------------------

docker-build:  ## Build the API Docker image
	docker build -f services/api/Dockerfile -t $(IMAGE) .

docker-run:  ## Run the API container alone (no Qdrant)
	docker run --rm -d -p 127.0.0.1:8000:8000 --name $(CONTAINER) $(IMAGE)

docker-stop:  ## Stop the API container
	docker stop $(CONTAINER) || true

# --- Full stack (Docker Compose) --------------------------------------------

up:  ## Build and start all services, wait until healthy
	$(COMPOSE) up -d --build --wait

down:  ## Stop all services (keeps Qdrant data)
	$(COMPOSE) down

reset:  ## Stop all services and DELETE Qdrant data
	@printf 'This deletes all Qdrant data. Type "yes" to continue: '; \
	read answer; \
	[ "$$answer" = "yes" ] || { echo "Aborted."; exit 1; }
	$(COMPOSE) down -v

logs:  ## Follow logs (one service: make logs SERVICE=api)
	$(COMPOSE) logs -f $(SERVICE)

ps:  ## List services, including stopped ones
	$(COMPOSE) ps -a

smoke:  ## Run the end-to-end smoke test on a throwaway stack
	bash scripts/smoke.sh
