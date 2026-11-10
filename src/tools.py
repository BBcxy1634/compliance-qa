"""Typed, bounded tools for the controlled compliance agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Literal, Protocol

from src.schemas import SearchHit


ToolErrorCode = Literal[
    "catalog_unavailable",
    "execution_error",
    "insufficient_versions",
    "invalid_period",
    "not_found",
    "timeout",
    "unavailable",
    "version_not_found",
]
DEFAULT_TOOL_MAX_ATTEMPTS = 2
MAX_TOOL_ATTEMPTS = 3
DATE_TOKEN_PATTERN = (
    r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:日)?"
)
DATE_RANGE_PATTERN = re.compile(
    rf"({DATE_TOKEN_PATTERN})\s*(?:至|到|~|—|–|－)\s*"
    rf"({DATE_TOKEN_PATTERN})"
)


class Retriever(Protocol):
    def search(self, query: str, *, top_k: int) -> list[SearchHit]: ...


class ToolInvocationError(RuntimeError):
    """Stable internal failure used to build a public tool result."""

    def __init__(self, code: ToolErrorCode, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class ToolExecutionError(RuntimeError):
    """Raised when a core tool fails after its bounded retry budget."""

    def __init__(self, tool_name: str, code: ToolErrorCode) -> None:
        super().__init__(f"{tool_name} failed: {code}")
        self.tool_name = tool_name
        self.code = code


@dataclass(frozen=True)
class SearchSourcesInput:
    query: str
    top_k: int

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be blank")
        if not 1 <= self.top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")


@dataclass(frozen=True)
class InspectSnapshotInput:
    source_id: str

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be blank")


@dataclass(frozen=True)
class CompareVersionsInput:
    source_id: str
    from_version: str | None = None
    to_version: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id must not be blank")


@dataclass(frozen=True)
class ValidateValidityPeriodInput:
    start_date: date
    end_date: date
    as_of: date


@dataclass(frozen=True)
class PolicySnapshot:
    source_id: str
    version: str
    source: str
    title: str
    url: str
    publisher: str
    authority: str
    published_at: str
    updated_at: str
    captured_at: str
    sha256: str
    path: str

    @classmethod
    def from_manifest(cls, item: dict[str, Any]) -> "PolicySnapshot":
        sha256 = str(item.get("sha256", ""))
        version = str(
            item.get("version")
            or item.get("captured_at")
            or item.get("updated_at")
            or item.get("published_at")
            or sha256[:12]
        )
        return cls(
            source_id=str(item.get("source_id", "")),
            version=version,
            source=str(item.get("source", "")),
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            publisher=str(item.get("publisher", "")),
            authority=str(item.get("authority", "")),
            published_at=str(item.get("published_at", "")),
            updated_at=str(item.get("updated_at", "")),
            captured_at=str(item.get("captured_at", "")),
            sha256=sha256,
            path=str(item.get("path", "")),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "version": self.version,
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "publisher": self.publisher,
            "authority": self.authority,
            "published_at": self.published_at,
            "updated_at": self.updated_at,
            "captured_at": self.captured_at,
            "sha256": self.sha256,
            "path": self.path,
        }


@dataclass(frozen=True)
class ToolSuccess:
    tool: str
    output: dict[str, Any]
    attempts: int

    def to_state(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": True,
            "attempts": self.attempts,
            "output": dict(self.output),
        }


@dataclass(frozen=True)
class ToolFailure:
    tool: str
    code: ToolErrorCode
    message: str
    attempts: int
    retryable: bool

    def to_state(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "ok": False,
            "attempts": self.attempts,
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
            },
        }


ToolOutcome = ToolSuccess | ToolFailure


def _snapshot_sort_key(snapshot: PolicySnapshot) -> tuple[str, str, str]:
    return (
        snapshot.version,
        snapshot.updated_at,
        snapshot.published_at,
    )


class PolicySnapshotCatalog:
    """Read-only in-memory index of official source snapshots."""

    def __init__(self, snapshots: list[PolicySnapshot]) -> None:
        self._snapshots: dict[str, list[PolicySnapshot]] = {}
        for snapshot in snapshots:
            if not snapshot.source_id:
                continue
            self._snapshots.setdefault(snapshot.source_id, []).append(snapshot)
        for versions in self._snapshots.values():
            versions.sort(key=_snapshot_sort_key)

    @classmethod
    def from_jsonl(cls, path: Path) -> "PolicySnapshotCatalog":
        snapshots = [
            PolicySnapshot.from_manifest(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls(snapshots)

    def versions(self, source_id: str) -> list[PolicySnapshot]:
        return list(self._snapshots.get(source_id, []))

    def latest(self, source_id: str) -> PolicySnapshot | None:
        versions = self._snapshots.get(source_id, [])
        return versions[-1] if versions else None

    def compare(
        self,
        source_id: str,
        *,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> dict[str, Any]:
        versions = self._snapshots.get(source_id, [])
        if not versions:
            raise ToolInvocationError("not_found")
        if len(versions) < 2:
            raise ToolInvocationError("insufficient_versions")

        by_version = {snapshot.version: snapshot for snapshot in versions}
        old = (
            by_version.get(from_version)
            if from_version is not None
            else versions[-2]
        )
        new = (
            by_version.get(to_version)
            if to_version is not None
            else versions[-1]
        )
        if old is None or new is None:
            raise ToolInvocationError("version_not_found")

        compared_fields = (
            "title",
            "url",
            "publisher",
            "authority",
            "published_at",
            "updated_at",
            "captured_at",
            "sha256",
            "path",
        )
        changed_fields = {
            field: {
                "from": getattr(old, field),
                "to": getattr(new, field),
            }
            for field in compared_fields
            if getattr(old, field) != getattr(new, field)
        }
        return {
            "source_id": source_id,
            "from_version": old.version,
            "to_version": new.version,
            "changed": bool(changed_fields),
            "content_changed": old.sha256 != new.sha256,
            "changed_fields": changed_fields,
        }


def _parse_date_token(value: str) -> date:
    normalized = (
        value.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )
    year, month, day = (int(part) for part in normalized.split("-"))
    return date(year, month, day)


def extract_date_ranges(text: str) -> list[tuple[date, date]]:
    """Extract explicit date ranges without inferring missing dates."""
    ranges: list[tuple[date, date]] = []
    for match in DATE_RANGE_PATTERN.finditer(text):
        try:
            start_date = _parse_date_token(match.group(1))
            end_date = _parse_date_token(match.group(2))
        except ValueError:
            continue
        ranges.append((start_date, end_date))
    return ranges


class ToolRuntime:
    """Injected runtime for typed tools with a hard retry ceiling."""

    def __init__(
        self,
        retriever: Retriever,
        *,
        snapshot_catalog: PolicySnapshotCatalog | None = None,
        max_attempts: int = DEFAULT_TOOL_MAX_ATTEMPTS,
        today: date | None = None,
    ) -> None:
        if not 1 <= max_attempts <= MAX_TOOL_ATTEMPTS:
            raise ValueError(
                f"max_attempts must be between 1 and {MAX_TOOL_ATTEMPTS}"
            )
        self.retriever = retriever
        self.snapshot_catalog = snapshot_catalog
        self.max_attempts = max_attempts
        self.today = today or date.today()

    def _invoke(
        self,
        tool_name: str,
        operation: Callable[[], dict[str, Any]],
    ) -> ToolOutcome:
        for attempts in range(1, self.max_attempts + 1):
            try:
                return ToolSuccess(
                    tool=tool_name,
                    output=operation(),
                    attempts=attempts,
                )
            except ToolInvocationError as exc:
                if not exc.retryable or attempts >= self.max_attempts:
                    return ToolFailure(
                        tool=tool_name,
                        code=exc.code,
                        message=exc.code.replace("_", " "),
                        attempts=attempts,
                        retryable=exc.retryable,
                    )
            except (TimeoutError, ConnectionError) as exc:
                code: ToolErrorCode = (
                    "timeout" if isinstance(exc, TimeoutError) else "unavailable"
                )
                if attempts >= self.max_attempts:
                    return ToolFailure(
                        tool=tool_name,
                        code=code,
                        message=code.replace("_", " "),
                        attempts=attempts,
                        retryable=True,
                    )
            except Exception:
                return ToolFailure(
                    tool=tool_name,
                    code="execution_error",
                    message="execution error",
                    attempts=attempts,
                    retryable=False,
                )
        raise AssertionError("tool retry loop ended without an outcome")

    def search_sources(self, arguments: SearchSourcesInput) -> ToolOutcome:
        def operation() -> dict[str, Any]:
            hits = self.retriever.search(
                arguments.query,
                top_k=arguments.top_k,
            )
            return {
                "query": arguments.query,
                "hits": [
                    {
                        "chunk": dict(hit.chunk),
                        "score": float(hit.score),
                    }
                    for hit in hits
                ],
            }

        return self._invoke("search_official_policy_sources", operation)

    def inspect_latest_snapshot(
        self,
        arguments: InspectSnapshotInput,
    ) -> ToolOutcome:
        def operation() -> dict[str, Any]:
            if self.snapshot_catalog is None:
                raise ToolInvocationError("catalog_unavailable")
            snapshot = self.snapshot_catalog.latest(arguments.source_id)
            if snapshot is None:
                raise ToolInvocationError("not_found")
            return {"snapshot": snapshot.to_dict()}

        return self._invoke("inspect_latest_policy_snapshot", operation)

    def compare_policy_versions(
        self,
        arguments: CompareVersionsInput,
    ) -> ToolOutcome:
        def operation() -> dict[str, Any]:
            if self.snapshot_catalog is None:
                raise ToolInvocationError("catalog_unavailable")
            return self.snapshot_catalog.compare(
                arguments.source_id,
                from_version=arguments.from_version,
                to_version=arguments.to_version,
            )

        return self._invoke("compare_policy_versions", operation)

    def validate_validity_period(
        self,
        arguments: ValidateValidityPeriodInput,
    ) -> ToolOutcome:
        def operation() -> dict[str, Any]:
            if arguments.start_date > arguments.end_date:
                raise ToolInvocationError("invalid_period")
            if arguments.as_of < arguments.start_date:
                status = "upcoming"
            elif arguments.as_of > arguments.end_date:
                status = "expired"
            else:
                status = "active"
            return {
                "start_date": arguments.start_date.isoformat(),
                "end_date": arguments.end_date.isoformat(),
                "as_of": arguments.as_of.isoformat(),
                "status": status,
                "days_remaining": max(
                    0,
                    (arguments.end_date - arguments.as_of).days,
                ),
            }

        return self._invoke("validate_validity_period", operation)
