"""Run the D2 naive RAG question answering pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from src.config import DEFAULT_CHUNKS_PATH, DEFAULT_TOP_K
from src.generate import deepseek_answer, extractive_answer
from src.retrieve import (
    BM25Retriever,
    BGEVectorRetriever,
    HybridRetriever,
)
from src.schemas import SearchHit


def create_retriever(
    backend: str,
    chunks_path: Path,
    collection: str = "bge_m3_semantic",
    *,
    candidate_k: int = 20,
    rrf_k: int = 60,
) -> BM25Retriever | BGEVectorRetriever | HybridRetriever:
    if backend == "bm25":
        return BM25Retriever.from_jsonl(chunks_path)
    if backend == "bge_m3":
        return BGEVectorRetriever(collection_name=collection)
    if backend == "hybrid":
        return HybridRetriever(
            BGEVectorRetriever(collection_name=collection),
            BM25Retriever.from_jsonl(chunks_path),
            candidate_k=candidate_k,
            rrf_k=rrf_k,
        )
    raise ValueError(f"Unsupported backend: {backend}")


def answer_with_retriever(
    question: str,
    *,
    retriever: BM25Retriever | BGEVectorRetriever | HybridRetriever,
    backend: str,
    mode: str,
    top_k: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    hits = retriever.search(question, top_k=top_k)
    retrieval_ms = (time.perf_counter() - started) * 1000
    min_score = 0.25 if backend == "bge_m3" else 0.5
    if mode == "deepseek":
        result = deepseek_answer(question, hits)
    else:
        result = extractive_answer(
            question,
            hits,
            min_score=min_score,
            enforce_term_coverage=backend == "bm25",
            backend=backend,
        )
    result.update(
        {
            "question": question,
            "backend": backend,
            "retrieval_ms": round(retrieval_ms, 2),
            "total_ms": round((time.perf_counter() - started) * 1000, 2),
            "hits": [
                {
                    "score": round(hit.score, 4),
                    "chunk_id": hit.chunk.get("chunk_id"),
                    "title": hit.chunk.get("title"),
                    "source": hit.chunk.get("source"),
                    "page_label": hit.chunk.get("page_label"),
                    "text": hit.chunk.get("text"),
                }
                for hit in hits
            ],
        }
    )
    return result


def answer_question(
    question: str,
    *,
    backend: str,
    mode: str,
    chunks_path: Path,
    top_k: int,
) -> dict[str, Any]:
    retriever = create_retriever(backend, chunks_path)
    return answer_with_retriever(
        question,
        retriever=retriever,
        backend=backend,
        mode=mode,
        top_k=top_k,
    )


def print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(result["answer"])
    if result.get("citations"):
        print("\n引用：")
        for citation in result["citations"]:
            print(
                f"- [{citation['citation_id']}] {citation['title']} | "
                f"{citation['location']} | {citation['source']}"
            )
    print(
        f"\n模式：{result['mode']}；后端：{result['backend']}；"
        f"耗时：{result['total_ms']} ms"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", help="Question to answer")
    parser.add_argument(
        "--backend",
        choices=("bm25", "bge_m3", "hybrid"),
        default="bge_m3",
    )
    parser.add_argument("--collection", default="bge_m3_semantic")
    parser.add_argument(
        "--mode",
        choices=("extractive", "deepseek"),
        default="extractive",
    )
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    retriever = create_retriever(args.backend, args.chunks, args.collection)
    if args.question:
        result = answer_with_retriever(
            args.question,
            retriever=retriever,
            backend=args.backend,
            mode=args.mode,
            top_k=args.top_k,
        )
        print_result(result, args.as_json)
        return

    print("输入问题，回车查看结果；输入 exit 退出。")
    while True:
        question = input("\n问题> ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue
        result = answer_with_retriever(
            question,
            retriever=retriever,
            backend=args.backend,
            mode=args.mode,
            top_k=args.top_k,
        )
        print_result(result, args.as_json)


if __name__ == "__main__":
    main()
