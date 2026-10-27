# syntax=docker/dockerfile:1

# ---------- Builder stage: install dependencies into a virtual environment ----------
FROM python:3.12.15-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

# Compile bytecode at build time for faster startup; copy from the cache mount
# instead of hard-linking (different filesystem); always use the image's own
# Python so the venv matches the runtime stage.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies before copying source code, so code changes
# don't invalidate this cached layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Install the shared package itself. It is non-editable, so the runtime stage
# only needs /app/.venv, not the source tree.
# README.md is required by the build (pyproject: readme = "README.md").
COPY README.md ./
COPY docagent_core/ docagent_core/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------- Runtime stage: only what is needed to run the API ----------
# Must use the same base image as the builder: the venv's python is a link
# to this image's /usr/local/bin/python3.12.
FROM python:3.12.15-slim AS runtime

# Unbuffered output so logs reach `docker logs` immediately; no .pyc writes at
# runtime (already compiled in the builder); venv tools first on PATH.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Dedicated unprivileged user with a fixed numeric ID, so file permissions are
# predictable and Kubernetes can verify runAsNonRoot.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --no-create-home app

WORKDIR /app

# The venv must keep the same path as in the builder (its scripts contain
# absolute paths). Files stay owned by root: the app can read its code but
# cannot modify it if the process is compromised.
COPY --from=builder /app/.venv /app/.venv

# The API code is not packaged yet (see ADR-003), so it is copied directly.
# Uvicorn adds the working directory (/app) to the import path, which makes
# `docagent_api` importable.
COPY services/api/docagent_api/ docagent_api/

# Run as non-root to limit the damage if the application is compromised.
USER 10001:10001

EXPOSE 8000

# The slim image has no curl, so the check uses Python's standard library.
# Any connection error or non-2xx response raises, giving a non-zero exit code.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# Exec form: uvicorn runs as PID 1, receives stop signals and shuts down cleanly.
# 0.0.0.0 accepts connections from outside the container (127.0.0.1 would not).
CMD ["uvicorn", "docagent_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
