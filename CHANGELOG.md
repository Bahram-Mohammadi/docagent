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
