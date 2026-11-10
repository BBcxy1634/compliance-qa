#!/usr/bin/env python3
"""Validate the Phase 4 agentic dataset, labels, and evidence quotes."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools import extract_date_ranges


BASE_PATH = ROOT / "eval" / "questions.jsonl"
QUESTIONS_PATH = ROOT / "eval" / "agentic_v2" / "questions.jsonl"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
TOOLS = {
    "search_official_policy_sources",
    "inspect_latest_policy_snapshot",
    "compare_policy_versions",
    "validate_validity_period",
}
ROUTES = {"simple_fact", "multi_hop", "high_risk"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    errors: list[str] = []
    base = load_jsonl(BASE_PATH)
    questions = load_jsonl(QUESTIONS_PATH)
    chunks = {
        row["chunk_id"]: row
        for row in load_jsonl(CHUNKS_PATH)
    }

    if len(questions) != 150:
        errors.append(f"expected 150 questions, found {len(questions)}")
    actual_ids = [row.get("id") for row in questions]
    expected_ids = [f"q{number:03d}" for number in range(1, 151)]
    if actual_ids != expected_ids:
        errors.append("IDs must be sequential from q001 to q150")
    if len(set(actual_ids)) != len(actual_ids):
        errors.append("question IDs are not unique")

    base_by_id = {row["id"]: row for row in base}
    for row in questions[:60]:
        original = base_by_id.get(row["id"])
        if original is None:
            errors.append(f"{row['id']}: original question missing")
            continue
        for key, value in original.items():
            if row.get(key) != value:
                errors.append(f"{row['id']}: original field changed: {key}")
        if row.get("agentic", {}).get("review_status") != "draft":
            errors.append(f"{row['id']}: new agentic labels must be draft")

    for row in questions[60:]:
        if row.get("review_status") != "draft":
            errors.append(f"{row['id']}: new question must be draft")
        if row.get("agentic", {}).get("review_status") != "draft":
            errors.append(f"{row['id']}: new labels must be draft")

    required = {
        "id",
        "type",
        "question",
        "gold_answer",
        "key_facts",
        "gold_chunks",
        "gold_evidence",
        "lang",
        "expected_behavior",
        "review_status",
        "created_at",
        "agentic",
    }
    seen_questions: set[str] = set()
    for row in questions:
        question_id = row.get("id", "<unknown>")
        missing = required - row.keys()
        if missing:
            errors.append(f"{question_id}: missing fields {sorted(missing)}")
            continue
        if row["question"] in seen_questions:
            errors.append(f"{question_id}: duplicate question text")
        seen_questions.add(row["question"])
        if row["lang"] not in {"zh", "en"}:
            errors.append(f"{question_id}: unsupported language")
        if any(
            key in row
            for key in ("reviewer", "reviewed_at", "manual_correct")
        ):
            errors.append(f"{question_id}: must not claim human review")

        agentic = row["agentic"]
        if agentic.get("expected_route") not in ROUTES:
            errors.append(f"{question_id}: invalid expected_route")
        tools = agentic.get("required_tools")
        if not isinstance(tools, list) or not tools:
            errors.append(f"{question_id}: required_tools must be non-empty")
        else:
            if "search_official_policy_sources" not in tools:
                errors.append(f"{question_id}: search tool is required")
            if len(tools) != len(set(tools)):
                errors.append(f"{question_id}: duplicate required tools")
            unknown_tools = set(tools) - TOOLS
            if unknown_tools:
                errors.append(
                    f"{question_id}: unknown tools {sorted(unknown_tools)}"
                )
            if (
                "validate_validity_period" in tools
                and not extract_date_ranges(row["question"])
            ):
                errors.append(
                    f"{question_id}: date tool needs an explicit date range"
                )
            if (
                "compare_policy_versions" in tools
                and not re.search(
                    r"比较|对比|差异|版本|旧版|新版|修订|变更",
                    row["question"],
                    re.IGNORECASE,
                )
            ):
                errors.append(
                    f"{question_id}: compare tool needs a version trigger"
                )
        if not isinstance(agentic.get("expected_evidence_sufficient"), bool):
            errors.append(
                f"{question_id}: expected_evidence_sufficient must be bool"
            )

        for chunk_id in row["gold_chunks"]:
            if chunk_id not in chunks:
                errors.append(f"{question_id}: unknown chunk {chunk_id}")
        source_ids = {
            chunks[chunk_id]["source_id"]
            for chunk_id in row["gold_chunks"]
            if chunk_id in chunks
        }

        if row["type"] == "refusal":
            if row["expected_behavior"] != "refuse":
                errors.append(f"{question_id}: refusal must expect refuse")
            if row["gold_chunks"] or row["gold_evidence"]:
                errors.append(f"{question_id}: refusal must not have evidence")
            if agentic["expected_evidence_sufficient"] is not False:
                errors.append(f"{question_id}: refusal evidence must be false")
            continue
        if row["expected_behavior"] != "answer":
            errors.append(f"{question_id}: answerable must expect answer")
        if not row["key_facts"] or not row["gold_chunks"]:
            errors.append(f"{question_id}: answerable facts/chunks are empty")
        if row["type"] == "fact" and len(source_ids) != 1:
            errors.append(f"{question_id}: fact must use one source")
        if row["type"] == "multi_hop" and len(source_ids) < 2:
            errors.append(f"{question_id}: multi-hop needs two sources")
        if agentic["expected_evidence_sufficient"] is not True:
            errors.append(f"{question_id}: answerable evidence must be true")
        for evidence in row["gold_evidence"]:
            chunk_id = evidence.get("chunk_id")
            quote = evidence.get("quote", "")
            chunk = chunks.get(chunk_id)
            if chunk is None:
                errors.append(
                    f"{question_id}: evidence chunk not found: {chunk_id}"
                )
            elif not quote or quote not in chunk["text"]:
                errors.append(
                    f"{question_id}: quote not found in {chunk_id}"
                )

    type_counts = Counter(row["type"] for row in questions)
    expected_type_counts = {"fact": 70, "multi_hop": 60, "refusal": 20}
    if type_counts != expected_type_counts:
        errors.append(
            f"type counts must be {expected_type_counts}, "
            f"found {dict(type_counts)}"
        )
    route_counts = Counter(
        row["agentic"]["expected_route"] for row in questions
    )
    expected_route_counts = {
        "simple_fact": 68,
        "high_risk": 47,
        "multi_hop": 35,
    }
    if route_counts != expected_route_counts:
        errors.append(
            f"route counts must be {expected_route_counts}, "
            f"found {dict(route_counts)}"
        )
    tool_names = {
        tool
        for row in questions
        for tool in row["agentic"]["required_tools"]
    }
    if "compare_policy_versions" not in tool_names:
        errors.append("dataset does not cover compare_policy_versions")
    if "validate_validity_period" not in tool_names:
        errors.append("dataset does not cover validate_validity_period")

    print(
        f"questions={len(questions)} types={dict(type_counts)} "
        f"routes={dict(route_counts)} sources={len({row['source_id'] for row in chunks.values()})}"
    )
    if errors:
        print("AGENTIC VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("AGENTIC VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
