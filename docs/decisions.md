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

## ADR-005: A named Docker volume for Qdrant's data
- Date: 2026-11-01
- Context: Qdrant stores its collections on disk, and that data must survive container restarts, image upgrades and `docker compose down`. Development happens in WSL2 with Docker Desktop, where Docker runs in its own Linux VM, separate from both Windows and the WSL distribution. Docker Compose offers two ways to give a container persistent storage.
- Options:
  1. A bind mount of a folder in the repository (for example `./data/qdrant:/qdrant/storage`): the files are visible and easy to inspect, but they live in the working tree.
  2. A named volume (`qdrant_data:/qdrant/storage`) that Docker creates and manages.
  3. No persistence: the data disappears with the container. That is acceptable for tests, but means re-indexing every document after each restart.
- Decision: a named volume, `qdrant_data`, declared in `docker-compose.yml`.
- Consequences:
  - Easier: no file ownership problems. A bind mount exposes host files with host user IDs, which often do not match the user inside the container, so writes fail or the files end up owned by root on the host. A new named volume takes the ownership of the image's own directory, so Qdrant can write to it immediately.
  - Easier: faster disk access. The volume lives inside Docker's VM, next to the container. A bind mount has to cross into that VM, which is slower, and much slower still from a Windows path such as `/mnt/c/...`.
  - Easier: the database files are out of reach of tools that work on the repository (`git clean -fdx`, editor indexers, file watchers, backup or sync tools), so none of them can corrupt or delete them by accident.
  - Easier: portable. Nothing has to be created on the host first, and the same `docker-compose.yml` works on any machine.
  - Harder: the files are not visible in the project folder. To inspect or back them up, mount the volume in a throwaway container, e.g. `docker run --rm -v docagent_qdrant_data:/data -v "$PWD":/backup busybox tar czf /backup/qdrant.tgz -C /data .`. For a consistent backup of a running database, Qdrant's snapshot API is the better tool.
  - Harder: `docker compose down -v` deletes the volume. Plain `make down` keeps it; the only command that deletes it is `make reset`, which asks for confirmation first. The smoke test uses its own Compose project, so it gets its own volume (`docagent-smoke_qdrant_data`) and never touches development data.
  - Revisit for a real deployment, where storage would be a managed volume (for example a Kubernetes PersistentVolumeClaim) or a hosted Qdrant, or if data ever needs to be shared directly with tools on the host.

## ADR-006: Separate liveness (`/health`) and readiness (`/ready`) endpoints
- Date: 2026-11-01
- Context: the API depends on Qdrant now, and later on the VLM and retriever services. Orchestrators (Docker health checks, Kubernetes probes, load balancers) need two different answers: whether the process is alive, and whether it can serve requests right now. They act on these answers in different ways: a failed liveness check means the container gets restarted, while a failed readiness check means no traffic is sent to it.
- Options:
  1. One `/health` endpoint that also checks every dependency.
  2. `/health` for liveness only, plus `/ready` that checks dependencies.
  3. No dependency checks at all, letting requests fail when a dependency is down.
- Decision: option 2. The Dockerfile `HEALTHCHECK` calls `/health`. `/ready` returns `200`, or `503` with a per-dependency `checks` map. Each check uses a short timeout (2 s) and never raises: connection errors, timeouts and error status codes all count as "not ready". The checker is injected through a FastAPI dependency, so tests can replace it.
- Consequences:
  - Easier: a Qdrant outage does not restart the API. With option 1, every replica would be restarted in a loop that cannot fix a database outage.
  - Easier: recovery is automatic, because the check runs on every request. The smoke test proves this: `/ready` goes back to `200` after Qdrant restarts, without restarting the API.
  - Easier: diagnosis. The `checks` map shows which dependency is down, and each new dependency adds one entry without changing the response schema.
  - Harder: the two endpoints must keep their different meanings. A test (`test_health_stays_ok_when_qdrant_is_not_ready`) fails if someone adds dependency checks to `/health`.
  - Harder: every `/ready` request makes a network call to each dependency. That is cheap now, but with frequent probes and several dependencies the results may need short caching.
  - Note: Compose's `depends_on` only controls startup order, and nothing in Compose routes traffic based on `/ready`. Its full value appears behind a load balancer or in Kubernetes.

## ADR-007: A Docker Compose smoke test as the integration test layer
- Date: 2026-11-01
- Context: the unit tests replace Qdrant with fakes at two levels (the checker, and httpx's transport). They cannot show that the real parts work together: Compose DNS (`qdrant:6333`), environment variables, the Dockerfile, health-check ordering, and Qdrant's actual `/readyz` endpoint. That check has to run on GitHub's free runners, which have no GPU.
- Options:
  1. Manual checks only, before each merge.
  2. pytest integration tests that start a Qdrant container with testcontainers and call `is_qdrant_ready` against it.
  3. A shell script that starts the real Compose stack, makes Qdrant fail and recover, and checks the API's responses.
- Decision: option 3, as `scripts/smoke.sh` and `make smoke`, run by the CI `docker` job on every pull request. It uses a separate Compose project (`docagent-smoke`), always cleans up through a `trap`, prints container logs if a check fails, and has timeouts on every wait.
- Consequences:
  - Easier: one test covers the whole stack, including the image and the Compose file. The same command runs locally and in CI. A Qdrant upgrade that breaks `/readyz` is caught before it is merged.
  - Easier: no new Python dependency, and the unit tests stay fast and work offline.
  - Harder: it is slower (around 30 s including the build), and a failure shows that something broke, not exactly what. The unit tests and printed logs narrow it down.
  - Harder: it uses the same ports as the development stack, so the development stack must be stopped first (`make down`). The script is written in Bash, not Python.
  - Revisit when the retriever starts writing to and querying Qdrant: query behaviour needs container-backed integration tests (option 2), because fakes cannot reproduce it faithfully.
