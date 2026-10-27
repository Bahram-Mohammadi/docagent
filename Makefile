.PHONY: help setup lint format typecheck test check clean docker-build docker-run docker-stop

NAME      := docagent-api
IMAGE     := $(NAME):dev
CONTAINER := $(NAME)

help:  ## Show available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

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
	uv run pytest --cov --cov-report=term-missing

check: lint typecheck test  ## Everything CI runs

clean:  ## Remove caches
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov

# Docker

docker-build:  ## Build the API Docker image
	docker build -f services/api/Dockerfile -t $(IMAGE) .

docker-run:  ## Run the API Docker container
	docker run --rm -d -p 127.0.0.1:8000:8000 --name $(CONTAINER) $(IMAGE)

docker-stop:  ## Stop the API Docker container
	docker stop $(CONTAINER) || true
