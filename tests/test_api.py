"""API contract tests using deterministic in-memory engines."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from src.api import create_app
from src.generate import ModelGenerationError


def _result(
    *,
    answer: str = "不允许。[C1][C3]",
    refused: bool = False,
) -> dict[str, Any]:
    return {
        "answer": answer,
        "refused": refused,
        "citations": [
            {
                "citation_id": "C1",
                "title": "来源一",
                "source": "source-1.md",
                "location": "第 1 页",
                "url": "https://example.com/1",
                "chunk_id": "chunk-1",
                "score": 0.9,
            },
            {
                "citation_id": "C2",
                "title": "未使用候选",
                "source": "source-2.md",
                "location": "第 2 页",
                "url": "https://example.com/2",
                "chunk_id": "chunk-2",
                "score": 0.8,
            },
            {
                "citation_id": "C3",
                "title": "来源三",
                "source": "source-3.md",
                "location": "第 3 页",
                "url": "https://example.com/3",
                "chunk_id": "chunk-3",
                "score": 0.7,
            },
        ],
        "model": "stub-model",
        "retrieval_ms": 10.0,
        "generation_ms": 20.0,
        "verification_ms": 1.0,
        "total_ms": 31.0,
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
    }


class StubEngine:
    def __init__(
        self,
        *,
        result: dict[str, Any] | None = None,
        stream_events: list[dict[str, Any]] | None = None,
        stream_error: Exception | None = None,
        sync_error: Exception | None = None,
    ) -> None:
        self.result = result or _result()
        self.stream_events = stream_events
        self.stream_error = stream_error
        self.sync_error = sync_error
        self.stream_inputs: list[tuple[str, str]] = []

    def ask(self, question: str, mode_key: str) -> dict[str, Any]:
        if self.sync_error:
            raise self.sync_error
        return self.result

    def stream_ask(self, question: str, mode_key: str):
        self.stream_inputs.append((question, mode_key))
        if self.stream_error:
            raise self.stream_error
        return iter(self.stream_events or [])


def _parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line[7:] for line in lines if line.startswith("event: "))
        data = next(line[6:] for line in lines if line.startswith("data: "))
        events.append((event, json.loads(data)))
    return events


def test_health_returns_ok() -> None:
    client = TestClient(create_app(StubEngine()))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sync_answer_filters_unused_candidate_citations() -> None:
    client = TestClient(create_app(StubEngine()))
    response = client.post(
        "/api/v1/answer",
        json={"question": "测试问题", "mode": "fast"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"].startswith("req_")
    assert payload["mode"] == "fast"
    assert payload["answer"] == "不允许。[C1][C3]"
    assert [item["citation_id"] for item in payload["citations"]] == ["C1", "C3"]
    assert payload["timings"]["total_ms"] == 31.0
    assert payload["usage"]["total_tokens"] == 20


def test_sync_refusal_has_no_citations() -> None:
    result = _result(
        answer="文档中未找到足够依据，暂时无法回答这个问题。",
        refused=True,
    )
    client = TestClient(create_app(StubEngine(result=result)))
    response = client.post(
        "/api/v1/answer",
        json={"question": "证据不足的问题"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["refused"] is True
    assert payload["citations"] == []


def test_invalid_input_has_stable_error_shape() -> None:
    client = TestClient(create_app(StubEngine()))
    blank = client.post(
        "/api/v1/answer",
        json={"question": "   "},
    )
    invalid_mode = client.post(
        "/api/v1/answer",
        json={"question": "测试", "mode": "unknown"},
    )
    assert blank.status_code == 422
    assert blank.json() == {
        "error": {
            "code": "validation_error",
            "message": "请求参数无效。",
        }
    }
    assert invalid_mode.status_code == 422
    assert invalid_mode.json()["error"]["code"] == "validation_error"


def test_stream_follows_event_contract_and_filters_citations() -> None:
    result = _result(answer="你好 [C1]")
    engine = StubEngine(
        stream_events=[
            {"event": "status", "data": {"stage": "retrieving"}},
            {"event": "status", "data": {"stage": "generating"}},
            {"event": "token", "data": {"delta": "你"}},
            {"event": "token", "data": {"delta": "好 [C1]"}},
            {"event": "status", "data": {"stage": "verifying_citations"}},
            {"event": "done", "data": result},
        ]
    )
    client = TestClient(create_app(engine))
    response = client.post(
        "/api/v1/answer/stream",
        json={"question": "流式测试", "mode": "fast"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert [name for name, _data in events] == [
        "start",
        "status",
        "status",
        "token",
        "token",
        "status",
        "done",
    ]
    assert events[0][1] == {
        "request_id": events[0][1]["request_id"],
        "mode": "fast",
        "stream": True,
    }
    assert [data["stage"] for name, data in events if name == "status"] == [
        "retrieving",
        "generating",
        "verifying_citations",
    ]
    assert "".join(
        data["delta"] for name, data in events if name == "token"
    ) == "你好 [C1]"
    assert "未使用候选" not in response.text
    done = events[-1][1]
    assert set(done) == {
        "request_id",
        "answer",
        "refused",
        "citations",
        "model",
        "timings",
        "usage",
    }
    assert done["request_id"] == events[0][1]["request_id"]
    assert done["answer"] == "你好 [C1]"
    assert done["refused"] is False
    assert [item["citation_id"] for item in done["citations"]] == ["C1"]
    assert done["model"] == "stub-model"
    assert done["timings"] == {
        "retrieval_ms": 10.0,
        "generation_ms": 20.0,
        "verification_ms": 1.0,
        "total_ms": 31.0,
    }
    assert done["usage"]["total_tokens"] == 20
    assert engine.stream_inputs == [("流式测试", "fast")]


def test_stream_refusal_has_no_citations() -> None:
    result = _result(
        answer="文档中未找到足够依据，暂时无法回答这个问题。",
        refused=True,
    )
    engine = StubEngine(
        stream_events=[
            {"event": "status", "data": {"stage": "retrieving"}},
            {"event": "status", "data": {"stage": "generating"}},
            {
                "event": "token",
                "data": {"delta": "文档中未找到足够依据，暂时无法回答这个问题。"},
            },
            {"event": "status", "data": {"stage": "verifying_citations"}},
            {"event": "done", "data": result},
        ]
    )
    client = TestClient(create_app(engine))
    response = client.post(
        "/api/v1/answer/stream",
        json={"question": "证据不足的问题"},
    )
    done = _parse_sse(response.text)[-1][1]
    assert done["refused"] is True
    assert done["citations"] == []


def test_sync_model_error_is_sanitized() -> None:
    engine = StubEngine(
        sync_error=ModelGenerationError("sensitive provider detail")
    )
    client = TestClient(create_app(engine))
    response = client.post(
        "/api/v1/answer",
        json={"question": "触发错误"},
    )
    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "model_error",
            "message": "生成模型暂时不可用。",
        }
    }
    assert "sensitive provider detail" not in response.text


def test_stream_error_is_sanitized() -> None:
    engine = StubEngine(
        stream_error=ModelGenerationError("sensitive provider detail")
    )
    client = TestClient(create_app(engine))
    response = client.post(
        "/api/v1/answer/stream",
        json={"question": "触发错误"},
    )
    events = _parse_sse(response.text)
    assert [name for name, _data in events] == ["start", "error"]
    error = events[-1][1]
    assert error["request_id"] == events[0][1]["request_id"]
    assert error["code"] == "model_error"
    assert error["message"] == "生成模型暂时不可用。"
    assert "sensitive provider detail" not in response.text
    assert "Traceback" not in response.text
