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

### Changed
- Python 3.12 is now required (previously 3.11–3.12); local development, CI and the Docker image all use 3.12.
