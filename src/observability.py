"""Best-effort local JSONL traces with explicit payload allowlists."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from src.config import ROOT


TRACE_SCHEMA_VERSION = "agentic-v2-phase4.1"


def _json_line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def _query_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _number(value: Any) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return 0.0


def public_error_code(exc: Exception) -> str:
    name = type(exc).__name__
    if name == "ToolExecutionError":
        return "tool_unavailable"
    if name == "ModelGenerationError":
        return "model_error"
    if name == "FileNotFoundError":
        return "data_unavailable"
    if name == "ValueError":
        return "invalid_request"
    return "internal_error"


def _timings(result: dict[str, Any]) -> dict[str, float]:
    nested = result.get("timings")
    source = nested if isinstance(nested, dict) else result
    return {
        "retrieval_ms": _number(source.get("retrieval_ms")),
        "generation_ms": _number(source.get("generation_ms")),
        "verification_ms": _number(source.get("verification_ms")),
        "total_ms": _number(source.get("total_ms")),
    }


def _usage(result: dict[str, Any]) -> dict[str, int]:
    raw = result.get("usage")
    if not isinstance(raw, dict):
        return {}
    values: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = raw.get(key)
        if isinstance(value, int):
            values[key] = value
    return values


def _tool_calls(result: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    raw_calls = result.get("tool_calls")
    if not isinstance(raw_calls, list):
        return calls
    for raw in raw_calls:
        if not isinstance(raw, dict):
            continue
        error = raw.get("error")
        try:
            attempts = int(raw.get("attempts") or 0)
        except (TypeError, ValueError):
            attempts = 0
        calls.append(
            {
                "tool": str(raw.get("tool", "")),
                "ok": bool(raw.get("ok")),
                "attempts": attempts,
                "error_code": (
                    str(error.get("code", ""))
                    if isinstance(error, dict)
                    else None
                ),
            }
        )
    return calls


def _retrieval(result: dict[str, Any]) -> dict[str, Any]:
    breakdown = result.get("retrieval_breakdown")
    breakdown = breakdown if isinstance(breakdown, dict) else {}
    raw_queries = breakdown.get("queries", [])
    query_hashes: list[str] = []
    if isinstance(raw_queries, list):
        for item in raw_queries:
            query = item.get("query") if isinstance(item, dict) else None
            if isinstance(query, str) and query:
                query_hashes.append(_query_hash(query))
    hits = []
    raw_hits = result.get("hits")
    if not isinstance(raw_hits, list):
        raw_hits = []
    for raw in raw_hits:
        if not isinstance(raw, dict):
            continue
        hits.append(
            {
                "chunk_id": str(raw.get("chunk_id", "")),
                "source_id": str(raw.get("source_id", "")),
                "score": _number(raw.get("score")),
            }
        )
    return {
        "query_hashes": query_hashes,
        "query_count": len(query_hashes),
        "hit_count": len(hits),
        "top_hits": hits[:5],
        "breakdown": {
            key: value
            for key, value in breakdown.items()
            if key != "queries"
            and key.endswith("_ms")
            and isinstance(value, (int, float))
        },
    }


class TraceStore:
    """Write safe local traces without allowing trace failures to surface."""

    def __init__(self, directory: Path, *, enabled: bool = True) -> None:
        self.directory = directory
        self.enabled = enabled
        self._lock = threading.Lock()
        self._counts = {
            "traces": 0,
            "errors": 0,
            "tool_failures": 0,
        }
        self._tool_failure_codes: dict[str, int] = {}

    @classmethod
    def from_environment(cls) -> "TraceStore | None":
        enabled = os.getenv("TRACE_ENABLED", "false").strip().lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return None
        directory = Path(os.getenv("TRACE_DIR", ".cache/traces"))
        if not directory.is_absolute():
            directory = ROOT / directory
        return cls(directory)

    def _append(self, name: str, payload: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        try:
            with self._lock:
                self.directory.mkdir(parents=True, exist_ok=True)
                with (self.directory / name).open(
                    "a",
                    encoding="utf-8",
                ) as handle:
                    handle.write(_json_line(payload))
            return True
        except Exception:
            self.enabled = False
            return False

    def _increment(self, name: str) -> None:
        with self._lock:
            self._counts[name] += 1

    def reset(self) -> None:
        """Start a reproducible run with empty trace artifacts."""
        self._counts = {
            "traces": 0,
            "errors": 0,
            "tool_failures": 0,
        }
        self._tool_failure_codes = {}
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            for name in (
                "traces.jsonl",
                "errors.jsonl",
                "tool_failures.jsonl",
            ):
                (self.directory / name).write_text("", encoding="utf-8")
        except Exception:
            self.enabled = False

    def record_result(
        self,
        request_id: str,
        result: dict[str, Any],
        *,
        case_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        calls = _tool_calls(result)
        payload = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "recorded_at": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "request_id": request_id,
            "case_id": case_id,
            "status": "ok",
            "mode": result.get("mode"),
            "backend": result.get("backend"),
            "top_k": result.get("top_k"),
            "model": result.get("model"),
            "prompt_version": result.get("prompt_version"),
            "route": result.get("route"),
            "evidence": {
                "sufficient": result.get("evidence_sufficient"),
                "reason": result.get("evidence_reason"),
                "source_count": result.get("sufficient_source_count"),
            },
            "retrieval": _retrieval(result),
            "tools": calls,
            "usage": _usage(result),
            "latency_ms": _timings(result),
        }
        if self._append("traces.jsonl", payload):
            self._increment("traces")
        for call in calls:
            if call["ok"]:
                continue
            failure = {
                "schema_version": TRACE_SCHEMA_VERSION,
                "recorded_at": payload["recorded_at"],
                "request_id": request_id,
                "case_id": case_id,
                "tool": call["tool"],
                "attempts": call["attempts"],
                "error_code": call["error_code"],
            }
            if self._append("tool_failures.jsonl", failure):
                self._increment("tool_failures")
                code = str(call["error_code"] or "unknown")
                with self._lock:
                    self._tool_failure_codes[code] = (
                        self._tool_failure_codes.get(code, 0) + 1
                    )

    def record_error(
        self,
        request_id: str,
        exc: Exception,
        *,
        case_id: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        recorded_at = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        code = public_error_code(exc)
        payload = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "recorded_at": recorded_at,
            "request_id": request_id,
            "case_id": case_id,
            "status": "error",
            "error": {
                "type": type(exc).__name__,
                "code": code,
            },
        }
        if self._append("traces.jsonl", payload):
            self._increment("traces")
        if self._append("errors.jsonl", payload):
            self._increment("errors")

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "enabled": self.enabled,
            "directory": str(self.directory.relative_to(ROOT))
            if self.directory.is_relative_to(ROOT)
            else str(self.directory),
            **dict(self._counts),
            "tool_failure_codes": dict(sorted(self._tool_failure_codes.items())),
        }
