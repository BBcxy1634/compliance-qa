"""Tests for text cleaning and chunking."""

from __future__ import annotations

from src.ingest import clean_text, split_semantic


def test_clean_text_removes_template_and_unsafe_advice() -> None:
    raw = "\n".join(
        [
            "正常政策内容",
            "好评返现券不应进入知识库",
            "制作人：陈星宇",
            "行业PPT模板http://www.1ppt.com/hangye/",
        ]
    )
    cleaned = clean_text(raw, kind="ppt", source_id="ppt_04_compliance")
    assert "正常政策内容" in cleaned
    assert "好评返现" not in cleaned
    assert "制作人" not in cleaned
    assert "1ppt.com" not in cleaned


def test_semantic_chunks_respect_maximum_size() -> None:
    text = "\n\n".join(
        [
            "第一段说明跨境商品准入要求。" * 10,
            "第二段说明平台账户健康要求。" * 10,
            "第三段说明申报和退运要求。" * 10,
        ]
    )
    chunks = split_semantic(text, max_chars=120, overlap=24)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 120 for chunk in chunks)


def test_semantic_chunks_add_overlap() -> None:
    text = "甲" * 70 + "。" + "乙" * 70 + "。" + "丙" * 70 + "。"
    chunks = split_semantic(text, max_chars=100, overlap=20)
    assert len(chunks) >= 2
    assert len(set(chunks)) == len(chunks)
