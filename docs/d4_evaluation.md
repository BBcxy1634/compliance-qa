# D4 评测流程与首轮结果

## D4 完成内容

D4 已实现一键评测脚本，覆盖：

- 读取冻结的 60 条评测集。
- 对每题执行 BGE-M3 或 BM25 检索。
- 生成抽取式或 DeepSeek 回答。
- 计算 Hit@5、引用准确率、答案正确率、拒答准确率。
- 记录逐题检索片段、引用、延迟和 token 使用。
- 使用 DeepSeek 对答案正确率做辅助判题，并缓存判题结果。
- 生成人工复核 CSV，允许人工结论覆盖自动判题。
- 输出 CSV、JSON 和逐题结果。

## 运行方式

默认配置：

```text
backend = bge_m3
mode = extractive
judge = deepseek
top_k = 5
```

运行完整评测：

```powershell
Set-Location 'D:\大学学习\跨境卖家合规问答助手项目\compliance-qa'
.\.venv\Scripts\Activate.ps1
python evaluate.py
```

也可以直接运行模块：

```powershell
python -m src.evaluate
```

BM25 对照：

```powershell
python evaluate.py --backend bm25 --mode extractive --judge deepseek --run-name bm25_extractive
```

DeepSeek 回答生成：

```powershell
python evaluate.py --backend bge_m3 --mode deepseek --judge deepseek --run-name bge_deepseek
```

## 指标口径

- Hit@5：可答题的前 5 个检索结果中至少出现一个 gold chunk。
- Gold chunk recall@5：前 5 个结果覆盖全部 gold chunk 的平均比例。
- 引用准确率：有引用的可答题中，引用包含 gold chunk 的比例。
- 引用覆盖率：可答题中生成了非空引用的比例。
- 答案正确率：答案覆盖全部 key facts 且不存在实质冲突。
- 拒答准确率：10 道拒答题中正确拒答的比例。
- P50 / P95：单题检索到回答完成的时间，不含模型首次加载。

## 输出目录

每次运行创建 `eval/results/<run_name>/`：

| 文件 | 内容 |
|---|---|
| `summary.json` | 配置、时间、指标和分类统计 |
| `summary.csv` | 可直接放进报告的指标表 |
| `review.csv` | 50 道可答题的人工判题表 |
| `per_question.jsonl` | 完整逐题结果，本地保留 |

`eval/results/judge_cache.jsonl` 缓存 DeepSeek 判题结果，相同问题、标准答案和候选答案不会重复调用。

## 首轮试跑结果

运行配置：BGE-M3 检索、抽取式回答、DeepSeek 辅助判题、Top 5。

| 指标 | 结果 |
|---|---:|
| Hit@5 | 1.0000 |
| Gold chunk recall@5 | 0.9100 |
| 引用准确率 | 0.9783 |
| 引用覆盖率 | 0.9200 |
| 答案正确率（自动判题） | 0.3000 |
| 拒答准确率 | 1.0000 |
| P50 延迟 | 163.96 ms |
| P95 延迟 | 185.49 ms |

分类结果：

- 事实题正确率：0.3750
- 多跳题正确率：0.0000
- 拒答题准确率：1.0000
- 可答题误拒答：4 条
- 拒答题误回答：0 条

## 结果解释

检索能力明显好于回答能力。50 道可答题全部命中 gold chunk，说明当前切分、BGE-M3 和 Chroma 检索基本可用。答案正确率只有 0.30，主要原因是当前使用抽取式回答：

- 只拼接原文句子，不一定会先给出明确结论。
- 多跳题缺少跨来源综合。
- 有 4 道可答题被拒答门控错误拒绝。

因此这不是最终 B0 指标，而是 D4 的评测器试跑结果。D5 将使用统一配置正式测 B0，并在此基础上改进回答生成和拒答门控。

## 人工复核

打开：

```text
eval/results/d4_bge_extractive/review.csv
```

填写 `manual_correct` 列：

```text
true
false
```

可选填写 `manual_notes`。然后使用人工标签重新计算：

```powershell
python evaluate.py --run-name d4_bge_extractive_manual --labels eval/results/d4_bge_extractive/review.csv
```

人工标签存在时优先于 DeepSeek 自动判题，汇总中会记录 `correctness_sources`。
