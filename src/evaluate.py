"""Run the frozen D3 evaluation set and produce reproducible metrics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from openai import OpenAI

from src.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    ROOT,
)
from src.generate import REFUSAL_TEXT
from src.observability import TraceStore, public_error_code
from src.rag import answer_with_retriever, create_retriever


QUESTIONS_PATH = ROOT / "eval" / "questions.jsonl"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
RESULTS_DIR = ROOT / "eval" / "results"
DEFAULT_CONFIG = ROOT / "eval" / "configs" / "d4_bge_extractive.yaml"
JUDGE_CACHE = RESULTS_DIR / "judge_cache.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return float(
        ordered[lower] + (ordered[upper] - ordered[lower]) * fraction
    )


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "correct"}


def gold_match_key(chunk_id: str, match_mode: str) -> str:
    """Map a strategy-specific chunk ID to the configured comparison unit."""
    if match_mode == "exact":
        return chunk_id
    if match_mode == "unit":
        parts = chunk_id.split("#")
        if len(parts) < 2:
            raise ValueError(f"Invalid chunk ID for unit matching: {chunk_id}")
        return "#".join(parts[:2])
    raise ValueError(f"Unsupported gold match mode: {match_mode}")


def load_manual_labels(path: Path | None) -> dict[str, bool]:
    if path is None or not path.exists():
        return {}
    labels: dict[str, bool] = {}
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                value = (row.get("manual_correct") or "").strip()
                if value:
                    labels[row["id"]] = parse_bool(value)
    else:
        for row in load_jsonl(path):
            if row.get("manual_correct") is not None:
                labels[row["id"]] = bool(row["manual_correct"])
    return labels


class DeepSeekJudge:
    """Cacheable strict key-fact judge used for provisional correctness scores."""

    def __init__(self, model: str = DEEPSEEK_MODEL) -> None:
        if not DEEPSEEK_API_KEY:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        self.model = model
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
        )
        self.cache = {}
        if JUDGE_CACHE.exists():
            for row in load_jsonl(JUDGE_CACHE):
                self.cache[row["key"]] = row

    @staticmethod
    def cache_key(question: dict[str, Any], answer: str) -> str:
        payload = {
            "question": question["question"],
            "gold_answer": question["gold_answer"],
            "key_facts": question["key_facts"],
            "answer": answer,
            "model": DEEPSEEK_MODEL,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def judge(self, question: dict[str, Any], answer: str) -> dict[str, Any]:
        key = self.cache_key(question, answer)
        if key in self.cache:
            cached = dict(self.cache[key])
            cached["cached"] = True
            return cached

        prompt = f"""你是严格的RAG答案评测员。
只判断候选答案是否覆盖下列全部关键事实，并检查是否存在与标准答案冲突的陈述。
不要因为表达风格、语言或额外引用扣分。缺少任一关键事实即判错。

问题：
{question["question"]}

标准答案：
{question["gold_answer"]}

必须覆盖的关键事实：
{json.dumps(question["key_facts"], ensure_ascii=False, indent=2)}

候选答案：
{answer}

