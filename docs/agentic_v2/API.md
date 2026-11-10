# Compliance RAG API v1

FastAPI exposes the existing B1 Fast and B3 RAG paths through FastAPI. Both the
synchronous and SSE endpoints run the controlled LangGraph state machine
documented in `docs/agentic_v2/GRAPH.md`. The default mode is `fast`. The graph
uses the bounded tools documented in `docs/agentic_v2/TOOLS.md`.

Run locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

## Request

Both answer endpoints accept:

```json
{
  "question": "eBay 是否允许销售假冒商品？",
  "mode": "fast"
}
```

- `question`: 1 to 2000 characters after trimming.
- `mode`: `fast` (default) or `high`.
- Optional header `X-Session-ID`: 1 to 128 characters using letters, numbers,
  `.`, `_`, `:`, or `-`.

When the header is omitted, the request is stateless and receives no prior
conversation context. When supplied, the same process-local session can reuse
up to four recent turns and a bounded summary of older turns. Session context
is never returned in the JSON response or SSE payload.

## Endpoints

- `GET /health`: returns `{"status":"ok"}`.
- `POST /api/v1/answer`: returns the complete answer.
- `POST /api/v1/answer/stream`: returns `text/event-stream`.

The synchronous response contains:

```json
{
  "request_id": "req_...",
  "mode": "fast",
  "answer": "回答正文 [C1]",
  "refused": false,
  "citations": [],
  "model": "deepseek-chat",
  "timings": {
    "retrieval_ms": 0.0,
    "generation_ms": 0.0,
    "verification_ms": 0.0,
    "total_ms": 0.0
  },
  "usage": {}
}
```

`citations` contains only citation IDs present in the answer body. A refusal
always has `refused: true` and an empty `citations` array.

The graph records route decisions internally. They do not add fields to the
public response model.

## SSE Events

Each event uses standard SSE framing:

```text
event: token
data: {"delta":"增量文本"}

```

The events appear in this order:

1. `start`: `request_id`, `mode`, `stream: true`.
2. `status`: `stage` is one of `retrieving`, `generating`, or
   `verifying_citations`. The graph emits these stages in that order.
3. `token`: `delta` contains one incremental answer fragment.
4. `done`: `request_id`, complete `answer`, `refused`, used `citations`,
   `model`, `timings`, and `usage`.
5. `error`: `request_id`, public `code`, and public `message`.

Candidate citations are never sent before `done`. If an error occurs after the
stream starts, an `error` event replaces `done`. Error payloads do not include
stack traces, API keys, environment values, or other internal configuration.

Tool failure uses the existing `error` event with public code
`tool_unavailable`. The event order remains `start`, optionally `status`, and
then either `done` or `error`.
