# v2.0.0 Release Notes

## Status

Prepared as a release candidate on 2026-11-10. The Git tag and GitHub Release
have not been created. Publishing requires explicit project-owner approval.

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

- 94 full tests pass when ignored local data and Chroma artifacts are present.
- 86 deterministic tests are selected with `-m "not data"`.
- The synthetic BM25/extractive evaluation smoke passes 3/3 questions.
- The smoke validates refusal accuracy 1.0 and route accuracy 1.0.
- No DeepSeek call is made by the deterministic tests or smoke.
- Compose, workflow, Dockerfile, Docker context, and fixture structure pass
  static tests.

Docker is not installed on the current machine, so no container build or startup
was executed. GitHub Actions has not run because this phase was not pushed.

## Evaluation Status

- Original set: 60 approved questions.
- Agentic set: 150 questions: 70 fact, 60 multi-hop, 20 refusal.
- New Phase 4 labels: `draft`.
- Deterministic route accuracy against draft labels: 136/150 (`0.9067`).
- Independent human review: not executed and not represented as passed.
- Full paid DeepSeek V2 evaluation: not run in Phase 4 or Phase 5.

## Performance Status

The recorded B1 Fast benchmark remains the v1 reference: mean latency 1.92
seconds, P95 3.31 seconds, and mean cost about CNY 0.0010 per request. These are
not new V2 end-to-end measurements.

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

## Release Actions Requiring Approval

- Run the GitHub Actions workflow after pushing the branch or opening a PR.
- Run an actual Docker build and startup on a Docker-enabled machine.
- Decide whether to run the full paid 150-question DeepSeek evaluation.
- Decide whether draft labels need independent human review before release.
- Create the `v2.0.0` tag and GitHub Release.
- Merge to `master`.

## Known Limitations

- No human-approved V2 evaluation subset exists yet.
- No full paid V2 evaluation or V2 benchmark has been run.
- Policy version comparison needs a multi-snapshot corpus.
- Sessions and traces are not shared across replicas.
- B3 is slow on CPU.
- Compose exposes the API only; Gradio remains a local entry point.