只输出一个JSON对象，不要使用Markdown：
{{"correct": true或false, "reason": "不超过80字的中文理由"}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                max_tokens=160,
                messages=[
                    {
                        "role": "system",
                        "content": "你只输出严格JSON，不接受外部知识，不讨论题目本身。",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                raise ValueError(f"Judge response is not JSON: {content[:200]}")
            parsed = json.loads(match.group(0))
            record = {
                "key": key,
                "correct": bool(parsed.get("correct")),
                "reason": str(parsed.get("reason", ""))[:200],
                "model": self.model,
                "usage": {
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                    "completion_tokens": getattr(
                        response.usage,
                        "completion_tokens",
                        None,
                    ),
                    "total_tokens": getattr(response.usage, "total_tokens", None),
                },
                "cached": False,
            }
        except Exception as exc:
            record = {
                "key": key,
                "correct": None,
                "reason": f"judge_error: {type(exc).__name__}: {exc}"[:250],
                "model": self.model,
                "usage": {},
                "cached": False,
            }

        if record["correct"] is not None:
            self.cache[key] = record
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            with JUDGE_CACHE.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record


def compute_metrics(
    results: list[dict[str, Any]],
    manual_labels: dict[str, bool],
) -> dict[str, Any]:
    answerable = [row for row in results if row["type"] != "refusal"]
    refusals = [row for row in results if row["type"] == "refusal"]
    hit_count = sum(bool(row["hit_at_k"]) for row in answerable)
    cited = [row for row in answerable if row["citations"]]
    citation_hit_count = sum(bool(row["citation_hit"]) for row in cited)

    correctness_values: list[bool] = []
    auto_judged = 0
    manual_count = 0
    for row in answerable:
        if row["id"] in manual_labels:
            correct = manual_labels[row["id"]]
            manual_count += 1
            row["correctness_source"] = "manual"
        else:
            correct = row.get("auto_correct")
            row["correctness_source"] = "deepseek"
            if correct is not None:
                auto_judged += 1
        row["final_correct"] = correct
        correctness_values.append(bool(correct))

    correct_count = sum(correctness_values)
    refusal_correct = sum(bool(row["refused"]) for row in refusals)
    latency_values = [row["total_ms"] for row in results if row.get("total_ms") is not None]
    answerable_latencies = [
        row["total_ms"] for row in answerable if row.get("total_ms") is not None
    ]

    by_type: dict[str, dict[str, Any]] = {}
    for question_type in ("fact", "multi_hop", "refusal"):
        group = [row for row in results if row["type"] == question_type]
        if question_type == "refusal":
            correct = sum(bool(row["refused"]) for row in group)
        else:
            correct = sum(bool(row.get("final_correct")) for row in group)
        by_type[question_type] = {
            "count": len(group),
            "correct": correct,
            "accuracy": round(correct / len(group), 4) if group else 0.0,
            "mean_gold_recall_at_k": round(
                statistics.mean(row["gold_recall_at_k"] for row in group),
                4,
            )
            if group
            else 0.0,
        }

    return {
        "total_questions": len(results),
        "answerable_questions": len(answerable),
        "refusal_questions": len(refusals),
        "hit_at_5": round(hit_count / len(answerable), 4) if answerable else 0.0,
        "gold_chunk_recall_at_5": round(
            statistics.mean(row["gold_recall_at_k"] for row in answerable),
            4,
        )
        if answerable
        else 0.0,
        "citation_accuracy": round(citation_hit_count / len(cited), 4) if cited else 0.0,
        "citation_coverage": round(len(cited) / len(answerable), 4)
        if answerable
        else 0.0,
        "answer_correctness": round(correct_count / len(answerable), 4)
        if answerable
        else 0.0,
        "refusal_accuracy": round(refusal_correct / len(refusals), 4)
        if refusals
        else 0.0,
        "answerable_false_refusal": sum(
            bool(row["refused"]) for row in answerable
        ),
        "refusal_false_positive": sum(
            not bool(row["refused"]) for row in refusals
        ),
        "correctness_sources": {
            "manual": manual_count,
            "deepseek_auto": auto_judged,
            "unknown": len(answerable) - manual_count - auto_judged,
        },
        "latency_ms": {
            "p50_all": round(percentile(latency_values, 0.50), 2),
            "p95_all": round(percentile(latency_values, 0.95), 2),
            "p50_answerable": round(percentile(answerable_latencies, 0.50), 2),
            "p95_answerable": round(percentile(answerable_latencies, 0.95), 2),
        },
        "by_type": by_type,
    }


def _row_source_ids(row: dict[str, Any]) -> set[str]:
    return {
        str(chunk_id).split("#", 1)[0]
        for chunk_id in row.get("gold_chunks", [])
        if str(chunk_id)
    }


def _citation_source_ids(row: dict[str, Any]) -> set[str]:
    source_ids: set[str] = set()
    for citation in row.get("citations", []):
        if not isinstance(citation, dict):
            continue
        source_id = str(citation.get("source_id", "")).strip()
        if not source_id:
            source_id = str(citation.get("chunk_id", "")).split("#", 1)[0]
        if source_id:
            source_ids.add(source_id)
    return source_ids


def compute_agentic_metrics(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    route_rows = [
        row for row in results if row.get("expected_route") is not None
    ]
    route_correct = sum(
        row.get("route") == row["expected_route"] for row in route_rows
    )
    route_by_expected: dict[str, dict[str, Any]] = {}
    for expected in ("simple_fact", "multi_hop", "high_risk"):
        group = [
            row for row in route_rows if row["expected_route"] == expected
        ]
        correct = sum(row.get("route") == expected for row in group)
        route_by_expected[expected] = {
            "count": len(group),
            "correct": correct,
            "accuracy": round(correct / len(group), 4) if group else 0.0,
        }
    confusion: dict[str, dict[str, int]] = {}
    for row in route_rows:
        expected = str(row["expected_route"])
        actual = str(row.get("route") or "missing")
        confusion.setdefault(expected, {})
        confusion[expected][actual] = confusion[expected].get(actual, 0) + 1

    selection_rows = [
        row
        for row in results
        if isinstance(row.get("required_tools"), list)
    ]
    selection_correct = 0
    for row in selection_rows:
        invoked = {
            str(call.get("tool", ""))
            for call in row.get("tool_calls", [])
            if isinstance(call, dict)
        }
        required = {str(tool) for tool in row["required_tools"]}
        if required.issubset(invoked):
            selection_correct += 1

    tool_calls = [
        call
        for row in results
        for call in row.get("tool_calls", [])
        if isinstance(call, dict)
    ]
    tool_success_count = sum(bool(call.get("ok")) for call in tool_calls)
    tools_by_name: dict[str, dict[str, Any]] = {}
    failure_codes: Counter[str] = Counter()
    for call in tool_calls:
        name = str(call.get("tool", ""))
        bucket = tools_by_name.setdefault(
            name,
            {"calls": 0, "successes": 0, "failures": 0},
        )
        bucket["calls"] += 1
        if call.get("ok"):
            bucket["successes"] += 1
        else:
            bucket["failures"] += 1
            error = call.get("error")
            code = (
                str(error.get("code", "unknown"))
                if isinstance(error, dict)
                else "unknown"
            )
            failure_codes[code] += 1
    for bucket in tools_by_name.values():
        bucket["success_rate"] = (
            round(bucket["successes"] / bucket["calls"], 4)
            if bucket["calls"]
            else 0.0
        )

    evidence_rows = [
        row
        for row in results
        if isinstance(row.get("expected_evidence_sufficient"), bool)
        and isinstance(row.get("evidence_sufficient"), bool)
    ]
    evidence_correct = sum(
        row["evidence_sufficient"] == row["expected_evidence_sufficient"]
        for row in evidence_rows
    )

    multi_step_rows = [
        row
        for row in results
        if row.get("type") == "multi_hop"
        and row.get("final_correct") is not None
    ]
    multi_step_complete = sum(
        not bool(row.get("refused"))
        and _row_source_ids(row).issubset(_citation_source_ids(row))
        and bool(row.get("final_correct"))
        for row in multi_step_rows
    )

    return {
        "route_accuracy": {
            "evaluated_cases": len(route_rows),
            "correct_cases": route_correct,
            "accuracy": round(route_correct / len(route_rows), 4)
            if route_rows
            else 0.0,
            "by_expected_route": route_by_expected,
            "confusion": confusion,
        },
        "tool_selection_accuracy": {
            "evaluated_cases": len(selection_rows),
            "correct_cases": selection_correct,
            "accuracy": round(selection_correct / len(selection_rows), 4)
            if selection_rows
            else 0.0,
            "definition": "all required_tools were invoked",
        },
        "tool_success_rate": {
            "tool_calls": len(tool_calls),
            "successful_calls": tool_success_count,
            "success_rate": round(tool_success_count / len(tool_calls), 4)
            if tool_calls
            else 0.0,
            "by_tool": dict(sorted(tools_by_name.items())),
            "failure_codes": dict(sorted(failure_codes.items())),
        },
        "multi_step_completion_rate": {
            "evaluated_cases": len(multi_step_rows),
            "completed_cases": multi_step_complete,
            "completion_rate": round(
                multi_step_complete / len(multi_step_rows),
                4,
            )
            if multi_step_rows
            else 0.0,
            "definition": (
                "not refused, all expected source_ids cited, "
                "and final correctness is true"
            ),
        },
        "evidence_sufficiency_accuracy": {
            "evaluated_cases": len(evidence_rows),
            "correct_cases": evidence_correct,
            "accuracy": round(evidence_correct / len(evidence_rows), 4)
            if evidence_rows
            else 0.0,
        },
    }


def write_review_csv(path: Path, results: list[dict[str, Any]]) -> None:
    columns = [
        "id",
        "type",
        "question",
        "answer",
        "gold_answer",
        "key_facts",
        "auto_correct",
        "auto_reason",
        "manual_correct",
        "manual_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in results:
            if row["type"] == "refusal":
                continue
            writer.writerow(
                {
                    "id": row["id"],
                    "type": row["type"],
                    "question": row["question"],
                    "answer": row["answer"],
                    "gold_answer": row["gold_answer"],
                    "key_facts": json.dumps(row["key_facts"], ensure_ascii=False),
                    "auto_correct": row.get("auto_correct"),
                    "auto_reason": row.get("auto_reason", ""),
                    "manual_correct": "",
                    "manual_notes": "",
                }
            )


def write_summary_csv(
    path: Path,
    metrics: dict[str, Any],
    gold_match: str,
    agentic_metrics: dict[str, Any] | None = None,
) -> None:
    recall_label = (
        "gold_chunk_recall@5"
        if gold_match == "exact"
        else "gold_unit_recall@5"
    )
    rows = [
        ("Hit@5", metrics["hit_at_5"]),
        ("citation_accuracy", metrics["citation_accuracy"]),
        ("answer_correctness", metrics["answer_correctness"]),
        ("refusal_accuracy", metrics["refusal_accuracy"]),
        (recall_label, metrics["gold_chunk_recall_at_5"]),
        ("citation_coverage", metrics["citation_coverage"]),
        ("P50_latency_ms", metrics["latency_ms"]["p50_all"]),
        ("P95_latency_ms", metrics["latency_ms"]["p95_all"]),
    ]
    if agentic_metrics is not None:
        rows.extend(
            [
                (
                    "agentic_route_accuracy",
                    agentic_metrics["route_accuracy"]["accuracy"],
                ),
                (
                    "agentic_tool_selection_accuracy",
                    agentic_metrics["tool_selection_accuracy"]["accuracy"],
                ),
                (
                    "agentic_tool_success_rate",
                    agentic_metrics["tool_success_rate"]["success_rate"],
                ),
                (
                    "agentic_multi_step_completion_rate",
                    agentic_metrics["multi_step_completion_rate"][
                        "completion_rate"
                    ],
                ),
                (
                    "agentic_evidence_sufficiency_accuracy",
                    agentic_metrics["evidence_sufficiency_accuracy"][
                        "accuracy"
                    ],
                ),
            ]
        )
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Evaluation config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    parser.add_argument("--chunks", type=Path, default=CHUNKS_PATH)
    parser.add_argument("--run-name")
    parser.add_argument(
        "--backend",
        choices=("bm25", "bge_m3", "hybrid", "rerank"),
    )
    parser.add_argument("--collection")
    parser.add_argument("--mode", choices=("extractive", "deepseek"))
    parser.add_argument("--judge", choices=("none", "deepseek"))
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--candidate-k", type=int)
    parser.add_argument("--rrf-k", type=int)
    parser.add_argument("--rerank-candidate-k", type=int)
    parser.add_argument(
        "--thinking",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--gold-match", choices=("exact", "unit"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--labels", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = (
        args.config if args.config.is_absolute() else ROOT / args.config
    )
    questions_path = (
        args.questions if args.questions.is_absolute() else ROOT / args.questions
    )
    chunks_path = (
        args.chunks if args.chunks.is_absolute() else ROOT / args.chunks
    )
    labels_path = (
        args.labels
        if args.labels is None or args.labels.is_absolute()
        else ROOT / args.labels
    )
    config = load_config(config_path)
    run_name = args.run_name or config.get("run_name") or "evaluation"
    backend = args.backend or config.get("backend", "bge_m3")
    mode = args.mode or config.get("mode", "extractive")
    judge_mode = args.judge or config.get("judge", "none")
    top_k = args.top_k or int(config.get("top_k", 5))
    collection = args.collection or config.get("collection", "bge_m3_semantic")
    gold_match = args.gold_match or config.get("gold_match", "exact")
    candidate_k = args.candidate_k or int(config.get("candidate_k", 20))
    rrf_k = args.rrf_k or int(config.get("rrf_k", 60))
    rerank_candidate_k = args.rerank_candidate_k or int(
        config.get("rerank_candidate_k", 8)
    )
    thinking = (
        args.thinking
        if args.thinking is not None
        else bool(config.get("thinking", True))
    )
    max_tokens = args.max_tokens or config.get("max_tokens")

    questions = load_jsonl(questions_path)
    if args.limit:
        questions = questions[: args.limit]
    manual_labels = load_manual_labels(labels_path)
    retriever = create_retriever(
        backend,
        chunks_path,
        collection,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        rerank_candidate_k=rerank_candidate_k,
    )
    judge = DeepSeekJudge() if judge_mode == "deepseek" else None

    run_dir = RESULTS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    error_summaries: list[dict[str, Any]] = []
    trace_store = TraceStore(run_dir)
    trace_store.reset()
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")

    for index, question in enumerate(questions, 1):
        print(f"[{index:02d}/{len(questions):02d}] {question['id']} {question['question']}")
        try:
            result = answer_with_retriever(
                question["question"],
                retriever=retriever,
                backend=backend,
                mode=mode,
                top_k=top_k,
                thinking=thinking,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            code = public_error_code(exc)
            trace_store.record_error(
                f"eval_{question['id']}",
                exc,
                case_id=str(question["id"]),
            )
            error_summaries.append(
                {
                    "id": question["id"],
                    "error_type": type(exc).__name__,
                    "code": code,
                }
            )
            continue
        trace_store.record_result(
            f"eval_{question['id']}",
            result,
            case_id=str(question["id"]),
        )
        retrieved = result["hits"]
        retrieved_ids = [hit["chunk_id"] for hit in retrieved]
        gold_ids = set(question["gold_chunks"])
        retrieved_keys = {
            gold_match_key(chunk_id, gold_match) for chunk_id in retrieved_ids
        }
        gold_keys = {
            gold_match_key(chunk_id, gold_match) for chunk_id in gold_ids
        }
        found = gold_keys.intersection(retrieved_keys)
        citations = result.get("citations", [])
        cited_keys = {
            gold_match_key(citation["chunk_id"], gold_match)
            for citation in citations
        }
        citation_found = gold_keys.intersection(cited_keys)
        agentic = dict(question.get("agentic") or {})

        row: dict[str, Any] = {
            "id": question["id"],
            "type": question["type"],
            "question": question["question"],
            "gold_answer": question["gold_answer"],
            "key_facts": question["key_facts"],
            "gold_chunks": question["gold_chunks"],
            "expected_behavior": question["expected_behavior"],
            "answer": result["answer"],
            "refused": bool(result.get("refused")),
            "citations": citations,
            "retrieved": retrieved,
            "hit_at_k": bool(found),
            "gold_recall_at_k": round(len(found) / len(gold_keys), 4)
            if gold_keys
            else 0.0,
            "citation_hit": bool(citation_found),
            "citation_recall": round(len(citation_found) / len(gold_keys), 4)
            if gold_keys
            else 0.0,
            "retrieval_ms": result.get("retrieval_ms"),
            "total_ms": result.get("total_ms"),
            "mode": result.get("mode"),
            "backend": result.get("backend"),
            "model": result.get("model"),
            "prompt_version": result.get("prompt_version"),
            "usage": dict(result.get("usage") or {}),
            "top_k": result.get("top_k"),
            "route": result.get("route"),
            "route_decision": dict(result.get("route_decision") or {}),
            "route_trace": list(result.get("route_trace") or []),
            "tool_calls": list(result.get("tool_calls") or []),
            "evidence_sufficient": result.get("evidence_sufficient"),
            "evidence_reason": result.get("evidence_reason"),
            "sufficient_source_count": result.get(
                "sufficient_source_count"
            ),
            "expected_route": agentic.get("expected_route"),
            "required_tools": list(agentic.get("required_tools") or []),
            "expected_evidence_sufficient": agentic.get(
                "expected_evidence_sufficient"
            ),
            "agentic_review_status": agentic.get("review_status"),
            "auto_correct": None,
            "auto_reason": "",
        }

        if question["type"] == "refusal":
            row["auto_correct"] = bool(result.get("refused"))
            row["auto_reason"] = (
                "正确拒答" if result.get("refused") else "拒答题未拒答"
            )
        elif judge is not None:
            judged = judge.judge(question, result["answer"])
            row["auto_correct"] = judged.get("correct")
            row["auto_reason"] = judged.get("reason", "")
            row["judge_cached"] = judged.get("cached", False)
            row["judge_usage"] = judged.get("usage", {})
        results.append(row)

    metrics = compute_metrics(results, manual_labels)
    agentic_metrics = compute_agentic_metrics(results)
    summary = {
        "run_name": run_name,
        "experiment": config.get("experiment", {}),
        "started_at": started_at,
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_hashes": {
            "questions_sha256": file_sha256(questions_path),
            "chunks_sha256": file_sha256(chunks_path),
        },
        "config": {
            "backend": backend,
            "mode": mode,
            "judge": judge_mode,
            "top_k": top_k,
            "collection": collection,
            "gold_match": gold_match,
            "candidate_k": candidate_k,
            "rrf_k": rrf_k,
            "rerank_candidate_k": rerank_candidate_k,
            "thinking": thinking,
            "max_tokens": max_tokens,
            "limit": args.limit,
            "questions": str(questions_path.relative_to(ROOT)),
            "chunks": str(chunks_path.relative_to(ROOT)),
        },
        "metrics": metrics,
        "agentic_metrics": agentic_metrics,
        "observability": trace_store.summary(),
        "errors": error_summaries,
        "successful_questions": len(results),
        "failed_questions": len(error_summaries),
        "human_review": {
            "status": "exempted_by_project_owner",
            "executed": False,
        },
    }

    write_jsonl(run_dir / "per_question.jsonl", results)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_summary_csv(
        run_dir / "summary.csv",
        metrics,
        gold_match,
        agentic_metrics,
    )
    write_review_csv(run_dir / "review.csv", results)
    (RESULTS_DIR / "latest_run.json").write_text(
        json.dumps(
            {"run_name": run_name, "path": str(run_dir.relative_to(ROOT))},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"Results: {run_dir}")


if __name__ == "__main__":
    main()
