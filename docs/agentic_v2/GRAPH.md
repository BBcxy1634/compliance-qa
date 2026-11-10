# Compliance Agent Graph

Phase 3 runs both the synchronous and SSE answer paths through one controlled
LangGraph state machine. The graph is bounded, has no loop edges, and uses a
small typed tool runtime plus process-local short-term session context.

## Dependency Boundary

The graph state contains only serializable data. Runtime objects are injected
through `GraphDependencies` and never stored in graph state:

- retriever instance
- retrieval backend and Top K
- DeepSeek or extractive generation mode
- thinking and token-limit configuration
- whether custom SSE events are enabled
- typed `ToolRuntime` with retriever, snapshot catalog, retry ceiling, and
  deterministic as-of date

The existing retriever, generation functions, evidence rules, and citation
filter are reused by adapters. Phase 2 does not duplicate their scoring,
prompting, or citation logic.

## Flow

```text
START
  -> classify_question
  -> rewrite_or_split_query
  -> retrieve_evidence
       - search tool for one to three queries
       - optional latest-snapshot, version comparison, date validation
  -> assess_evidence
       -> compose_answer                 (evidence sufficient)
       -> verify_citations_or_refuse     (evidence insufficient)
  -> verify_citations_or_refuse
  -> END
```

`verify_citations_or_refuse` is the only terminal node. A normal answer reaches
it through `compose_answer`; an insufficient-evidence refusal reaches it
directly without calling the generation model.

No conditional edge returns to a previous node. Tool retries happen inside a
single invocation and use a hard ceiling of three total attempts.

## Route Decision

Classification precedence is fixed:

```text
high_risk > multi_hop > simple_fact
```

Rules are deterministic regular expressions. No model is called to classify a
question.

High-risk rule IDs:

- `counterfeit_ip`: counterfeit, infringement, trademark, copyright, patent
- `restricted_product_safety`: prohibited goods, product safety, recall,
  restricted medical or food products, hazardous goods
- `customs_tax_sanctions`: customs, tariffs, VAT, export controls, sanctions
- `privacy_data`: personal data, privacy, GDPR, CCPA, customer-data protection
- `penalty_liability`: penalties, fines, legal responsibility, lawsuits

Multi-hop indicators:

- explicit connectors such as `分别`, `同时`, `对比`, `which two`,
  `respectively`, `both`, or `while`
- paired questions such as `A 和 B 哪个`
- two or more question marks
- semicolon-separated subquestions
- English `and` together with a second policy, requirement, violation, or
  obligation target

Simple questions are queries with no high-risk or multi-hop rule match. The
default API mode and Gradio mode still use B1 Fast. B3 remains an explicit
optional mode; the graph does not create a reranker itself.

## Graph State

`AgentState` is a `TypedDict` with these serializable fields:

| Field | Meaning |
|---|---|
| `question` | Trimmed user question |
| `conversation_context` | Bounded summary and recent turns; no session ID |
| `route` | Route name, reason IDs, multi-hop flag, required source count, rerank flag |
| `route_trace` | One decision record per executed node |
| `tool_calls` | Tool outcomes, attempt counts, and stable error codes |
| `retrieval_queries` | Normalized question or at most three split queries |
| `retrieval_results` | Per-query serialized hits |
| `evidence_hits` | Deduplicated serialized hits |
| `retrieval_ms` | Total retrieval time |
| `retrieval_breakdown` | Per-query and retriever timing metadata |
| `evidence_sufficient` | Deterministic evidence result |
| `evidence_reason` | Stable reason code |
| `sufficient_source_count` | Distinct strong source count |
| `candidate_result` | Existing generator result before final verification |
| `answer` | Candidate or terminal answer |
| `refused` | Terminal refusal flag |
| `citations` | Candidate or terminal citations |
| `generation_ms` | Generation time |
| `verification_ms` | Citation-verification time |
| `model` | Model reported by the existing generator |
| `prompt_version` | Version identifier for the active generation prompt |
| `usage` | Token usage reported by the existing generator |

`SearchHit` values are converted to plain dictionaries inside the graph.
Runtime dependencies and retriever objects are not part of state.

## Node Contract

| Node | Input | Output |
|---|---|---|
| `classify_question` | `question` | `route`, route trace |
| `rewrite_or_split_query` | question and route | one to three retrieval queries |
| `retrieve_evidence` | queries and injected tool runtime | deduplicated hits, tool traces, timings |
| `assess_evidence` | per-query hits and route | sufficiency, reason, source count, optional refusal |
| `compose_answer` | sufficient evidence | existing generator result and timings |
| `verify_citations_or_refuse` | candidate or refusal | final answer, `refused`, filtered citations |

## Evidence And Citations

Evidence assessment reuses the existing extractive rules without changing
thresholds, year coverage, or query-term coverage.

- No strong evidence: refuse before generation.
- Multi-hop: every split query must have sufficient evidence.
- High-risk: strong evidence must come from at least two distinct `source_id`
  values; `source` is used only when `source_id` is absent.
- Refusal always returns the standard refusal text, `refused=true`, and
  `citations=[]`.

Citations are filtered to IDs that occur in the complete final answer body.
For high-risk answers, the used citations must represent the required number of
distinct sources. Otherwise the candidate answer is replaced by refusal.

Short-term conversation context is included in the generation prompt only to
resolve references. The prompt explicitly states that it is not evidence.
For explicit follow-up patterns such as `那欧盟呢`, the last user question is
also prepended to the retrieval query. Current retrieval hits remain the only
citation source.

The finalized internal result also exposes `top_k`, `evidence_sufficient`,
`evidence_reason`, and `sufficient_source_count` for evaluation and local
tracing. The public API response model remains unchanged.

## Tool Calls

The core search tool wraps the existing retriever and returns the same
`SearchHit` values. Optional metadata tools do not bypass evidence assessment:

- latest snapshot inspection returns provenance metadata
- version comparison returns changed fields or `insufficient_versions`
- validity validation reports the calendar state of an explicit date range

Auxiliary tool failure is recorded in `tool_calls` and does not hide
successfully retrieved evidence. A core search-tool failure stops the graph
after its retry budget and is mapped by FastAPI to `tool_unavailable`.

## SSE Mapping

SSE events are emitted from graph nodes through LangGraph custom streaming:

1. `retrieving` at the start of `retrieve_evidence`
2. `generating` at the start of `assess_evidence`
3. zero or more `token` events emitted by `compose_answer`
4. `verifying_citations` at the start of `verify_citations_or_refuse`
5. final `done` event from the completed graph state

The FastAPI layer remains responsible for `start` and sanitized `error` events.
The external event names, payload fields, and order remain the Phase 1 contract.

When local tracing is enabled, the FastAPI boundary records the completed graph
result or sanitized failure after the existing event/response handling path is
known. Trace failure is ignored by the user-facing request.

## Errors

The graph does not catch or rewrite runtime exceptions. Tool retries are
bounded and return typed failures. A core tool failure raises a sanitized
`ToolExecutionError`; model and other runtime exceptions still propagate to the
existing API boundary. No partial candidate citations are emitted, and no
graph-level retry loop is present.
