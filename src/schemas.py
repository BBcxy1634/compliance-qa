"""Typed records shared by ingestion, retrieval and generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExtractedUnit:
    source_id: str
    source: str
    title: str
    kind: str
    lang: str
    page: int | None
    page_label: str
    section_title: str
    text: str
    url: str
    updated_at: str
    authority: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    source: str
    title: str
    kind: str
    lang: str
    page: int | None
    page_label: str
    section_title: str
    text: str
    url: str
    updated_at: str
    authority: str
    strategy: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source": self.source,
            "title": self.title,
            "kind": self.kind,
            "lang": self.lang,
            "page": self.page,
            "page_label": self.page_label,
            "section_title": self.section_title,
            "text": self.text,
            "url": self.url,
            "updated_at": self.updated_at,
            "authority": self.authority,
            "strategy": self.strategy,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SearchHit:
    chunk: dict[str, Any]
    score: float
