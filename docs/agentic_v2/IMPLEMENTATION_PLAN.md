# Agentic Compliance Copilot v2 Implementation Plan

## Product Scope

Build a controlled Agentic RAG application for cross-border compliance
questions. The application must remain useful for v1-style single-turn
questions while adding controlled routing, tools, short-term conversation
context, and measurable production behavior.

## In Scope

- FastAPI application interface
- SSE streaming responses
- LangGraph state machine
- explicit route selection
- query rewriting and multi-hop decomposition
- evidence sufficiency checks
- citation verification
- three or four concrete tools
- short-term conversation memory
- evaluation expansion
- trace and observability
- Docker Compose
- CI regression tests
- v2.0.0 documentation and release

## Out of Scope

- free-form multi-agent conversation
- long-term user memory
- Kubernetes or distributed microservices
- a full identity provider or enterprise SSO
- model training or fine-tuning
- a graph or vector database rewrite before measurements justify it
- speculative features not required by a phase

## Phase 0: Context and Setup

Status: complete after setup commit

Deliverables:

- `AGENTS.md`
- `PROJECT_STATE.md`
- `IMPLEMENTATION_PLAN.md`
- `DECISIONS.md`
- `REVIEW_CHECKLIST.md`
- `feat/agentic-v2` branch

Acceptance:

- baseline tests pass
- current architecture and constraints are documented
- next task is unambiguous

## Phase 1: FastAPI and SSE

Status: complete

Goal:

Expose the current RAG pipeline through a stable HTTP API and stream the answer
to clients without breaking existing CLI and Gradio paths.

Deliverables:

- API request and response models
- `/health` endpoint
- `/api/v1/answer` synchronous endpoint
- `/api/v1/answer/stream` SSE endpoint
- incremental DeepSeek token streaming through the existing RAG orchestration
- consistent error handling for invalid input, missing data, and model errors
- tests for normal answer, refusal, validation, and streaming
- no LangGraph nodes yet

Acceptance:

- current tests continue to pass
- API tests cover at least one successful answer and one refusal path
- SSE events have stable event names and a documented payload shape
- default B1 Fast behavior is unchanged

Phase 1 verification (2026-11-10):

- 43 tests passed with `python -m pytest -q`.
- API and stream tests use deterministic stubs and do not call DeepSeek.
- SSE emits `start`, `status`, `token`, `done`, and sanitized `error` events.
- References in `done` are filtered to IDs present in the answer body.
- The API contract is documented in `docs/agentic_v2/API.md`.

## Phase 2: LangGraph State Machine and Routing

Status: complete

Goal:

Replace the implicit answer flow with an explicit controlled graph. Keep the
existing retriever and generator as nodes or adapters.

Required nodes:

- classify question
- rewrite or split query
- retrieve evidence
- decide whether evidence is sufficient
- compose answer
- verify citations or refuse

Routing rules:

- simple fact question: B1 Fast path
- multi-hop question: query decomposition plus optional B3 reranker
- high-risk question: require more than one source
- insufficient evidence: refuse without citations

Acceptance:

- graph state is serializable and testable
- route decisions are recorded
- simple path does not invoke expensive reranking
- existing refusal and citation rules are preserved
- tests cover routing, multi-hop, and refusal

Phase 2 verification (2026-11-10):

- 58 tests passed with `python -m pytest -q`.
- LangGraph 1.2.20 and all newly resolved transitive dependencies are pinned.
- Both synchronous and SSE paths execute the controlled graph.
- Deterministic routing records `high_risk > multi_hop > simple_fact`
  decisions and node reasons in `route_trace`.
- High-risk answers require two distinct cited sources; insufficient evidence
  refuses with zero citations.
- Parameterized tests cover all five approved high-risk rule categories.
- The existing evidence thresholds and year/term coverage rules are reused
  unchanged through a regression-tested helper.
- The graph contract is documented in `docs/agentic_v2/GRAPH.md`.

## Phase 3: Tools and Short-Term Conversation

Status: complete

Goal:

Add controlled tool use and conversation context without building a free-form
multi-agent system.

Tools:

- search official policy sources
- fetch or inspect the latest policy snapshot
- compare policy versions
- validate dates or validity periods
- optional cost or currency calculation

Implementation rules:

- start with plain typed Python tool functions
- add an MCP adapter for selected tools if time permits
- every tool has a typed result and failure result
- graph retries are bounded
- no unbounded loops

Conversation:

- keep only the current session
- summarize older turns
- do not add long-term memory

Acceptance:

- tool success and failure are tested
- tool calls appear in traces
- repeated tool loops are impossible or bounded
- session context is isolated between requests

