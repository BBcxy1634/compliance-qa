"""Tests for the D11 benchmark table builder."""

from scripts.build_bench_table import summary_to_row


def test_summary_row_includes_latency_and_cost() -> None:
    summary = {
        "samples_requested": 100,
        "samples_successful": 100,
        "samples_failed": 0,
        "answer_models": ["deepseek-flash"],
        "pricing_periods": ["off_peak"],
        "latency_ms": {
            "total_p50": 1000.0,
            "total_p95": 2800.0,
            "retrieval_p95": 100.0,
            "rerank_p95": 0.0,
            "generation_p95": 2700.0,
            "within_3s_rate": 1.0,
        },
        "tokens": {"mean_prompt": 1000.0, "mean_completion": 100.0},
        "cost_cny": {"mean": 0.001, "p95": 0.002},
    }
    row = summary_to_row("B1", summary)
    assert row["latency_under_3s"] is True
    assert row["cost_under_001_cny"] is True
    assert row["total_p95_ms"] == 2800.0
