"""Gradio single-page demo for the compliance RAG system."""

from __future__ import annotations

import argparse

import gradio as gr

from src.demo import (
    DemoEngine,
    format_answer_html,
    format_citations_html,
    format_error_html,
    format_status_html,
    is_refusal_result,
    mode_hint_html,
)


CSS = """
:root {
  --ink: #19221f;
  --muted: #5f6b66;
  --line: #d8dfdb;
  --surface: #f7f9f7;
  --paper: #ffffff;
  --accent: #176b57;
  --accent-soft: #e8f3ef;
  --warning: #8a5a13;
  --warning-soft: #fff6e6;
  --danger: #a43d37;
  --danger-soft: #fff1ef;
}

body {
  background: var(--surface);
}

.gradio-container {
  max-width: 1180px !important;
  margin: 0 auto !important;
  padding: 22px 24px 42px !important;
  color: var(--ink);
  font-family: "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
}

.app-header {
  border-top: 5px solid var(--accent);
  padding: 28px 0 22px;
  margin-bottom: 18px;
}

.app-kicker {
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.app-header h1 {
  margin: 8px 0 10px;
  color: var(--ink);
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.15;
}

.app-header p {
  max-width: 760px;
  margin: 0;
  color: var(--muted);
  font-size: 16px;
  line-height: 1.65;
}

.app-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.app-meta span {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--paper);
  padding: 5px 9px;
  color: var(--muted);
  font-size: 12px;
}

.query-panel {
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: 18px 0;
}

#question-box textarea {
  min-height: 112px !important;
  border-radius: 6px !important;
  font-size: 16px !important;
  line-height: 1.55 !important;
}

#ask-button {
  min-width: 132px;
  min-height: 44px;
  border-radius: 6px !important;
  font-weight: 700 !important;
}

#clear-button,
.example-button {
  min-height: 40px;
  border-radius: 6px !important;
}

.example-button {
  font-size: 13px !important;
}

.mode-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  padding: 11px 0;
  color: var(--muted);
  font-size: 13px;
}

.mode-hint strong {
  color: var(--ink);
}

.mode-ok,
.mode-warning {
  border-radius: 4px;
  padding: 3px 7px;
  font-weight: 600;
}

.mode-ok {
  color: var(--accent);
  background: var(--accent-soft);
}

.mode-warning {
  color: var(--warning);
  background: var(--warning-soft);
}

.status-line {
  display: flex;
  flex-wrap: wrap;
  gap: 7px 18px;
  border-left: 3px solid var(--accent);
  padding: 8px 0 8px 12px;
  color: var(--muted);
  font-size: 12px;
}

.answer-surface {
  min-height: 150px;
  padding: 20px 0 6px;
}

.answer-body {
  color: var(--ink);
  font-size: 16px;
  line-height: 1.8;
  overflow-wrap: anywhere;
}

.answer-body.refused,
.answer-body.error {
  border-left: 3px solid var(--danger);
  background: var(--danger-soft);
  padding: 14px 16px;
}

.answer-placeholder,
.citation-empty {
  color: var(--muted);
  line-height: 1.7;
}

.citation-section-title {
  margin: 22px 0 10px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: 17px;
  font-weight: 700;
}

.citation-list {
  display: grid;
  gap: 10px;
}

.citation-item {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--paper);
  padding: 14px;
}

.citation-id {
  display: flex;
  align-items: center;
  justify-content: center;
  align-self: start;
  width: 36px;
  height: 28px;
  border-radius: 4px;
  background: var(--accent);
  color: white;
  font-size: 12px;
  font-weight: 700;
}

.citation-title {
  font-weight: 700;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.citation-meta,
.citation-link,
.citation-item details {
  margin-top: 5px;
  color: var(--muted);
  font-size: 12px;
}

.citation-link a {
  color: var(--accent);
  font-weight: 600;
}

.citation-item details p {
  margin: 8px 0 0;
  color: var(--ink);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
}

.local-source {
  color: var(--muted);
}

.app-footer {
  margin-top: 28px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 640px) {
  .gradio-container {
    padding: 14px 14px 30px !important;
  }
  .app-header {
    padding-top: 20px;
  }
  .citation-item {
    grid-template-columns: 34px minmax(0, 1fr);
    padding: 11px;
  }
  #ask-button {
    width: 100%;
  }
}
"""


THEME = gr.themes.Base(
    primary_hue="emerald",
    neutral_hue="slate",
)


