# D1 语料收集计划

## 已就绪资料

7 份自建 PPT 已复制并登记在 `data/raw/sources.jsonl`。这些资料属于二级权威来源，用于解释业务流程和基础概念。

## 官方平台政策页计划

目标收集 12 个官方页面，最终数量保持在 10 至 15 个。

| source_id | 平台 | 主题 | 状态 |
|---|---|---|---|
| amazon_product_compliance | Amazon | 商品合规要求 | 待收集 |
| amazon_restricted_products | Amazon | 禁售和限制销售商品 | 待收集 |
| amazon_batteries | Amazon | 电池和危险品要求 | 待收集 |
| amazon_ip_policy | Amazon | 知识产权政策 | 待收集 |
| amazon_account_health | Amazon | 账户健康 | 待收集 |
| amazon_appeal | Amazon | 停用与申诉流程 | 待收集 |
| amazon_seller_code | Amazon | 卖家行为准则 | 待收集 |
| ebay_restricted_items | eBay | 限制和禁售商品 | 待收集 |
| ebay_vero | eBay | 知识产权和 VeRO | 待收集 |
| ebay_seller_protection | eBay | 卖家保护 | 待收集 |
| ebay_international_shipping | eBay | 国际物流和跨境销售 | 待收集 |
| ebay_account_restrictions | eBay | 账户限制与申诉 | 待收集 |

收集时必须保存页面正文、官方 URL、发布方和访问日期。不得用搜索摘要、第三方解读或截图代替官方正文。

## 监管文件计划

目标收集 3 至 5 份海关总署、商务部等官方公开文件。

| source_id | 文件主题 | 计划来源 | 状态 |
|---|---|---|---|
| customs_retail_supervision | 跨境电商零售进出口监管 | 海关总署 | 待收集 |
| customs_export_return | 跨境电商出口退运 | 海关总署 | 待收集 |
| mofcom_b2b_export | 跨境电商 B2B 出口政策 | 商务部 | 待收集 |
| customs_tax_policy | 跨境电商税费政策 | 海关总署或财政部 | 待收集 |
| customs_restricted_goods | 禁止或限制进出境商品 | 海关总署 | 待收集 |

## 拒答语料边界

“欧盟包装法 2026 年新要求”是固定拒答场景。D1 至 D3 收集语料时不得加入能够直接回答该问题的政策文件。若后续业务范围扩展并加入对应资料，必须同时修改评测集和项目范围说明。

## D1 验收

- `data/raw/ppt` 中存在 7 份核心 PPT，文件名与 `source_id` 一致。
- 每份 PPT 的 SHA256、页数、更新时间和原始名称均已登记。
- `docs/project_definition.md` 包含目标、范围、指标、语料策略和风险。
- 官方平台政策页和监管文件已有明确主题、数量和登记规则。
- 未把计划中的网页或 PDF 虚假登记为本地已有文件。
