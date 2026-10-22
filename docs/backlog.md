# Backlog: v0.1 issues

Create one GitHub issue per line (milestone "v0.1"), then work through them
on the Projects board, one branch and one pull request each.

- [ ] chore: project skeleton, tooling and CI (this commit)
- [ ] feat: docker-compose with qdrant, vlm (vLLM) and api services, GPU profile
- [ ] feat: multi-stage Dockerfile for the api service, non-root user, healthcheck
- [ ] feat: render PDF pages to PNG with PyMuPDF
- [ ] feat: Docling layout parsing (text, tables, captions with page + bbox)
- [ ] feat: chunking with metadata (doc_id, page, bbox, type)
- [ ] feat: retriever service with BGE-M3 text embeddings into Qdrant `chunks`
- [ ] feat: ColQwen2 page embeddings into Qdrant `pages` (multivector, MaxSim)
- [ ] feat: hybrid search with Reciprocal Rank Fusion
- [ ] feat: answer generation via vLLM OpenAI-compatible API, JSON output
- [ ] feat: FastAPI `/ingest`, `/ask`, `/health`, structured logging
- [ ] feat: mock VLM mode for CPU-only runs and CI
- [ ] test: unit tests for chunking, fusion, prompt building, parsing
- [ ] test: GPU integration test (ingest one PDF, ask one question)
- [ ] feat: evaluation harness (DocVQA, ChartQA, ViDoRe subsets)
- [ ] docs: README results table for v0.1, tag v0.1.0
