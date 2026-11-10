"""Tests for typed tools, failures, and bounded retries."""

from __future__ import annotations

import json
from datetime import date

import pytest

from src.schemas import SearchHit
from src.tools import (
    CompareVersionsInput,
    InspectSnapshotInput,
    PolicySnapshot,
    PolicySnapshotCatalog,
    SearchSourcesInput,
    ToolFailure,
    ToolRuntime,
    ToolSuccess,
    ValidateValidityPeriodInput,
    extract_date_ranges,
)


def _hit() -> SearchHit:
    return SearchHit(
        chunk={
            "chunk_id": "source-1#c01",
            "source_id": "source-1",
            "source": "source-1.md",
            "title": "Policy",
            "text": "Official policy text.",
        },
        score=0.9,
    )


class FlakyRetriever:
    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.error = error or TimeoutError("temporary")
        self.calls = 0

    def search(self, query: str, *, top_k: int) -> list[SearchHit]:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return [_hit()]


def _snapshot(
    version: str,
    *,
    sha256: str,
    title: str = "Policy",
) -> PolicySnapshot:
    return PolicySnapshot(
        source_id="source-1",
        version=version,
        source="source-1.md",
        title=title,
        url="https://example.com/policy",
        publisher="Regulator",
        authority="primary",
        published_at=version,
        updated_at=version,
        captured_at=version,
        sha256=sha256,
        path=f"data/raw/{version}.md",
    )


def test_search_tool_retries_once_then_succeeds() -> None:
    retriever = FlakyRetriever(failures=1)
    runtime = ToolRuntime(retriever, max_attempts=2)

    outcome = runtime.search_sources(
        SearchSourcesInput(query="policy", top_k=5)
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.attempts == 2
    assert outcome.output["hits"][0]["chunk"]["source_id"] == "source-1"
    assert retriever.calls == 2


def test_search_tool_stops_at_retry_ceiling() -> None:
    retriever = FlakyRetriever(failures=10)
    runtime = ToolRuntime(retriever, max_attempts=2)

    outcome = runtime.search_sources(
        SearchSourcesInput(query="policy", top_k=5)
    )

    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "timeout"
    assert outcome.attempts == 2
    assert retriever.calls == 2


def test_tool_runtime_rejects_attempt_count_above_hard_limit() -> None:
    with pytest.raises(ValueError):
        ToolRuntime(FlakyRetriever(0), max_attempts=4)


def test_latest_snapshot_tool_returns_metadata() -> None:
    catalog = PolicySnapshotCatalog(
        [
            _snapshot("2025-01-01", sha256="old"),
            _snapshot("2026-01-01", sha256="new"),
        ]
    )
    runtime = ToolRuntime(FlakyRetriever(0), snapshot_catalog=catalog)

    outcome = runtime.inspect_latest_snapshot(
        InspectSnapshotInput(source_id="source-1")
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.output["snapshot"]["version"] == "2026-01-01"
    assert json.loads(json.dumps(outcome.to_state()))["ok"] is True


def test_compare_versions_reports_changed_metadata() -> None:
    catalog = PolicySnapshotCatalog(
        [
            _snapshot("2025-01-01", sha256="old", title="Old policy"),
            _snapshot("2026-01-01", sha256="new", title="New policy"),
        ]
    )
    runtime = ToolRuntime(FlakyRetriever(0), snapshot_catalog=catalog)

    outcome = runtime.compare_policy_versions(
        CompareVersionsInput(source_id="source-1")
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.output["changed"] is True
    assert outcome.output["content_changed"] is True
    assert "title" in outcome.output["changed_fields"]


def test_compare_versions_is_explicit_when_history_is_insufficient() -> None:
    catalog = PolicySnapshotCatalog(
        [_snapshot("2026-01-01", sha256="only")]
    )
    runtime = ToolRuntime(FlakyRetriever(0), snapshot_catalog=catalog)

    outcome = runtime.compare_policy_versions(
        CompareVersionsInput(source_id="source-1")
    )

    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "insufficient_versions"
    assert outcome.attempts == 1


@pytest.mark.parametrize(
    ("as_of", "status"),
    [
        (date(2025, 12, 31), "upcoming"),
        (date(2026, 6, 1), "active"),
        (date(2028, 1, 1), "expired"),
    ],
)
def test_validate_validity_period_status(
    as_of: date,
    status: str,
) -> None:
    runtime = ToolRuntime(FlakyRetriever(0), today=as_of)

    outcome = runtime.validate_validity_period(
        ValidateValidityPeriodInput(
            start_date=date(2026, 1, 1),
            end_date=date(2027, 12, 31),
            as_of=as_of,
        )
    )

    assert isinstance(outcome, ToolSuccess)
    assert outcome.output["status"] == status


def test_date_range_extraction_handles_explicit_chinese_dates() -> None:
    ranges = extract_date_ranges("适用期为2026年1月1日至2027年12月31日。")

    assert ranges == [
        (date(2026, 1, 1), date(2027, 12, 31))
    ]
