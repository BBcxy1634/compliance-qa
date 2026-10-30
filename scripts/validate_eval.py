#!/usr/bin/env python3
"""Validate the D3 evaluation set and its evidence mapping."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "eval" / "questions.jsonl"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
REFUSAL_TEXT = "文档中未找到足够依据，暂时无法回答这个问题。"
REQUIRED_FIELDS = {
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
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    errors: list[str] = []
    questions = load_jsonl(QUESTIONS_PATH)
    chunks = load_jsonl(CHUNKS_PATH)
    chunk_map = {chunk["chunk_id"]: chunk for chunk in chunks}

    if len(questions) != 60:
        errors.append(f"expected 60 questions, found {len(questions)}")
    expected_ids = [f"q{number:03d}" for number in range(1, 61)]
    actual_ids = [record.get("id") for record in questions]
    if actual_ids != expected_ids:
        errors.append("IDs must be sequential from q001 to q060")
    if len(set(actual_ids)) != len(actual_ids):
        errors.append("question IDs are not unique")

    type_counts = Counter(record.get("type") for record in questions)
    expected_counts = {"fact": 40, "multi_hop": 10, "refusal": 10}
    if type_counts != expected_counts:
        errors.append(
            f"type counts must be {expected_counts}, found {dict(type_counts)}"
        )

    seen_questions: set[str] = set()
    for record in questions:
        question_id = record.get("id", "<unknown>")
        missing = REQUIRED_FIELDS - record.keys()
        if missing:
            errors.append(f"{question_id}: missing fields {sorted(missing)}")
            continue
        question = record["question"].strip()
        if question in seen_questions:
            errors.append(f"{question_id}: duplicate question text")
        seen_questions.add(question)
        if record["lang"] not in {"zh", "en"}:
            errors.append(f"{question_id}: unsupported language")
        if not isinstance(record["key_facts"], list):
            errors.append(f"{question_id}: key_facts must be a list")
        if not isinstance(record["gold_chunks"], list):
            errors.append(f"{question_id}: gold_chunks must be a list")
        if not isinstance(record["gold_evidence"], list):
            errors.append(f"{question_id}: gold_evidence must be a list")

        if record["type"] == "refusal":
            if record["expected_behavior"] != "refuse":
                errors.append(f"{question_id}: refusal question must expect refuse")
            if record["gold_chunks"] or record["gold_evidence"]:
                errors.append(f"{question_id}: refusal question must not have evidence")
            if record["gold_answer"] != REFUSAL_TEXT:
                errors.append(f"{question_id}: unexpected refusal answer")
            continue

        if record["expected_behavior"] != "answer":
            errors.append(f"{question_id}: answerable question must expect answer")
        if not record["key_facts"]:
            errors.append(f"{question_id}: key_facts cannot be empty")
        if not record["gold_chunks"]:
            errors.append(f"{question_id}: gold_chunks cannot be empty")
        for chunk_id in record["gold_chunks"]:
            if chunk_id not in chunk_map:
                errors.append(f"{question_id}: unknown chunk {chunk_id}")
        evidence_chunk_ids = {
            evidence.get("chunk_id") for evidence in record["gold_evidence"]
        }
        if not evidence_chunk_ids:
            errors.append(f"{question_id}: gold_evidence cannot be empty")
        for evidence in record["gold_evidence"]:
            chunk_id = evidence.get("chunk_id")
            quote = evidence.get("quote", "")
            chunk = chunk_map.get(chunk_id)
            if chunk is None:
                errors.append(f"{question_id}: evidence chunk not found: {chunk_id}")
                continue
            if not quote or quote not in chunk["text"]:
                errors.append(f"{question_id}: quote not found in {chunk_id}")

        source_ids = {
            chunk_map[chunk_id]["source_id"]
            for chunk_id in record["gold_chunks"]
            if chunk_id in chunk_map
        }
        if record["type"] == "fact" and len(source_ids) != 1:
            errors.append(f"{question_id}: fact question must use one source")
        if record["type"] == "multi_hop" and len(source_ids) < 2:
            errors.append(f"{question_id}: multi-hop question needs at least 2 sources")

    print(
        f"questions={len(questions)} types={dict(type_counts)} "
        f"sources={len({record['source_id'] for record in chunks})}"
    )
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
