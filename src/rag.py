"""Run the D2 naive RAG question answering pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from src.config import DEFAULT_CHUNKS_PATH, DEFAULT_TOP_K
from src.generate import (
    deepseek_answer,
    deepseek_answer_stream,
    extractive_answer,
    filter_used_citations,
)
from src.retrieve import (
    BM25Retriever,
    BGEVectorRetriever,
    CrossEncoderReranker,
    HybridRetriever,
    RerankedRetriever,
)
from src.schemas import SearchHit


@dataclass(frozen=True)
class RetrievalRun:
    hits: list[SearchHit]
    retrieval_ms: float
    retrieval_breakdown: dict[str, Any]
    started_at: float


def create_retriever(
    backend: str,
    chunks_path: Path,
    collection: str = "bge_m3_semantic",
    *,
    candidate_k: int = 20,
    rrf_k: int = 60,
    rerank_candidate_k: int = 8,
) -> BM25Retriever | BGEVectorRetriever | HybridRetriever | RerankedRetriever:
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
    if backend == "rerank":
        hybrid = HybridRetriever(
            BGEVectorRetriever(collection_name=collection),
            BM25Retriever.from_jsonl(chunks_path),
            candidate_k=candidate_k,
            rrf_k=rrf_k,
        )
        return RerankedRetriever(
            hybrid,
            CrossEncoderReranker(),
            initial_k=rerank_candidate_k,
        )
    raise ValueError(f"Unsupported backend: {backend}")


def _retrieve_for_answer(
    question: str,
    retriever: (
        BM25Retriever
        | BGEVectorRetriever
        | HybridRetriever
        | RerankedRetriever
    ),
    top_k: int,
) -> RetrievalRun:
    started = time.perf_counter()
    hits = retriever.search(question, top_k=top_k)
    retrieval_ms = (time.perf_counter() - started) * 1000
    return RetrievalRun(
        hits=hits,
        retrieval_ms=retrieval_ms,
        retrieval_breakdown=getattr(retriever, "last_timing_ms", {}),
        started_at=started,
    )


def _finalize_result(
    result: dict[str, Any],
    *,
    question: str,
    backend: str,
    thinking: bool,
    retrieval: RetrievalRun,
) -> dict[str, Any]:
    total_ms = (time.perf_counter() - retrieval.started_at) * 1000
    refused = bool(result.get("refused"))
    answer = str(result.get("answer", ""))
    citations = filter_used_citations(
        answer,
        list(result.get("citations", [])),
        refused=refused,
    )
    result.update(
        {
            "answer": answer,
            "citations": citations,
            "refused": refused,
            "question": question,
            "backend": backend,
            "thinking": thinking,
            "retrieval_ms": round(retrieval.retrieval_ms, 2),
            "retrieval_breakdown": retrieval.retrieval_breakdown,
            "generation_ms": round(
                max(0.0, total_ms - retrieval.retrieval_ms),
                2,
            ),
            "total_ms": round(total_ms, 2),
            "hits": [
                {
                    "score": round(hit.score, 4),
                    "chunk_id": hit.chunk.get("chunk_id"),
                    "title": hit.chunk.get("title"),
                    "source": hit.chunk.get("source"),
                    "page_label": hit.chunk.get("page_label"),
                    "text": hit.chunk.get("text"),
                }
                for hit in retrieval.hits
            ],
        }
    )
    return result


def answer_with_retriever(
    question: str,
    *,
    retriever: (
        BM25Retriever
        | BGEVectorRetriever
        | HybridRetriever
        | RerankedRetriever
    ),
    backend: str,
    mode: str,
    top_k: int,
    thinking: bool = True,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    retrieval = _retrieve_for_answer(question, retriever, top_k)
    min_score = 0.25 if backend == "bge_m3" else 0.5
    if mode == "deepseek":
        result = deepseek_answer(
            question,
            retrieval.hits,
            thinking=thinking,
            **({"max_tokens": max_tokens} if max_tokens is not None else {}),
        )
    else:
        result = extractive_answer(
            question,
            retrieval.hits,
            min_score=min_score,
            enforce_term_coverage=backend == "bm25",
            backend=backend,
        )
    return _finalize_result(
        result,
        question=question,
        backend=backend,
        thinking=thinking,
        retrieval=retrieval,
    )


def stream_answer_with_retriever(
    question: str,
    *,
    retriever: (
        BM25Retriever
        | BGEVectorRetriever
        | HybridRetriever
        | RerankedRetriever
    ),
    backend: str,
    top_k: int,
    thinking: bool = True,
    max_tokens: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream the DeepSeek answer through the existing RAG orchestration."""
    yield {"event": "status", "data": {"stage": "retrieving"}}
    retrieval = _retrieve_for_answer(question, retriever, top_k)
    yield {"event": "status", "data": {"stage": "generating"}}

    result: dict[str, Any] | None = None
    stream = deepseek_answer_stream(
        question,
        retrieval.hits,
        thinking=thinking,
        **({"max_tokens": max_tokens} if max_tokens is not None else {}),
    )
    for item in stream:
        if item.get("type") == "token":
            yield {
                "event": "token",
                "data": {"delta": str(item.get("delta", ""))},
            }
        elif item.get("type") == "result":
            result = dict(item.get("result", {}))
    if result is None:
        raise RuntimeError("Streaming generation ended without a final result.")

    yield {"event": "status", "data": {"stage": "verifying_citations"}}
    yield {
        "event": "done",
        "data": _finalize_result(
            result,
            question=question,
            backend=backend,
            thinking=thinking,
            retrieval=retrieval,
        ),
    }


def answer_question(
    question: str,
    *,
    backend: str,
    mode: str,
    chunks_path: Path,
    top_k: int,
    thinking: bool = True,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    retriever = create_retriever(backend, chunks_path)
    return answer_with_retriever(
        question,
        retriever=retriever,
        backend=backend,
        mode=mode,
        top_k=top_k,
        thinking=thinking,
        max_tokens=max_tokens,
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
        choices=("bm25", "bge_m3", "hybrid", "rerank"),
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
    parser.add_argument(
        "--thinking",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
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
            thinking=args.thinking,
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
            thinking=args.thinking,
        )
        print_result(result, args.as_json)


if __name__ == "__main__":
    main()
