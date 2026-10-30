# D3 评测集说明

## 版本状态

当前版本为 `v1.0-draft`，生成日期 2026-10-31。全部 60 条记录的 `review_status` 均为 `pending_review`，需要人工检查后才能冻结。

评测集文件：`eval/questions.jsonl`

## 题目分布

| 类型 | 数量 | 行为 |
|---|---:|---|
| 事实型 | 40 | 单个文档内可找到答案 |
| 多跳型 | 10 | 需要跨 2 至 3 个文档综合 |
| 拒答型 | 10 | 知识库没有足够依据，应明确拒答 |

语言分布：中文 44 条，英文 16 条。英文题主要用于验证中文界面下的跨语言语义检索能力。

## 数据字段

每条记录包含：

- `id`：从 `q001` 到 `q060` 的固定编号。
- `type`：`fact`、`multi_hop` 或 `refusal`。
- `question`：用户问题。
- `gold_answer`：人工标准答案。
- `key_facts`：判定答案正确率时必须覆盖的关键事实。
- `gold_chunks`：支持答案的 chunk ID。
- `gold_evidence`：chunk ID 与原文精确摘录。
- `lang`：`zh` 或 `en`。
- `expected_behavior`：`answer` 或 `refuse`。
- `review_status`：当前为 `pending_review`。
- `created_at`：创建日期。

## 覆盖情况

- Amazon 官方政策事实：评论、公平行事、受限商品、申诉和消费者告知法案。
- eBay 官方政策事实：知识产权、搜索操纵、商品描述、冒犯性材料、成人商品和评价政策。
- 监管文件事实：出口退运税收、海外仓退税、海关出口监管、进口商品清单和零售进口监管。
- 自建 PPT 事实：基础概念、选品、ERP、跨境支付和信用评分。
- 多跳题覆盖 Amazon、eBay、海关与税务、商品清单与监管流程、PPT 与官方政策之间的组合。
- 拒答题覆盖欧盟包装法、CBAM、英国VAT、UN38.3、平台未来费率、加州65等当前知识库外主题。

## 检索烟测

使用当前 `bge_m3_semantic` Chroma collection 进行 Top 5 检索烟测：

- 50 道可答题均至少命中一个 gold chunk。
- 10 道拒答题均没有出现相似度达到 0.65 的高置信误命中。
- 烟测只用于发现坏题，不作为正式 Hit@5。正式指标在 D4 评测脚本中计算。

## 人工复核步骤

1. 打开 `eval/questions.jsonl`，按 `q001` 至 `q060` 顺序检查。
2. 对照 `gold_evidence`，确认引文确实存在于指定 chunk。
3. 检查 `gold_answer` 是否完整覆盖 `key_facts`。
4. 多跳题检查是否确实需要至少两个不同来源。
5. 拒答题检查知识库中是否没有任何 chunk 能直接回答。
6. 修改完成后把 `review_status` 从 `pending_review` 改为 `approved`。
7. 全部复核完成后冻结版本，并记录冻结日期。

## 自动校验

```powershell
python scripts/validate_eval.py
python -m pytest -q
```

结构校验会检查：

- 总数是否为 60。
- 类型分布是否为 40/10/10。
- ID 是否连续且唯一。
- 题目是否重复。
- gold chunk 是否存在。
- 证据引文是否为对应 chunk 的精确子串。
- 事实题是否只使用一个来源。
- 多跳题是否至少使用两个不同来源。
- 拒答题是否没有 gold chunk。
