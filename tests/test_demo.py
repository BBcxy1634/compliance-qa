"""Tests for Gradio demo helpers."""

from app import CSS, build_demo
from src.demo import (
    DemoEngine,
    format_answer_html,
    format_citations_html,
    format_status_html,
    mode_hint_html,
)


def _result() -> dict:
    return {
        "answer": "不允许。<script>alert(1)</script> [C1]",
        "refused": False,
        "model": "deepseek-flash",
        "total_ms": 1234.0,
        "retrieval_ms": 120.0,
        "generation_ms": 1114.0,
        "citations": [
            {
                "citation_id": "C1",
                "title": "评论政策",
                "source": "amazon_reviews_policy.md",
                "location": "第 1 页",
                "url": "https://example.com/policy?a=1&b=2",
                "chunk_id": "chunk-1",
            },
            {
                "citation_id": "C2",
                "title": "无关候选",
                "source": "irrelevant.md",
                "location": "第 2 页",
                "url": "https://example.com/irrelevant",
                "chunk_id": "chunk-2",
            },
        ],
        "hits": [
            {
                "chunk_id": "chunk-1",
                "text": "来源 <原文>",
            }
        ],
    }


def test_answer_html_escapes_model_output() -> None:
    rendered = format_answer_html(_result()["answer"])
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_answer_html_renders_safe_bold_text() -> None:
    rendered = format_answer_html("**结论**：不允许。")
    assert "<strong>结论</strong>" in rendered


def test_citations_render_safe_link_and_snippet() -> None:
    rendered = format_citations_html(_result())
    assert "amazon_reviews_policy.md" in rendered
    assert "第 1 页" in rendered
    assert "https://example.com/policy?a=1&amp;b=2" in rendered
    assert "来源 &lt;原文&gt;" in rendered
    assert "无关候选" not in rendered


def test_status_and_mode_hint_identify_modes() -> None:
    status = format_status_html(_result(), "fast")
    assert "总耗时 1.23s" in status
    assert "1 条引用" in status
    assert "默认在线配置" in mode_hint_html("fast")
    assert "CPU 下单题可能超过 10 秒" in mode_hint_html("high")


def test_refusal_hides_citations_and_reports_zero() -> None:
    result = _result()
    result["refused"] = False
    result["answer"] = "文档中未找到足够依据，暂时无法回答这个问题。"
    rendered = format_citations_html(result)
    status = format_status_html(result, "fast")
    assert "amazon_reviews_policy.md" not in rendered
    assert "0 条引用" in status


def test_gradio_page_builds_without_loading_models() -> None:
    demo = build_demo(DemoEngine())
    assert demo is not None


def test_demo_keeps_stable_desktop_width_and_example_grid() -> None:
    assert "width: 100% !important;" in CSS
    assert "max-width: 1180px !important;" in CSS
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in CSS
