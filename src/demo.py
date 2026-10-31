"""Reusable logic for the Gradio compliance QA demo."""

from __future__ import annotations

import html
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.config import DEEPSEEK_API_KEY, DEFAULT_CHUNKS_PATH
from src.rag import answer_with_retriever, create_retriever


@dataclass(frozen=True)
class ModeConfig:
    key: str
    label: str
    backend: str
    collection: str
    thinking: bool
    max_tokens: int
    description: str


MODES = {
    "fast": ModeConfig(
        key="fast",
        label="Fast · 默认",
        backend="bge_m3",
        collection="bge_m3_semantic",
        thinking=False,
        max_tokens=600,
        description="BGE-M3 纯向量 Top 5 · 非思考生成",
    ),
    "high": ModeConfig(
        key="high",
        label="High Quality · B3",
        backend="rerank",
        collection="bge_m3_semantic",
        thinking=True,
        max_tokens=1200,
        description="混合检索 Top 8 · BGE 重排 Top 5 · CPU 环境较慢",
    ),
}
REFUSAL_PREFIX = "文档中未找到足够依据"


def is_refusal_result(result: dict[str, Any]) -> bool:
    return bool(result.get("refused")) or str(
        result.get("answer", "")
    ).strip().startswith(REFUSAL_PREFIX)


class DemoEngine:
    """Lazily load retrievers and keep them warm across browser requests."""

    def __init__(self, chunks_path: Path = DEFAULT_CHUNKS_PATH) -> None:
        self.chunks_path = chunks_path
        self._retrievers: dict[str, Any] = {}
        self._load_lock = threading.Lock()

    def get_retriever(self, mode_key: str) -> Any:
        if mode_key not in MODES:
            raise ValueError(f"Unknown demo mode: {mode_key}")
        with self._load_lock:
            if mode_key not in self._retrievers:
                config = MODES[mode_key]
                self._retrievers[mode_key] = create_retriever(
                    config.backend,
                    self.chunks_path,
                    config.collection,
                )
            return self._retrievers[mode_key]

    def warm_default(self) -> None:
        self.get_retriever("fast")

    def ask(self, question: str, mode_key: str) -> dict[str, Any]:
        question = (question or "").strip()
        if not question:
            raise ValueError("请输入问题。")
        if len(question) > 2000:
            raise ValueError("问题过长，请控制在 2000 字以内。")
        if not DEEPSEEK_API_KEY:
            raise RuntimeError(".env 中未配置 DEEPSEEK_API_KEY。")
        config = MODES.get(mode_key)
        if config is None:
            raise ValueError(f"Unknown demo mode: {mode_key}")
        retriever = self.get_retriever(mode_key)
        return answer_with_retriever(
            question,
            retriever=retriever,
            backend=config.backend,
            mode="deepseek",
            top_k=5,
            thinking=config.thinking,
            max_tokens=config.max_tokens,
        )


def format_answer_html(answer: str, refused: bool = False) -> str:
    safe = html.escape(answer or "")
    safe = re.sub(r"\n{3,}", "\n\n", safe)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
    safe = safe.replace("\n", "<br>")
    css_class = "answer-body refused" if refused else "answer-body"
    return f'<div class="{css_class}">{safe}</div>'


def format_citations_html(result: dict[str, Any]) -> str:
    refused = is_refusal_result(result)
    citations = [] if refused else result.get("citations", [])
    if not refused:
        used_ids = {
            f"C{number}"
            for number in re.findall(r"\[C(\d+)\]", result.get("answer", ""))
        }
        citations = [
            citation
            for citation in citations
            if citation.get("citation_id") in used_ids
        ]
    snippets = {
        hit.get("chunk_id"): hit.get("text", "")
        for hit in result.get("hits", [])
    }
    if not citations:
        return '<p class="citation-empty">本次回答没有可展示的引用。</p>'

    items: list[str] = ['<div class="citation-list">']
    for citation in citations:
        citation_id = html.escape(str(citation.get("citation_id", "")))
        title = html.escape(str(citation.get("title", "未命名来源")))
        source = html.escape(str(citation.get("source", "")))
        location = html.escape(str(citation.get("location", "")))
        url = str(citation.get("url", "")).strip()
        chunk_id = citation.get("chunk_id", "")
        snippet = html.escape(str(snippets.get(chunk_id, ""))[:420])
        link = (
            f'<a href="{html.escape(url)}" target="_blank" '
            'rel="noopener noreferrer">打开官方来源</a>'
            if url
            else '<span class="local-source">本地资料</span>'
        )
        details = (
            f"<details><summary>查看原文片段</summary><p>{snippet}</p></details>"
            if snippet
            else ""
        )
        items.append(
            '<article class="citation-item">'
            f'<div class="citation-id">{citation_id}</div>'
            '<div class="citation-content">'
            f'<div class="citation-title">{title}</div>'
            f'<div class="citation-meta">{source} · {location}</div>'
            f'<div class="citation-link">{link}</div>'
            f"{details}"
            "</div>"
            "</article>"
        )
    items.append("</div>")
    return "".join(items)


def format_status_html(result: dict[str, Any] | None, mode_key: str) -> str:
    config = MODES[mode_key]
    if result is None:
        return (
            f'<div class="status-line"><span>{config.label}</span>'
            f"<span>{config.description}</span></div>"
        )
    model = html.escape(str(result.get("model", "deepseek-flash")))
    total = float(result.get("total_ms", 0)) / 1000
    retrieval = float(result.get("retrieval_ms", 0)) / 1000
    generation = float(result.get("generation_ms", 0)) / 1000
    refused = is_refusal_result(result)
    citation_count = (
        0
        if refused
        else len(
            {
                f"C{number}"
                for number in re.findall(
                    r"\[C(\d+)\]",
                    result.get("answer", ""),
                )
            }
        )
    )
    outcome = "已拒答" if refused else "已回答"
    return (
        '<div class="status-line">'
        f"<span>{html.escape(config.label)}</span>"
        f"<span>{outcome}</span>"
        f"<span>总耗时 {total:.2f}s</span>"
        f"<span>检索 {retrieval:.2f}s</span>"
        f"<span>生成 {generation:.2f}s</span>"
        f"<span>{citation_count} 条引用</span>"
        f"<span>{model}</span>"
        "</div>"
    )


def format_error_html(message: str) -> str:
    return (
        '<div class="answer-body error">'
        f"{html.escape(message)}"
        "</div>"
    )


def mode_hint_html(mode_key: str) -> str:
    config = MODES.get(mode_key, MODES["fast"])
    warning = (
        '<span class="mode-warning">CPU 下单题可能超过 10 秒</span>'
        if config.key == "high"
        else '<span class="mode-ok">默认在线配置</span>'
    )
    return (
        '<div class="mode-hint">'
        f"<strong>{html.escape(config.label)}</strong>"
        f"<span>{html.escape(config.description)}</span>"
        f"{warning}"
        "</div>"
    )
