# Design decisions

One short record per decision. Write it when you decide, not afterwards.
Interviewers ask "why did you choose X?", and these records are your answers.

Template:

```
## ADR-NNN: <title>
- Date:
- Context: what problem or constraint forced a choice
- Options: what you considered
- Decision: what you chose
- Consequences: what gets easier, what gets harder
```

---

## ADR-001: uv for Python dependency management
- Date: 2026-10-22
- Context: several services share code; installs must be fast and reproducible in Docker and CI.
- Options: pip + requirements.txt, Poetry, uv.
- Decision: uv with a committed `uv.lock`.
- Consequences: fast, reproducible installs and one tool for Python versions too. Contributors need uv installed.

## ADR-002: One shared settings module (`docagent_core.config`)
- Date: 2026-10-22
- Context: every service needs model URLs, retrieval settings and secrets.
- Options: read `os.environ` in each service; a shared pydantic-settings class.
- Decision: a typed `Settings` class read from environment variables or `.env`.
- Consequences: invalid config fails at startup with a clear error; secrets are hidden in logs.

## ADR-003: One root package for all services (for now)
- Date: 2026-10-23
- Context: the API is the first service in `services/`. More will follow (retriever, MCP tools, sandbox, UI) with very different dependencies: the retriever needs PyTorch and GPU libraries, while the API and sandbox need only light web libraries. We have to decide how the Python code of several services is packaged and installed.
- Options:
  1. One `pyproject.toml` at the repo root that installs everything, with each service's code in `services/<name>/<package>/`.
  2. A uv workspace: one `pyproject.toml` per service plus `docagent_core` as a shared package, each installed separately.
- Decision: option 1 while the API is the only service. It needs no extra setup and keeps one lock file, which lets us focus on building features first.
- Consequences:
  - Easier: one `uv sync`, one lock file, one CI job.
  - Harder: tools do not find `services/api` on their own, so four settings point at it (pytest `pythonpath`, mypy `mypy_path`, ruff `src`, coverage `source`), and each new service adds another entry to all four.
  - Harder: every Docker image would install every dependency, so the small API image would carry the retriever's GPU libraries.
  - Revisit when the second service (the retriever) is added: split into a uv workspace so each image installs only what it needs and the four path settings can be removed.


## ADR-004: python:3.12-slim as the base image, with Python 3.12 everywhere
- Date: 2026-10-25
- Context: the API needs a Docker image, and later services (retriever, training) will add ML libraries with compiled code such as NumPy and PyTorch. The base image decides image size, security exposure, how easily those libraries install, and how easy the container is to debug. Until now CI tested Python 3.11 while development used 3.12, so tests did not cover the version we would ship.
- Options:
  1. `python:3.12` (full Debian): every tool and compiler included, but around 1 GB and many packages that are never used at runtime, each a possible security issue.
  2. `python:3.12-slim` (minimal Debian): a fraction of the size of the full image, uses glibc so pre-built Python wheels install directly, and keeps a shell for debugging; no compilers.
  3. `python:3.12-alpine`: the smallest, but uses musl instead of glibc. Many ML packages, PyTorch included, publish no musl wheels, so they would have to compile from source or could not be installed at all.
  4. Distroless Python: very small with almost nothing to attack, but no shell or package manager, which makes debugging hard while the system is still being built.
- Decision: `python:3.12-slim`, pinned to a specific version tag, for all Python services. It is the smallest option on which the ML packages we need install from pre-built wheels without extra work.
- Consequences:
  - Easier: small images that are quick to pull; standard wheels install as-is; `docker exec` into a shell works for debugging.
  - Harder: there are no compilers, so a package without a pre-built wheel needs build tools installed in the builder stage only (the multi-stage build keeps them out of the final image).
  - Python 3.12 is now used for local development, CI (changed in PR #3) and the image, so tests run on the version we ship (dev/prod parity). `requires-python` was narrowed to 3.12, which also removed the `tomli` backport from `uv.lock`.
  - GPU services may need an NVIDIA CUDA base image instead; that will be a separate decision when the retriever is containerised.
  - Revisit when Python 3.13 is supported by all our ML dependencies, or if image size or security scans become a problem (distroless then becomes attractive).