def build_demo(engine: DemoEngine) -> gr.Blocks:
    with gr.Blocks(
        title="跨境卖家合规问答助手",
    ) as demo:
        gr.HTML(
            """
            <header class="app-header">
              <div class="app-kicker">Compliance RAG</div>
              <h1>跨境卖家合规问答助手</h1>
              <p>每个答案附来源、页码与可展开的原文片段；知识库无依据时明确拒答。</p>
              <div class="app-meta">
                <span>默认 B1 Fast</span>
                <span>60 题答案正确率 92%</span>
                <span>官方来源可追溯</span>
              </div>
            </header>
            """
        )

        with gr.Column(elem_classes=["query-panel"]):
            mode = gr.Radio(
                choices=[
                    ("Fast · 默认", "fast"),
                    ("High Quality · B3", "high"),
                ],
                value="fast",
                label="问答模式",
                elem_id="mode-selector",
            )
            mode_hint = gr.HTML(mode_hint_html("fast"))
            question = gr.Textbox(
                label="问题",
                placeholder="例如：eBay 是否允许销售假冒商品？",
                lines=3,
                max_lines=6,
                elem_id="question-box",
            )
            with gr.Row():
                ask_button = gr.Button(
                    "查询",
                    variant="primary",
                    elem_id="ask-button",
                )
                clear_button = gr.Button(
                    "清空",
                    variant="secondary",
                    elem_id="clear-button",
                )

            gr.HTML('<div class="example-label">示例问题</div>')
            example_specs = [
                ("返现换好评", "亚马逊是否允许卖家通过返现换取评论？", "fast"),
                ("eBay 假冒商品", "eBay 是否允许销售假冒商品？", "fast"),
                ("包装法 2026", "欧盟包装法在2026年有什么新要求？", "fast"),
                (
                    "B3 多跳示例",
                    (
                        "An eBay listing offers counterfeit goods and gives "
                        "an inaccurate description. Which two policy areas "
                        "are violated?"
                    ),
                    "high",
                ),
            ]
            with gr.Row():
                for label, value, example_mode in example_specs:
                    button = gr.Button(
                        label,
                        variant="secondary",
                        elem_classes=["example-button"],
                    )
                    button.click(
                        fn=lambda value=value, example_mode=example_mode: (
                            value,
                            example_mode,
                            mode_hint_html(example_mode),
                        ),
                        outputs=[question, mode, mode_hint],
                    )

        status = gr.HTML(format_status_html(None, "fast"))
        answer = gr.HTML(
            '<div class="answer-surface"><p class="answer-placeholder">'
            "输入问题后开始检索。</p></div>",
            elem_classes=["answer-surface"],
        )
        gr.HTML('<div class="citation-section-title">引用与原文</div>')
        citations = gr.HTML(
            '<p class="citation-empty">回答后将在此展示引用。</p>'
        )

        def ask(question_value: str, mode_value: str):
            try:
                result = engine.ask(question_value, mode_value)
            except Exception as exc:
                return (
                    format_error_html(str(exc)),
                    format_status_html(None, mode_value),
                    format_citations_html({}),
                )
            return (
                format_answer_html(
                    result.get("answer", ""),
                    refused=is_refusal_result(result),
                ),
                format_status_html(result, mode_value),
                format_citations_html(result),
            )

        ask_button.click(
            fn=ask,
            inputs=[question, mode],
            outputs=[answer, status, citations],
            show_progress="full",
        )
        question.submit(
            fn=ask,
            inputs=[question, mode],
            outputs=[answer, status, citations],
            show_progress="full",
        )
        clear_button.click(
            fn=lambda mode_value: (
                "",
                '<div class="answer-surface"><p class="answer-placeholder">'
                "输入问题后开始检索。</p></div>",
                format_status_html(None, mode_value),
                '<p class="citation-empty">回答后将在此展示引用。</p>',
            ),
            inputs=[mode],
            outputs=[question, answer, status, citations],
        )
        mode.change(
            fn=mode_hint_html,
            inputs=[mode],
            outputs=[mode_hint],
        )

        gr.HTML(
            '<footer class="app-footer">'
            "结果供合规工作参考，不构成法律意见。"
            "</footer>"
        )
    return demo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-warmup", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = DemoEngine()
    if not args.no_warmup:
        engine.warm_default()
    demo = build_demo(engine)
    demo.queue(default_concurrency_limit=1).launch(
        server_name=args.host,
        server_port=args.port,
        show_error=False,
        css=CSS,
        theme=THEME,
    )


if __name__ == "__main__":
    main()
