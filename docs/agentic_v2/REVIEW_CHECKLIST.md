# Agentic Compliance Copilot v2 Review Checklist

## Before Coding

- [ ] Read `AGENTS.md` and the three V2 planning documents.
- [ ] Run `git status --short --branch`.
- [ ] Confirm the current implementation phase.
- [ ] State assumptions and files expected to change.
- [ ] Do not implement future phases.

## Compatibility

- [ ] B1 Fast remains the default.
- [ ] B3 remains optional.
- [ ] Refusal still returns zero citations.
- [ ] Citation IDs come from the actual answer body.
- [ ] Existing CLI entry points still work.
- [ ] Existing Gradio demo still works or is intentionally migrated.
- [ ] Evaluation behavior remains comparable.

## Implementation Quality

- [ ] The change uses existing modules and patterns.
- [ ] No speculative abstraction was added.
- [ ] Tools and graph transitions are bounded.
- [ ] Errors have predictable, testable behavior.
- [ ] No secrets appear in code, logs, fixtures, or documents.
- [ ] Traces contain neither private content nor credentials.
- [ ] Trace write failure cannot break API or SSE responses.
- [ ] No raw official sources, vector databases, or private data are committed.

## Tests

- [ ] New behavior has focused tests.
- [ ] Invalid input is tested.
- [ ] Refusal behavior is tested when relevant.
- [ ] Streaming behavior is tested when relevant.
- [ ] Tool failure is tested when relevant.
- [ ] `python -m pytest -q` passes.
- [ ] `python scripts/check_environment.py --require-data` passes when data is
  needed.

## Documentation

- [ ] API, graph, or tool contracts are documented.
- [ ] `PROJECT_STATE.md` is updated.
- [ ] `IMPLEMENTATION_PLAN.md` status is updated if a phase is complete.
- [ ] Failures and limitations are recorded honestly.
- [ ] Metrics include the command or source used to generate them.
- [ ] Draft questions and labels are not represented as human-approved.

## Packaging and Release

- [ ] Docker Compose adds no infrastructure without a phase requirement.
- [ ] Docker build context excludes `.env`, official raw data, Chroma, and
  private data.
- [ ] Trace directory failure cannot prevent service startup or change API/SSE
  behavior.
- [ ] CI uses deterministic tests and a no-provider evaluation smoke.
- [ ] Actual Docker startup and remote CI results are recorded only after they
  run.
- [ ] Tag and GitHub Release creation remain separate approval-gated actions.

## Git

- [ ] One phase maps to one coherent commit.
- [ ] No unrelated changes are included.
- [ ] Worktree is clean after the commit.
- [ ] Push, force-push, release publication, and repository visibility changes
  require explicit user approval.

