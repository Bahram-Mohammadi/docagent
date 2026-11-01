# DocAgent

**An agentic, multimodal research assistant that answers multi-step questions across PDFs, slides and scans, with cited and highlighted evidence. Runs fully on your own GPU.**

![CI](https://github.com/Bahram-Mohammadi/docagent/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

> **Status:** 🚧 v0.1 (multimodal RAG baseline) in progress. Done so far: project tooling and CI, the API service with health and readiness endpoints, its Docker image, and a Docker Compose stack with Qdrant that is smoke-tested in CI.

<!-- Add a 15-second demo GIF here once the UI exists. -->

## Results

Results are added as each version is released. Every number is reproducible from `eval/`.

| Version | System | Custom multi-doc acc. | ChartQA acc. | Recall@5 | p95 latency |
| --- | --- | --- | --- | --- | --- |
| v0.1 | Single-pass multimodal RAG | – | – | – | – |
| v0.2 | Agent (planner + tools) | – | – | – | – |
| v0.3 | Agent + verifier + abstention | – | – | – | – |

## What it does

Ask a question such as *"Compare the revenue growth of Company A and Company B over the last three years using the charts in their annual reports."* DocAgent:

1. **Plans** the steps needed to answer it
2. **Searches** pages with vision-native (ColQwen2) and text (BGE-M3) retrieval
3. **Reads** charts and tables, zooming into page regions with a vision-language model
4. **Calculates** in an isolated, network-less sandbox
5. **Verifies** every claim against its evidence, and abstains when evidence is weak
6. **Answers** with citations and highlighted evidence boxes

## Architecture

| Service | Role | GPU | Available |
| --- | --- | --- | --- |
| `api` | FastAPI + LangGraph agent | No | ✅ health and readiness only |
| `qdrant` | Vector database | No | ✅ |
| `ui` | Chat, live agent trace, document viewer | No | – |
| `vlm` | vLLM serving Qwen2.5-VL | Yes | – |
| `retriever` | ColQwen2 + BGE-M3 embeddings and search | Yes | – |
| `mcp_tools` | MCP tool servers (search, chart, table, zoom) | No | – |
| `sandbox` | Locked-down Python executor | No | – |
| `langfuse` | Tracing, tokens, cost (optional) | No | – |

## Quickstart (development)

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Git. On Windows, work inside WSL2.

```bash
git clone https://github.com/Bahram-Mohammadi/docagent.git
cd docagent
cp .env.example .env
make setup   # install dependencies + pre-commit hooks
make check   # lint, type check, tests
```

Run `make` on its own to list every available command. To run the services, see [Run with Docker Compose](#run-with-docker-compose).

## Run with Docker Compose

Requirements: [Docker](https://docs.docker.com/get-docker/) with the Compose plugin. On Windows, use Docker Desktop with WSL integration enabled for your distribution.

**1. Start the stack:**

```bash
make up
```

This builds the API image, starts Qdrant and the API, and returns once every service reports healthy. The API starts only after Qdrant is healthy. The first run also downloads the Qdrant image.

**2. Open the services:**

| URL | What it shows |
| --- | --- |
| <http://127.0.0.1:8000/health> | Liveness: `200` while the API process is running |
| <http://127.0.0.1:8000/ready> | Readiness: `200` when every dependency is reachable, otherwise `503` with a per-dependency `checks` map |
| <http://127.0.0.1:8000/docs> | Interactive API documentation |
| <http://127.0.0.1:6333/dashboard> | Qdrant web dashboard |

If Qdrant goes down, `/ready` returns `503` while `/health` stays `200`. The API keeps running and recovers by itself as soon as Qdrant is back.

Ports are bound to `127.0.0.1`, so nothing is reachable from other machines. This matters because Qdrant runs without authentication in development.

**3. Everyday commands:**

| Command | What it does |
| --- | --- |
| `make ps` | List services and their health, including stopped ones |
| `make logs` | Follow the logs of all services (`make logs SERVICE=api` for one) |
| `make down` | Stop and remove the containers. **Qdrant data is kept.** |
| `make reset` | Stop everything and **delete all Qdrant data** (asks for confirmation) |
| `make smoke` | Run the end-to-end smoke test (see [Testing](#testing)) |

Qdrant stores its data in the named Docker volume `docagent_qdrant_data`, so it survives `make down` and image rebuilds. See ADR-005 in [docs/decisions.md](docs/decisions.md) for why a named volume is used rather than a folder in the repository.

Without `make`, the equivalent commands are:

```bash
docker compose up -d --build --wait   # start
docker compose down                   # stop, keep data
docker compose down -v                # stop, delete data
```

### API container only

To run the API image on its own, without Qdrant:

```bash
make docker-build
make docker-run
make docker-stop
```

In this mode `/health` returns `200`, but `/ready` returns `503`, because there is no Qdrant to reach.

## Testing

| Layer | Command | What it covers | Needs |
| --- | --- | --- | --- |
| Unit | `make test` | Routes, readiness logic and settings, with external services replaced by fakes | Python only |
| Smoke | `make smoke` | The real stack: builds the image, starts Qdrant and the API, stops and restarts Qdrant, and checks that `/ready` follows it | Docker |

`make check` runs linting, type checking and the unit tests. The smoke test uses its own Compose project (`docagent-smoke`) and deletes everything it created when it finishes, so your development data is never touched. Stop your development stack first (`make down`), because both use the same ports.

CI runs both layers on every pull request: the `check` job runs `make lint`, `make typecheck` and `make test`, and the `docker` job builds the image and runs `make smoke`. Tests marked `gpu` are excluded from both.

## Project structure

```text
services/       one folder per container (api, retriever, mcp_tools, sandbox, ui)
docagent_core/  shared library: settings, schemas, clients
ingestion/      parsing, chunking, page rendering
training/       LoRA fine-tuning of the chart reader
eval/           benchmarks, metrics, ablations
scripts/        developer and CI scripts (smoke test)
tests/          unit and integration tests
docs/           architecture, design decisions, evaluation report
```

## Development workflow

- `main` is protected; every change goes through a pull request with green CI (`check` and `docker`).
- Pull requests are squash-merged, so each commit on `main` is one reviewed change.
- Branch names: `feat/...`, `fix/...`, `docs/...`, `chore/...`.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
- Design decisions are recorded in [docs/decisions.md](docs/decisions.md).

## Roadmap

- [ ] **v0.1** Multimodal RAG baseline: ingestion, two retrieval pipelines, vLLM answers, evaluation
- [ ] **v0.2** Agent: MCP tool servers, LangGraph planner/executor, ablation vs. v0.1
- [ ] **v0.3** Trustworthy agent: verifier, calibrated abstention, sandbox, injection defence, LoRA chart reader
- [ ] **v1.0** UI, tracing, image releases on GHCR, docs, demo

## License

[MIT](LICENSE)
