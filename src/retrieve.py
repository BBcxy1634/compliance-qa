"""Lexical retrieval and an optional BGE-M3 plus Chroma vector backend."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jieba
from rank_bm25 import BM25Okapi

from src.config import (
    CHROMA_DIR,
    EMBEDDING_MAX_SEQ_LENGTH,
    EMBEDDING_MODEL,
    resolve_embedding_model,
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
    model = SentenceTransformer(resolve_embedding_model(model_name), device="cpu")
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

        self.model = SentenceTransformer(resolve_embedding_model(model_name), device="cpu")
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
