#!/usr/bin/env python3
"""Build the B0-B3 comparison table from evaluation summary files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def summary_row(label: str, summary_path: Path) -> dict[str, Any]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    experiment = summary.get("experiment") or {}
    metrics = summary["metrics"]
    return {
        "version": experiment.get("label", label),
        "name": experiment.get("name", summary.get("run_name", label)),
        "chunking": experiment.get("chunking", ""),
        "retrieval": experiment.get("retrieval", ""),
        "reranker": experiment.get("reranker", ""),
        "hit_at_5": metrics["hit_at_5"],
        "gold_recall_at_5": metrics["gold_chunk_recall_at_5"],
        "citation_accuracy": metrics["citation_accuracy"],
        "answer_correctness": metrics["answer_correctness"],
        "refusal_accuracy": metrics["refusal_accuracy"],
        "p50_ms": metrics["latency_ms"]["p50_all"],
        "p95_ms": metrics["latency_ms"]["p95_all"],
    }


def parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Run must use LABEL=PATH format")
    label, raw_path = value.split("=", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    return label, path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        type=parse_run,
        help="Evaluation summary as LABEL=PATH. Repeat for B0-B3.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "eval" / "results" / "baseline_table.csv",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=ROOT / "eval" / "results" / "baseline_table.json",
    )
    args = parser.parse_args()

    rows = [summary_row(label, path) for label, path in args.run]
    rows.sort(key=lambda row: row["version"])
    fieldnames = list(rows[0])
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    args.json.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
