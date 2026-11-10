"""Integration checks for the completed D2 artifacts."""

from __future__ import annotations

import json
from collections import Counter

import chromadb
import pytest

from src.config import CHROMA_DIR, DEFAULT_CHUNKS_PATH
from src.generate import REFUSAL_TEXT, extractive_answer
from src.retrieve import BM25Retriever


pytestmark = pytest.mark.data


def load_chunks() -> list[dict]:
    return [
        json.loads(line)
        for line in DEFAULT_CHUNKS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_semantic_chunk_count_and_metadata() -> None:
    chunks = load_chunks()
    counts = Counter(chunk["kind"] for chunk in chunks)
    assert 200 <= len(chunks) <= 300
    assert counts["ppt"] > 0
    assert counts["html"] > 0
    assert counts["pdf"] > 0
    assert len({chunk["chunk_id"] for chunk in chunks}) == len(chunks)
    assert all(chunk["source_id"] for chunk in chunks)
    assert all(chunk["page_label"] for chunk in chunks)
    assert all(chunk["strategy"] == "semantic" for chunk in chunks)


def test_unsafe_slide_advice_is_not_indexed() -> None:
    chunks = load_chunks()
    assert not any("好评返现" in chunk["text"] for chunk in chunks)


def test_bm25_retrieves_amazon_review_policy() -> None:
    retriever = BM25Retriever.from_jsonl(DEFAULT_CHUNKS_PATH)
    hits = retriever.search("亚马逊是否允许卖家通过返现换取好评？", top_k=5)
    assert hits
    assert hits[0].chunk["source_id"] == "amazon_reviews_policy"
    result = extractive_answer(
        "亚马逊是否允许卖家通过返现换取好评？",
        hits,
    )
    assert result["refused"] is False
    assert result["citations"]


def test_absence_question_is_refused() -> None:
    retriever = BM25Retriever.from_jsonl(DEFAULT_CHUNKS_PATH)
    hits = retriever.search("欧盟包装法在2026年有什么新要求？", top_k=5)
    result = extractive_answer(
        "欧盟包装法在2026年有什么新要求？",
        hits,
        backend="bm25",
    )
    assert result["refused"] is True
    assert result["answer"] == REFUSAL_TEXT


def test_chroma_collection_has_all_chunks() -> None:
    chunks = load_chunks()
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection("bge_m3_semantic")
    assert collection.count() == len(chunks)
