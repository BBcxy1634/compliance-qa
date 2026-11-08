# Project Instructions

## Scope

This repository contains the released v1.0.0 compliance RAG assistant and the
in-progress Agentic Compliance Copilot v2.0 work.

Unless the user explicitly asks for an unrelated task, all work must preserve
the released v1 behavior while extending it in small, tested steps.

## Required Reading

Before planning or editing code, read:

1. `docs/agentic_v2/PROJECT_STATE.md`
2. `docs/agentic_v2/IMPLEMENTATION_PLAN.md`
3. `docs/agentic_v2/DECISIONS.md`
4. `docs/agentic_v2/REVIEW_CHECKLIST.md`

Then inspect:

```powershell
git status --short --branch
git log -5 --oneline
```

If the current task is not covered by the documented current phase, stop and
ask instead of silently extending scope.

## Workflow

1. State the assumptions and the single phase being implemented.
2. List the files expected to change before editing.
3. Prefer the existing modules and patterns over new abstractions.
4. Make the smallest change that satisfies the current phase.
5. Add or update tests for the changed behavior.
6. Run the relevant tests before claiming completion.
7. Update `docs/agentic_v2/PROJECT_STATE.md`.
8. Commit the phase as one coherent Git commit.

Do not implement future phases in the same task unless the user explicitly
expands the scope.

## Compatibility Requirements

- Keep the current B1 Fast default behavior.
- Keep B3 as an optional quality mode, not the default.
- Preserve refusal behavior and the rule that refused answers show zero
  citations.
- Preserve real citation filtering based on citation IDs present in the answer.
- Keep the existing CLI entry points in `src/rag.py` working.
- Keep the existing Gradio app working until an API/UI migration is explicitly
  completed.
- Do not change benchmark or evaluation metrics without documenting the reason.

## V2 Technical Boundaries

- Use a controlled LangGraph state machine, not free-form multi-agent chat.
- Use FastAPI and SSE for the streaming application interface.
- Keep the current Chroma and B1 Fast retrieval path initially.
- Add tools behind a small interface; MCP is an adapter, not a rewrite.
- Add short-term conversation context only when the relevant phase starts.
- Add Qdrant, PostgreSQL, or Redis only when a concrete phase requirement
  justifies them.
- Do not add Kubernetes, microservices, or speculative abstractions.
- Do not introduce features outside the current implementation phase.

## Testing Commands

```powershell
python -m pytest -q
python scripts/check_environment.py --require-data
```

Use the existing `.venv` for runtime checks when appropriate:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Data and Security

- Never commit `.env`, API keys, credentials, model caches, vector databases,
  raw official HTML/PDF snapshots, or private data.
- Never print API keys or tokens in logs, tests, documentation, or final replies.
- Keep source URLs and provenance metadata intact.
- Do not force-push, rewrite history, change repository visibility, or publish
  release artifacts without explicit user approval.

## Completion Standard

A phase is complete only when:

- The requested behavior is implemented.
- Tests cover the new behavior.
- Existing tests still pass.
- Documentation and `PROJECT_STATE.md` are updated.
- The Git worktree is clean after the phase commit.

