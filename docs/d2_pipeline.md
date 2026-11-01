# D2 文档解析与最小 RAG 流程

## 完成范围

D2 已实现从原始文档到最小问答的完整本地流程：

```text
原始 PPT / 网页正文 / PDF
        ↓
解析、清洗、过滤模板内容
        ↓
语义切分与固定切分
        ↓
BGE-M3 向量化并写入 Chroma
        ↓
BGE-M3 语义检索或 BM25 关键词检索
        ↓
抽取式回答或 DeepSeek 生成
        ↓
答案 + 文件 + 页码/章节引用
```

## 当前产物

| 产物 | 路径 | 数量或说明 |
|---|---|---|
| 语义 chunk | `data/processed/chunks.jsonl` | 271 条 |
| B0 固定切分 chunk | `data/processed/chunks_b0.jsonl` | 334 条 |
| 语义切分报告 | `data/processed/ingest_report_semantic.json` | 含数量、长度和哈希 |
| 固定切分报告 | `data/processed/ingest_report_fixed.json` | 含数量、长度和哈希 |
| Chroma 向量库 | `chroma_db/` | collection `bge_m3_semantic`，271 条 |
| BGE-M3 模型缓存 | `.cache/huggingface/` | 约 4.27 GB |

语义 chunk 平均约 512 字符，最大 800 字符；固定切分最大 512 字符。

## 代码模块

| 文件 | 作用 |
|---|---|
| `src/config.py` | 路径、模型、API 和离线缓存配置 |
| `src/schemas.py` | 文档单元、chunk 和检索结果数据结构 |
| `src/ingest.py` | PPT、Markdown、PDF 解析，清洗和切分 |
| `src/embed.py` | BGE-M3 向量化与 Chroma 入库命令 |
| `src/retrieve.py` | BM25 和 BGE-M3/Chroma 检索 |
| `src/generate.py` | 抽取式回答和 DeepSeek 回答适配器 |
| `src/rag.py` | 单问题与交互式问答入口 |

## 清洗规则

- 跳过 PPT 封面、目录页、章节分隔页和致谢页。
- 过滤 `第一PPT`、模板网址、制作人、汇报人和占位公司名称。
- 排除 `ppt_04_compliance` 中“好评返现券”相关段落。
- eBay 页面在 “Was this article helpful” 后截断，避免相关文章串入正文。
- PDF 按页解析，网页按标题和段落切分。
- 每个 chunk 保存来源、标题、页码或章节、URL、语言、权威级别和稳定 ID。

## 运行命令

激活环境：

在克隆后的项目根目录执行：

```powershell
.\.venv\Scripts\Activate.ps1
```

生成语义切分：

```powershell
python -m src.ingest --strategy semantic --output data/processed/chunks.jsonl
```

生成 B0 固定切分：

```powershell
python -m src.ingest --strategy fixed --max-chars 512 --output data/processed/chunks_b0.jsonl
```

建立 BGE-M3 向量库：

```powershell
python -m src.embed --chunks data/processed/chunks.jsonl --collection bge_m3_semantic --batch-size 8
```

单问题语义问答：

```powershell
python -m src.rag "亚马逊是否允许卖家通过返现换取好评？" --backend bge_m3 --mode extractive
```

BM25 对照：

```powershell
python -m src.rag "Can I sell counterfeit products on eBay?" --backend bm25 --mode extractive
```

交互问答：

```powershell
python -m src.rag --backend bge_m3 --mode extractive
```

## 实际验证

### Amazon 评论政策

问题：亚马逊是否允许卖家通过返现换取好评？

结果：正确检索到 `amazon_reviews_policy.md`，返回“不得通过返现换取评论”的原文，并生成 `[C1]` 引用。

### eBay 知识产权政策

问题：Can I sell counterfeit products on eBay？

结果：正确检索到 `ebay_intellectual_property_policy.md`，返回 counterfeit、replica 和 unauthorized copy 均不被允许。

### 跨语言检索

问题：eBay 是否允许销售假冒商品？

结果：BGE-M3 用中文问题命中英文 eBay 政策，Top 1 相似度约 0.73。

### 拒答

问题：欧盟包装法在 2026 年有什么新要求？

结果：返回“文档中未找到足够依据，暂时无法回答这个问题”，不生成引用。

## 性能说明

- BGE-M3 在本机 CPU 上首次索引 271 个 chunk 约需 4 分 24 秒。
- 模型加载约 30 秒，属于冷启动，不计入单次查询延迟。
- 已完成索引后，BGE-M3 查询和 Chroma 检索约数百毫秒。
- BM25 查询约 1 至 3 毫秒，但跨语言和同义表达能力弱于 BGE-M3。

## 当前限制

- 抽取式回答直接拼接原文句子，表达不如 DeepSeek 自然。
- 本次没有配置 DeepSeek API Key，因此只验证了本地抽取式模式。
- 图片中的文字尚未 OCR，Amazon 和 eBay 图片内信息可能无法召回。
- 执行 `pip check` 和 10 个自动测试均通过。
- 官方原文、chunk 和向量库只保存在本地，不提交到公开 Git 仓库。
