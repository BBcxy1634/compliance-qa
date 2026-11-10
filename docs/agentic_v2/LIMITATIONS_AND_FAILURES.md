# V2 Limitations, Failures, and Operating Bounds

## Known Limitations

| Area | Current limitation |
|---|---|
| Human review | The 150-question agentic labels remain `draft`; independent human review was not executed |
| Automatic quality | Full 150-question answer correctness is 0.8077; 4 answerable questions are still falsely refused |
| Policy history | The current corpus has one snapshot per `source_id`, so real version comparison returns `insufficient_versions` |
| Deployment | No authentication, rate limiting, tenant isolation, or production secret manager |
| Sessions | Short-term context is process-local, bounded, and not shared between replicas |
| Trace | Local JSONL only; no hosted UI or distributed trace correlation |
| Hardware | B3 CPU reranking is slow; Compose defaults to CPU |
| Data startup | Clean checkout does not include official HTML/PDF, chunks, or Chroma data |
| Latency | The Phase 6 quality-oriented evaluation recorded answer P95 of 10.07 seconds; the simpler v1 benchmark P95 is 3.31 seconds |

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

These numbers used `deepseek-flash` pricing captured on 2026-10-31. They remain
the 100-request benchmark reference and are not a V2 benchmark.

The Phase 6 full evaluation separately recorded:

| Recorded metric | Value |
|---|---:|
| Answer P50 | 3085.76 ms |
| Answer P95 | 10069.12 ms |
| Prompt tokens | 510,589 |
| Completion tokens | 48,074 |
| Estimated model cost | CNY 0.6917 |

The cost estimate includes answer generation and automatic judging at recorded
off-peak rates. It is not a billing statement. A new 100-request V2 benchmark is
still required before making a new throughput claim.

## Release Boundary

v2.0.0 is released without:

- mark draft labels as human-approved
- claim actual Docker startup on a machine without Docker
- claim a new V2 100-request latency benchmark

GitHub Actions passed for the release commit, and v1/v2 release provenance is
preserved in Git tags and release notes.
