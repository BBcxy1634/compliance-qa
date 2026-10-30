"""Structural tests for the D3 evaluation set."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "eval" / "questions.jsonl"


def test_eval_set_has_required_distribution() -> None:
    questions = [
        json.loads(line)
        for line in QUESTIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(questions) == 60
    assert Counter(question["type"] for question in questions) == {
        "fact": 40,
        "multi_hop": 10,
        "refusal": 10,
    }
    assert all(question["review_status"] == "approved" for question in questions)


def test_eval_validator_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_eval.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "VALIDATION PASSED" in result.stdout
