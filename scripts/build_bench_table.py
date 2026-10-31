#!/usr/bin/env python3
"""Build the D11 B1/B3 latency and cost comparison table."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "eval" / "bench" / "benchmark_table.csv"
DEFAULT_JSON = ROOT / "eval" / "bench" / "benchmark_table.json"


def parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Run must use LABEL=PATH format")
    label, raw_path = value.split("=", 1)
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    return label, path


def summary_to_row(label: str, summary: dict[str, Any]) -> dict[str, Any]:
    if summary["samples_successful"] != summary["samples_requested"]:
        raise ValueError(
            f"{label}: benchmark has failed samples: {summary['samples_failed']}"
        )
    latency = summary["latency_ms"]
    cost = summary["cost_cny"]
    tokens = summary["tokens"]
    config = summary.get("config", {})
    return {
        "version": label,
        "samples": summary["samples_successful"],
        "model": ",".join(summary["answer_models"]),
        "thinking": summary.get("thinking", config.get("thinking", True)),
        "max_tokens": summary.get("max_tokens", config.get("max_tokens")),
        "pricing_period": ",".join(summary["pricing_periods"]),
        "total_p50_ms": latency["total_p50"],
        "total_p95_ms": latency["total_p95"],
        "retrieval_p95_ms": latency["retrieval_p95"],
        "rerank_p95_ms": latency["rerank_p95"],
        "generation_p95_ms": latency["generation_p95"],
        "within_3s_rate": latency["within_3s_rate"],
        "mean_prompt_tokens": tokens["mean_prompt"],
        "mean_completion_tokens": tokens["mean_completion"],
        "mean_cost_cny": cost["mean"],
        "p95_cost_cny": cost["p95"],
        "cost_under_001_cny": cost["p95"] <= 0.01,
        "latency_under_3s": latency["total_p95"] <= 3000,
    }


def summary_row(label: str, path: Path) -> dict[str, Any]:
    return summary_to_row(
        label,
        json.loads(path.read_text(encoding="utf-8")),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=parse_run)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    args = parser.parse_args()

    rows = [summary_row(label, path) for label, path in args.run]
    rows.sort(key=lambda row: row["version"])
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.json.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
