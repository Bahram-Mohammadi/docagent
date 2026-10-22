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
