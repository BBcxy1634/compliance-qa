# Changelog

All notable project changes are documented in this file.

## [1.0.0] - 2026-11-01

### Added

- 可追溯的跨境合规 RAG 问答链路。
- BGE-M3 语义向量检索和 BM25 混合检索。
- B3 可选高质量模式与 `bge-reranker-v2-m3` 重排。
- DeepSeek 依据上下文生成、引用过滤和无依据拒答。
- Gradio 单页 Demo，支持 Fast/B3 模式和移动端布局。
- 60 题冻结评测集：40 事实、10 多跳、10 拒答。
- B0-B3 消融实验、Badcase 分析、延迟和成本压测。
- 数据准备、评测、压测、复现和环境检查脚本。
- 官方来源清单、PPT、评测报告和 Demo 截图。

### Verified

- B1 Fast 完整 60 题答案正确率 0.92，拒答准确率 1.00。
- B3 完整 60 题答案正确率 0.94，多跳题正确率 0.90。
- 自动化测试 33 项通过。
- Python 3.13、271 条语义向量和本地数据检查通过。

### Notes

- 默认使用 B1 Fast；B3 是可选高质量实验，不是默认部署配置。
- B1 Fast 的 CPU P95 为 3.31 秒，尚未完全达到 3 秒目标。
- 自动判题结果尚未完成独立人工复核。
- MIT License 只覆盖代码和原创文档，数据材料适用单独说明。
