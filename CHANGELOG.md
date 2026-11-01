# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Project skeleton: folder structure, `pyproject.toml` (uv), shared settings module.
- Tooling: ruff, mypy, pytest with coverage, pre-commit hooks, Makefile.
- CI workflow running lint, type checks and tests on every pull request.
- API service (FastAPI) with a `GET /health` endpoint that reports service status and version.
- Docker image for the API service: multi-stage build, non-root user and a health check, with `make docker-build`, `make docker-run` and `make docker-stop`.
- CI builds the API Docker image on every pull request.
- Docker Compose stack with Qdrant (`qdrant/qdrant:v1.20.0`) and the API. Qdrant has a health check, the API starts only once Qdrant is healthy, data is kept in the named volume `qdrant_data`, and ports are bound to `127.0.0.1` only.
- `GET /ready` readiness endpoint: returns `200` when Qdrant is reachable and `503` with a per-dependency `checks` map when it is not, while `GET /health` keeps reporting liveness.
- Make targets for the Compose stack: `up`, `down`, `reset` (deletes Qdrant data after confirmation), `logs`, `ps` and `smoke`. Running `make` on its own lists all targets.
- End-to-end smoke test (`scripts/smoke.sh`, `make smoke`) that starts the real stack in a separate Compose project, stops and restarts Qdrant, checks that `/ready` and `/health` respond correctly, and prints container logs if a check fails.
- CI runs the smoke test on every pull request as part of the `docker` job.
- `gpu` pytest marker for tests that need a CUDA GPU; these tests are excluded from `make test` and CI. Unknown markers are now an error (`--strict-markers`).

### Changed
- Python 3.12 is now required (previously 3.11–3.12); local development, CI and the Docker image all use 3.12.
- `httpx` is now a runtime dependency (previously development-only), because the API uses it for readiness checks.
- CI now runs the same Make targets as local development (`make lint`, `make typecheck`, `make test`), fails if `uv.lock` is out of date (`uv sync --locked`), and reads the Python version from `.python-version`.
- CI jobs time out after 10 minutes, and runs on `main` are no longer cancelled when a newer commit arrives (only pull request runs are).
