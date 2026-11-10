# Changelog

All notable project changes are documented in this file.

## [2.0.0] - 2026-11-10

Status: release candidate prepared; Git tag and GitHub Release are not created.

### Added

- FastAPI synchronous answer and SSE streaming endpoints.
- Controlled LangGraph routing with deterministic high-risk, multi-hop, and
  simple-fact handling.
- Bounded search, snapshot inspection, version comparison, and validity-period
  tools.
- Optional process-local short-term conversation context.
- High-risk answers require two distinct cited sources.
- Local best-effort JSONL tracing with payload allowlists.
- 150-question agentic evaluation set with separate route, tool, evidence, and
  multi-step metrics.
- Dockerfile, Docker Compose API service, and named Trace/model-cache volumes.
- GitHub Actions deterministic test and synthetic evaluation smoke jobs.
- V2 architecture, deployment, failure-case, and release documentation.

### Preserved

- B1 Fast remains the default mode.
- B3 remains an optional quality mode.
- Refusals always return zero citations.
- Public citations are filtered to IDs present in the final answer.
- CLI and Gradio entry points remain available.
- Existing metric definitions are unchanged; agentic metrics remain separate.

### Verified

- 110 automated tests pass with local data and vector artifacts present.
- 102 deterministic tests are selected when data-dependent tests are excluded.
- The synthetic BM25/extractive evaluation smoke passes 3/3 questions without a
  DeepSeek key or network model call.
- GitHub Actions run `42826433942` passed both deterministic test and evaluation
  smoke jobs.
- The full 150-question B1 Fast DeepSeek evaluation completed with 150
  successful and 0 failed requests.
- Phase 6 evidence, routing, and repair changes raised answer correctness to
  0.8077, multi-hop correctness to 0.7833, route accuracy to 0.9933,
  evidence sufficiency accuracy to 0.9867, and multi-step completion to 0.75.
- The final run had 4 answerable false refusals, citation accuracy 1.0, and
  refusal accuracy 1.0.
- Python YAML parsing and packaging tests validate the Compose, Dockerfile,
  Docker context, workflow, and smoke fixture structure.

### Notes

- Docker was not executed in the current local environment.
- Independent human review has not been completed for the V2 question labels.
- The quality-oriented path increased answer P95 to 10.07 seconds; this
  tradeoff is documented.
- Existing benchmark latency and cost results are v1 reference measurements,
  not a new V2 paid benchmark.

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
