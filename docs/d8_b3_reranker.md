# D8 重排 B3 结果

运行日期：2026-10-31  
状态：已完成并固化  
人工复核：未执行，答案正确率采用 DeepSeek 辅助判题

## B3 定义

| 项目 | 配置 |
|---|---|
| 切分 | 与 B1/B2 相同的语义切分 |
| Chunk 数量 | 271 |
| 最大长度与重叠 | 800 字符，重叠 64 字符 |
| 初筛 | BGE-M3 向量 + BM25，RRF 融合 |
| 每路候选数 | 20 |
| RRF 参数 | k=60 |
| 重排输入 | 混合检索 Top 8 |
| 重排模型 | `BAAI/bge-reranker-v2-m3` |
| 重排输出 | Top 5 |
| 生成 | DeepSeek，与 B1/B2 相同 Prompt |
| 判题 | DeepSeek 按关键事实辅助判题 |
| 评测集 | 冻结的 60 题 |

B3 与 B2 只改变“是否重排”和 Top 5 前的候选处理。切分、DeepSeek 生成、判题和评测集保持一致。

## 重排原理

BGE-M3 是双塔式向量检索：问题和文档分别编码，再比较向量距离。它适合从大规模语料中快速召回候选，但问题和每个文档没有逐词交互。

CrossEncoder 重排器会把“问题 + 候选正文”一起送入模型，直接输出相关性分数。模型可以看到问题中的条件、数字和候选正文之间的对应关系，因此精排通常比向量相似度更准确。

本次流程：

```text
271 个 chunk
→ BGE-M3 向量与 BM25 各取 20 个候选
→ RRF 融合
→ 取混合检索 Top 8
→ bge-reranker-v2-m3 逐对打分
→ 按重排分数取 Top 5
→ DeepSeek 生成答案
```

## 正式结果

| 指标 | B2 | B3 | B3 - B2 |
|---|---:|---:|---:|
| Hit@5 | 1.0000 | 1.0000 | 0.0000 |
| Gold unit recall@5 | 0.9733 | 0.9767 | +0.0034 |
| 引用准确率 | 1.0000 | 1.0000 | 0.0000 |
| 引用覆盖率 | 1.0000 | 1.0000 | 0.0000 |
| 答案正确率 | 0.9000 | 0.9400 | +0.0400 |
| 拒答准确率 | 1.0000 | 1.0000 | 0.0000 |
| 可答题误拒答 | 1 | 0 | -1 |
| 拒答题误回答 | 0 | 0 | 0 |
| P50 延迟 | 1404.15 ms | 8487.70 ms | +7083.55 ms |
| P95 延迟 | 3606.73 ms | 11889.72 ms | +8282.99 ms |

分类结果：

| 类型 | B2 正确率 | B3 正确率 | 变化 |
|---|---:|---:|---:|
| 事实题 | 0.9500 | 0.9500 | 0.0000 |
| 多跳题 | 0.7000 | 0.9000 | +0.2000 |
| 拒答题 | 1.0000 | 1.0000 | 0.0000 |

## 结果解释

B3 的主要收益集中在多跳题：

- 多跳题从 7/10 提升到 9/10。
- 可答题误拒答从 1 条降到 0。
- Gold unit recall 从 0.9733 提升到 0.9767。
- 总体答案正确率从 0.90 提升到 0.94。

与 B2 相比只有两道题由错变对：

- q044 恢复了对 eBay 反馈政策和冒犯性材料政策的双来源覆盖。
- q048 同时保留了电池运输限制与平台受限商品政策的关键证据。

这两道都是多跳题，说明 CrossEncoder 能通过问题与正文的交互，把初筛中排名不高但真正相关的第二来源重新排进 Top 5。

事实题没有额外提升，说明 B2 的混合检索对单来源事实题已经足够；B3 的主要价值是处理跨来源问题。

## 性能代价

B3 的质量提升伴随明显延迟增加：

- P50 增加约 7.08 秒。
- P95 增加约 8.28 秒。
- 当前 P95 为 11.89 秒，明显高于 3 秒目标。

当前重排在 CPU 上对每题 8 个候选逐对推理，耗时代价很大。D11 需要通过缩短候选正文、降低候选数、模型量化、缓存或减少调用范围来控制成本。

如果最终部署环境没有 GPU，B3 不适合作为默认在线链路；更合理的方案是：

- 在线默认使用 B1 或 B2。
- 对多跳问题或低置信检索按需启用重排。
- 在报告中明确质量和延迟 trade-off。

## 产物

- `eval/configs/b3_deepseek.yaml`：B3 实验配置。
- `eval/results/b3_deepseek/summary.json`：B3 配置、输入哈希和指标。
- `eval/results/b3_deepseek/summary.csv`：B3 指标表。
- `eval/results/baseline_table.csv`：当前 B0-B3 对比表。
- `src/retrieve.py`：混合检索、CrossEncoder 重排和 Top K 处理实现。
- `.cache/huggingface/`：本地 BGE-M3 和 reranker 模型缓存，不提交 Git。

## 复现命令

```powershell
python evaluate.py `
  --config eval/configs/b3_deepseek.yaml `
  --chunks data/processed/chunks.jsonl
```

更新 B0-B3 对比表：

```powershell
python scripts/build_baseline_table.py `
  --run "B0=eval/results/b0_deepseek/summary.json" `
  --run "B1=eval/results/b1_deepseek/summary.json" `
  --run "B2=eval/results/b2_deepseek/summary.json" `
  --run "B3=eval/results/b3_deepseek/summary.json"
```
