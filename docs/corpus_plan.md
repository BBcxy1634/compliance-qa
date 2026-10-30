# D1 语料清单与收集状态

采集日期：2026-10-30。

## 已完成资料

| 类别 | 数量 | 存储位置 | 状态 |
|---|---:|---|---|
| 自建 PPT | 7 | `data/raw/ppt/` | 已登记 |
| Amazon 官方政策页 | 5 | `data/raw/html/` | 已保存正文 |
| eBay 官方政策页 | 7 | `data/raw/html/` | 已保存正文 |
| 海关等部门监管文件 | 5 | `data/raw/pdf/` | 已保存 PDF |

平台政策页合计 12 个，符合 10 至 15 个的目标。监管文件合计 5 份，符合 3 至 5 份的目标。所有实际文件均登记在 `data/raw/sources.jsonl`。

## Amazon 政策页

| source_id | 主题 | 状态 |
|---|---|---|
| `amazon_reviews_policy` | 商品评论与评论操纵政策 | 已保存 |
| `amazon_restricted_products_policy` | 受限商品与违规申诉 | 已保存 |
| `amazon_fair_conduct_policy` | 公平行事与功能滥用 | 已保存 |
| `amazon_appeal_process` | 账户申诉流程 | 已保存 |
| `amazon_inform_act` | 美国消费者告知法案信息验证 | 已保存 |

## eBay 政策页

| source_id | 主题 | 状态 |
|---|---|---|
| `ebay_intellectual_property_policy` | 知识产权政策 | 已保存 |
| `ebay_offensive_materials_policy` | 冒犯性材料政策 | 已保存 |
| `ebay_illegal_explicit_content_policy` | 非法露骨内容政策 | 已保存 |
| `ebay_adult_items_policy` | 成人商品限制政策 | 已保存 |
| `ebay_feedback_policy` | 评价政策 | 已保存 |
| `ebay_item_description_policy` | 商品描述政策 | 已保存 |
| `ebay_search_manipulation_policy` | 搜索操纵政策 | 已保存 |

## 监管文件

| source_id | 文件主题 | 发布机构 | 状态 |
|---|---|---|---|
| `gov_export_return_tax_2026` | 跨境电商出口退运税收优惠 | 财政部、海关总署、税务总局 | 已保存 |
| `gov_overseas_warehouse_tax_2025` | 出口海外仓退免税 | 国家税务总局 | 已保存 |
| `gov_customs_export_2024` | 进一步促进跨境电商出口 | 海关总署 | 已保存 |
| `gov_import_list_2022` | 调整跨境电商零售进口商品清单 | 财政部等多部门 | 已保存 |
| `gov_retail_supervision_2018` | 跨境电商零售进出口监管 | 海关总署 | 已保存 |

## 存储与版权

官方正文和 PDF 仅作为本地实验语料，不提交到公开 Git 仓库。`sources.jsonl` 保存来源 URL、发布日期、采集日期、语言、路径与哈希；`scripts/fetch_official_sources.py` 用于重新获取正文。

## 拒答语料边界

“欧盟包装法 2026 年新要求”是固定拒答场景。当前语料没有加入能够直接回答该问题的政策文件。若后续扩展业务范围，必须同时修改评测集和项目范围。

## D1 验收

- 7 份核心 PPT 已复制、重命名并登记。
- 12 个官方平台政策页已保存正文和 URL。
- 5 份官方监管文件已保存为 PDF。
- `sources.jsonl` 共 24 条，`source_id` 唯一。
- 所有路径、URL、语言、日期、哈希和 PDF 页数均通过脚本校验。
- `python scripts/validate_sources.py` 返回 `VALIDATION PASSED`。
