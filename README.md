# 跨境卖家合规问答助手

一个可追溯的 RAG 项目：从 7 份自建 PPT、Amazon/eBay 官方政策和海关监管文件中检索依据，生成带来源和页码的合规答案；证据不足时明确拒答。

## 系统架构

```mermaid
flowchart LR
    A[PPT / 官方网页 / 监管 PDF] --> B[解析、清洗、语义切分]
    B --> C[271 个语义 chunk]
    C --> D[BGE-M3 向量库]
    C --> E[BM25 索引]
    Q[用户问题] --> D
    Q --> E
    D --> R[向量 Top 5]
    E --> H[RRF 混合检索]
    R --> H
    H --> K[B3 可选：Top 8 重排]
    K --> G[DeepSeek 生成]
    R --> G
    G --> O[答案 + 文件名 + 页码/章节]
    G --> N[证据不足：拒答]
```

默认系统使用 **B1 Fast**：语义切分、BGE-M3 纯向量 Top 5、无重排、DeepSeek 非思考模式、输出上限 600 token。

B3 是可选高质量模式：混合检索 Top 8 后使用 `BAAI/bge-reranker-v2-m3` 精排到 Top 5，再交给 DeepSeek。它提升多跳题表现，但 CPU 延迟较高。

## 评测指标

评测集为冻结的 60 题：40 事实、10 多跳、10 拒答。B0-B3 均使用相同的 DeepSeek 生成 Prompt 和自动判题口径。

| 版本 | 切分 | 检索 | 重排 | Hit@5 | 引用准确率 | 答案正确率 | 事实题 | 多跳题 | 拒答准确率 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| B0 | 固定 512 | 向量 Top 5 | 无 | 1.00 | 1.00 | 0.82 | 0.85 | 0.70 | 1.00 |
| B1 | 语义切分 | 向量 Top 5 | 无 | 1.00 | 1.00 | 0.90 | 0.925 | 0.80 | 1.00 |
| B2 | 语义切分 | 混合 RRF Top 5 | 无 | 1.00 | 1.00 | 0.90 | 0.95 | 0.70 | 1.00 |
| B3 | 语义切分 | 混合 RRF Top 8 | BGE reranker | 1.00 | 1.00 | 0.94 | 0.95 | 0.90 | 1.00 |

生产候选 B1 Fast 的 60 题答案正确率为 0.92，100 次压测平均延迟 1.92 秒、平均成本约 ¥0.0010，但 P95 为 3.31 秒，尚未完全满足 3 秒目标。

指标由 [evaluate.py](evaluate.py)、[src/evaluate.py](src/evaluate.py) 和 [bench.py](bench.py) 生成。自动判题结果尚未经过人工复核，最终报告需保留这一限制。

## 三个典型 Badcase

| 题目 | 类型 | 现象 | 修法 |
|---|---|---|---|
| q023 | 生成不完整 | 找到 eBay 评价政策，但只回答仇恨内容可移除，漏掉亵渎/露骨内容。 | 并列政策项做关键事实后检，缺失时触发补充生成。 |
| q032 | 召回噪声 | 找到增加 29 项的 chunk，但删除项和税则调整所在的 c02 被无关海关页面挤出 Top 5。 | 同 source 相邻 chunk 扩展，并限制无关来源占用。 |
| q049 | 召回噪声 | 找到商品描述语言政策，但 search manipulation 官方政策缺失，混入运营 PPT 和成人商品政策。 | 多意图拆分检索，平台政策题优先官方来源。 |

完整 22 个失败实例和修法见 [D10 Badcase 分析](docs/d10_badcase_analysis.md)。

## 快速开始

先安装 Python 3.10+，并把 `.env.example` 复制为 `.env`，填写 DeepSeek Key。之后在项目根目录执行三条命令：

```powershell
python -m pip install -r requirements.txt
python scripts/bootstrap.py
python -m src.rag "eBay 是否允许销售假冒商品？" --mode deepseek --no-thinking --max-tokens 600
```

