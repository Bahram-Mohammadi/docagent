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
