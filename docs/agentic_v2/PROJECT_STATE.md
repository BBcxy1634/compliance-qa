# Agentic Compliance Copilot v2 Project State

Last updated: 2026-11-08

## Repository Snapshot

| Item | Current value |
|---|---|
| Project root | `D:\大学学习\跨境卖家合规问答助手项目\compliance-qa` |
| Current branch | `feat/agentic-v2` |
| Base release | `v1.0.0` |
| Base commit | `1ea2f4b9161b921d126466f86e69782bec9b34b1` |
| Current V2 phase | Phase 0: context and implementation setup |
| V2 code status | Not started |
| Current release state | v1.0.0 remains the released version |

## V2 Goal

Upgrade the released compliance RAG assistant into a controlled Agentic RAG
application without discarding the existing retrieval, evaluation, citation,
refusal, and demo work.

The V2 project should demonstrate:

- LLM application backend engineering
- controlled agent routing and multi-step execution
- tool calling with failure handling
- short-term conversation context
- evidence sufficiency and citation verification
- measurable routing, tool, quality, latency, and cost metrics
- traceability, deployment, and regression testing

## Existing v1 Capabilities

- 24 source files: 7 PPTs, 12 Amazon/eBay policy pages, and 5 regulator PDFs.
- Semantic ingestion into 271 chunks.
- BGE-M3 vector retrieval through Chroma.
- BM25 lexical retrieval and RRF fusion.
- Optional `bge-reranker-v2-m3` reranking.
- DeepSeek generation with real citation filtering and evidence-based refusal.
- Gradio single-page demo.
- Frozen 60-question evaluation set.
- B0-B3 ablation and B1 Fast default configuration.
- Public GitHub v1.0.0 release with tests and reproducibility documentation.

## Existing Baseline Metrics

| Configuration | Answer accuracy | Fact | Multi-hop | Refusal |
|---|---:|---:|---:|---:|
| B0 | 0.82 | 0.850 | 0.70 | 1.00 |
| B1 | 0.90 | 0.925 | 0.80 | 1.00 |
| B2 | 0.90 | 0.950 | 0.70 | 1.00 |
| B3 | 0.94 | 0.950 | 0.90 | 1.00 |
| B1 Fast | 0.92 | 0.950 | 0.80 | 1.00 |

B1 Fast has a recorded average latency of 1.92 seconds, P95 of 3.31 seconds,
and average cost of about CNY 0.0010 per request.

The answer metrics are DeepSeek-assisted automatic judgments. Independent
human review has not been completed.

## Current Architecture

```text
PPT / HTML / PDF
  -> parsing and cleaning
  -> semantic chunks
  -> BGE-M3 vectors in Chroma
  -> optional BM25 + RRF
  -> optional BGE reranker
  -> DeepSeek answer generation
  -> citation filtering or refusal
  -> Gradio UI / CLI
```

Important existing modules:

| Path | Purpose |
|---|---|
| `src/ingest.py` | document parsing, cleaning, splitting, chunk metadata |
| `src/embed.py` | BGE-M3 embedding and Chroma indexing |
| `src/retrieve.py` | BM25, vector retrieval, RRF, reranker |
| `src/generate.py` | extractive and DeepSeek generation |
| `src/rag.py` | current CLI and answer orchestration |
| `app.py` | Gradio demo |
| `src/demo.py` | demo modes, HTML rendering, citation filtering |
| `evaluate.py`, `src/evaluate.py` | evaluation entry point and metrics |
| `eval/questions.jsonl` | frozen 60-question evaluation set |
| `bench.py`, `src/benchmark.py` | latency and cost benchmark |
| `scripts/bootstrap.py` | data, chunk, vector, and environment preparation |

## Verified State Before V2

Validation performed on 2026-11-08:

```powershell
python -m pytest -q
python scripts/check_environment.py --require-data
```

Results:

- 33 tests passed.
- Python 3.13.2.
- DeepSeek API key is configured locally.
- CUDA is unavailable; `TORCH_DEVICE=auto` resolves to CPU.
- `bge_m3_semantic`: 271 vectors.
- `bge_m3_b0`: 334 vectors.
- Git worktree was clean before V2 setup files were added.

## Current Gaps

- No streaming HTTP API.
- No LangGraph state machine or explicit route selection.
- No tool-calling layer or tool failure handling.
- No short-term conversation state.
- No policy-version or date-validation tools.
- No Langfuse or equivalent trace.
- No routing accuracy, tool success, or evidence sufficiency metrics.
- No Docker-based service composition.
- No GitHub Actions workflow.
- Current Gradio app is local and single-request oriented.

## Current Phase and Next Task

Phase 0 is complete when these context files and `AGENTS.md` are committed.

The next task is **Phase 1: FastAPI + SSE streaming**.

That task must:

- preserve the existing CLI and Gradio behavior
- add an API with request and response models
- add an SSE streaming response
- add tests for success, refusal, validation, and streaming
- update this file after completion
- commit the phase

Do not implement LangGraph nodes or tools in Phase 1.

## Environment and Data Rules

- Python 3.12+ is required; the validated local runtime is Python 3.13.2.
- Use the project `.venv` for runtime verification when possible.
- `.env`, API keys, vector databases, official raw snapshots, chunks, and caches
  are not to be committed.
- The official source manifest is `data/raw/sources.jsonl`.

