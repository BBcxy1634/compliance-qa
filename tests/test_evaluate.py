"""Metric tests for the D4 evaluator."""

from scripts.build_baseline_table import add_deltas
from src.evaluate import compute_metrics, gold_match_key, parse_bool, percentile


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
