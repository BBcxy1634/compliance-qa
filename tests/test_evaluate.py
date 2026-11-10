"""Metric tests for the D4 evaluator."""

from scripts.build_baseline_table import add_deltas
from src.evaluate import (
    compute_agentic_metrics,
    compute_metrics,
    gold_match_key,
    parse_bool,
    percentile,
)


def test_percentile_interpolates() -> None:
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0.5) == 25.0
    assert percentile(values, 0.95) == 38.5
    assert percentile([], 0.95) == 0.0


def test_manual_labels_override_auto_judgement() -> None:
    results = [
        {
            "id": "q1",
            "type": "fact",
            "citations": [{"chunk_id": "a"}],
            "hit_at_k": True,
            "gold_recall_at_k": 1.0,
            "citation_hit": True,
            "refused": False,
            "auto_correct": True,
            "total_ms": 10.0,
        },
        {
            "id": "q2",
            "type": "multi_hop",
            "citations": [],
            "hit_at_k": False,
            "gold_recall_at_k": 0.0,
            "citation_hit": False,
            "refused": True,
            "auto_correct": False,
            "total_ms": 20.0,
        },
        {
            "id": "q3",
            "type": "refusal",
            "citations": [],
            "hit_at_k": False,
            "gold_recall_at_k": 0.0,
            "citation_hit": False,
            "refused": True,
            "auto_correct": True,
            "total_ms": 30.0,
        },
    ]
    metrics = compute_metrics(results, {"q2": True})
    assert metrics["hit_at_5"] == 0.5
    assert metrics["citation_accuracy"] == 1.0
    assert metrics["answer_correctness"] == 1.0
    assert metrics["refusal_accuracy"] == 1.0
    assert metrics["correctness_sources"]["manual"] == 1
    assert metrics["correctness_sources"]["deepseek_auto"] == 1


def test_boolean_label_parser() -> None:
    assert parse_bool("yes")
    assert parse_bool("1")
    assert not parse_bool("false")
    assert not parse_bool("")


def test_unit_match_maps_strategy_specific_chunks() -> None:
    assert gold_match_key("source#p01#c01", "exact") == "source#p01#c01"
    assert gold_match_key("source#p01#c01", "unit") == "source#p01"
    assert gold_match_key("source#p01#c99", "unit") == "source#p01"


def test_baseline_delta_uses_b0() -> None:
    rows = [
        {
            "version": "B0",
            "hit_at_5": 0.8,
            "gold_recall_at_5": 0.7,
            "citation_accuracy": 0.75,
            "citation_coverage": 0.8,
            "answer_correctness": 0.5,
            "fact_accuracy": 0.6,
            "multi_hop_accuracy": 0.4,
            "refusal_accuracy": 0.9,
            "answerable_false_refusal": 5,
            "refusal_false_positive": 1,
            "p50_ms": 100.0,
            "p95_ms": 200.0,
        },
        {
            "version": "B1",
            "hit_at_5": 0.9,
            "gold_recall_at_5": 0.8,
            "citation_accuracy": 0.85,
            "citation_coverage": 0.9,
            "answer_correctness": 0.6,
            "fact_accuracy": 0.7,
            "multi_hop_accuracy": 0.5,
            "refusal_accuracy": 1.0,
            "answerable_false_refusal": 4,
            "refusal_false_positive": 0,
            "p50_ms": 110.0,
            "p95_ms": 220.0,
        },
    ]
    result = add_deltas(rows)
    assert result[1]["delta_hit_at_5_vs_b0"] == 0.1
    assert result[1]["delta_p95_ms_vs_b0"] == 20.0


def test_agentic_metrics_use_separate_definitions() -> None:
    results = [
        {
            "id": "q1",
            "type": "multi_hop",
            "gold_chunks": ["source-a#c01", "source-b#c01"],
            "citations": [
                {"source_id": "source-a", "chunk_id": "source-a#c01"},
                {"source_id": "source-b", "chunk_id": "source-b#c01"},
            ],
            "refused": False,
            "final_correct": True,
            "expected_route": "high_risk",
            "route": "high_risk",
            "required_tools": [
                "search_official_policy_sources",
                "compare_policy_versions",
            ],
            "tool_calls": [
                {
                    "tool": "search_official_policy_sources",
                    "ok": True,
                    "attempts": 1,
                },
                {
                    "tool": "compare_policy_versions",
                    "ok": False,
                    "attempts": 1,
                    "error": {"code": "insufficient_versions"},
                },
            ],
            "expected_evidence_sufficient": True,
            "evidence_sufficient": True,
        },
        {
            "id": "q2",
            "type": "fact",
            "gold_chunks": ["source-c#c01"],
            "citations": [],
            "refused": True,
            "final_correct": False,
            "expected_route": "simple_fact",
            "route": "multi_hop",
            "required_tools": [
                "search_official_policy_sources",
                "compare_policy_versions",
            ],
            "tool_calls": [
                {
                    "tool": "search_official_policy_sources",
                    "ok": True,
                    "attempts": 2,
                }
            ],
            "expected_evidence_sufficient": True,
            "evidence_sufficient": False,
        },
    ]

    metrics = compute_agentic_metrics(results)

    assert metrics["route_accuracy"]["accuracy"] == 0.5
    assert metrics["route_accuracy"]["confusion"]["high_risk"] == {
        "high_risk": 1
    }
    assert metrics["tool_selection_accuracy"]["accuracy"] == 0.5
    assert metrics["tool_success_rate"]["success_rate"] == 0.6667
    assert metrics["tool_success_rate"]["failure_codes"] == {
        "insufficient_versions": 1
    }
    assert metrics["multi_step_completion_rate"]["completion_rate"] == 1.0
    assert metrics["evidence_sufficiency_accuracy"]["accuracy"] == 0.5


def test_existing_metrics_shape_is_unchanged_when_agentic_metrics_added() -> None:
    results = [
        {
            "id": "q1",
            "type": "fact",
            "citations": [{"chunk_id": "a"}],
            "hit_at_k": True,
            "gold_recall_at_k": 1.0,
            "citation_hit": True,
            "refused": False,
            "auto_correct": True,
            "total_ms": 10.0,
        }
    ]
    metrics = compute_metrics(results, {})
    agentic = compute_agentic_metrics(
        [
            {
                **results[0],
                "final_correct": True,
                "gold_chunks": ["a"],
                "expected_route": "simple_fact",
                "route": "simple_fact",
                "required_tools": ["search_official_policy_sources"],
                "tool_calls": [],
                "expected_evidence_sufficient": True,
                "evidence_sufficient": True,
            }
        ]
    )

    assert metrics["hit_at_5"] == 1.0
    assert metrics["answer_correctness"] == 1.0
    assert set(agentic) == {
        "route_accuracy",
        "tool_selection_accuracy",
        "tool_success_rate",
        "multi_step_completion_rate",
        "evidence_sufficiency_accuracy",
    }
