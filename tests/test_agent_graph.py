"""Deterministic tests for the controlled LangGraph answer flow."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

import src.agent_graph as agent_graph
from src.agent_graph import (
    GraphDependencies,
    _expand_adjacent_hits,
    answer_with_graph,
    build_agent_graph,
    classify_route,
    stream_answer_with_graph,
)
from src.generate import REFUSAL_TEXT
from src.schemas import SearchHit
from src.tools import ToolExecutionError, ToolRuntime


class StubRetriever:
    def __init__(
        self,
        *,
        hits_by_query: dict[str, list[SearchHit]] | None = None,
        default_hits: list[SearchHit] | None = None,
    ) -> None:
        self.hits_by_query = hits_by_query or {}
        self.default_hits = default_hits or []
        self.questions: list[str] = []
        self.top_k_values: list[int] = []
        self.last_timing_ms = {"stub_ms": 1.0}

    def search(self, query: str, *, top_k: int) -> list[SearchHit]:
        assert top_k in {5, 10}
        self.questions.append(query)
        self.top_k_values.append(top_k)
        return self.hits_by_query.get(query, self.default_hits)


class FailingRetriever:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, *, top_k: int) -> list[SearchHit]:
        self.calls += 1
        raise TimeoutError(query)


def _hit(
    source_id: str,
    *,
    chunk_id: str | None = None,
    score: float = 0.9,
) -> SearchHit:
    return SearchHit(
        chunk={
            "chunk_id": chunk_id or f"{source_id}-chunk",
            "source_id": source_id,
            "source": f"{source_id}.md",
            "title": f"{source_id} title",
            "page": 1,
            "kind": "html",
            "page_label": "第 1 页",
            "text": "policy requirements for sellers",
            "url": f"https://example.com/{source_id}",
        },
        score=score,
    )


def _generated(
    answer: str,
    *source_ids: str,
) -> dict[str, Any]:
    return {
        "answer": answer,
        "refused": False,
        "citations": [
            {
                "citation_id": f"C{index}",
                "source_id": source_id,
                "source": f"{source_id}.md",
                "title": f"{source_id} title",
            }
            for index, source_id in enumerate(source_ids, 1)
        ],
        "mode": "deepseek",
        "model": "stub-model",
        "usage": {"total_tokens": 8},
        "prompt_version": "deepseek-compliance-v2.1",
    }


def _dependencies(
    retriever: StubRetriever | FailingRetriever,
    *,
    tool_runtime: ToolRuntime | None = None,
) -> GraphDependencies:
    return GraphDependencies(
        retriever=retriever,
        backend="bge_m3",
        generation_mode="deepseek",
        top_k=5,
        thinking=False,
        max_tokens=600,
        tool_runtime=tool_runtime,
    )


def test_adjacent_chunk_expansion_adds_same_page_neighbor(
    monkeypatch,
) -> None:
    first = {"chunk_id": "source#p01#c01", "text": "first"}
    second = {"chunk_id": "source#p01#c02", "text": "second"}
    monkeypatch.setattr(
        agent_graph,
        "_adjacent_chunk_map",
        lambda: {"source#p01": [first, second]},
    )

    expanded = _expand_adjacent_hits(
        [{"chunk": first, "score": 0.9}]
    )

    assert [item["chunk"]["chunk_id"] for item in expanded] == [
        "source#p01#c01",
        "source#p01#c02",
    ]


@pytest.mark.parametrize(
    ("question", "rule_id"),
    [
        ("Amazon counterfeit policy?", "counterfeit_ip"),
        ("儿童玩具的产品安全要求？", "restricted_product_safety"),
        ("欧盟 VAT 和清关要求？", "customs_tax_sanctions"),
        ("客户数据与隐私保护要求？", "privacy_data"),
        ("违规会被罚款或承担法律责任吗？", "penalty_liability"),
    ],
)
def test_high_risk_rule_taxonomy(
    question: str,
    rule_id: str,
) -> None:
    decision = classify_route(question, "bge_m3")

    assert decision["route"] == "high_risk"
    assert f"high_risk:{rule_id}" in decision["reasons"]
    assert decision["required_source_count"] == 2


@pytest.mark.parametrize(
    ("question", "route"),
    [
        (
            "Can an eBay seller use product photos copied from "
            "another website without permission?",
            "high_risk",
        ),
        ("Are parallel imports always allowed on eBay?", "high_risk"),
        (
            "Must logos on an authentic branded item be visible in "
            "eBay listing photos?",
            "high_risk",
        ),
        ("充电宝出口加拿大需要哪些运输标签？", "high_risk"),
        ("出口海外仓预退税的核算期是什么时间段？", "high_risk"),
        (
            "亚马逊卖家承认违规后，当前申诉形式发生了什么变化，"
            "还需要覆盖哪些内容？",
            "multi_hop",
        ),
        (
            "How do the feedback and offensive materials policies apply?",
            "multi_hop",
        ),
        (
            "商品被列入零售进口清单，是否就等于可以直接进口销售？",
            "multi_hop",
        ),
    ],
)
def test_route_regressions_for_phase6(question: str, route: str) -> None:
    assert classify_route(question, "bge_m3")["route"] == route


def test_simple_fact_uses_fast_route_and_records_decisions(
    monkeypatch,
) -> None:
    question = "Amazon return policy?"
    retriever = StubRetriever(default_hits=[_hit("source-1")])
    calls: list[str] = []

    def fake_answer(question_value: str, _hits, **_kwargs):
        calls.append(question_value)
        return _generated("Sellers can return items [C1].", "source-1")

    monkeypatch.setattr(agent_graph, "deepseek_answer", fake_answer)
    result = answer_with_graph(question, _dependencies(retriever))

    assert result["route"] == "simple_fact"
    assert result["route_decision"]["rerank"] is False
    assert retriever.questions == [question]
    assert calls == [question]
    assert [item["node"] for item in result["route_trace"]] == [
        "classify_question",
        "rewrite_or_split_query",
        "retrieve_evidence",
        "assess_evidence",
        "compose_answer",
        "verify_citations_or_refuse",
    ]
    assert result["refused"] is False
    assert [item["citation_id"] for item in result["citations"]] == ["C1"]
    assert result["retrieval_breakdown"]["stub_ms"] == 1.0
    assert result["retrieval_breakdown"]["queries"][0]["hit_count"] == 1
    assert result["tool_calls"][0]["tool"] == (
        "search_official_policy_sources"
    )
    assert result["tool_calls"][0]["ok"] is True
    assert result["evidence_sufficient"] is True
    assert result["evidence_reason"] == "sufficient"
    assert result["top_k"] == 5
    assert result["prompt_version"] == "deepseek-compliance-v2.1"


def test_multi_hop_question_is_split_without_reranking(
    monkeypatch,
) -> None:
    question = (
        "Amazon return policy and listing description policy: "
        "which two policy areas apply?"
    )
    retriever = StubRetriever(
        default_hits=[
            _hit("return-policy", chunk_id="return-1"),
            _hit("description-policy", chunk_id="description-1"),
        ]
    )
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: _generated(
            "Both policies apply [C1][C2].",
            "return-policy",
            "description-policy",
        ),
    )
    result = answer_with_graph(question, _dependencies(retriever))

    assert result["route"] == "multi_hop"
    assert result["route_decision"]["multi_hop"] is True
    assert result["route_decision"]["rerank"] is False
    assert len(retriever.questions) == 2
    retrieve_trace = next(
        item
        for item in result["route_trace"]
        if item["node"] == "retrieve_evidence"
    )
    assert retrieve_trace["query_count"] == 2


def test_multi_hop_uses_aggregate_evidence_across_subqueries(
    monkeypatch,
) -> None:
    question = (
        "Amazon return policy and listing description policy: "
        "which two policy areas apply?"
    )
    retriever = StubRetriever(
        hits_by_query={
            "Amazon return policy": [
                SearchHit(
                    chunk={
                        "chunk_id": "return-1",
                        "source_id": "return-policy",
                        "source": "return-policy.md",
                        "text": "Amazon return policy",
                    },
                    score=0.4,
                )
            ],
            "listing description policy: which two policy areas apply": [
                SearchHit(
                    chunk={
                        "chunk_id": "description-1",
                        "source_id": "description-policy",
                        "source": "description-policy.md",
                        "text": "listing description policy",
                    },
                    score=0.4,
                )
            ],
        }
    )
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: _generated(
            "Both policies apply [C1][C2].",
            "return-policy",
            "description-policy",
        ),
    )

    result = answer_with_graph(question, _dependencies(retriever))

    assert result["evidence_sufficient"] is True
    assert result["refused"] is False


def test_high_risk_requires_two_distinct_sources(
    monkeypatch,
) -> None:
    question = "Amazon 是否允许销售假冒商品？"
    retriever = StubRetriever(
        default_hits=[
            _hit("source-1", chunk_id="source-1-a"),
            _hit("source-1", chunk_id="source-1-b"),
        ]
    )
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generation must not run without two sources")
        ),
    )
    result = answer_with_graph(question, _dependencies(retriever))

    assert classify_route(question, "bge_m3")["route"] == "high_risk"
    assert result["route"] == "high_risk"
    assert result["refused"] is True
    assert result["answer"] == REFUSAL_TEXT
    assert result["citations"] == []
    assert result["route_decision"]["required_source_count"] == 2
    assessment = next(
        item
        for item in result["route_trace"]
        if item["node"] == "assess_evidence"
    )
    assert assessment["reason"] == "high_risk:insufficient_source_count"


def test_high_risk_accepts_two_sources_when_both_are_cited(
    monkeypatch,
) -> None:
    question = "Amazon 是否允许销售假冒商品？"
    retriever = StubRetriever(
        default_hits=[_hit("source-1"), _hit("source-2")]
    )
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: _generated(
            "不允许 [C1][C2]。",
            "source-1",
            "source-2",
        ),
    )
    result = answer_with_graph(question, _dependencies(retriever))

    assert result["refused"] is False
    assert [item["source_id"] for item in result["citations"]] == [
        "source-1",
        "source-2",
    ]


def test_high_risk_counts_sources_beyond_first_three_hits(
    monkeypatch,
) -> None:
    question = "Amazon 是否允许销售假冒商品？"
    retriever = StubRetriever(
        default_hits=[
            _hit("source-1", chunk_id=f"source-1-{index}")
            for index in range(6)
        ]
        + [
            _hit("source-2", chunk_id=f"source-2-{index}")
            for index in range(2)
        ]
    )
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: _generated(
            "不允许 [C1][C2]。",
            "source-1",
            "source-2",
        ),
    )

    result = answer_with_graph(question, _dependencies(retriever))

    assert result["evidence_sufficient"] is True
    assert result["sufficient_source_count"] == 2
    assert result["refused"] is False
    assert retriever.top_k_values == [10]


def test_high_risk_refuses_when_final_answer_cites_one_source(
    monkeypatch,
) -> None:
    question = "Amazon 是否允许销售假冒商品？"
    retriever = StubRetriever(
        default_hits=[_hit("source-1"), _hit("source-2")]
    )
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: _generated(
            "不允许 [C1]。",
            "source-1",
            "source-2",
        ),
    )
    result = answer_with_graph(question, _dependencies(retriever))

    assert result["refused"] is True
    assert result["citations"] == []
    verification = result["route_trace"][-1]
    assert verification["node"] == "verify_citations_or_refuse"
    assert verification["reason"] == "high_risk:insufficient_cited_sources"


def test_insufficient_evidence_refuses_without_generation(
    monkeypatch,
) -> None:
    retriever = StubRetriever(default_hits=[])
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generation must not run without evidence")
        ),
    )
    result = answer_with_graph(
        "Unknown policy question?",
        _dependencies(retriever),
    )

    assert result["refused"] is True
    assert result["answer"] == REFUSAL_TEXT
    assert result["citations"] == []
    assert result["route_trace"][-1]["node"] == "verify_citations_or_refuse"


def test_deepseek_refusal_falls_back_to_extractive_answer(
    monkeypatch,
) -> None:
    retriever = StubRetriever(
        default_hits=[
            _hit(
                "source-1",
                chunk_id="source-1",
            )
        ]
    )
    calls: list[bool] = []

    def fake_answer(*_args, **kwargs):
        calls.append(bool(kwargs.get("repair")))
        if kwargs.get("repair"):
            return {
                "answer": "Policy requirement [C1].",
                "refused": False,
                "citations": [
                    {
                        "citation_id": "C1",
                        "source_id": "source-1",
                        "source": "source-1.md",
                    }
                ],
                "mode": "deepseek",
                "model": "stub-model",
            }
        return {
            "answer": REFUSAL_TEXT,
            "refused": True,
            "citations": [],
            "mode": "deepseek",
            "model": "stub-model",
        }

    monkeypatch.setattr(agent_graph, "deepseek_answer", fake_answer)

    result = answer_with_graph(
        "What is the policy requirement?",
        _dependencies(retriever),
    )

    assert result["refused"] is False
    assert result["citations"]
    assert calls == [False, True]
    compose_trace = next(
        item
        for item in result["route_trace"]
        if item["node"] == "compose_answer"
    )
    assert compose_trace["repair_generation"] is True


def test_graph_state_is_json_serializable_and_records_route(
    monkeypatch,
) -> None:
    retriever = StubRetriever(default_hits=[_hit("source-1")])
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: _generated(
            "Conclusion [C1].",
            "source-1",
        ),
    )
    state = build_agent_graph(_dependencies(retriever)).invoke(
        {
            "question": "Simple policy question?",
            "route_trace": [],
        }
    )
    payload = json.dumps(state, ensure_ascii=False)

    assert '"route": "simple_fact"' in payload
    assert state["route"]["route"] == "simple_fact"
    assert state["route_trace"][0]["route"] == "simple_fact"


def test_core_tool_failure_stops_generation_after_bounded_retries(
    monkeypatch,
) -> None:
    retriever = FailingRetriever()
    runtime = ToolRuntime(retriever, max_attempts=2)
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("generation must not run after a tool failure")
        ),
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        answer_with_graph(
            "Simple policy question?",
            _dependencies(retriever, tool_runtime=runtime),
        )

    assert exc_info.value.code == "timeout"
    assert retriever.calls == 2


def test_date_validation_tool_is_recorded_in_graph_trace(
    monkeypatch,
) -> None:
    question = (
        "2026年1月1日至2027年12月31日期间，"
        "跨境出口退运税收优惠的适用条件是什么？"
    )
    retriever = StubRetriever(default_hits=[_hit("source-1")])
    runtime = ToolRuntime(
        retriever,
        max_attempts=2,
        today=date(2026, 11, 10),
    )
    monkeypatch.setattr(
        agent_graph,
        "deepseek_answer",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("high-risk single-source answer must refuse")
        ),
    )

    result = answer_with_graph(
        question,
        _dependencies(retriever, tool_runtime=runtime),
    )

    date_call = next(
        item
        for item in result["tool_calls"]
        if item["tool"] == "validate_validity_period"
    )
    assert date_call["ok"] is True
    assert date_call["output_summary"]["status"] == "active"


def test_conversation_context_reaches_generation(
    monkeypatch,
) -> None:
    retriever = StubRetriever(default_hits=[_hit("source-1")])
    captured: dict[str, Any] = {}
    context = {
        "summary": "Seller sells in the US.",
        "recent_turns": [
            {
                "question": "US policy?",
                "answer": "US answer [C1]",
                "refused": False,
            }
        ],
    }

    def fake_answer(_question, _hits, **kwargs):
        captured["conversation_context"] = kwargs.get(
            "conversation_context"
        )
        return _generated("Answer [C1].", "source-1")

    monkeypatch.setattr(agent_graph, "deepseek_answer", fake_answer)
    answer_with_graph(
        "What about returns?",
        _dependencies(retriever),
        conversation_context=context,
    )

    assert captured["conversation_context"] == context
    assert retriever.questions == ["US policy What about returns?"]


def test_custom_stream_preserves_event_order_and_tokens(
    monkeypatch,
) -> None:
    retriever = StubRetriever(default_hits=[_hit("source-1")])

    def fake_stream(_question: str, _hits, **_kwargs):
        yield {"type": "token", "delta": "Answer "}
        yield {"type": "token", "delta": "[C1]"}
        yield {
            "type": "result",
            "result": _generated("Answer [C1]", "source-1"),
        }

    monkeypatch.setattr(agent_graph, "deepseek_answer_stream", fake_stream)
    dependencies = GraphDependencies(
        retriever=retriever,
        backend="bge_m3",
        generation_mode="deepseek",
        top_k=5,
        thinking=False,
        max_tokens=600,
        stream_tokens=True,
    )
    events = list(
        stream_answer_with_graph(
            "Simple streaming question?",
            dependencies,
        )
    )

    assert [item["event"] for item in events] == [
        "status",
        "status",
        "token",
        "token",
        "status",
        "done",
    ]
    assert [item["data"]["stage"] for item in events if item["event"] == "status"] == [
        "retrieving",
        "generating",
        "verifying_citations",
    ]
    assert "".join(
        item["data"]["delta"] for item in events if item["event"] == "token"
    ) == "Answer [C1]"
    assert [item["citation_id"] for item in events[-1]["data"]["citations"]] == [
        "C1"
    ]
