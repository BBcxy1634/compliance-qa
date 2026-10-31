# D5 B0 Baseline 结果

> 说明：本文记录的是抽取式诊断版本。后续已将 B0/B1 正式生成方式统一为 DeepSeek，正式结果见 `docs/b0_b1_deepseek_rerun.md`。

运行日期：2026-10-31  
状态：已固化  
人工复核：未执行，答案正确率采用 DeepSeek 辅助判题

## B0 定义

| 项目 | 配置 |
|---|---|
| 切分 | 固定 512 字符，无重叠 |
| Chunk 数量 | 334 |
| 检索 | BGE-M3 纯向量检索 |
| Top K | 5 |
| 混合检索 | 无 |
| 重排 | 无 |
| 生成方式 | 抽取式回答 |
| 评测集 | 冻结的 60 题，40 事实 / 10 多跳 / 10 拒答 |
| 答案判定 | DeepSeek 按关键事实辅助判题 |

固定切分改变了 chunk 边界，因此 B0 不能直接使用语义切分时生成的精确 chunk ID。本次比较口径为 `gold_match=unit`：先将 gold chunk 和检索结果映射到“来源 + 页面/章节”单元，再判断命中。这样 B0-B3 能在不同切分策略下进行同一层面的比较。

## 固化结果

| 指标 | 结果 |
|---|---:|
| Hit@5 | 1.0000 |
| Gold unit recall@5 | 0.9767 |
| 引用准确率 | 1.0000 |
| 引用覆盖率 | 0.9400 |
| 答案正确率（DeepSeek辅助判题） | 0.3400 |
| 拒答准确率 | 0.9000 |
| P50 延迟 | 203.78 ms |
| P95 延迟 | 231.18 ms |

分类结果：

| 类型 | 数量 | 正确 | 正确率 | 平均 gold unit recall@5 |
|---|---:|---:|---:|---:|
| 事实型 | 40 | 17 | 0.4250 | 1.0000 |
| 多跳型 | 10 | 0 | 0.0000 | 0.8833 |
| 拒答型 | 10 | 9 | 0.9000 | 不适用 |

## 结果解释

B0 的检索链路已经很强：50 道可答题全部在 Top 5 中命中至少一个正确来源单元，平均覆盖 97.67% 的 gold unit。引用准确率达到 1.0，说明当前引用选择没有指向错误来源。

主要瓶颈在回答层：

- 事实题正确率为 0.425，抽取式回答缺少明确结论，容易遗漏关键事实。
- 多跳题正确率为 0，当前抽取逻辑没有真正跨来源综合。
- 拒答准确率为 0.9，有 1 道拒答题未被正确拒绝。
- 有 3 道可答题被误拒答。

因此，B0 并不是最终效果，而是后续 B1-B3 的固定对照点。后续改动必须使用同一套 60 题，并保持指标口径一致。

## 产物

- `eval/configs/b0.yaml`：B0 实验配置。
- `eval/results/b0/summary.json`：完整配置、输入哈希和指标。
- `eval/results/b0/summary.csv`：可直接引用的指标表。
- `eval/results/b0/review.csv`：逐题答案和自动判题结果。
- `eval/results/baseline_table.csv`：由脚本生成的 B0-B3 汇总表，当前包含 B0-B2。
- `eval/results/baseline_table.json`：同一汇总表的结构化版本。
- `chroma_db/`：本地 collection `bge_m3_b0`，334 条向量，不提交 Git。

## 复现命令

生成固定切分：

```powershell
python -m src.ingest --strategy fixed --max-chars 512 --output data/processed/chunks_b0.jsonl
```

建立 B0 向量库：

```powershell
python -m src.embed --chunks data/processed/chunks_b0.jsonl --collection bge_m3_b0 --batch-size 8
```

运行 B0：

```powershell
python evaluate.py --config eval/configs/b0.yaml --chunks data/processed/chunks_b0.jsonl
```

生成 baseline 汇总表：

```powershell
python scripts/build_baseline_table.py --run "B0=eval/results/b0/summary.json"
```

后续 B1-B3 完成后，重复传入多个 `--run` 参数即可更新同一张表。
