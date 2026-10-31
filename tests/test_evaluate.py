"""Metric tests for the D4 evaluator."""

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
