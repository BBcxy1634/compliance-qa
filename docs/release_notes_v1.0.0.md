# v1.0.0 - 跨境卖家合规问答助手

这是项目首个正式版本，提供一条从多来源资料处理到可追溯问答的完整 RAG 链路。

## 主要功能

- BGE-M3 语义检索、BM25 混合检索和 BGE reranker 精排。
- DeepSeek 上下文生成、正文引用过滤和无依据拒答。
- 默认 B1 Fast 与可选 B3 高质量模式。
- Gradio 单页 Demo，支持桌面端和移动端。
- 60 题冻结评测集及 B0-B3 消融实验。
- 100 次延迟与成本压测、Badcase 分析和 GPU 说明。
- 一键数据准备、环境检查、评测和复现脚本。

## 核心结果

- B1 Fast：60 题答案正确率 0.92，拒答准确率 1.00。
- B3：60 题答案正确率 0.94，多跳题正确率 0.90。
- B1 Fast：平均延迟 1.92 秒，P95 3.31 秒，平均成本约人民币 0.0010 元/次。
- 自动化测试：33 项通过。

## 使用说明

安装 Python 3.12+，复制 `.env.example` 为 `.env` 并配置 DeepSeek API Key，然后执行：

```powershell
python -m pip install -r requirements.txt
python scripts/bootstrap.py
.\.venv\Scripts\python.exe app.py --port 7860
```

完整步骤见仓库中的 `README.md` 和 `docs/d15_final_delivery.md`。

## 注意事项

- B1 Fast 是默认模式；B3 是可选高质量模式，不是最终默认配置。
- B1 Fast 的 P95 尚未完全达到 3 秒目标。
- 自动判题结果尚未完成独立人工复核。
- 代码和原创文档采用 MIT License；数据材料适用 `NOTICE.md`。
