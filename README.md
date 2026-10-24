# DocAgent

**An agentic, multimodal research assistant that answers multi-step questions across PDFs, slides and scans, with cited and highlighted evidence. Runs fully on your own GPU.**

![CI](https://github.com/Bahram-Mohammadi/docagent/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)

> **Status:** 🚧 Phase 0: project skeleton. v0.1 (multimodal RAG baseline) in progress.

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

| Service | Role | GPU |
| --- | --- | --- |
| `api` | FastAPI + LangGraph agent | No |
| `ui` | Chat, live agent trace, document viewer | No |
| `vlm` | vLLM serving Qwen2.5-VL | Yes |
| `retriever` | ColQwen2 + BGE-M3 embeddings and search | Yes |
| `mcp_tools` | MCP tool servers (search, chart, table, zoom) | No |
| `sandbox` | Locked-down Python executor | No |
| `qdrant` | Vector database | No |
| `langfuse` | Tracing, tokens, cost (optional) | No |

## Quickstart (development)

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Git. On Windows, work inside WSL2.

```bash
git clone https://github.com/Bahram-Mohammadi/docagent.git
cd docagent
cp .env.example .env
make setup   # install dependencies + pre-commit hooks
make check   # lint, type check, tests
```

Docker Compose instructions arrive with v0.1.

## Project structure

```text
services/       one folder per container (api, retriever, mcp_tools, sandbox, ui)
docagent_core/  shared library: settings, schemas, clients
ingestion/      parsing, chunking, page rendering
training/       LoRA fine-tuning of the chart reader
eval/           benchmarks, metrics, ablations
tests/          unit and integration tests
docs/           architecture, design decisions, evaluation report
```

## Development workflow

- `main` is protected; every change goes through a pull request with green CI.
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
