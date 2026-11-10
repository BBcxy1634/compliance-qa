# V2 Limitations, Failures, and Operating Bounds

## Known Limitations

| Area | Current limitation |
|---|---|
| Human review | The 150-question agentic labels remain `draft`; independent human review was not executed |
| Paid evaluation | No full DeepSeek V2 evaluation was run in Phase 4 or Phase 5 |
| Policy history | The current corpus has one snapshot per `source_id`, so real version comparison returns `insufficient_versions` |
| Deployment | No authentication, rate limiting, tenant isolation, or production secret manager |
| Sessions | Short-term context is process-local, bounded, and not shared between replicas |
| Trace | Local JSONL only; no hosted UI or distributed trace correlation |
| Hardware | B3 CPU reranking is slow; Compose defaults to CPU |
| Data startup | Clean checkout does not include official HTML/PDF, chunks, or Chroma data |
| Latency | B1 Fast reference P95 is 3.31 seconds and remains above the 3-second target |

## Failure Cases

| Failure | Current behavior | Verification or mitigation |
|---|---|---|
| API key missing during an answer | Public generic API error; health remains available | Configure `.env`; use deterministic tests and smoke without a key |
| Chroma or chunk data missing | Answer request fails; process can still start | Run `bootstrap.py`; `/health` does not load data |
| Core search tool exhausts retries | HTTP 503 `tool_unavailable` or SSE `error` | Bounded at three total attempts with default two |
| Generator provider fails | HTTP 502 `model_error` or SSE `error` | Public message omits provider detail |
| Evidence below threshold | Refusal with `refused=true` and zero citations | Generation is skipped |
| High-risk final answer cites one source | Candidate is replaced by refusal | At least two distinct cited sources are required |
| Model cites an unused candidate | Candidate citation is filtered out | Citation IDs must occur in the answer body |
| Optional snapshot/version tool fails | Failure is recorded; valid search evidence can continue | Stable tool failure code is stored |
| Trace directory is not writable | TraceStore disables itself | API/SSE response remains unchanged |
| SSE fails after stream start | `error` event replaces `done` | Event payload excludes stack traces and secrets |
| Compose host data is absent | Service and health endpoint can start; Q&A is not ready | Run host-side bootstrap before answering |
| B3 is used in the CPU container | High latency and first-load model download | Keep Fast as default; use B3 explicitly |

## Cost and Latency Reference

The recorded 100-request benchmark predates the V2 graph wrapper and is kept as a
v1 reference, not as a new V2 paid benchmark:

| Mode | Mean latency | P95 latency | Mean cost CNY/request |
|---|---:|---:|---:|
| B1 Fast | 1.92 s | 3.31 s | 0.0010 |
| B3 | 8.17 s | 12.31 s | 0.0011 |

These numbers used `deepseek-flash` pricing captured on 2026-10-31. The graph
adds local routing and tool overhead, and no Phase 5 claim is made about the
V2 end-to-end paid latency or cost. Measurements must be regenerated with
`bench.py` before publishing new performance claims.

## Release Boundary

Phase 5 prepares packaging and documentation only. It does not:

- mark draft labels as human-approved
- claim that GitHub Actions passed before it runs
- claim actual Docker startup on a machine without Docker
- create a tag, push a branch, merge `master`, or publish a GitHub Release
