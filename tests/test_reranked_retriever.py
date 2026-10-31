"""Tests for the Top 8 to Top 5 reranking stage."""

from src.retrieve import RerankedRetriever
from src.schemas import SearchHit


class FakeBaseRetriever:
    def search(self, query: str, top_k: int = 5) -> list[SearchHit]:
        return [
            SearchHit(chunk={"chunk_id": str(index), "text": f"doc {index}"}, score=0.0)
            for index in range(top_k)
        ]


class FakeReranker:
    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(len(texts) - index) for index in range(len(texts))]


def test_reranker_reorders_eight_candidates_to_top_five() -> None:
    retriever = RerankedRetriever(
        FakeBaseRetriever(),
        FakeReranker(),
        initial_k=8,
    )
    hits = retriever.search("query", top_k=5)
    assert [hit.chunk["chunk_id"] for hit in hits] == ["0", "1", "2", "3", "4"]
    assert len(hits) == 5


def test_reranker_can_recall_initial_eight() -> None:
    base = FakeBaseRetriever()
    candidates = base.search("query", top_k=8)
    assert [hit.chunk["chunk_id"] for hit in candidates] == [
        str(index) for index in range(8)
    ]
