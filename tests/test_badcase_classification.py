"""Tests for the D10 badcase taxonomy."""

from collections import Counter

from scripts.classify_badcases import CATEGORY_LABELS, build_badcases


def test_all_observed_failures_are_classified() -> None:
    rows, stats = build_badcases()
    assert len(rows) == 22
    assert stats["total_failure_instances"] == 22
    assert len(stats["final_b3_failures"]) == 3
    assert set(CATEGORY_LABELS).issuperset(
        {row["category"] for row in rows}
    )
    counts = Counter(row["category"] for row in rows)
    assert counts["retrieval_incomplete"] >= 2
    assert counts["retrieval_noise"] >= 2
    assert counts["generation_incomplete"] >= 2
    assert counts["refusal_failure"] >= 2
