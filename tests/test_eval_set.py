"""Structural tests for the D3 evaluation set."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from src.agent_graph import classify_route


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = ROOT / "eval" / "questions.jsonl"
AGENTIC_QUESTIONS_PATH = (
    ROOT / "eval" / "agentic_v2" / "questions.jsonl"
)


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


@pytest.mark.data
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


def test_agentic_eval_set_is_versioned_and_draft_reviewed() -> None:
    questions = [
        json.loads(line)
        for line in AGENTIC_QUESTIONS_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    assert len(questions) == 150
    assert Counter(question["type"] for question in questions) == {
        "fact": 70,
        "multi_hop": 60,
        "refusal": 20,
    }
    assert [question["id"] for question in questions] == [
        f"q{number:03d}" for number in range(1, 151)
    ]
    assert all(
        question["agentic"]["review_status"] == "draft"
        for question in questions
    )
    assert all(
        question["review_status"] == "draft"
        for question in questions[60:]
    )
    assert all(
        "reviewer" not in question
        and "reviewed_at" not in question
        and "manual_correct" not in question
        for question in questions
    )


@pytest.mark.data
def test_agentic_eval_validator_passes() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate_agentic_eval.py"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "AGENTIC VALIDATION PASSED" in result.stdout


def test_agentic_route_accuracy_meets_phase_target() -> None:
    questions = [
        json.loads(line)
        for line in AGENTIC_QUESTIONS_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    correct = sum(
        classify_route(question["question"], "bge_m3")["route"]
        == question["agentic"]["expected_route"]
        for question in questions
    )

    assert round(correct / len(questions), 4) == 0.9067
