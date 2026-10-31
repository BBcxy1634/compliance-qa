"""Tests for B0-B3 stage delta analysis."""

from scripts.analyze_ablation import build_analysis


def _row(version: str, answer: float, multihop: float, p95: float) -> dict:
    return {
        "version": version,
        "hit_at_5": 1.0,
        "gold_recall_at_5": 0.9,
        "citation_accuracy": 1.0,
        "answer_correctness": answer,
        "fact_accuracy": answer,
        "multi_hop_accuracy": multihop,
        "refusal_accuracy": 1.0,
        "answerable_false_refusal": 0,
        "refusal_false_positive": 0,
        "p50_ms": p95 / 2,
        "p95_ms": p95,
    }


def test_ablation_identifies_largest_stage_gain() -> None:
    rows = [
        _row("B0", 0.80, 0.60, 3000),
        _row("B1", 0.88, 0.70, 3200),
        _row("B2", 0.88, 0.65, 3400),
        _row("B3", 0.92, 0.85, 9000),
    ]
    analysis = build_analysis(rows)
    assert analysis["summary"]["largest_answer_gain_stage"] == "B0->B1"
    assert analysis["summary"]["largest_multihop_gain_stage"] == "B2->B3"
    assert analysis["stages"][-1]["stage"] == "B0->B3"
    assert analysis["stages"][-1]["answer_correctness"] == 0.12
