"""Lexical retrieval and an optional BGE-M3 plus Chroma vector backend."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import jieba
from rank_bm25 import BM25Okapi

from src.config import (
    CHROMA_DIR,
    EMBEDDING_MAX_SEQ_LENGTH,
    EMBEDDING_MODEL,
    RERANKER_MAX_LENGTH,
    RERANKER_MODEL,
    resolve_embedding_model,
    resolve_reranker_model,
    resolve_torch_device,
)
from src.schemas import SearchHit


TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)
STOPWORDS = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "有",
    "与",
    "及",
    "或",
    "吗",
    "什么",
    "怎么",
    "如何",
    "是否",
    "可以",
    "需要",
    "一个",
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "for",
    "is",
    "are",
    "can",
    "i",
    "what",
    "how",
}
DEFAULT_HYBRID_CANDIDATE_K = 20
DEFAULT_RRF_K = 60
DEFAULT_RERANK_CANDIDATE_K = 8


def tokenize(text: str) -> list[str]:
    """Tokenize mixed Chinese and English text for BM25."""
    normalized = text.lower()
    tokens: list[str] = []
    for segment in TOKEN_PATTERN.findall(normalized):
        pieces = jieba.lcut(segment) if re.search(r"[\u4e00-\u9fff]", segment) else [segment]
        for piece in pieces:
            token = piece.strip().lower()
            if (
                token
                and token not in STOPWORDS
                and not re.fullmatch(r"[\W_]+", token)
                and len(token) > 1
            ):
                tokens.append(token)
    return tokens


def load_chunks(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class BM25Retriever:
    """Small local retriever used by the D2 naive RAG baseline."""

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            raise ValueError("Cannot build a BM25 index without chunks")
        self.chunks = chunks
        self.tokenized_corpus = [tokenize(chunk["text"]) for chunk in chunks]
        self.index = BM25Okapi(self.tokenized_corpus)

    @classmethod
    def from_jsonl(cls, path: Path) -> "BM25Retriever":
        return cls(load_chunks(path))

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = self.index.get_scores(query_tokens)
        ranked = sorted(
            enumerate(scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        hits: list[SearchHit] = []
        for index, score in ranked[:top_k]:
            chunk_tokens = set(self.tokenized_corpus[index])
            if not chunk_tokens.intersection(query_tokens):
                continue
            if float(score) <= 0:
                continue
            hits.append(SearchHit(chunk=self.chunks[index], score=float(score)))
        return hits


class HybridRetriever:
    """Fuse dense and lexical rankings with reciprocal rank fusion."""

    def __init__(
        self,
        vector_retriever: BGEVectorRetriever,
        bm25_retriever: BM25Retriever,
        *,
        candidate_k: int = DEFAULT_HYBRID_CANDIDATE_K,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        if candidate_k < 1:
            raise ValueError("candidate_k must be positive")
        if rrf_k < 1:
            raise ValueError("rrf_k must be positive")
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        vector_hits = self.vector_retriever.search(query, top_k=self.candidate_k)
        bm25_hits = self.bm25_retriever.search(query, top_k=self.candidate_k)
        scores: dict[str, float] = {}
        chunks: dict[str, dict[str, Any]] = {}

        for hits in (vector_hits, bm25_hits):
            for rank, hit in enumerate(hits, 1):
                chunk_id = hit.chunk.get("chunk_id")
                if not chunk_id:
                    continue
                chunks.setdefault(chunk_id, hit.chunk)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (
                    self.rrf_k + rank
                )

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [
            SearchHit(chunk=chunks[chunk_id], score=score)
            for chunk_id, score in ranked[:top_k]
        ]


class CrossEncoderReranker:
    """Lazy CPU reranker for query-document relevance scoring."""

    def __init__(
        self,
        model_name: str = RERANKER_MODEL,
        *,
        max_length: int = RERANKER_MAX_LENGTH,
        batch_size: int = 8,
    ) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(
            resolve_reranker_model(model_name),
            device=resolve_torch_device(),
            max_length=max_length,
        )
        self.batch_size = batch_size

    def score(self, query: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        scores = self.model.predict(
            [(query, text) for text in texts],
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        return [float(score) for score in scores]


class RerankedRetriever:
    """Retrieve a wider candidate set, then rerank it to the final Top K."""

    def __init__(
        self,
        base_retriever: HybridRetriever,
        reranker: CrossEncoderReranker,
        *,
        initial_k: int = DEFAULT_RERANK_CANDIDATE_K,
    ) -> None:
        if initial_k < 1:
            raise ValueError("initial_k must be positive")
        self.base_retriever = base_retriever
        self.reranker = reranker
        self.initial_k = initial_k

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        started = time.perf_counter()
        candidates = self.base_retriever.search(
            query,
            top_k=max(self.initial_k, top_k),
        )
        base_retrieval_ms = (time.perf_counter() - started) * 1000
        if not candidates:
            self.last_timing_ms = {
                "base_retrieval_ms": round(base_retrieval_ms, 2),
                "rerank_ms": 0.0,
            }
            return []
        rerank_started = time.perf_counter()
        scores = self.reranker.score(
            query,
            [candidate.chunk["text"] for candidate in candidates],
        )
        rerank_ms = (time.perf_counter() - rerank_started) * 1000
        self.last_timing_ms = {
            "base_retrieval_ms": round(base_retrieval_ms, 2),
            "rerank_ms": round(rerank_ms, 2),
        }
        ranked = sorted(
            zip(candidates, scores),
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            SearchHit(chunk=candidate.chunk, score=score)
            for candidate, score in ranked[:top_k]
        ]


def _chroma_metadata(chunk: dict[str, Any]) -> dict[str, str | int]:
    metadata: dict[str, str | int] = {}
    for key, value in chunk.items():
        if key == "text":
            continue
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
    return metadata


def build_vector_index(
    chunks_path: Path,
    collection_name: str = "bge_m3_semantic",
    model_name: str = EMBEDDING_MODEL,
    batch_size: int = 16,
) -> int:
    """Embed chunks with BGE-M3 and persist them in Chroma."""
    from chromadb import PersistentClient
    from sentence_transformers import SentenceTransformer

    chunks = load_chunks(chunks_path)
    model = SentenceTransformer(
        resolve_embedding_model(model_name),
        device=resolve_torch_device(),
    )
    model.max_seq_length = EMBEDDING_MAX_SEQ_LENGTH
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    client = PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        collection_name,
        metadata={"hnsw:space": "cosine", "embedding_model": model_name},
    )
    collection.upsert(
        ids=[chunk["chunk_id"] for chunk in chunks],
        documents=texts,
        metadatas=[_chroma_metadata(chunk) for chunk in chunks],
        embeddings=embeddings.tolist(),
    )
    return len(chunks)


class BGEVectorRetriever:
    """Chroma-backed BGE-M3 retriever for later evaluation stages."""

    def __init__(
        self,
        collection_name: str = "bge_m3_semantic",
        model_name: str = EMBEDDING_MODEL,
    ) -> None:
        from chromadb import PersistentClient
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            resolve_embedding_model(model_name),
            device=resolve_torch_device(),
        )
        self.model.max_seq_length = EMBEDDING_MAX_SEQ_LENGTH
        self.client = PersistentClient(path=str(CHROMA_DIR))
        self.collection = self.client.get_collection(collection_name)

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        query_embedding = self.model.encode(
            [query],
            normalize_embeddings=True,
        )[0]
        result = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[SearchHit] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for document, metadata, distance in zip(documents, metadatas, distances):
            chunk = dict(metadata or {})
            chunk["text"] = document
            hits.append(SearchHit(chunk=chunk, score=1.0 - float(distance)))
        return hits
