#!/usr/bin/env python3
"""Compute stage-by-stage B0-B3 ablation deltas from the baseline table."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "eval" / "results" / "baseline_table.json"
DEFAULT_JSON = ROOT / "eval" / "results" / "ablation_stage_deltas.json"
DEFAULT_CSV = ROOT / "eval" / "results" / "ablation_stage_deltas.csv"
VERSIONS = ("B0", "B1", "B2", "B3")
METRICS = (
    "hit_at_5",
    "gold_recall_at_5",
    "citation_accuracy",
    "answer_correctness",
    "fact_accuracy",
    "multi_hop_accuracy",
    "refusal_accuracy",
    "answerable_false_refusal",
    "refusal_false_positive",
    "p50_ms",
    "p95_ms",
)
STAGES = (
    ("B0->B1", "切分方式", "固定切分 -> 语义切分"),
    ("B1->B2", "检索方式", "纯向量检索 -> 混合检索"),
    ("B2->B3", "重排", "无重排 -> bge-reranker-v2-m3"),
)


def delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, float]:
    return {
        metric: round(float(after[metric]) - float(before[metric]), 4)
        for metric in METRICS
    }


def build_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_version = {row["version"]: row for row in rows}
    missing = [version for version in VERSIONS if version not in by_version]
    if missing:
        raise ValueError(f"Missing baseline versions: {missing}")

    stage_rows: list[dict[str, Any]] = []
    for label, variable, change in STAGES:
        before_version, after_version = label.split("->")
        changes = delta(by_version[before_version], by_version[after_version])
        stage_rows.append(
            {
                "stage": label,
                "variable": variable,
                "change": change,
                **changes,
            }
        )

    cumulative = delta(by_version["B0"], by_version["B3"])
    stage_rows.append(
        {
            "stage": "B0->B3",
            "variable": "累计",
            "change": "全部三个变量",
            **cumulative,
        }
    )

    answer_stages = [
        row for row in stage_rows if row["stage"] != "B0->B3"
    ]
    largest_answer_gain = max(
        answer_stages,
        key=lambda row: row["answer_correctness"],
    )
    largest_multihop_gain = max(
        answer_stages,
        key=lambda row: row["multi_hop_accuracy"],
    )
    best_quality = max(
        rows,
        key=lambda row: (row["answer_correctness"], row["multi_hop_accuracy"]),
    )
    lowest_p95 = min(rows, key=lambda row: row["p95_ms"])

    return {
        "versions": list(VERSIONS),
        "stages": stage_rows,
        "summary": {
            "largest_answer_gain_stage": largest_answer_gain["stage"],
            "largest_answer_gain_delta": largest_answer_gain[
                "answer_correctness"
            ],
            "largest_multihop_gain_stage": largest_multihop_gain["stage"],
            "largest_multihop_gain_delta": largest_multihop_gain[
                "multi_hop_accuracy"
            ],
            "best_quality_version": best_quality["version"],
            "best_quality_answer_correctness": best_quality[
                "answer_correctness"
            ],
            "lowest_p95_version": lowest_p95["version"],
            "lowest_p95_ms": lowest_p95["p95_ms"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()

    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    rows = json.loads(input_path.read_text(encoding="utf-8"))
    analysis = build_analysis(rows)
    args.json.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    fieldnames = ["stage", "variable", "change", *METRICS]
    with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(analysis["stages"])
    print(json.dumps(analysis, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
