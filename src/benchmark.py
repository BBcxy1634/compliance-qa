"""Benchmark end-to-end latency and token cost for a RAG configuration."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from src.config import ROOT
from src.evaluate import file_sha256, load_jsonl, percentile, write_jsonl
from src.rag import answer_with_retriever, create_retriever


QUESTIONS_PATH = ROOT / "eval" / "questions.jsonl"
DEFAULT_PRICING = (
    ROOT / "eval" / "pricing" / "deepseek_flash_2026-10-31.json"
)
BENCH_RESULTS_DIR = ROOT / "eval" / "bench"
CN_TZ = ZoneInfo("Asia/Shanghai")


def is_peak(timestamp: datetime) -> bool:
    """Return whether China-time falls inside DeepSeek's weekday peak hours."""
    local = timestamp.astimezone(CN_TZ)
    if local.weekday() >= 5:
        return False
    hour = local.hour + local.minute / 60
    return 9 <= hour < 12 or 14 <= hour < 18


def pricing_rates(pricing: dict[str, Any], timestamp: datetime) -> dict[str, float]:
    period = "peak" if is_peak(timestamp) else "off_peak"
    return {"period": period, **pricing[period]}


def request_cost(
    usage: dict[str, Any],
    pricing: dict[str, Any],
    timestamp: datetime,
) -> tuple[float, dict[str, Any]]:
    rates = pricing_rates(pricing, timestamp)
    hit_tokens = int(usage.get("prompt_cache_hit_tokens") or 0)
    miss_tokens = int(usage.get("prompt_cache_miss_tokens") or 0)
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if hit_tokens + miss_tokens == 0:
        miss_tokens = prompt_tokens
    cost = (
        hit_tokens * rates["input_cache_hit"] / 1_000_000
        + miss_tokens * rates["input_cache_miss"] / 1_000_000
        + completion_tokens * rates["output"] / 1_000_000
    )
    return cost, {
        **rates,
        "prompt_cache_hit_tokens": hit_tokens,
        "prompt_cache_miss_tokens": miss_tokens,
        "completion_tokens": completion_tokens,
    }


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    parser.add_argument("--chunks", type=Path)
    parser.add_argument("--pricing", type=Path, default=DEFAULT_PRICING)
    parser.add_argument("--run-name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    questions_path = (
        args.questions if args.questions.is_absolute() else ROOT / args.questions
    )
    pricing_path = (
        args.pricing if args.pricing.is_absolute() else ROOT / args.pricing
    )
    config = load_config(config_path)
    run_name = args.run_name or f"{config['run_name']}_bench100"
    chunks_value = args.chunks or config.get("chunks")
    experiment = config.get("experiment", {})
    if chunks_value is None:
        chunks_path = ROOT / "data" / "processed" / (
            "chunks_b0.jsonl"
            if experiment.get("label") == "B0"
            else "chunks.jsonl"
        )
    else:
        chunks_path = Path(chunks_value)
        if not chunks_path.is_absolute():
            chunks_path = ROOT / chunks_path

    questions = load_jsonl(questions_path)
    pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
    backend = config["backend"]
    collection = config.get("collection", "bge_m3_semantic")
    thinking = bool(config.get("thinking", True))
    max_tokens = config.get("max_tokens")
    retriever = create_retriever(
        backend,
        chunks_path,
        collection,
        candidate_k=int(config.get("candidate_k", 20)),
        rrf_k=int(config.get("rrf_k", 60)),
        rerank_candidate_k=int(config.get("rerank_candidate_k", 8)),
    )
    benchmark_started_at = datetime.now(CN_TZ)

    def run_one(question: dict[str, Any]) -> dict[str, Any]:
        result = answer_with_retriever(
            question["question"],
            retriever=retriever,
            backend=backend,
            mode="deepseek",
            top_k=int(config.get("top_k", 5)),
            thinking=thinking,
            max_tokens=max_tokens,
        )
        timestamp = datetime.now(CN_TZ)
        usage = result.get("usage") or {}
        cost, cost_basis = request_cost(usage, pricing, timestamp)
        return {
            "id": question["id"],
            "requested_at": timestamp.isoformat(timespec="seconds"),
            "answer_model": result.get("model"),
            "retrieval_ms": float(result["retrieval_ms"]),
            "retrieval_breakdown": result.get("retrieval_breakdown", {}),
            "generation_ms": float(result["generation_ms"]),
            "total_ms": float(result["total_ms"]),
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "cost_cny": cost,
            "cost_basis": cost_basis,
        }

    print(f"Warming up {run_name} with {args.warmup} requests")
    for index in range(args.warmup):
        run_one(questions[index % len(questions)])

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    print(f"Benchmarking {args.samples} requests for {run_name}")
    for index in range(args.samples):
        question = questions[index % len(questions)]
        try:
            row = run_one(question)
            row["sample_index"] = index + 1
            rows.append(row)
        except Exception as exc:
            errors.append(
                {
                    "sample_index": index + 1,
                    "id": question["id"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    totals = [row["total_ms"] for row in rows]
    retrievals = [row["retrieval_ms"] for row in rows]
    generations = [row["generation_ms"] for row in rows]
    costs = [row["cost_cny"] for row in rows]
    rerank_values = [
        float(row["retrieval_breakdown"]["rerank_ms"])
        for row in rows
        if "rerank_ms" in row["retrieval_breakdown"]
    ]
    models = sorted({str(row["answer_model"]) for row in rows})
    periods = sorted({row["cost_basis"]["period"] for row in rows})
    summary = {
        "run_name": run_name,
        "config": {**config, "judge": "not_run_in_benchmark"},
        "benchmark_scope": "retrieval_and_generation; judge_excluded",
        "started_at": benchmark_started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now(CN_TZ).isoformat(timespec="seconds"),
        "samples_requested": args.samples,
        "samples_successful": len(rows),
        "samples_failed": len(errors),
        "warmup_requests": args.warmup,
        "cache_policy": "application answer cache disabled",
            "thinking": thinking,
            "max_tokens": max_tokens,
        "answer_models": models,
        "pricing_periods": periods,
        "pricing": {
            "source_url": pricing["source_url"],
            "captured_at": pricing["captured_at"],
            "currency": pricing["currency"],
            "unit": pricing["unit"],
        },
        "latency_ms": {
            "total_p50": round(percentile(totals, 0.50), 2),
            "total_p95": round(percentile(totals, 0.95), 2),
            "total_mean": round(statistics.mean(totals), 2) if totals else 0.0,
            "total_min": round(min(totals), 2) if totals else 0.0,
            "total_max": round(max(totals), 2) if totals else 0.0,
            "retrieval_p50": round(percentile(retrievals, 0.50), 2),
            "retrieval_p95": round(percentile(retrievals, 0.95), 2),
            "retrieval_mean": round(statistics.mean(retrievals), 2)
            if retrievals
            else 0.0,
            "generation_p50": round(percentile(generations, 0.50), 2),
            "generation_p95": round(percentile(generations, 0.95), 2),
            "generation_mean": round(statistics.mean(generations), 2)
            if generations
            else 0.0,
            "rerank_p50": round(percentile(rerank_values, 0.50), 2),
            "rerank_p95": round(percentile(rerank_values, 0.95), 2),
            "rerank_mean": round(statistics.mean(rerank_values), 2)
            if rerank_values
            else 0.0,
            "within_3s_rate": round(
                sum(value <= 3000 for value in totals) / len(totals),
                4,
            )
            if totals
            else 0.0,
        },
        "tokens": {
            "mean_prompt": round(
                statistics.mean(row["prompt_tokens"] for row in rows),
                2,
            )
            if rows
            else 0.0,
            "mean_completion": round(
                statistics.mean(row["completion_tokens"] for row in rows),
                2,
            )
            if rows
            else 0.0,
            "total_prompt": sum(row["prompt_tokens"] for row in rows),
            "total_completion": sum(row["completion_tokens"] for row in rows),
        },
        "cost_cny": {
            "total": round(sum(costs), 6),
            "mean": round(statistics.mean(costs), 8) if costs else 0.0,
            "p50": round(percentile(costs, 0.50), 8),
            "p95": round(percentile(costs, 0.95), 8),
        },
        "errors": errors,
        "inputs": {
            "questions_sha256": file_sha256(questions_path),
            "chunks_sha256": file_sha256(chunks_path),
        },
    }

    run_dir = BENCH_RESULTS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(run_dir / "requests.jsonl", rows)
    write_jsonl(run_dir / "errors.jsonl", errors)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Results: {run_dir}")


if __name__ == "__main__":
    main()
