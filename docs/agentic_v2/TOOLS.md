# Compliance Agent Tools

Phase 3 adds a small read-only tool layer behind the controlled LangGraph. Tools
are typed Python functions, not MCP servers or free-form agents.

## Runtime Boundary

`ToolRuntime` receives its runtime dependencies explicitly:

- existing retriever instance
- optional policy snapshot catalog
- retry ceiling
- deterministic "today" date for validity checks

Runtime objects are not stored in `AgentState`. Tool outputs and failures are
converted to JSON-serializable dictionaries before being recorded in graph
state.

## Tools

| Tool | Input | Success output | Stable failure codes |
|---|---|---|---|
| `search_official_policy_sources` | query, Top K | query and serialized `SearchHit` values | `timeout`, `unavailable`, `execution_error` |
| `inspect_latest_policy_snapshot` | `source_id` | latest snapshot metadata | `catalog_unavailable`, `not_found`, `execution_error` |
| `compare_policy_versions` | `source_id`, optional from/to versions | changed fields and content-hash comparison | `insufficient_versions`, `version_not_found`, `not_found`, `catalog_unavailable` |
| `validate_validity_period` | start date, end date, as-of date | `active`, `upcoming`, or `expired` with remaining days | `invalid_period`, `execution_error` |

Every invocation produces either `ToolSuccess` or `ToolFailure`. Failure
records contain a stable code, a retryable flag, and the final attempt count.
Internal exception text is not placed in graph state.

Phase 4 evaluation records tool selection separately from execution. A tool is
considered selected when its name appears in `tool_calls`, even if the call
later returns a stable failure. Tool success rate is computed independently
from those final outcomes.

## Retry Policy

- The default retry ceiling is 2 total attempts.
- Runtime configuration rejects values above the hard limit of 3.
- `TimeoutError` and `ConnectionError` are retryable.
- Other unexpected exceptions return `execution_error` without retrying.
- A multi-hop request is limited to three retrieval queries, so retrieval
  invocations also have a fixed upper bound.

The graph has no retry loop. If the core search tool still fails after its
budget, generation does not run and the API returns the existing sanitized
error channel with public code `tool_unavailable`.

## Policy Versions

The current source manifest contains one snapshot per `source_id`. The catalog
therefore supports version history when multiple rows with the same
`source_id` are supplied, but real comparison against the current corpus
returns `insufficient_versions`. It does not infer or fabricate policy
changes.

Version comparison checks metadata fields and `sha256`. It does not produce a
text diff.

## Conversation Boundary

Short-term session context is kept by the injected `ConversationStore`:

- process-local and bounded to 128 sessions by default
- at most 4 recent turns per session
- older turns are compacted into a deterministic summary
- no long-term memory and no persistence
- missing `X-Session-ID` produces a stateless single request

The graph stores only the serialized summary and recent turns. The model prompt
states that conversation context may resolve references but cannot replace
retrieved evidence or citation requirements.

Explicit follow-up patterns such as `那欧盟呢` prepend the last user question
to the retrieval query. This is a deterministic query rewrite, not an
autonomous planning loop.
