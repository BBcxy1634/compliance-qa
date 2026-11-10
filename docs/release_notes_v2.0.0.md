# v2.0.0 Release Notes

## Status

Released on 2026-11-11.

## Summary

Agentic Compliance Copilot v2 turns the existing compliance RAG application
into a controlled Agentic RAG service while preserving the B1 Fast default and
the released v1 CLI and Gradio paths.

## Highlights

- FastAPI and SSE interfaces for synchronous and streaming answers.
- Six-node LangGraph orchestration with deterministic routing and no loop edges.
- Bounded search, snapshot, version-comparison, and validity-period tools.
- Optional short-term context isolated by `X-Session-ID`.
- High-risk two-source rule and final-answer citation filtering.
- Local JSONL traces with payload allowlists and best-effort writes.
- Separate agentic evaluation metrics without changing original metric formulas.
- Docker Compose application startup with no extra infrastructure.
- GitHub Actions deterministic test and evaluation smoke jobs.

## Compatibility

- B1 Fast remains the default mode.
- B3 remains optional.
- Refused answers always have zero citations.
- Citations are filtered against the complete answer body.
- High-risk answers must cite at least two distinct sources.
- Existing CLI and Gradio entry points remain available.
- Original evaluation metrics and formulas remain unchanged.

## Verification Record

Phase 5 verification performed locally:

- 110 full tests pass when ignored local data and Chroma artifacts are present.
- 102 deterministic tests are selected with `-m "not data"`.
- The synthetic BM25/extractive evaluation smoke passes 3/3 questions.
- The smoke validates refusal accuracy 1.0 and route accuracy 1.0.
- No DeepSeek call is made by the deterministic tests or smoke.
- Compose, workflow, Dockerfile, Docker context, and fixture structure pass
  static tests.

Docker is not installed on the current machine, so no container build or startup
was executed. GitHub Actions run `42826433942` passed both jobs for commit
`e5ca1f5`.

## Evaluation Status

- Original set: 60 approved questions.
- Agentic set: 150 questions: 70 fact, 60 multi-hop, 20 refusal.
- New Phase 4 labels: `draft`.
- Deterministic route accuracy against draft labels: 149/150 (`0.9933`).
- Independent human review: not executed and not represented as passed.
- Full DeepSeek V2 evaluation: 150/150 requests completed, 0 failed.
- Answer correctness: 0.8077 overall, 0.8286 fact, 0.7833 multi-hop, 1.0 refusal.
- Citation accuracy: 1.0; answerable false refusals fell from 54 to 4.
- Agentic route accuracy: 0.9933.
- Tool selection accuracy: 1.0; tool success rate: 0.9915.
- Multi-step completion: 0.75; evidence sufficiency accuracy: 0.9867.
- Estimated model cost at recorded off-peak rates: CNY 0.6917.

## Performance Status

The recorded 100-request B1 Fast benchmark remains the v1 reference: mean
latency 1.92 seconds, P95 3.31 seconds, and mean cost about CNY 0.0010 per
request. The Phase 6 full evaluation separately recorded V2 answer P50 of
3085.76 ms and P95 of 10069.12 ms. It is an evaluation run, not a new 100-request
latency benchmark.

## Upgrade and Run

Prepare local data once:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/bootstrap.py
```

Run the API locally:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

Run with Compose:

```powershell
docker compose up --build -d
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Release Verification

- GitHub Actions run `42845638249` passed both jobs.
- The release branch is merged to `master`.
- Git tag and GitHub Release are `v2.0.0`.
- Docker runtime is intentionally unverified on the local machine.
- Independent human review of draft labels remains incomplete.

## Known Limitations

- No human-approved V2 evaluation subset exists yet.
- The quality-oriented path has a 10.07-second P95, so it is not a latency
  benchmark replacement.
- No new 100-request V2 benchmark has been run.
- Policy version comparison needs a multi-snapshot corpus.
- Sessions and traces are not shared across replicas.
- B3 is slow on CPU.
- Compose exposes the API only; Gradio remains a local entry point.
