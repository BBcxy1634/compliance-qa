"""Tests for safe local JSONL traces."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.observability import TraceStore


@pytest.fixture
def trace_dir() -> Path:
    path = (
        Path(__file__).resolve().parents[1]
        / "pytest-cache-files-trace"
        / uuid4().hex
    )
    yield path
    shutil.rmtree(path, ignore_errors=True)


def _result() -> dict[str, Any]:
    return {
        "answer": "PRIVATE ANSWER WITH KEY sk-secret",
        "refused": False,
        "mode": "fast",
        "backend": "bge_m3",
        "top_k": 5,
        "model": "stub-model",
        "prompt_version": "prompt-v1",
        "route": "simple_fact",
        "evidence_sufficient": True,
        "evidence_reason": "sufficient",
        "sufficient_source_count": 1,
        "retrieval_breakdown": {
            "queries": [
                {
                    "query": "private customer question",
                    "retrieval_ms": 1.0,
                    "hit_count": 1,
                }
            ]
        },
        "hits": [
            {
                "chunk_id": "public#c01",
                "source_id": "public",
                "score": 0.9,
                "text": "PRIVATE FULL TEXT",
            }
        ],
        "tool_calls": [
            {"tool": "search_official_policy_sources", "ok": True, "attempts": 1},
            {
                "tool": "compare_policy_versions",
                "ok": False,
                "attempts": 1,
                "error": {
                    "code": "insufficient_versions",
                    "message": "PRIVATE EXCEPTION TEXT",
                },
            },
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "private_metric": "must not be copied",
        },
        "retrieval_ms": 1.0,
        "generation_ms": 2.0,
        "verification_ms": 0.5,
        "total_ms": 3.5,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_trace_records_metadata_without_private_content(
    trace_dir: Path,
) -> None:
    store = TraceStore(trace_dir)
    store.reset()
    store.record_result("req-1", _result(), case_id="q001")

    trace_text = (trace_dir / "traces.jsonl").read_text(encoding="utf-8")
    failures = _read_jsonl(trace_dir / "tool_failures.jsonl")
    trace = json.loads(trace_text)

    assert trace["request_id"] == "req-1"
    assert trace["route"] == "simple_fact"
    assert trace["prompt_version"] == "prompt-v1"
    assert trace["usage"] == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert len(trace["retrieval"]["query_hashes"][0]) == 16
    assert failures[0]["error_code"] == "insufficient_versions"
    assert "PRIVATE" not in trace_text
    assert "private customer question" not in trace_text
    assert "sk-secret" not in trace_text
    assert store.summary()["tool_failures"] == 1


def test_trace_error_is_sanitized(trace_dir: Path) -> None:
    store = TraceStore(trace_dir)
    store.reset()

    class ToolExecutionError(RuntimeError):
        pass

    store.record_error(
        "req-2",
        ToolExecutionError("sk-secret private message"),
        case_id="q002",
    )

    error = _read_jsonl(trace_dir / "errors.jsonl")[0]
    text = (trace_dir / "errors.jsonl").read_text(encoding="utf-8")
    assert error["error"]["code"] == "tool_unavailable"
    assert error["case_id"] == "q002"
    assert "sk-secret" not in text
    assert "private message" not in text


class StubEngine:
    def ask(
        self,
        question: str,
        mode_key: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        return _result()

    def stream_ask(
        self,
        question: str,
        mode_key: str,
        session_id: str | None = None,
    ):
        yield {
            "event": "done",
            "data": _result(),
        }


def test_api_survives_trace_write_failure(trace_dir: Path) -> None:
    not_a_directory = trace_dir / "trace-file"
    trace_dir.mkdir(parents=True, exist_ok=True)
    not_a_directory.write_text("occupied", encoding="utf-8")
    trace_store = TraceStore(not_a_directory)
    client = TestClient(create_app(StubEngine(), trace_store))

    response = client.post(
        "/api/v1/answer",
        json={"question": "trace failure test", "mode": "fast"},
    )
    stream_response = client.post(
        "/api/v1/answer/stream",
        json={"question": "trace failure test", "mode": "fast"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "PRIVATE ANSWER WITH KEY sk-secret"
    assert stream_response.status_code == 200
    assert "event: done" in stream_response.text


def test_api_trace_omits_session_and_question(trace_dir: Path) -> None:
    trace_store = TraceStore(trace_dir)
    trace_store.reset()
    client = TestClient(create_app(StubEngine(), trace_store))

    response = client.post(
        "/api/v1/answer",
        headers={"X-Session-ID": "private-session-id"},
        json={"question": "private user question", "mode": "fast"},
    )

    trace_text = (trace_dir / "traces.jsonl").read_text(encoding="utf-8")
    assert response.status_code == 200
    assert set(response.json()) == {
        "request_id",
        "mode",
        "answer",
        "refused",
        "citations",
        "model",
        "timings",
        "usage",
    }
    assert "private-session-id" not in trace_text
    assert "private user question" not in trace_text
    assert "PRIVATE ANSWER" not in trace_text
