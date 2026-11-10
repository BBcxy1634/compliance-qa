# Compliance Agent Graph

Phase 2 runs both the synchronous and SSE answer paths through one controlled
LangGraph state machine. The graph is bounded, has no retry loop, and does not
perform tool calls or conversation-memory work.

## Dependency Boundary

The graph state contains only serializable data. Runtime objects are injected
through `GraphDependencies` and never stored in graph state:

- retriever instance
- retrieval backend and Top K
- DeepSeek or extractive generation mode
- thinking and token-limit configuration
- whether custom SSE events are enabled

The existing retriever, generation functions, evidence rules, and citation
filter are reused by adapters. Phase 2 does not duplicate their scoring,
prompting, or citation logic.

## Flow

```text
START
  -> classify_question
  -> rewrite_or_split_query
  -> retrieve_evidence
  -> assess_evidence
       -> compose_answer                 (evidence sufficient)
       -> verify_citations_or_refuse     (evidence insufficient)
  -> verify_citations_or_refuse
  -> END
```

`verify_citations_or_refuse` is the only terminal node. A normal answer reaches
it through `compose_answer`; an insufficient-evidence refusal reaches it
directly without calling the generation model.

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
| `route` | Route name, reason IDs, multi-hop flag, required source count, rerank flag |
| `route_trace` | One decision record per executed node |
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
| `usage` | Token usage reported by the existing generator |

`SearchHit` values are converted to plain dictionaries inside the graph.
Runtime dependencies and retriever objects are not part of state.

## Node Contract

| Node | Input | Output |
|---|---|---|
| `classify_question` | `question` | `route`, route trace |
| `rewrite_or_split_query` | question and route | one to three retrieval queries |
| `retrieve_evidence` | queries and injected retriever | serialized, deduplicated hits and timings |
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

## SSE Mapping

SSE events are emitted from graph nodes through LangGraph custom streaming:

1. `retrieving` at the start of `retrieve_evidence`
2. `generating` at the start of `assess_evidence`
3. zero or more `token` events emitted by `compose_answer`
4. `verifying_citations` at the start of `verify_citations_or_refuse`
5. final `done` event from the completed graph state

The FastAPI layer remains responsible for `start` and sanitized `error` events.
The external event names, payload fields, and order remain the Phase 1 contract.

## Errors

The graph does not catch or rewrite runtime exceptions. Retriever, data, model,
and validation exceptions propagate to the existing API boundary, which maps
them to the documented public error codes. No partial candidate citations are
emitted, and no retry loop is present.
