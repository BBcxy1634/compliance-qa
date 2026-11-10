"""Static checks for Phase 5 packaging and CI configuration."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _yaml(path: Path, *, base_loader: bool = False) -> dict:
    loader = yaml.BaseLoader if base_loader else yaml.SafeLoader
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
    assert isinstance(value, dict)
    return value


def test_compose_defines_only_the_existing_api_runtime() -> None:
    compose = _yaml(ROOT / "compose.yaml")
    services = compose["services"]

    assert set(services) == {"api"}
    assert services["api"]["ports"] == ["${API_PORT:-8000}:8000"]
    assert services["api"]["environment"]["TRACE_ENABLED"] == (
        "${TRACE_ENABLED:-false}"
    )
    assert services["api"]["environment"]["TRACE_DIR"] == "/app/.cache/traces"
    assert "./data:/app/data:ro" in services["api"]["volumes"]
    assert "./chroma_db:/app/chroma_db:ro" in services["api"]["volumes"]
    assert set(compose["volumes"]) == {"huggingface-cache", "trace-data"}


def test_docker_image_uses_non_root_user_and_writable_trace_directory() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "python:3.13-slim" in dockerfile
    assert "mkdir -p /app/.cache/huggingface /app/.cache/traces" in dockerfile
    assert "USER app" in dockerfile
    assert "http://127.0.0.1:8000/health" in dockerfile


def test_docker_context_excludes_secrets_data_and_vector_store() -> None:
    ignored = {
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert {".env", ".env.*", "chroma_db", "data/raw/html", "data/raw/pdf"} <= ignored
    assert "data/processed" in ignored
    assert "official_pdf_*" in ignored


def test_ci_has_deterministic_tests_and_smoke_without_model_calls() -> None:
    workflow = _yaml(
        ROOT / ".github" / "workflows" / "ci.yml",
        base_loader=True,
    )
    jobs = workflow["jobs"]

    assert set(jobs) == {"tests", "eval-smoke"}
    test_text = yaml.safe_dump(jobs["tests"], sort_keys=False)
    smoke_text = yaml.safe_dump(jobs["eval-smoke"], sort_keys=False)
    combined = test_text + smoke_text
    assert 'python -m pytest -q -m "not data"' in test_text
    assert "docker compose config --quiet" in test_text
    assert "--backend bm25" in smoke_text
    assert "--mode extractive" in smoke_text
    assert "--judge none" in smoke_text
    assert "DEEPSEEK_API_KEY" not in combined


def test_smoke_fixture_is_synthetic_and_complete() -> None:
    questions = [
        yaml.safe_load(line)
        for line in (
            ROOT / "eval" / "fixtures" / "agentic_smoke_questions.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    chunks = [
        yaml.safe_load(line)
        for line in (
            ROOT / "eval" / "fixtures" / "agentic_smoke_chunks.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(questions) == 3
    assert len(chunks) >= 10
    assert all("synthetic fixture" in chunk["text"] for chunk in chunks)
    assert all(question["agentic"]["review_status"] == "draft" for question in questions)