Phase 3 verification (2026-11-10):

- 80 tests passed with `python -m pytest -q`.
- Four typed tools cover retrieval, latest snapshot inspection, version
  comparison, and validity-period validation.
- Every tool has a typed success record and a stable failure record.
- Retries use a configurable ceiling capped at three total attempts.
- Core search failure uses the existing API/SSE error channel with public code
  `tool_unavailable`.
- Optional tool failures are recorded without discarding valid evidence.
- Session context is process-local, bounded, and isolated by optional
  `X-Session-ID`; requests without the header remain stateless.
- Current one-snapshot source data returns `insufficient_versions` for version
  comparison rather than fabricating changes.
- Existing B1 Fast, B3, refusal, high-risk, citation, CLI, Gradio, API, and SSE
  behavior remains covered by tests.

## Phase 4: Evaluation and Observability

Status: complete

Goal:

Measure application behavior rather than only answer correctness.

Evaluation:

- keep the original 60 questions
- expand to 120-150 questions
- add at least 30 human-reviewed cases
- add route accuracy
- add tool selection accuracy
- add tool success rate
- add multi-step task completion
- add evidence sufficiency accuracy
- keep answer correctness and citation accuracy

Observability:

- add Langfuse or a documented equivalent
- record retrieval, model, prompt version, tool call, token, latency, and error
- keep secrets out of traces

Acceptance:

- metrics can be regenerated by one command
- current baseline remains comparable
- errors and failed tools are visible without reading raw console logs

Phase 4 verification (2026-11-10):

- The original 60-question file and original metric formulas are unchanged.
- `eval/agentic_v2/questions.jsonl` contains 150 questions:
  fact 70, multi_hop 60, and refusal 20.
- Expected agentic routes are simple_fact 68, high_risk 47, and multi_hop 35.
- The 90 new questions are all `review_status: draft`.
- Every gold evidence quote is verified against its referenced chunk.
- New agentic metrics are emitted separately under `agentic_metrics`.
- Local JSONL trace artifacts are written for evaluation runs and optionally
  for the API/SSE path.
- Trace write failures do not affect API responses or SSE events.
- Independent human review was not executed and was exempted by the project
  owner; no reviewer identity, review timestamp, or human pass rate is
  fabricated.
- The full DeepSeek evaluation was not run because it requires network access,
  an API key, and paid model calls.

## Phase 5: Packaging, CI, and Release

Status: complete in the repository; external Docker runtime and remote GitHub
Actions execution remain approval-dependent

Goal:

Make V2 runnable and reviewable from a clean checkout.

Deliverables:

- Docker Compose for the application
- only add Qdrant, PostgreSQL, or Redis if Phase 3/4 requirements justify them
- GitHub Actions test and evaluation smoke job
- architecture diagram
- README V2 section
- failure cases and cost/latency report
- v2.0.0 release notes and tag

Acceptance:

- one documented command starts the application
- CI passes from a clean checkout
- README includes API examples and limitations
- release assets and version notes are complete

Phase 5 verification (2026-11-10):

- `Dockerfile`, `.dockerignore`, `compose.yaml`, and a GitHub Actions workflow
  are added.
- Compose starts one FastAPI service and adds no Qdrant, PostgreSQL, Redis, or
  other infrastructure.
- Corpus and Chroma data are read-only bind mounts; Hugging Face cache and Trace
  output use named volumes.
- The image runs as a non-root user with pre-created writable cache and Trace
  directories.
- Deterministic CI tests use `-m "not data"`; 86 tests are selected without
  ignored local corpus or Chroma artifacts.
- The evaluation smoke uses synthetic fixture chunks, BM25, extractive
  generation, and `--judge none`; it executes no DeepSeek request.
- The smoke completes 3/3 questions with refusal accuracy 1.0 and route accuracy
  1.0.
- Full local tests pass: 94 tests.
- Compose, Dockerfile, Docker context, workflow, and fixture structure are
  covered by static packaging tests.
- Docker is not installed on the current machine, so no container build or
  startup is claimed.
- GitHub Actions has not been executed because this phase was not pushed.
- `VERSION`, README, architecture, deployment, limitation/failure, changelog,
  and v2.0.0 release-note drafts are updated.

## Overall Success Criteria

- at least 50 automated tests
- route accuracy at least 90%
- tool success at least 95%
- citation accuracy at least 95%
- fast-path P95 around 5 seconds or better where feasible
- human-reviewed evaluation subset retained
- no secrets or private data committed
- v1.0.0 behavior remains traceable

