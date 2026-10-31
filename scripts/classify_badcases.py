#!/usr/bin/env python3
"""Classify all failed answerable questions across the official B0-B3 runs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = (
    ("B0", "b0_deepseek"),
    ("B1", "b1_deepseek"),
    ("B2", "b2_deepseek"),
    ("B3", "b3_deepseek"),
)
LABELS_PATH = ROOT / "eval" / "badcase_labels.json"
DEFAULT_JSONL = ROOT / "eval" / "results" / "badcases.jsonl"
DEFAULT_STATS_JSON = ROOT / "eval" / "results" / "badcase_stats.json"
DEFAULT_STATS_CSV = ROOT / "eval" / "results" / "badcase_stats.csv"
CATEGORY_LABELS = {
    "retrieval_incomplete": "检索未召回完整证据",
    "retrieval_noise": "召回噪声",
    "generation_incomplete": "生成不完整",
    "hallucination": "生成幻觉",
    "citation_mismatch": "引用错配",
    "refusal_failure": "拒答失败",
    "parse_failure": "解析失败",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def find_failures() -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for version, run_name in RUNS:
        path = ROOT / "eval" / "results" / run_name / "per_question.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Missing per-question result: {path}")
        for row in load_jsonl(path):
            failed = (
                not row["refused"]
                if row["type"] == "refusal"
                else not bool(row.get("auto_correct"))
            )
            if failed:
                failures.append(
                    {
                        "key": f"{run_name}:{row['id']}",
                        "version": version,
                        "run_name": run_name,
                        "id": row["id"],
                        "type": row["type"],
                        "question": row["question"],
                        "refused": bool(row["refused"]),
                        "auto_reason": row.get("auto_reason", ""),
                        "gold_chunks": row["gold_chunks"],
                        "retrieved_chunk_ids": [
                            hit["chunk_id"] for hit in row["retrieved"]
                        ],
                        "is_final_b3": version == "B3",
                    }
                )
    return failures


def exact_recall(row: dict[str, Any]) -> float:
    gold = set(row["gold_chunks"])
    if not gold:
        return 0.0
    retrieved = set(row["retrieved_chunk_ids"])
    return round(len(gold.intersection(retrieved)) / len(gold), 4)


def build_badcases() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    labels = json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    failures = find_failures()
    failure_keys = {row["key"] for row in failures}
    label_keys = set(labels)
    if failure_keys != label_keys:
        missing = sorted(failure_keys - label_keys)
        extra = sorted(label_keys - failure_keys)
        raise ValueError(f"Badcase labels mismatch; missing={missing}, extra={extra}")

    rows: list[dict[str, Any]] = []
    for failure in failures:
        label = labels[failure["key"]]
        category = label["category"]
        if category not in CATEGORY_LABELS:
            raise ValueError(f"Unknown category: {category}")
        failure.update(
            {
                "category": category,
                "category_label": CATEGORY_LABELS[category],
                "exact_gold_recall_at_5": exact_recall(failure),
                "fix": label["fix"],
            }
        )
        rows.append(failure)

    count_by_category = Counter(row["category"] for row in rows)
    count_by_version = Counter(row["version"] for row in rows)
    unique_by_category: dict[str, set[str]] = {}
    for row in rows:
        unique_by_category.setdefault(row["category"], set()).add(row["id"])
    final_rows = [row for row in rows if row["is_final_b3"]]

    stats = {
        "total_failure_instances": len(rows),
        "unique_failed_questions": len({row["id"] for row in rows}),
        "count_by_version": dict(sorted(count_by_version.items())),
        "category_counts": {
            category: count_by_category.get(category, 0)
            for category in CATEGORY_LABELS
        },
        "category_unique_questions": {
            category: len(unique_by_category.get(category, set()))
            for category in CATEGORY_LABELS
        },
        "final_b3_failures": [
            {
                "id": row["id"],
                "category": row["category"],
                "exact_gold_recall_at_5": row["exact_gold_recall_at_5"],
            }
            for row in final_rows
        ],
        "observed_categories": [
            category
            for category in CATEGORY_LABELS
            if count_by_category.get(category, 0) > 0
        ],
        "unobserved_categories": [
            category
            for category in CATEGORY_LABELS
            if count_by_category.get(category, 0) == 0
        ],
    }
    return rows, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    parser.add_argument("--stats-json", type=Path, default=DEFAULT_STATS_JSON)
    parser.add_argument("--stats-csv", type=Path, default=DEFAULT_STATS_CSV)
    args = parser.parse_args()

    rows, stats = build_badcases()
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    args.jsonl.write_text(content + "\n", encoding="utf-8")
    args.stats_json.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with args.stats_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "label", "count", "unique_questions"])
        for category, label in CATEGORY_LABELS.items():
            writer.writerow(
                [
                    category,
                    label,
                    stats["category_counts"][category],
                    stats["category_unique_questions"][category],
                ]
            )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
