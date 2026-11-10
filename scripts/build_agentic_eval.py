#!/usr/bin/env python3
"""Build and verify the Phase 4 agentic evaluation dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_QUESTIONS = ROOT / "eval" / "questions.jsonl"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
OUTPUT_PATH = ROOT / "eval" / "agentic_v2" / "questions.jsonl"
CREATED_AT = "2026-11-10"
TOOL_SEARCH = "search_official_policy_sources"
TOOL_SNAPSHOT = "inspect_latest_policy_snapshot"
TOOL_COMPARE = "compare_policy_versions"
TOOL_DATE = "validate_validity_period"


BASE_ROUTES = {
    "q001": "simple_fact",
    "q002": "simple_fact",
    "q003": "simple_fact",
    "q004": "simple_fact",
    "q005": "simple_fact",
    "q006": "simple_fact",
    "q007": "high_risk",
    "q008": "high_risk",
    "q009": "simple_fact",
    "q010": "simple_fact",
    "q011": "high_risk",
    "q012": "high_risk",
    "q013": "high_risk",
    "q014": "high_risk",
    "q015": "high_risk",
    "q016": "simple_fact",
    "q017": "simple_fact",
    "q018": "simple_fact",
    "q019": "simple_fact",
    "q020": "simple_fact",
    "q021": "high_risk",
    "q022": "simple_fact",
    "q023": "simple_fact",
    "q024": "high_risk",
    "q025": "high_risk",
    "q026": "high_risk",
    "q027": "high_risk",
    "q028": "high_risk",
    "q029": "high_risk",
    "q030": "high_risk",
    "q031": "high_risk",
    "q032": "simple_fact",
    "q033": "simple_fact",
    "q034": "simple_fact",
    "q035": "simple_fact",
    "q036": "simple_fact",
    "q037": "simple_fact",
    "q038": "multi_hop",
    "q039": "simple_fact",
    "q040": "simple_fact",
    "q041": "multi_hop",
    "q042": "high_risk",
    "q043": "high_risk",
    "q044": "multi_hop",
    "q045": "high_risk",
    "q046": "high_risk",
    "q047": "multi_hop",
    "q048": "high_risk",
    "q049": "multi_hop",
    "q050": "multi_hop",
    "q051": "simple_fact",
    "q052": "high_risk",
    "q053": "simple_fact",
    "q054": "simple_fact",
    "q055": "simple_fact",
    "q056": "simple_fact",
    "q057": "high_risk",
    "q058": "simple_fact",
    "q059": "high_risk",
    "q060": "simple_fact",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def case(
    case_id: str,
    case_type: str,
    question: str,
    gold_answer: str,
    key_facts: list[str],
    quotes: list[tuple[str, str]],
    *,
    route: str,
    tools: list[str] | None = None,
    evidence_sufficient: bool = True,
) -> dict[str, Any]:
    if case_type == "refusal":
        expected_behavior = "refuse"
        gold_answer = "文档中未找到足够依据，暂时无法回答这个问题。"
        key_facts = []
        quotes = []
    else:
        expected_behavior = "answer"
    return {
        "id": case_id,
        "type": case_type,
        "question": question,
        "gold_answer": gold_answer,
        "key_facts": key_facts,
        "gold_evidence": [
            {"chunk_id": chunk_id, "quote": quote}
            for chunk_id, quote in quotes
        ],
        "lang": "zh",
        "expected_behavior": expected_behavior,
        "review_status": "draft",
        "created_at": CREATED_AT,
        "agentic": {
            "expected_route": route,
            "required_tools": [TOOL_SEARCH, *(tools or [])],
            "expected_evidence_sufficient": evidence_sufficient,
            "review_status": "draft",
        },
    }


NEW_CASES = [
    case(
        "q061",
        "fact",
        "跨境电商中的B2B模式指什么？",
        "B2B是企业与企业之间的交易模式，例如制造商向海外批发商供货或企业间采购原材料。",
        ["B2B是企业对企业", "交易批量大且周期较长"],
        [
            (
                "ppt_01_foundations#s09#c01",
                "跨境电商中企业与企业之间的交易模式",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q062",
        "fact",
        "跨境电商中的C2C模式如何定义？",
        "C2C是个人卖家通过平台向海外个人买家销售商品的模式，常见于二手或小众商品。",
        ["个人卖家向个人买家销售", "常见于二手或小众商品"],
        [
            (
                "ppt_01_foundations#s09#c01",
                "个人卖家通过平台向海外个人买家销售商品的模式",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q063",
        "fact",
        "平台型跨境电商平台自身参与商品销售吗？",
        "平台型跨境电商提供交易场所和服务，连接买卖双方，自身不直接参与商品销售，主要收取佣金或服务费。",
        ["平台连接买卖双方", "平台自身不直接销售商品"],
        [
            (
                "ppt_01_foundations#s10#c01",
                "提供交易场所和服务的第三方平台,连接买卖双方,自身不直接参与商品销售",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q064",
        "fact",
        "跨境电商订单履约环节需要完成哪些工作？",
        "消费者下单后需要快速处理订单，确认订单信息、检查库存、准备商品发货，并避免延误或错发。",
        ["确认订单信息", "检查库存并准备发货"],
        [
            (
                "ppt_01_foundations#s13#c01",
                "订单履约:消费者下单后,快速处理订单,包括确认订单信息、检查库存、准备商品发货",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q065",
        "fact",
        "跨境卖家使用信用卡收款需要关注什么风险？",
        "信用卡支付便捷且覆盖广，但存在盗刷风险，商家还需承担一定比例的交易手续费。",
        ["信用卡存在盗刷风险", "商家承担交易手续费"],
        [
            (
                "ppt_01_foundations#s16#c01",
                "信用卡支付存在一定的盗刷风险,而且对于商家来说,信用卡组织会收取一定比例的交易手续费",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q066",
        "fact",
        "跨境电商选品在政策合规方面要满足什么条件？",
        "选品应符合目标国法规，例如欧盟REACH、美国CPSC标准，并避开电子烟、侵权商品等禁售清单。",
        ["符合目标国法规", "不触碰禁售清单"],
        [
            (
                "ppt_02_selection#s04#c01",
                "政策合规:符合目标国法规(如欧盟 REACH 认证、美国 CPSC 标准),不触碰禁售清单",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q067",
        "fact",
        "热销榜单选品法的核心思路是什么？",
        "通过追踪平台官方热销数据快速捕捉市场趋势，筛选潜力商品。",
        ["追踪平台官方热销数据", "筛选潜力商品"],
        [
            (
                "ppt_02_selection#s08#c01",
                "热销榜单选品法是通过追踪跨境电商平台官方热销数据",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q068",
        "fact",
        "大数据选品中的供需比如何计算？",
        "供需比按搜索量与卖家数量之比计算，比值越高通常说明市场机会越大。",
        ["搜索量除以卖家数量", "比值越高市场机会越大"],
        [
            (
                "ppt_02_selection#s09#c01",
                "计算供需比(搜索量与卖家数量之比)",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q069",
        "fact",
        "差评选品法收集哪些评论来寻找产品机会？",
        "收集热销商品的1至3星差评，分析反复出现的负面反馈并据此改进产品。",
        ["收集1至3星差评", "针对负面反馈改进产品"],
        [
            (
                "ppt_02_selection#s10#c01",
                "差评选品法是通过收集热销商品的 1-3 星差评",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q070",
        "fact",
        "选品时常见的隐性成本包括哪些？",
        "隐性成本包括库存积压成本、退换货成本和认证、标签整改等合规成本。",
        ["库存积压成本", "退换货成本", "合规成本"],
        [
            (
                "ppt_02_selection#s16#c01",
                "隐性成本包括库存积压成本",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q071",
        "fact",
        "入驻成熟跨境电商平台对新手卖家有什么主要优势？",
        "平台提供成熟交易系统、支付体系和物流渠道，降低技术与资金门槛，并提供流量和运营支持。",
        ["降低技术和资金门槛", "获得平台流量与服务支持"],
        [
            (
                "ppt_03_platforms#s04#c01",
                "大大降低了进入跨境电商领域的技术和资金门槛",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q072",
        "fact",
        "亚马逊A9算法的相关性维度关注什么？",
        "相关性以关键词匹配为基础，要求标题、五点描述和Search Term精准覆盖搜索词，并选择正确品类节点。",
        ["关键词匹配是基础", "品类节点必须正确"],
        [
            (
                "ppt_03_platforms#s17#c01",
                "关键词匹配是基础",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q073",
        "fact",
        "eBay相关性搜索排名的五层匹配包括哪些维度？",
        "五层匹配包括主题、重要字、详细页面描写、类别和属性。",
        ["主题与重要字", "详细页面描写、类别和属性"],
        [
            (
                "ppt_03_platforms#s23#c01",
                "五层匹配(主题、重要字、详细页面描写、类别、属性)",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q074",
        "fact",
        "成为eBay Top Rated Seller对流量有什么影响？",
        "eBay会给Top Rated Seller流量倾斜，体现在搜索排名靠前和专属标识等方面。",
        ["Top Rated Seller获得流量倾斜", "搜索排名靠前"],
        [
            (
                "ppt_03_platforms#s25#c01",
                "平台会给大量流量倾斜",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q075",
        "fact",
        "ERP系统通常包含哪些核心功能？",
        "ERP系统通常包含商品管理、订单处理、库存管理和物流对接。",
        ["商品与订单管理", "库存管理与物流对接"],
        [
            (
                "ppt_05_tools#s05#c01",
                "商品管理:包括商品信息的录入、编辑、分类",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q076",
        "fact",
        "初创小卖家选择ERP系统时，预算与功能应如何取舍？",
        "初创小卖家可优先选择基础功能免费或低价的系统，并关注平台适配、预算和售后服务质量。",
        ["优先免费或低价基础功能", "关注平台适配和售后"],
        [
            (
                "ppt_05_tools#s07#c01",
                "初创期的小卖家可选择基础功能免费或低价的系统",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q077",
        "fact",
        "Jungle Scout主要能帮助卖家分析哪些数据？",
        "Jungle Scout可分析销量预估、市场趋势和竞争程度，并支持关键词研究。",
        ["销量与市场趋势", "竞争程度与关键词研究"],
        [
            (
                "ppt_05_tools#s12#c01",
                "销量预估、市场趋势、竞争程度",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q078",
        "fact",
        "点击率CTR如何定义？",
        "CTR是商品被点击次数与曝光次数的比例。",
        ["点击次数除以曝光次数"],
        [
            (
                "ppt_05_tools#s22#c01",
                "点击率(CTR):指商品被点击的次数与曝光次数的比例",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q079",
        "fact",
        "使用翻译工具处理跨境Listing时为什么不能只依赖直译？",
        "直译可能不符合目标市场表达习惯，应结合当地文化背景和消费习惯进行本地化调整。",
        ["不能只依赖直译", "需要本地化调整"],
        [
            (
                "ppt_05_tools#s17#c01",
                "不能简单依赖工具的直译,要结合目标市场的文化背景和消费习惯进行本地化调整",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q080",
        "fact",
        "使用美国海外仓发货通常能缩短多少物流时间？",
        "美国本土发货通常3至5天送达，快于国际快递常见的15至30天。",
        ["本土发货3至5天", "国际快递常见15至30天"],
        [
            (
                "ppt_04_compliance#s12#c01",
                "美国本土发货 3-5 天送达,远快于国际快递的 15-30 天",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q081",
        "fact",
        "与供应商首次合作时建议采用什么付款方式？",
        "首次合作优先采用30%预付款加70%尾款，尾款在见提单或验货后支付，避免全额预付。",
        ["30%预付款", "70%尾款在验货或见提单后支付"],
        [
            (
                "ppt_04_compliance#s08#c01",
                "首次合作优先采用 “30% 预付款 + 70% 尾款(见提单 / 验货后付)”",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q082",
        "fact",
        "自建跨境独立站应优先支持哪些支付方式？",
        "欧美市场应支持PayPal和Visa、MasterCard等信用卡支付，并可按市场补充本地支付方式。",
        ["支持PayPal和信用卡", "按市场补充本地支付"],
        [
            (
                "ppt_04_compliance#s20#c01",
                "PayPal、信用卡支付(如 Visa、MasterCard)在欧美市场广泛使用",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q083",
        "fact",
        "注册亚马逊专业卖家通常需要准备哪些基础资料？",
        "通常需要营业执照彩色扫描件、法定代表人身份证件、可国际付款的信用卡、联系方式、收款账户和税务信息。",
        ["公司营业执照", "法定代表人身份证件", "可用于收款和付款的账户"],
        [
            (
                "ppt_04_compliance#s16#c01",
                "公司营业执照彩色扫描件",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q084",
        "fact",
        "FICO评分用于跨境电商企业信用评估有哪些局限？",
        "FICO主要评估美国个人信贷违约风险，不适用于企业端，且缺乏电商消费等新型数据。",
        ["不适用于B端企业", "数据维度偏传统"],
        [
            (
                "ppt_07_credit#s04#c01",
                "主要针对美国市场的个人信用评估",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q085",
        "fact",
        "跨境支付的基本定义是什么？",
        "跨境支付是不同国家或地区的交易主体通过结算工具和支付渠道实现资金跨国转移的行为。",
        ["不同国家或地区交易主体", "资金跨越国界转移"],
        [
            (
                "ppt_06_finance#s04#c01",
                "实现资金跨越国界转移的行为",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q086",
        "fact",
        "银行电汇更适合哪类跨境交易？",
        "银行电汇安全性较高，适合大额交易，尤其是超过10万美元的交易，但手续费较高且到账较慢。",
        ["适合大额交易", "手续费较高和到账较慢"],
        [
            (
                "ppt_06_finance#s12#c01",
                "适合大额交易,尤其是超过 10 万美元的交易",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q087",
        "fact",
        "PayPal跨境交易手续费通常按什么范围收取？",
        "PayPal跨境交易手续费通常为交易金额的3.4%至4.4%，另加按币种确定的固定费用。",
        ["交易金额的3.4%至4.4%", "另加固定费用"],
        [
            (
                "ppt_06_finance#s09#c01",
                "交易手续费通常为交易金额的 3.4%-4.4%",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q088",
        "fact",
        "2024年跨境电商出口监管公告从哪一天起施行？",
        "该公告自2024年12月15日起施行。",
        ["2024年12月15日施行"],
        [
            (
                "gov_customs_export_2024#p03#c01",
                "本公告自 2024 年 12 月 15 日起施行",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q089",
        "fact",
        "2022年零售进口清单中其他扇贝有什么监管备注？",
        "其他扇贝被注明仅限网购保税商品。",
        ["其他扇贝仅限网购保税"],
        [
            (
                "gov_import_list_2022#p01#c01",
                "其他扇贝 仅限网购保税商品",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q090",
        "fact",
        "出口退运商品已经办理出口退税的，企业应如何处理退税款？",
        "符合退运优惠条件的商品如果已办理出口退税，企业应按现行规定补缴已退税款。",
        ["已退税款需要补缴", "凭补税或未退税证明办理"],
        [
            (
                "gov_export_return_tax_2026#p01#c01",
                "已办理出口退税的,企业应当按现行规定补缴已退的税款",
            )
        ],
        route="simple_fact",
    ),
    case(
        "q091",
        "multi_hop",
        "亚马逊卖家销售假冒或受限商品时，商品责任如何判断，承认违规后应采用什么申诉方式？",
        "卖家有责任确保商品符合当地法律和亚马逊政策；当前承认违规的申诉已改为勾选、解释、编辑详情页或测验等形式，而不是传统行动计划书。",
        ["卖家承担商品合规责任", "承认违规采用新版申诉方式"],
        [
            (
                "amazon_restricted_products_policy#sec01#c01",
                "您有责任确保您的商品符合所有当地、州和联邦法律以及亚马逊政策",
            ),
            (
                "amazon_appeal_process#sec01#c01",
                "亚马逊取消了提交开放式问题形式的 “提交行动计划书”",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q092",
        "multi_hop",
        "亚马逊卖家操纵商品评论可能受到哪些处罚，申诉时又需要采用什么形式？",
        "评论操纵可能导致ASIN限流、撤销销售权限和扣留资金等后果；承认违规后需按页面要求勾选、解释或提交问卷式申诉。",
        ["评论操纵可能导致ASIN限流和撤权", "承认违规使用问卷式申诉"],
        [
            (
                "amazon_reviews_policy#sec01#c02",
                "ASIN被限流",
            ),
            (
                "amazon_appeal_process#sec01#c01",
                "阅读并勾选承认违规的选项",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q093",
        "multi_hop",
        "亚马逊卖家通过虚假订单操纵排名并恶意留下差评，可能承担什么法律责任？",
        "接受虚假订单、操纵销售排名属于滥用平台服务，恶意差评还可能涉及损害竞争对手；严重时可能受到账户停用并被追究法律责任。",
        ["虚假订单属于操纵销售排名", "恶意差评针对竞争对手", "可能承担法律责任"],
        [
            (
                "amazon_fair_conduct_policy#sec01#c02",
                "操纵销售排名(例如:接受虚假订单或您自己付款的订单)",
            ),
            (
                "amazon_reviews_policy#sec01#c02",
                "创建多个虚假买家账号来发布虚假评论",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q094",
        "multi_hop",
        "eBay商品Listing销售假冒商品且描述不准确，会分别违反哪些知识产权和商品描述规则？",
        "销售假冒商品违反知识产权政策；商品描述不准确则可能误导买家，违反商品描述政策。",
        ["假冒商品违反知识产权政策", "商品描述必须准确"],
        [
            (
                "ebay_intellectual_property_policy#sec01#c01",
                "Examples of items not allowed under this policy are counterfeit products",
            ),
            (
                "ebay_item_description_policy#sec01#c02",
                "Item descriptions must be accurate",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q095",
        "multi_hop",
        "eBay卖家未经许可使用商标并添加不相关热门关键词，会分别涉及商标侵权和搜索操纵问题吗？",
        "未经许可使用商标可能构成商标侵权；添加与商品无关的关键词属于搜索操纵。",
        ["未经许可使用商标可能侵权", "无关关键词属于搜索操纵"],
        [
            (
                "ebay_intellectual_property_policy#sec01#c07",
                "Items listed on eBay must not use a trademark without permission.",
            ),
            (
                "ebay_search_manipulation_policy#sec01#c01",
                "Manipulating eBay's search and browse experience by adding popular keywords",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q096",
        "multi_hop",
        "eBay卖家盗用第三方图片且Listing内容与商品无关，可能涉及哪些版权和描述合规问题？",
        "未经许可使用第三方图片可能侵犯版权；Listing内容与商品无关则不符合商品描述政策。",
        ["第三方图片未经许可可能侵权", "Listing内容必须与商品直接相关"],
        [
            (
                "ebay_intellectual_property_policy#sec01#c04",
                "Using third-party photos, images, or videos without permission",
            ),
            (
                "ebay_item_description_policy#sec01#c02",
                "All content in a listing must be directly related to the item",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q097",
        "multi_hop",
        "eBay卖家销售仿制专利产品并通过关键词获取流量，分别涉及哪些专利和搜索规则？",
        "销售侵犯专利的产品被禁止；使用与商品无关的关键词获取曝光属于搜索操纵。",
        ["侵犯专利的产品被禁止", "无关关键词获取流量属于搜索操纵"],
        [
            (
                "ebay_intellectual_property_policy#sec01#c12",
                "listing products that infringe on their patent is strictly prohibited on eBay",
            ),
            (
                "ebay_search_manipulation_policy#sec01#c02",
                "All the words in the listing need to be accurate and refer only to the item for sale",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q098",
        "multi_hop",
        "eBay卖家销售未经授权的平行进口商品，并对其来源作模糊描述，应如何判断知识产权侵权和描述合规性？",
        "平行进口在权利持有人未授权进口或销售的地区可能构成知识产权侵权；同时商品描述必须准确，不能误导买家。",
        ["平行进口可能构成知识产权侵权", "商品描述必须准确"],
        [
            (
                "ebay_intellectual_property_policy#sec01#c16",
                "Parallel imports can be considered intellectual property infringing in certain jurisdictions",
            ),
            (
                "ebay_item_description_policy#sec01#c01",
                "Item descriptions that don't accurately describe your item can mislead buyers.",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q099",
        "multi_hop",
        "供应商未告知产品安全认证缺失时，亚马逊卖家销售受限商品能否免责？",
        "供应商未告知不能免除卖家责任；卖家仍需提供适用生产许可或认证，并自行甄别商品是否属于受限商品。",
        ["供应商未告知不能免责", "卖家需要核查认证和受限商品"],
        [
            (
                "ppt_04_compliance#s08#c01",
                "生产许可证(如食品需 SC 认证、电子产品需 3C 认证)",
            ),
            (
                "amazon_restricted_products_policy#sec01#c02",
                "卖家有义务甄别自己要上架的商品是否属于受限商品",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q100",
        "multi_hop",
        "亚马逊受限商品仅改为缺货状态是否足够，申诉前还需如何处理库存和申诉流程？",
        "仅改为缺货不够，卖家必须停止销售并移除全部受限商品和FBA库存，同时按申诉页面采用当前问卷式流程。",
        ["缺货状态不能解决违规", "需要移除FBA库存", "申诉采用当前页面流程"],
        [
            (
                "amazon_restricted_products_policy#sec01#c05",
                "这还不够,卖家必须遵循正确的流程停止销售或从库存中移除所有的受限商品",
            ),
            (
                "amazon_appeal_process#sec01#c01",
                "修改详情页面(ASIN级别申诉)",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q101",
        "multi_hop",
        "在2026年1月1日至2027年12月31日期间，出口退运补缴退税需要什么证明，海关跨关区退货应退至哪里？",
        "办理免进口税和退出口关税时需提供《出口货物已补税/未退税证明》；9610跨关区退货应退至开展跨境电商零售出口业务的海关监管作业场所。",
        ["需要补税或未退税证明", "退货退至海关监管作业场所"],
        [
            (
                "gov_export_return_tax_2026#p01#c01",
                "《出口货物已补税/未退税证明》",
            ),
            (
                "gov_customs_export_2024#p02#c01",
                "退货商品应当退至开展跨境电商零售",
            ),
        ],
        route="high_risk",
        tools=[TOOL_DATE],
    ),
    case(
        "q102",
        "multi_hop",
        "比较当前海关监管版本变更后，出口海外仓备案、申报数据与退税核算分别有什么要求？",
        "海外仓业务模式备案已取消，但申报仍需传输订仓单电子数据；9810货物离境后可申报退税，未销售货物先预退税再于次月1日至次年4月30日核算。",
        ["取消海外仓业务模式备案", "仍需传输订仓单电子数据", "预退税核算期为次月1日至次年4月30日"],
        [
            (
                "gov_customs_export_2024#p01#c01",
                "取消跨境电商出口海外仓企业备案",
            ),
            (
                "gov_overseas_warehouse_tax_2025#p01#c02",
                "税务机关办结出口预退税的次月1日至次年4月30日",
            ),
        ],
        route="high_risk",
        tools=[TOOL_COMPARE],
    ),
    case(
        "q103",
        "multi_hop",
        "跨境电商零售进口清单中的商品在海关通关前，企业登记和数据传输分别有什么要求？",
        "清单商品可能注明仅限网购保税；参与零售进口的企业需向所在地海关办理注册登记，并传输交易、支付、物流等电子信息。",
        ["部分商品仅限网购保税", "企业需要注册登记", "需要传输交易支付物流数据"],
        [
            (
                "gov_import_list_2022#p01#c01",
                "仅限网购保税商品",
            ),
            (
                "gov_retail_supervision_2018#p01#c01",
                "向所在地海关办理注册登记",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q104",
        "multi_hop",
        "零售进口清单中的商品是否仍需缴纳关税和进口环节增值税，完税价格分别包括哪些费用？",
        "清单商品仍需按进口税收政策征税；完税价格为实际交易价格，包括商品零售价格、运费和保险费。",
        ["仍需缴纳关税和进口环节税", "完税价格包含零售价运费保险费"],
        [
            (
                "gov_import_list_2022#p01#c01",
                "跨境电子商务零售进口商品清单调整表",
            ),
            (
                "gov_retail_supervision_2018#p02#c02",
                "完税价格为实际交易价格,包括商品零售价格、运费和保险费",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q105",
        "multi_hop",
        "跨境电商企业传输虚假交易、支付、物流信息会面临什么处罚，发现违规应如何处理？",
        "企业应对数据真实性承担法律责任，虚假三单信息等违规会被依法处罚；发现涉嫌违规或走私应及时主动告知海关。",
        ["虚假三单信息需承担法律责任", "发现违规应主动告知海关"],
        [
            (
                "gov_customs_export_2024#p02#c01",
                "并对数据真实性承担相应法律责任",
            ),
            (
                "gov_retail_supervision_2018#p04#c01",
                "发现涉嫌违规或走私行为的,应当及时主动告知海关",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q106",
        "multi_hop",
        "跨境电商平台审核客户个人数据时，支付账户密码和手机验证码分别应如何保护？",
        "平台需审核订购人身份信息真实性；卖家和个人应设置复杂独立密码，不向他人泄露密码和验证码，并通过官方渠道核实异常。",
        ["平台审核订购人身份真实性", "密码和验证码不得泄露"],
        [
            (
                "gov_retail_supervision_2018#p02#c01",
                "消费者(订购人)身份信息真实性进行审核",
            ),
            (
                "ppt_06_finance#s28#c01",
                "不要将密码告知他人",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q107",
        "multi_hop",
        "电子产品出口前需要哪些产品安全和认证检查，亚马逊卖家对受限商品负什么责任？",
        "出口前应确认CE、FCC等标签合规和供应商资质；亚马逊卖家仍有责任确保商品符合法律和政策，并自行甄别是否属于受限商品。",
        ["电子产品需核对适用认证", "卖家承担受限商品核查责任"],
        [
            (
                "ppt_04_compliance#s09#c01",
                "确认产品标签合规(如欧盟需 CE 标识、美国需 FCC 认证)",
            ),
            (
                "amazon_restricted_products_policy#sec01#c01",
                "您有责任确保您的商品符合所有当地、州和联邦法律以及亚马逊政策",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q108",
        "multi_hop",
        "侵犯知识产权的商品在海关监管和eBay平台分别会受到什么限制？",
        "跨境电子商务企业不得进出口侵犯知识产权的商品；eBay也不允许销售侵犯他人知识产权的商品或Listing。",
        ["海关禁止侵犯知识产权的商品", "eBay禁止知识产权侵权商品"],
        [
            (
                "gov_retail_supervision_2018#p04#c01",
                "识产权的商品以及其他禁限商品",
            ),
            (
                "ebay_intellectual_property_policy#sec01#c01",
                "Listings or products that infringe on the intellectual property rights of others are not allowed on eBay.",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q109",
        "multi_hop",
        "美国消费者告知法案的信息验证与亚马逊受限商品责任，分别会如何影响卖家账户？",
        "未完成法案信息验证可能导致暂停销售权限和扣留款项；同时卖家必须确保商品符合法律和政策，否则受限商品违规也可能危及账户。",
        ["信息验证失败可能暂停销售", "受限商品违规影响账户"],
        [
            (
                "amazon_inform_act#sec01#c01",
                "否则亚马逊可能会暂停您的销售权限并扣留款项",
            ),
            (
                "amazon_restricted_products_policy#sec01#c01",
                "亚马逊将视情况采取纠正措施,包括但不限于立刻暂停或终止销售权限等",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q110",
        "multi_hop",
        "出口退运税收优惠中的偷税、骗税与虚假交易信息分别会面临什么法律后果？",
        "偷税、骗税等行为按国家法律法规处理；制造或传输虚假交易、支付、物流信息导致违规的企业也会被依法处罚。",
        ["偷税骗税依法处理", "虚假交易信息依法处罚"],
        [
            (
                "gov_export_return_tax_2026#p01#c02",
                "企业偷税、骗税等违法违规行为,按照国家有关法律法规等规定处理。",
            ),
            (
                "gov_retail_supervision_2018#p04#c02",
                "依法进行处罚",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q111",
        "multi_hop",
        "B2C模式如何定义，亚马逊平台又分别适合哪些卖家与商品？",
        "B2C是企业直接向海外消费者销售商品；亚马逊流量大、FBA成熟，更适合品牌商和供应链稳定的工厂型卖家，以及中高价商品。",
        ["B2C直接面向消费者", "亚马逊适合品牌和供应链型卖家"],
        [
            (
                "ppt_01_foundations#s09#c01",
                "企业直接向海外个人消费者销售商品的模式",
            ),
            (
                "ppt_04_compliance#s15#c01",
                "它更适合品牌商、供应链稳定的工厂型卖家入驻",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q112",
        "multi_hop",
        "B2C与C2C的交易主体有何差异，eBay的拍卖模式分别适合哪些商品？",
        "B2C是企业对消费者，C2C是个人对个人；eBay拍卖模式适合二手商品、稀缺品或收藏品。",
        ["B2C是企业对消费者", "C2C是个人对个人", "拍卖适合二手稀缺和收藏品"],
        [
            (
                "ppt_01_foundations#s09#c01",
                "B2C(企业对消费者)",
            ),
            (
                "ppt_03_platforms#s22#c01",
                "拍卖、一口价",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q113",
        "multi_hop",
        "第三方平台和自建独立站在技术门槛、流量与品牌控制方面分别有何差异？",
        "第三方平台拥有成熟系统和流量，技术门槛较低但受平台规则限制；独立站品牌和数据控制更强，但需要自行建设和获客。",
        ["第三方平台降低技术门槛并提供流量", "独立站控制品牌和客户数据"],
        [
            (
                "ppt_03_platforms#s04#c01",
                "大大降低了进入跨境电商领域的技术和资金门槛",
            ),
            (
                "ppt_04_compliance#s17#c01",
                "完全的品牌控制权",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q114",
        "multi_hop",
        "订单履约从下单到发货要经过哪些动作，海外仓又分别能缩短哪些物流环节？",
        "订单履约需要确认订单、检查库存、准备发货；海外仓提前备货并从本地发货，可缩短尾程配送时间。",
        ["订单履约确认信息库存和发货", "海外仓缩短本地配送时间"],
        [
            (
                "ppt_01_foundations#s13#c01",
                "订单履约:消费者下单后,快速处理订单,包括确认订单信息、检查库存、准备商品发货",
            ),
            (
                "ppt_04_compliance#s12#c01",
                "可大幅缩短物流时效",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q115",
        "multi_hop",
        "选品时的隐性成本与跨境财务核算中的成本分别包括哪些项目？",
        "选品隐性成本包括库存积压、退换货和合规成本；财务成本核算还包括采购、物流、营销、平台费用和其他运营成本。",
        ["隐性成本包含库存退货合规", "财务核算覆盖采购物流营销和平台费用"],
        [
            (
                "ppt_02_selection#s16#c01",
                "隐性成本包括库存积压成本",
            ),
            (
                "ppt_06_finance#s25#c01",
                "采购成本:商品的采购价格",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q116",
        "multi_hop",
        "热销榜单选品与数据分析工具分别如何判断市场趋势？",
        "热销榜单通过追踪平台官方热销数据发现趋势；数据分析工具整合搜索和销售数据，展示增长率和市场饱和度。",
        ["热销榜追踪官方榜单", "分析工具展示增长率和市场饱和度"],
        [
            (
                "ppt_02_selection#s08#c01",
                "追踪跨境电商平台官方热销数据",
            ),
            (
                "ppt_05_tools#s13#c01",
                "提供增长率、市场饱和度等关键数据",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q117",
        "multi_hop",
        "差评选品与竞品分析分别关注消费者的哪些反馈和数据？",
        "差评选品关注1至3星评论中的反复痛点；竞品分析关注好评差评原因、销售数据、价格和评价情况。",
        ["差评关注反复出现的痛点", "竞品分析关注销售价格和评价"],
        [
            (
                "ppt_02_selection#s10#c01",
                "收集其 1-3 星评论",
            ),
            (
                "ppt_05_tools#s13#c01",
                "评价情况(分析竞品的好评、差评原因",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q118",
        "multi_hop",
        "细分人群场景定位和亚马逊A9相关性分别依赖哪些匹配维度？",
        "细分人群定位依赖年龄、职业和生活场景需求；A9相关性依赖关键词匹配与正确品类节点。",
        ["细分定位拆解人群和场景", "A9依赖关键词和品类匹配"],
        [
            (
                "ppt_02_selection#s12#c01",
                "按年龄、职业、生活习惯等维度锁定细分人群",
            ),
            (
                "ppt_03_platforms#s17#c01",
                "标题、五点描述、Search Term 需精准覆盖买家搜索词",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q119",
        "multi_hop",
        "跨境电商平台和ERP系统分别如何降低运营门槛并提升效率？",
        "平台提供成熟交易、支付、物流和流量资源；ERP统一管理商品、订单、库存和物流，减少多平台重复操作。",
        ["平台提供成熟基础设施和流量", "ERP统一管理多平台运营"],
        [
            (
                "ppt_03_platforms#s04#c01",
                "成熟的交易系统、支付体系和物流合作渠道",
            ),
            (
                "ppt_05_tools#s05#c01",
                "避免重复操作,确保各平台商品数据一致",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q120",
        "multi_hop",
        "亚马逊A9与eBay搜索规则分别如何约束关键词和商品匹配？",
        "A9强调关键词、品类节点和用户体验；eBay要求Listing词语准确且只描述在售商品，禁止无关热门词。",
        ["A9关注关键词和品类相关性", "eBay禁止无关关键词"],
        [
            (
                "ppt_03_platforms#s17#c01",
                "产品品类节点不能错",
            ),
            (
                "ebay_search_manipulation_policy#sec01#c01",
                "adding popular keywords in your listings that don't have any relation to your items",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q121",
        "multi_hop",
        "eBay Top Rated Seller与商品描述政策分别要求卖家关注哪些运营和内容质量？",
        "Top Rated Seller要求低纠纷、高物流时效和退货服务；商品描述要求内容准确、与商品直接相关并使用站点主要语言。",
        ["Top Rated关注纠纷物流和退货", "描述要求准确相关和语言正确"],
        [
            (
                "ppt_03_platforms#s25#c01",
                "低纠纷率( <2% )、高物流时效",
            ),
            (
                "ebay_item_description_policy#sec01#c06",
                "must be in the primary language of the eBay site",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q122",
        "multi_hop",
        "亚马逊品牌备案和ERP商品管理分别能为多平台运营提供哪些支持？",
        "品牌备案可解锁A+页面和品牌广告并增强维权；ERP商品管理可统一录入、编辑、分类和同步多平台商品信息。",
        ["品牌备案解锁营销和维权权益", "ERP统一商品信息"],
        [
            (
                "ppt_03_platforms#s20#c01",
                "解锁 A + 页面、品牌广告等权益",
            ),
            (
                "ppt_05_tools#s05#c01",
                "多平台商品信息的同步",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q123",
        "multi_hop",
        "信用卡和第三方支付平台分别有哪些便捷性与手续费特点？",
        "信用卡覆盖广且便捷，但有盗刷风险和交易手续费；第三方支付支持多币种和担保，但可能存在账户冻结及提现费用。",
        ["信用卡便捷但存在盗刷和手续费", "第三方支付多币种但可能冻结和提现费"],
        [
            (
                "ppt_01_foundations#s16#c01",
                "支付便捷,覆盖范围广",
            ),
            (
                "ppt_06_finance#s16#c01",
                "PayPal 针对跨境交易,交易手续费通常为交易金额的 3.4%-4.4%",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q124",
        "multi_hop",
        "跨境支付从付款到到账的流程，与亚马逊美国站信息验证分别包含哪些步骤？",
        "PayPal流程包括买家确认支付、资金进入中间账户、确认收货后转入卖家账户并提现；美国站验证包括身份、银行账号、地址、电话和税务信息。",
        ["支付资金先进入中间账户再结算", "美国站验证五类企业信息"],
        [
            (
                "ppt_06_finance#s09#c01",
                "资金先进入 PayPal 的中间账户",
            ),
            (
                "amazon_inform_act#sec01#c01",
                "卖家身份验证",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q125",
        "multi_hop",
        "汇率波动与选品隐性成本分别会如何影响最终利润？",
        "汇率变化会改变实际结算金额；库存积压、退换货和合规等隐性成本会使实际利润低于预期。",
        ["汇率变化影响结算金额", "隐性成本导致利润低于预期"],
        [
            (
                "ppt_06_finance#s19#c01",
                "汇率波动会直接导致实际结算金额变化",
            ),
            (
                "ppt_02_selection#s16#c01",
                "导致实际利润远低于预期",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q126",
        "multi_hop",
        "利润表、资产负债表与数据分析中的CTR、转化率分别帮助卖家判断什么？",
        "利润表反映经营成果，资产负债表反映财务状况；CTR反映曝光吸引力，转化率反映购买意愿和商品竞争力。",
        ["利润表反映经营成果", "资产负债表反映财务状况", "点击和转化反映运营效果"],
        [
            (
                "ppt_06_finance#s23#c01",
                "利润表能清晰反映一定时期内的经营成果",
            ),
            (
                "ppt_05_tools#s22#c01",
                "转化率:即完成购买的访客数与总访客数的比例",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q127",
        "multi_hop",
        "FICO评分用于企业信用评估时有哪些局限，供应商筛选又应分别核查哪些资质与产能？",
        "FICO主要面向美国个人信贷且不适用B端；供应商筛选需核查营业执照、生产许可、产能、小批量试产和售后能力。",
        ["FICO不适用企业端", "供应商需核查资质和产能"],
        [
            (
                "ppt_07_credit#s04#c01",
                "不适用 B 端场景",
            ),
            (
                "ppt_04_compliance#s08#c01",
                "资质与产能",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q128",
        "multi_hop",
        "跨境电商信用评分关注哪些交易场景，支付方式选择又分别要考虑哪些风险与成本？",
        "信用评分覆盖支付风险、订单履约和营销场景；支付方式需比较安全、到账速度、手续费和账户风险。",
        ["信用评分覆盖支付履约和营销", "支付选择比较安全和成本"],
        [
            (
                "ppt_07_credit#s08#c01",
                "评估买家支付风险",
            ),
            (
                "ppt_06_finance#s16#c01",
                "手续费和汇率",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q129",
        "multi_hop",
        "eBay商品描述与搜索规则分别对内容准确性、关键词相关性提出什么要求？",
        "商品描述必须准确且与商品直接相关；搜索规则要求所有词语准确并只指向在售商品。",
        ["描述必须准确", "关键词只指向在售商品"],
        [
            (
                "ebay_item_description_policy#sec01#c02",
                "Item descriptions must be accurate",
            ),
            (
                "ebay_search_manipulation_policy#sec01#c02",
                "All the words in the listing need to be accurate",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q130",
        "multi_hop",
        "eBay买家因已披露瑕疵留差评时，商品描述与反馈政策分别如何处理？",
        "如果瑕疵已在描述中准确披露，相关负面反馈可能被移除；商品描述本身必须保持准确并反映真实状况。",
        ["已披露瑕疵的反馈可能移除", "商品描述需要准确披露"],
        [
            (
                "ebay_feedback_policy#sec01#c08",
                "the item description clearly stated that there was a stain",
            ),
            (
                "ebay_item_description_policy#sec01#c02",
                "The item condition selected must match the item",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q131",
        "multi_hop",
        "eBay成人商品上架与反馈图片分别有哪些预批准、年龄和内容限制？",
        "成人用品卖家需预先批准，商品须全新原包装且Listing不得展示裸体或性内容；反馈图片必须符合内容政策且不得包含裸体。",
        ["成人用品需要预批准", "反馈图片必须符合内容政策"],
        [
            (
                "ebay_adult_items_policy#sec01#c08",
                "Sellers must be pre-approved",
            ),
            (
                "ebay_feedback_policy#sec01#c05",
                "Any pictures left",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q132",
        "multi_hop",
        "亚马逊补偿换评和虚假订单操纵分别违反哪项政策，后果有何不同？",
        "补偿换评违反商品评论政策；为提升自己排名而接受虚假订单属于公平行事准则中的排名操纵，两者都可能受到警告或停用措施。",
        ["补偿换评违反评论政策", "虚假订单操纵违反公平行事", "两者都可能导致账户措施"],
        [
            (
                "amazon_reviews_policy#sec01#c01",
                "为获得好评而提供补偿(包括免费或打折的商品)。",
            ),
            (
                "amazon_fair_conduct_policy#sec01#c03",
                "轻则将收到政策滥用警告,重则将受到账户停用的惩罚",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q133",
        "multi_hop",
        "亚马逊公平行事违规的申诉需要哪些调查与材料，当前申诉方式又发生了什么变化？",
        "申诉前需排查第三方服务、虚假订单、补偿等根因并准备证据；承认违规的申诉已改为问卷形式并需说明纠正和预防措施。",
        ["申诉前调查根因", "准备第三方或内部证据", "当前采用问卷式申诉"],
        [
            (
                "amazon_fair_conduct_policy#sec01#c03",
                "申诉前进行分析调查,判定问题根源",
            ),
            (
                "amazon_appeal_process#sec01#c01",
                "卖家只需通过勾选相应选项或者测验答题等方式即可完成申诉",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q134",
        "multi_hop",
        "美国消费者告知法案验证和亚马逊开店注册分别需要准备哪些企业信息与资料？",
        "法案验证覆盖身份、银行账号、企业地址、电话和税务信息；开店注册还需营业执照、法人证件、付款工具、联系方式和收款账户。",
        ["法案验证身份银行地址电话税务", "开店准备执照法人付款和收款资料"],
        [
            (
                "amazon_inform_act#sec01#c01",
                "银行账号验证",
            ),
            (
                "ppt_04_compliance#s16#c01",
                "公司营业执照彩色扫描件",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q135",
        "multi_hop",
        "跨境电商零售进口清单备注和订购人身份分别有哪些限制？",
        "部分清单商品仅限网购保税；订购人与支付人在身份信息未经认证时应为同一人。",
        ["部分商品仅限网购保税", "未认证时订购人与支付人须一致"],
        [
            (
                "gov_import_list_2022#p01#c01",
                "仅限网购保税商品",
            ),
            (
                "gov_retail_supervision_2018#p02#c01",
                "订购人与支付人应当为同一人",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q136",
        "multi_hop",
        "跨境电商零售进口的数据传输要求，与B2C业务流程分别包含哪些主体和环节？",
        "零售进口需平台、支付和物流企业分别传输交易、支付和物流信息；B2C流程包括选品、开店、上架、履约、物流、结算和售后。",
        ["平台支付物流分别传数据", "B2C覆盖选品到售后全流程"],
        [
            (
                "gov_retail_supervision_2018#p02#c01",
                "物流企业应当分别通过国际",
            ),
            (
                "ppt_01_foundations#s13#c01",
                "四、跨境电商业务流程",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q137",
        "multi_hop",
        "第三方平台与自建独立站分别如何获取流量和沉淀客户数据？",
        "平台借助自身海量用户和搜索推荐带来流量；独立站可通过SEO、社交媒体和广告获客，并直接掌握客户购买和浏览数据。",
        ["平台提供现成流量", "独立站自主获客并掌握客户数据"],
        [
            (
                "ppt_03_platforms#s04#c01",
                "主流跨境电商平台在全球范围内拥有海量的用户群体",
            ),
            (
                "ppt_04_compliance#s17#c01",
                "客户数据控制",
            ),
        ],
        route="high_risk",
    ),
    case(
        "q138",
        "multi_hop",
        "ERP库存管理与海外仓库存系统分别应具备哪些同步、预警和API能力？",
        "ERP应实时监控库存、设置预警并支持多仓调拨；海外仓系统应支持API对接和低于安全库存的自动提醒。",
        ["ERP实时库存预警和调拨", "海外仓支持API和预警"],
        [
            (
                "ppt_05_tools#s05#c01",
                "实时监控库存数量,设置库存预警",
            ),
            (
                "ppt_04_compliance#s12#c01",
                "是否支持 API 对接",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q139",
        "multi_hop",
        "数据分析中的CTR与选品测试的转化率分别如何定义和使用？",
        "CTR是点击次数与曝光次数之比，用于判断标题和图片吸引力；转化率是访客中完成购买的比例，选品测试常以高于5%作为扩大推广条件。",
        ["CTR是点击除以曝光", "转化率是购买访客除以总访客", "选品测试转化率高于5%"],
        [
            (
                "ppt_05_tools#s22#c01",
                "点击率(CTR):指商品被点击的次数与曝光次数的比例",
            ),
            (
                "ppt_02_selection#s10#c01",
                "观察其转化率(>5% 为合格)",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q140",
        "multi_hop",
        "翻译工具本地化与eBay商品描述语言分别有哪些要求？",
        "翻译后应结合目标市场文化和习惯做本地化，并对重要信息人工核对；eBay商品描述、图片和视频必须使用Listing站点的主要语言。",
        ["翻译后需要本地化并人工核对", "eBay描述使用站点主要语言"],
        [
            (
                "ppt_05_tools#s17#c01",
                "翻译后最好再进行人工核对",
            ),
            (
                "ebay_item_description_policy#sec01#c06",
                "must be in the primary language of the eBay site",
            ),
        ],
        route="multi_hop",
    ),
    case(
        "q141",
        "refusal",
        "日本JCT在2026年的注册销售额门槛是多少？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
    case(
        "q142",
        "refusal",
        "巴西ANVISA化妆品通知备案在2027年的具体费用是多少？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
    case(
        "q143",
        "refusal",
        "澳大利亚低价值进口商品的GST起征门槛是多少澳元？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
    case(
        "q144",
        "refusal",
        "沙特SABER认证在2026年的申请截止日期是哪一天？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
    case(
        "q145",
        "refusal",
        "美国CPSC对儿童玩具可迁移铅含量的最新限值是多少？",
        "",
        [],
        [],
        route="high_risk",
        evidence_sufficient=False,
    ),
    case(
        "q146",
        "refusal",
        "欧盟EPR纺织品生产者责任注册在2027年的统一截止日期是什么？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
    case(
        "q147",
        "refusal",
        "墨西哥RFC验证在2026年对跨境卖家的新要求是什么？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
    case(
        "q148",
        "refusal",
        "加拿大CASL要求营销同意记录至少保存多少年？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
    case(
        "q149",
        "refusal",
        "无人机锂电池出口韩国时，KC认证和运输标签的最新要求是什么？",
        "",
        [],
        [],
        route="high_risk",
        evidence_sufficient=False,
    ),
    case(
        "q150",
        "refusal",
        "新加坡GST对境外数字服务供应商的注册门槛是多少？",
        "",
        [],
        [],
        route="simple_fact",
        evidence_sufficient=False,
    ),
]


def build() -> list[dict[str, Any]]:
    chunks = {
        row["chunk_id"]: row
        for row in load_jsonl(CHUNKS_PATH)
    }
    base_rows = load_jsonl(BASE_QUESTIONS)
    if len(base_rows) != 60:
        raise ValueError("Expected exactly 60 base questions.")

    combined: list[dict[str, Any]] = []
    for row in base_rows:
        item = dict(row)
        item["agentic"] = {
            "expected_route": BASE_ROUTES[row["id"]],
            "required_tools": [TOOL_SEARCH],
            "expected_evidence_sufficient": (
                row["expected_behavior"] == "answer"
            ),
            "review_status": "draft",
        }
        combined.append(item)

    for item in NEW_CASES:
        quotes = item["gold_evidence"]
        for evidence in quotes:
            chunk = chunks.get(evidence["chunk_id"])
            if chunk is None:
                raise ValueError(
                    f"{item['id']}: unknown chunk {evidence['chunk_id']}"
                )
            if evidence["quote"] not in chunk["text"]:
                raise ValueError(
                    f"{item['id']}: quote not found in "
                    f"{evidence['chunk_id']}"
                )
        item["gold_chunks"] = list(
            dict.fromkeys(
                evidence["chunk_id"] for evidence in quotes
            )
        )
        source_ids = {
            chunks[chunk_id]["source_id"]
            for chunk_id in item["gold_chunks"]
        }
        if item["type"] == "fact" and len(source_ids) != 1:
            raise ValueError(f"{item['id']}: fact must use one source")
        if item["type"] == "multi_hop" and len(source_ids) < 2:
            raise ValueError(
                f"{item['id']}: multi-hop must use two sources"
            )
        if item["type"] == "refusal" and item["gold_chunks"]:
            raise ValueError(f"{item['id']}: refusal must not use evidence")
        combined.append(item)

    expected_ids = [f"q{number:03d}" for number in range(1, 151)]
    actual_ids = [row["id"] for row in combined]
    if actual_ids != expected_ids:
        raise ValueError("Question IDs must be q001 through q150.")
    questions = [row["question"] for row in combined]
    if len(set(questions)) != len(questions):
        raise ValueError("Question text must be unique.")
    return combined


def main() -> None:
    rows = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        json.dumps(row, ensure_ascii=False)
        for row in rows
    )
    OUTPUT_PATH.write_text(content + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} questions to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
