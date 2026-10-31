"""Answer generation with a local extractive fallback and a DeepSeek adapter."""

from __future__ import annotations

import re
from typing import Any

from src.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)
from src.retrieve import tokenize
from src.schemas import SearchHit


REFUSAL_TEXT = "文档中未找到足够依据，暂时无法回答这个问题。"
HEADING_ONLY_LINES = {
    "What is the policy?",
    "Why does eBay have this policy?",
    "Helpful links",
    "Frequently Asked Questions",
    "On this page",
}
SYSTEM_PROMPT = """你是跨境卖家合规问答助手。
只能使用提供的检索片段回答问题，不得使用片段以外的知识，也不得补造条件、数字或流程。
先直接回答结论，再完整覆盖问题涉及的所有适用条件、期限、阈值、材料、例外和步骤。
如果答案需要多个来源，请综合这些来源，不要只复述某一个片段。
每个事实性句子或列表项都必须标注对应引用，例如 [C1] 或 [C1][C2]；只能使用检索片段中实际存在的引用编号。
如果证据只能回答部分问题，明确说明可以确认的内容和无法确认的部分，不要猜测。
如果所有检索片段都不足以回答，只输出：文档中未找到足够依据，暂时无法回答这个问题。
不要输出与问题无关的背景介绍。"""


def _citation(chunk: dict[str, Any]) -> dict[str, Any]:
    page = chunk.get("page")
    if page is None:
        location = chunk.get("section_title") or "正文"
    elif chunk.get("kind") == "ppt":
        location = f"第 {page} 张幻灯片"
    else:
        location = f"第 {page} 页"
    return {
        "title": chunk.get("title", chunk.get("source", "")),
        "source": chunk.get("source", ""),
        "location": location,
        "url": chunk.get("url", ""),
        "chunk_id": chunk.get("chunk_id", ""),
    }


def _candidate_sentences(text: str) -> list[str]:
    candidates: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line in HEADING_ONLY_LINES:
            continue
        parts = re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+", line)
        candidates.extend(part.strip() for part in parts if len(part.strip()) >= 15)
    return candidates


def extractive_answer(
    question: str,
    hits: list[SearchHit],
    *,
    max_hits: int = 3,
    min_score: float = 0.5,
    enforce_term_coverage: bool = True,
    backend: str = "bm25",
) -> dict[str, Any]:
    """Build a grounded answer without calling an external model."""
    strong_hits = [hit for hit in hits if hit.score >= min_score][:max_hits]
    query_tokens = set(tokenize(question))
    combined_text = "\n".join(hit.chunk["text"] for hit in strong_hits)
    hit_tokens = set(tokenize(combined_text))
    matched_tokens = query_tokens.intersection(hit_tokens)
    query_years = set(re.findall(r"(?:19|20)\d{2}", question))
    if backend == "bge_m3" and strong_hits:
        top_text = strong_hits[0].chunk["text"]
        top_tokens = set(tokenize(top_text))
        top_years = set(re.findall(r"(?:19|20)\d{2}", top_text))
        coverage_ok = strong_hits[0].score >= 0.65 or len(
            query_tokens.intersection(top_tokens)
        ) >= 2
        if query_years and not query_years.issubset(top_years):
            coverage_ok = False
    else:
        hit_years = set(re.findall(r"(?:19|20)\d{2}", combined_text))
        coverage_ok = (
            len(matched_tokens) >= 2
            if len(query_tokens) > 1
            else bool(matched_tokens)
        )
        if query_years and not query_years.issubset(hit_years):
            coverage_ok = False
    requires_coverage = backend == "bge_m3" or enforce_term_coverage
    if not strong_hits or (requires_coverage and not coverage_ok):
        return {
            "answer": REFUSAL_TEXT,
            "citations": [],
            "mode": "extractive",
            "refused": True,
        }

    selected: list[tuple[str, int, dict[str, Any]]] = []
    seen_sentences: set[str] = set()
    for hit_index, hit in enumerate(strong_hits, 1):
        sentences = _candidate_sentences(hit.chunk["text"])
        ranked = sorted(
            sentences,
            key=lambda sentence: len(query_tokens.intersection(tokenize(sentence))),
            reverse=True,
        )
        added = 0
        for sentence in ranked:
            compact = re.sub(r"\s+", " ", sentence).strip()
            if compact in seen_sentences:
                continue
            if not query_tokens.intersection(tokenize(compact)) and added > 0:
                continue
            seen_sentences.add(compact)
            selected.append((compact, hit_index, hit.chunk))
            added += 1
            if added >= 2:
                break

    if not selected:
        text = re.sub(r"\s+", " ", strong_hits[0].chunk["text"]).strip()
        selected.append((text[:300], 1, strong_hits[0].chunk))

    lines = ["根据检索到的官方资料，可确认："]
    for sentence, citation_index, _chunk in selected:
        lines.append(f"- {sentence} [C{citation_index}]")
    lines.append("以上内容仅依据当前知识库片段，具体执行前请核对引用原文及最新政策。")

    citations: list[dict[str, Any]] = []
    for index, hit in enumerate(strong_hits, 1):
        citation = _citation(hit.chunk)
        citation["citation_id"] = f"C{index}"
        citation["score"] = round(hit.score, 4)
        citations.append(citation)
    return {
        "answer": "\n".join(lines),
        "citations": citations,
        "mode": "extractive",
        "refused": False,
    }


def build_context(hits: list[SearchHit]) -> str:
    blocks: list[str] = []
    for index, hit in enumerate(hits, 1):
        chunk = hit.chunk
        blocks.append(
            f"[C{index}]\n"
            f"标题：{chunk.get('title', '')}\n"
            f"来源：{chunk.get('source', '')}，"
            f"位置：{chunk.get('page_label', '')}\n"
            f"正文：{chunk.get('text', '')}"
        )
    return "\n\n".join(blocks)


def deepseek_answer(question: str, hits: list[SearchHit]) -> dict[str, Any]:
    """Generate an answer through the DeepSeek OpenAI-compatible API."""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not configured. Use --mode extractive "
            "or add the key to .env."
        )
    from openai import OpenAI

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        temperature=0,
        max_tokens=1200,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"问题：{question}\n\n检索片段：\n{build_context(hits)}",
            },
        ],
    )
    answer = (response.choices[0].message.content or "").strip()
    citations = []
    for index, hit in enumerate(hits, 1):
        citation = _citation(hit.chunk)
        citation["citation_id"] = f"C{index}"
        citation["score"] = round(hit.score, 4)
        citations.append(citation)
    usage = response.usage
    return {
        "answer": answer or REFUSAL_TEXT,
        "citations": citations if answer else [],
        "mode": "deepseek",
        "refused": REFUSAL_TEXT in answer and len(answer) <= len(REFUSAL_TEXT) + 20,
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        },
    }
