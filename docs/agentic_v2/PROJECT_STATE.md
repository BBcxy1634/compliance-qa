# Agentic Compliance Copilot v2 Project State

Last updated: 2026-11-10

## Repository Snapshot

| Item | Current value |
|---|---|
| Project root | `D:\大学学习\跨境卖家合规问答助手项目\compliance-qa` |
| Current branch | `feat/agentic-v2` |
| Base release | `v1.0.0` |
| Base commit | `1ea2f4b9161b921d126466f86e69782bec9b34b1` |
| Current V2 phase | Phase 5: packaging, CI, and release preparation complete locally |
| V2 code status | Phase 5 implementation and documentation complete |
| Current release state | v1.0.0 is published; v2.0.0 release candidate is not tagged or published |

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
  -> controlled LangGraph routing
  -> bounded typed tool calls
  -> evidence assessment
  -> DeepSeek or extractive generation
  -> citation verification or refusal
  -> Gradio UI / CLI / FastAPI
  -> bounded per-session context
  -> best-effort local JSONL trace

Deployment:

FastAPI container
  -> read-only data/ and chroma_db/ mounts
  -> named Hugging Face cache and Trace volumes
  -> /health and /api/v1/* on port 8000
```

Important existing modules:

| Path | Purpose |
|---|---|
| `src/ingest.py` | document parsing, cleaning, splitting, chunk metadata |
| `src/embed.py` | BGE-M3 embedding and Chroma indexing |
| `src/retrieve.py` | BM25, vector retrieval, RRF, reranker |
| `src/generate.py` | extractive and DeepSeek generation |
| `src/agent_graph.py` | serializable state, deterministic routing, six-node graph |
| `src/rag.py` | CLI plus graph adapters for synchronous and streaming answers |
| `src/tools.py` | typed tool runtime, snapshot catalog, bounded retries |
| `src/conversation.py` | bounded process-local short-term session context |
| `src/observability.py` | best-effort local JSONL traces with payload allowlists |
| `app.py` | Gradio demo |
| `src/demo.py` | demo modes, HTML rendering, citation filtering |
| `src/api.py` | FastAPI models, synchronous answer endpoint, and SSE streaming |
| `evaluate.py`, `src/evaluate.py` | existing metrics plus agentic metrics and local traces |
| `eval/questions.jsonl` | frozen 60-question evaluation set |
| `eval/agentic_v2/questions.jsonl` | 150-question Phase 4 draft evaluation set |
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

## Phase 1 Verification

Validation performed on 2026-11-10:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Results:

- 43 tests passed.
- API tests use deterministic in-memory engines and do not call DeepSeek.
- Streaming generation tests use a fake OpenAI-compatible client.
- Synchronous and SSE paths reuse the existing retriever and generation
  orchestration.

## Phase 2 Verification

Validation performed on 2026-11-10:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Results:

- 58 tests passed.
- LangGraph 1.2.20 and its exact resolved transitive versions are pinned in
  `requirements.txt`.
- Graph tests use deterministic retrievers and generation stubs and do not call
  DeepSeek.
- Simple fact questions follow the B1 Fast path; default fast routing does not
  create or invoke a reranker.
- Multi-hop questions split into at most three deterministic retrieval queries.
- High-risk questions require two distinct sources and refuse when the final
  answer cites fewer than two.
- Parameterized tests cover all five approved high-risk rule categories.
- Insufficient evidence refuses without calling generation.
- Route decisions and node reasons are recorded in `route_trace`.
- Graph results are JSON serializable.
- Synchronous and SSE API behavior remains compatible with the Phase 1 contract.
- `python scripts/check_environment.py --require-data` passed with Python
  3.13.2, configured DeepSeek key, CPU device resolution, 271 semantic vectors,
  and 334 B0 vectors.
- The graph state and SSE mapping are documented in
  `docs/agentic_v2/GRAPH.md`.

## Phase 3 Verification

Validation performed on 2026-11-10:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/check_environment.py --require-data
```

Results:

- 80 tests passed.
- Typed search, latest-snapshot inspection, version comparison, and validity
  period tools are implemented.
- Tool success and stable failure results are JSON serializable and covered by
  deterministic tests.
- Tool retries are capped at three total attempts; the default is two.
- Core search-tool exhaustion maps to public `tool_unavailable` through the
  existing API error and SSE `error` channels.
- Short-term context is process-local, bounded to 128 sessions and four recent
  turns, with older turns compacted into a deterministic summary.
- Missing `X-Session-ID` remains stateless; distinct session IDs are isolated.
- Current source data has one snapshot per `source_id`, so real version
  comparison returns `insufficient_versions` instead of inventing differences.
- Existing route, refusal, citation filtering, high-risk, CLI, Gradio, API, and
  SSE tests remain green.
- Tool and session contracts are documented in
  `docs/agentic_v2/TOOLS.md`.

## Current Gaps

- No historical policy snapshot corpus, so real cross-version comparison is not
  yet available.
- No hosted trace UI; Phase 4 intentionally uses local JSONL traces.
- New Phase 4 questions and agentic labels are `draft`; independent human
  review was not executed and was exempted by the project owner.
- The full paid DeepSeek evaluation has not been run in Phase 4.
- Docker is not installed on the current development machine, so the container
  build and runtime have not been executed.
- GitHub Actions has not run because the branch was not pushed in Phase 5.
- Short-term sessions and local traces are process-local and do not support
  multi-replica coordination.
- Current Gradio app is local and single-request oriented.

## Phase 4 Verification

Phase 4 adds:

- unchanged original 60 questions and existing metric definitions
- a 150-question dated evaluation file with 90 new draft questions
- route, tool selection, tool success, multi-step completion, and evidence
  sufficiency metrics
- local `traces.jsonl`, `errors.jsonl`, `tool_failures.jsonl`, and trace summary
  metadata
- exact gold evidence validation for all 150 records

Validation performed on 2026-11-10:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/validate_eval.py
.\.venv\Scripts\python.exe scripts/validate_agentic_eval.py
.\.venv\Scripts\python.exe scripts/validate_sources.py
.\.venv\Scripts\python.exe scripts/check_environment.py --require-data
```

Results:

- 89 tests passed.
- Original evaluation set: 60 questions, 40 fact, 10 multi-hop, 10 refusal.
- Agentic evaluation set: 150 questions, 70 fact, 60 multi-hop, 20 refusal.
- Expected routes: 68 simple fact, 47 high risk, 35 multi-hop.
- Deterministic draft-label route accuracy: 136/150 (`0.9067`).
- All 24 official source records and Phase 4 evidence quotes validated.
- Environment check passed with Python 3.13.2 and both Chroma collections.
- The full paid DeepSeek evaluation was intentionally not run.

Public API and SSE responses remain unchanged. Trace writing is opt-in for the
API and best effort: a write failure does not affect the answer path.

The detailed contracts are in `docs/agentic_v2/EVALUATION.md` and
`docs/agentic_v2/OBSERVABILITY.md`.

## Phase 5 Verification

Phase 5 adds:

- a Python 3.13 Docker image running as a non-root user
- a single-service Docker Compose API deployment
- read-only corpus and Chroma mounts plus named cache and Trace volumes
- a GitHub Actions workflow with deterministic tests, Compose syntax validation,
  and a synthetic evaluation smoke
- explicit `data` markers for tests requiring ignored local corpus and Chroma
  artifacts
- a three-question synthetic BM25/extractive smoke fixture with no real sources
  and no DeepSeek calls
- v2 architecture, deployment, limitations/failure cases, and release-note
  documentation

Validation performed on 2026-11-10:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q -m "not data"
.\.venv\Scripts\python.exe -m src.evaluate `
  --config eval/configs/phase4_b1_fast.yaml `
  --questions eval/fixtures/agentic_smoke_questions.jsonl `
  --chunks eval/fixtures/agentic_smoke_chunks.jsonl `
  --backend bm25 `
  --mode extractive `
  --judge none `
  --run-name ci_eval_smoke
.\.venv\Scripts\python.exe scripts/check_eval_smoke.py `
  --summary eval/results/ci_eval_smoke/summary.json
```

Results:

- 94 full tests passed with local data and Chroma artifacts present.
- 86 deterministic tests were selected with data-dependent tests excluded.
- The synthetic evaluation smoke completed 3/3 questions.
- Smoke refusal accuracy was 1.0 and route accuracy was 1.0.
- Packaging tests parsed Compose and workflow YAML and checked the Dockerfile,
  Docker context, and fixture structure.
- Docker is not installed locally, so `docker compose config`, image build, and
  service startup were not executed on this machine.
- Remote GitHub Actions was not executed. The workflow is prepared but has not
  produced a CI result.

The detailed operation and failure contract is in
`docs/agentic_v2/DEPLOYMENT.md` and
`docs/agentic_v2/LIMITATIONS_AND_FAILURES.md`.

## Current Phase and Next Task

Phase 5 is complete in the repository. The FastAPI application exposes:

- `GET /health`
- `POST /api/v1/answer`
- `POST /api/v1/answer/stream`

Both endpoints execute the controlled graph. The SSE contract emits `start`,
`status`, `token`, `done`, and `error` events. DeepSeek output is streamed as
incremental token deltas. The `done` event contains only citations whose IDs
occur in the complete answer body. Refusals always return `refused=true` and no
citations.

The repository now includes Docker Compose packaging, a GitHub Actions workflow,
and v2.0.0 release notes. These actions still require explicit approval:

- push the branch or open a pull request to run remote CI
- run an actual Docker build and health check on a Docker-enabled machine
- decide whether to run the full paid V2 evaluation
- decide whether independent human review is required before release
- create the `v2.0.0` tag and GitHub Release
- merge the branch to `master`

The API contract is documented in `docs/agentic_v2/API.md`. The graph contract
is documented in `docs/agentic_v2/GRAPH.md`. Tool and session contracts are
documented in `docs/agentic_v2/TOOLS.md`.

## Environment and Data Rules

- Python 3.12+ is required; the validated local runtime is Python 3.13.2.
- Use the project `.venv` for runtime verification when possible.
- `.env`, API keys, vector databases, official raw snapshots, chunks, and caches
  are not to be committed.
- The official source manifest is `data/raw/sources.jsonl`.

