# V2 Deployment and Verification

## Prerequisites

- Python 3.12 or newer; CI uses Python 3.13.
- Network access for first dependency, model, and official-source download.
- A configured `DEEPSEEK_API_KEY` only for real DeepSeek answers.
- Docker Engine or Docker Desktop with Compose v2 only for container startup.

## Local Data Preparation

The repository intentionally excludes official HTML/PDF files, processed chunks,
and Chroma data. Prepare them before real Q&A:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/bootstrap.py
python scripts/check_environment.py --require-data
```

Fill `DEEPSEEK_API_KEY` in `.env` before using DeepSeek. Keep `.env` untracked.

## Run the FastAPI Service

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The endpoint returns `{"status":"ok"}` without loading Chroma or a model. A real
answer still requires prepared data and a configured model key.

## Run with Docker Compose

Compose starts only the API service. It does not add another database, queue, or
observability backend.

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Stop:

```powershell
docker compose down
```

The service mounts:

| Host path | Container path | Mode |
|---|---|---|
| `./data` | `/app/data` | read-only |
| `./chroma_db` | `/app/chroma_db` | read-only |
| named `huggingface-cache` | `/app/.cache/huggingface` | read-write |
| named `trace-data` | `/app/.cache/traces` | read-write |

Run `python scripts/bootstrap.py` on the host before asking questions in the
container. `TORCH_DEVICE=cpu` is the Compose default; override it only when the
container has the matching GPU runtime.

### Trace Writes in Docker

Tracing is disabled by default:

```dotenv
TRACE_ENABLED=false
TRACE_DIR=/app/.cache/traces
```

Enable it by setting `TRACE_ENABLED=true` in `.env`. The image creates the Trace
directory for the non-root application user, and the named volume persists it.
TraceStore remains best effort: a directory or permission failure disables
tracing and does not prevent service startup or alter API/SSE responses.

## Deterministic CI-equivalent Checks

These commands require no API key, official source snapshots, Chroma database,
or model call:

```powershell
python -m compileall -q src scripts app.py evaluate.py bench.py
python -m pytest -q -m "not data"
python -m src.evaluate `
  --config eval/configs/phase4_b1_fast.yaml `
  --questions eval/fixtures/agentic_smoke_questions.jsonl `
  --chunks eval/fixtures/agentic_smoke_chunks.jsonl `
  --backend bm25 `
  --mode extractive `
  --judge none `
  --run-name ci_eval_smoke
python scripts/check_eval_smoke.py `
  --summary eval/results/ci_eval_smoke/summary.json
```

The smoke uses three synthetic questions and three synthetic policy topics plus
synthetic filler chunks. It exercises retrieval, routing, evidence refusal,
citation filtering, and metric output without real compliance sources.

## Full Local Validation

With local data and the vector database prepared:

```powershell
python -m pytest -q
python scripts/validate_eval.py
python scripts/validate_agentic_eval.py
python scripts/validate_sources.py
python scripts/check_environment.py --require-data
```

The 8 `data`-marked tests are excluded only in the no-data CI job. A full local
run executes them against the ignored corpus and Chroma artifacts.

## Docker Validation Boundary

`docker compose config --quiet` is the required syntax check in GitHub Actions.
Actual container startup must be recorded separately because Docker may not be
installed on the development machine. A health-check success proves service
startup only; it does not prove the local corpus or model cache is ready.