`bootstrap.py` 会下载缺失的官方语料，执行解析和语义切分，建立默认 B1 向量库，并校验来源与评测集。BGE-M3 首次下载约 4.3 GB，不计入“10 分钟复现”时间。

完整复现 B0-B3、下载 reranker 和生成冻结指标：

```powershell
python scripts/bootstrap.py --full --with-reranker
python evaluate.py --config eval/configs/b1_fast.yaml --chunks data/processed/chunks.jsonl
python evaluate.py --config eval/configs/b3_deepseek.yaml --chunks data/processed/chunks.jsonl
```

验证安装：

```powershell
python scripts/check_environment.py --require-data
python -m pytest -q
```

## 语料来源与版权

- 7 份自建跨境业务 PPT 用于背景知识与操作流程。
- 12 个 Amazon/eBay 官方政策页用于平台规则回答。
- 5 份海关、财政、商务和税务公开文件用于监管问题。

官方正文、PDF 和 chunk 仅用于本地实验，版权归原发布方，不提交到公开 Git 仓库。所有来源 URL、抓取日期和哈希记录在 [sources.jsonl](data/raw/sources.jsonl)。详细来源见 [官方来源清单](docs/official_sources.md)。

## 默认模式与高质量模式

| 模式 | 配置 | 适用场景 | 质量 | 延迟 |
|---|---|---|---:|---:|
| B1 Fast | 语义切分 + 向量 Top 5 + 非思考生成 | 默认在线问答 | 0.92 | P95 3.31 秒 |
| B3 | 混合检索 Top 8 + BGE reranker | 多跳、低置信、高风险问题 | 0.94 | CPU P95 约 12 秒 |

B3 **不是最终默认配置**，而是项目的质量上限实验和可选高质量模式。

## GPU 模式

当前代码会自动检测 CUDA：

```dotenv
TORCH_DEVICE=auto
```

有可用 GPU 时自动使用 CUDA，否则回退 CPU。如需强制检查 CUDA：

```dotenv
TORCH_DEVICE=cuda
```

要求：

- NVIDIA GPU，建议至少 8 GB 显存，12 GB 更稳妥。
- 安装与驱动匹配的 CUDA 版 PyTorch，不能用当前 CPU-only wheel。
- 验证 `python -c "import torch; print(torch.cuda.is_available())"` 返回 `True`。

CPU 上 B3 的 P95 约为 12.3 秒，其中重排约 8.7 秒。GPU 上预计重排 P95 可降至约 0.3 至 1 秒，但这是容量估算，必须用目标显卡重新运行 100 次 benchmark。当前 DeepSeek 生成仍可能使 P95 保持在 4 秒左右。

详细复现与 GPU 说明见 [D12 复现指南](docs/d12_reproducibility.md)。

## 项目结构

```text
compliance-qa/
├─ data/raw/                 # PPT、官方网页、PDF 和来源清单
├─ data/processed/           # 语义/B0 chunks
├─ eval/
│  ├─ questions.jsonl        # 冻结的 60 题
│  ├─ configs/               # B0-B3、B1 Fast
│  ├─ results/               # 评测结果和 badcase
│  └─ bench/                 # 100 次延迟与成本结果
├─ src/                      # ingest / embed / retrieve / generate
├─ scripts/                  # 抓取、校验、复现和报告脚本
├─ evaluate.py               # 60 题评测入口
├─ bench.py                  # 100 次成本与延迟压测
└─ report.md                 # 一页评测报告
```

## 当前限制

- B1 Fast P95 为 3.31 秒，尚未完全达到 3 秒目标。
- B3 CPU 延迟过高，只适合按需启用。
- q032、q049 仍存在精确 chunk 覆盖不足。
- 自动判题结果尚未完成人工复核。
- Gradio Demo 将在 D13 接入。
