#!/usr/bin/env python3
"""Validate the deterministic CI evaluation smoke summary."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    errors: list[str] = []

    if summary.get("successful_questions") != 3:
        errors.append("expected 3 successful smoke questions")
    if summary.get("failed_questions") != 0:
        errors.append("smoke evaluation contains failed questions")
    if summary.get("config", {}).get("judge") != "none":
        errors.append("smoke evaluation must not use a model judge")
    if summary.get("config", {}).get("mode") != "extractive":
        errors.append("smoke evaluation must use extractive mode")
    if summary.get("metrics", {}).get("refusal_accuracy") != 1.0:
        errors.append("smoke refusal behavior did not match expectations")
    if (
        summary.get("agentic_metrics", {})
        .get("route_accuracy", {})
        .get("accuracy")
        != 1.0
    ):
        errors.append("smoke route accuracy did not match expectations")

    if errors:
        print("EVAL SMOKE VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("EVAL SMOKE VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
