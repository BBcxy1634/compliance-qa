# Local Observability

Phase 4 uses a local JSONL trace instead of Langfuse or another hosted
observability service. It adds no dependency, collector, account, or network
export.

## Enablement

Evaluation runs always write local trace artifacts into their result directory.
The API and SSE endpoints enable tracing only when configured:

```dotenv
TRACE_ENABLED=true
TRACE_DIR=.cache/traces
```

`TRACE_ENABLED=false` is the default. The Gradio and CLI paths remain unchanged.

## Files

| File | Content |
|---|---|
| `traces.jsonl` | One sanitized request-level trace per answer or error |
| `errors.jsonl` | Requests that failed before a complete answer |
| `tool_failures.jsonl` | Failed tool outcomes with stable error codes |
| `summary.json` | Evaluator summary including trace and error counts |

Evaluation creates empty files at the start of each run so the artifact set is
predictable.

## Trace Fields

The allowlisted trace payload can contain:

- request ID and optional case ID
- status, mode, backend, Top K, route, and evidence decision
- model name and prompt version
- retrieval query hashes, hit count, chunk IDs, source IDs, and scores
- tool name, success flag, attempts, and stable error code
- prompt, completion, and total token counts
- retrieval, generation, verification, and total latency
- sanitized exception class and public error code

The trace never includes:

- API keys, `.env` values, or credentials
- complete prompts
- complete answers
- session IDs
- raw user questions
- private chunk text or conversation context
- exception messages or stack traces

Question and query text is represented only by a truncated SHA-256 hash.
Tool output summaries are excluded. Usage dictionaries are copied through an
allowlist rather than serialized wholesale.

## Failure Behavior

Trace writes are best effort. A directory, permission, or other JSONL write
failure disables the trace store and never changes the API response or SSE
event stream. The same rule applies when tracing is enabled for a running API.

This makes observability useful without allowing a diagnostic side channel to
break the user-facing answer path.

## API and SSE

Tracing is attached at the FastAPI boundary:

- synchronous success: trace after the engine returns
- synchronous error: sanitized error trace before the existing HTTP error
- SSE success: trace from the existing `done` data
- SSE error: sanitized error trace while preserving the existing `error` event

The public response models and SSE event order are unchanged.

## Inspecting a Run

Use the evaluator summary first:

```powershell
Get-Content eval/results/<run-name>/summary.json
```

Inspect failed requests or tools without reading console logs:

```powershell
Get-Content eval/results/<run-name>/errors.jsonl
Get-Content eval/results/<run-name>/tool_failures.jsonl
```

Trace and failure JSONL files are ignored by Git because runtime payloads may
still reveal operational patterns even after content redaction.
