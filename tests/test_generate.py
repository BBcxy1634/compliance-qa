"""Deterministic tests for the streaming generation and RAG event path."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import src.generate as generate
import src.agent_graph as agent_graph
import src.rag as rag
from src.schemas import SearchHit


def _hits() -> list[SearchHit]:
    return [
        SearchHit(
            chunk={
                "chunk_id": "chunk-1",
                "title": "来源一",
                "source": "source-1.md",
                "page": 1,
                "kind": "html",
                "url": "https://example.com/1",
                "text": "来源一正文",
            },
            score=0.9,
        ),
        SearchHit(
            chunk={
                "chunk_id": "chunk-2",
                "title": "来源二",
                "source": "source-2.md",
                "page": 2,
                "kind": "html",
                "url": "https://example.com/2",
                "text": "来源二正文",
            },
            score=0.8,
        ),
    ]


def test_evidence_assessment_preserves_score_thresholds() -> None:
    question = "Amazon review policy"
    weak = SearchHit(
        chunk={"text": "Amazon review policy requirements"},
        score=0.2,
    )
    strong = SearchHit(
        chunk={"text": "Amazon review policy requirements"},
        score=0.8,
    )

    weak_result = generate.assess_evidence(
        question,
        [weak],
        min_score=0.25,
        backend="bge_m3",
    )
    strong_result = generate.assess_evidence(
        question,
        [strong],
        min_score=0.25,
        backend="bge_m3",
    )

    assert weak_result.sufficient is False
    assert weak_result.reason == "no_strong_hits"
    assert weak_result.strong_hits == []
    assert strong_result.sufficient is True
    assert strong_result.strong_hits == [strong]


def test_evidence_assessment_preserves_year_coverage_rule() -> None:
    hit = SearchHit(
        chunk={"text": "Policy updated in 2024 for sellers"},
        score=1.0,
    )
    result = generate.assess_evidence(
        "Policy updated in 2026 for sellers",
        [hit],
        min_score=0.5,
        backend="bm25",
    )

    assert result.sufficient is False
    assert result.reason == "query_year_not_covered"


def test_evidence_assessment_uses_combined_hits_and_date_metadata() -> None:
    hits = [
        SearchHit(
            chunk={
                "text": "2026 policy requirements for sellers",
                "updated_at": "2025-01-01",
            },
            score=0.4,
        ),
        SearchHit(
            chunk={
                "text": "Effective 2026 policy requirements",
                "updated_at": "2026-01-01",
            },
            score=0.3,
        ),
    ]

    result = generate.assess_evidence(
        "2026 policy requirements",
        hits,
        min_score=0.25,
        backend="bge_m3",
    )

    assert result.sufficient is True


def test_evidence_assessment_rejects_missing_entity_anchor() -> None:
    hit = SearchHit(
        chunk={"text": "2026 seller requirements and registration threshold"},
        score=0.8,
    )

    result = generate.assess_evidence(
        "What is the 2026 GST registration threshold?",
        [hit],
        min_score=0.25,
        backend="bge_m3",
    )

    assert result.sufficient is False
    assert result.reason == "term_coverage_missing"


def test_evidence_assessment_detects_acronym_after_chinese_text() -> None:
    hit = SearchHit(
        chunk={"text": "2026 registration threshold and seller requirements"},
        score=0.8,
    )

    result = generate.assess_evidence(
        "新加坡GST在2026年的注册门槛是多少？",
        [hit],
        min_score=0.25,
        backend="bge_m3",
    )

    assert result.sufficient is False


def test_deepseek_stream_yields_deltas_and_filters_done_citations(
    monkeypatch,
) -> None:
    usage = SimpleNamespace(
        model_dump=lambda: {
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
        }
    )
    chunks = [
        SimpleNamespace(
            model="stub-model",
            usage=None,
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="依据资料，"),
                )
            ],
        ),
        SimpleNamespace(
            model="stub-model",
            usage=None,
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="结论成立 [C2]。"),
                )
            ],
        ),
        SimpleNamespace(
            model="stub-model",
            usage=usage,
            choices=[],
        ),
    ]

    class FakeCompletions:
        def create(self, **kwargs: Any):
            assert kwargs["stream"] is True
            assert kwargs["stream_options"] == {"include_usage": True}
            return iter(chunks)

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(
                completions=FakeCompletions(),
            )

    monkeypatch.setattr(generate, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", FakeClient)

    items = list(generate.deepseek_answer_stream("测试", _hits()))
    assert items[0] == {"type": "token", "delta": "依据资料，"}
    assert items[1] == {"type": "token", "delta": "结论成立 [C2]。"}
    result = items[-1]["result"]
    assert items[-1]["type"] == "result"
    assert result["answer"] == "依据资料，结论成立 [C2]。"
    assert result["refused"] is False
    assert [item["citation_id"] for item in result["citations"]] == ["C2"]
    assert result["model"] == "stub-model"
    assert result["usage"]["total_tokens"] == 14


def test_deepseek_prompt_requests_two_sources_for_high_risk(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeCompletions:
        def create(self, **kwargs: Any):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="答案 [C1][C2]")
                    )
                ],
                model="stub-model",
                usage=None,
            )

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.chat = SimpleNamespace(
                completions=FakeCompletions(),
            )

    monkeypatch.setattr(generate, "DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr("openai.OpenAI", FakeClient)

    generate.deepseek_answer(
        "高风险问题",
        _hits(),
        required_source_count=2,
    )

    user_message = captured["messages"][1]["content"]
    assert "至少 2 个不同来源" in user_message


def test_rag_stream_uses_shared_retrieval_and_emits_contract_events(
    monkeypatch,
) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.last_timing_ms = {"vector_ms": 3.0}
            self.questions: list[str] = []

        def search(self, question: str, *, top_k: int):
            self.questions.append(question)
            assert top_k == 5
            return _hits()

    def fake_stream(question: str, hits: list[SearchHit], **_kwargs: Any):
        assert question == "流式查询"
        assert hits == _hits()
        yield {"type": "token", "delta": "增量 "}
        yield {"type": "token", "delta": "回答 [C1]"}
        yield {
            "type": "result",
            "result": {
                "answer": "增量 回答 [C1]",
                "refused": False,
                "citations": [
                    {"citation_id": "C1", "title": "来源一"},
                    {"citation_id": "C2", "title": "来源二"},
                ],
                "model": "stub-model",
                "usage": {"total_tokens": 8},
            },
        }

    monkeypatch.setattr(agent_graph, "deepseek_answer_stream", fake_stream)
    retriever = FakeRetriever()
    events = list(
        rag.stream_answer_with_retriever(
            "流式查询",
            retriever=retriever,
            backend="bge_m3",
            top_k=5,
            thinking=False,
            max_tokens=600,
        )
    )
    assert retriever.questions == ["流式查询"]
    assert [event["event"] for event in events] == [
        "status",
        "status",
        "token",
        "token",
        "status",
        "done",
    ]
    assert [event["data"]["stage"] for event in events if event["event"] == "status"] == [
        "retrieving",
        "generating",
        "verifying_citations",
    ]
    done = events[-1]["data"]
    assert done["answer"] == "增量 回答 [C1]"
    assert [item["citation_id"] for item in done["citations"]] == ["C1"]
    assert done["hits"][0]["chunk_id"] == "chunk-1"
