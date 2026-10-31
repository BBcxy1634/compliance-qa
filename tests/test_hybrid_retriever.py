"""Tests for reciprocal rank fusion."""

from src.retrieve import HybridRetriever
from src.schemas import SearchHit


class FakeRetriever:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        return [
            SearchHit(chunk={"chunk_id": chunk_id}, score=float(top_k - index))
            for index, chunk_id in enumerate(self.ids[:top_k])
        ]


def test_rrf_favors_items_ranked_by_both_routes() -> None:
    retriever = HybridRetriever(
        FakeRetriever(["a", "b", "c"]),
        FakeRetriever(["b", "c", "d"]),
        candidate_k=3,
        rrf_k=60,
    )
    hits = retriever.search("query", top_k=3)
    assert [hit.chunk["chunk_id"] for hit in hits] == ["b", "c", "a"]
    assert hits[0].score > hits[1].score


def test_rrf_handles_one_route_without_results() -> None:
    retriever = HybridRetriever(
        FakeRetriever(["a", "b"]),
        FakeRetriever([]),
        candidate_k=2,
        rrf_k=60,
    )
    hits = retriever.search("query", top_k=2)
    assert [hit.chunk["chunk_id"] for hit in hits] == ["a", "b"]
