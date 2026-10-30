#!/usr/bin/env python3
"""Download and normalize the official sources used by the D1 corpus."""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
HTML_DIR = ROOT / "data" / "raw" / "html"
PDF_DIR = ROOT / "data" / "raw" / "pdf"
MANIFEST = ROOT / "data" / "raw" / "sources.jsonl"
SUMMARY = ROOT / "docs" / "official_sources.md"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
CAPTURED_AT = "2026-10-30"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

AMAZON_SOURCES = [
    {
        "source_id": "amazon_reviews_policy",
        "url": "https://gs.amazon.cn/news/news-brand-240418",
        "published_at": "2024-04-18",
    },
    {
        "source_id": "amazon_restricted_products_policy",
        "url": "https://gs.amazon.cn/news/news-brand-240411",
        "published_at": "2024-04-11",
    },
    {
        "source_id": "amazon_fair_conduct_policy",
        "url": "https://gs.amazon.cn/news/news-brand-240501",
        "published_at": "2024-05-01",
    },
    {
        "source_id": "amazon_appeal_process",
        "url": "https://gs.amazon.cn/news/news-notices-230228",
        "published_at": "2023-02-28",
    },
    {
        "source_id": "amazon_inform_act",
        "url": "https://gs.amazon.cn/news/news-notices-230518",
        "published_at": "2023-05-18",
    },
]

EBAY_SOURCES = [
    {
        "source_id": "ebay_intellectual_property_policy",
        "url": (
            "https://www.ebay.com/help/policies/listing-policies/"
            "selling-policies/intellectual-property-vero-program?id=4349"
        ),
    },
    {
        "source_id": "ebay_offensive_materials_policy",
        "url": (
            "https://www.ebay.com/help/policies/prohibited-restricted-items/"
            "offensive-materials-policy?id=4324"
        ),
    },
    {
        "source_id": "ebay_illegal_explicit_content_policy",
        "url": (
            "https://www.ebay.com/help/policies/prohibited-restricted-items/"
            "illegal-explicit-content-policy?id=5053"
        ),
    },
    {
        "source_id": "ebay_adult_items_policy",
        "url": (
            "https://www.ebay.com/help/policies/prohibited-restricted-items/"
            "adult-items-policy?id=4278"
        ),
    },
    {
        "source_id": "ebay_feedback_policy",
        "url": (
            "https://www.ebay.com/help/policies/feedback-policies/"
            "feedback-policies?id=4208"
        ),
    },
    {
        "source_id": "ebay_item_description_policy",
        "url": (
            "https://www.ebay.com/help/policies/listing-policies/"
            "item-description-policy?id=4372"
        ),
    },
    {
        "source_id": "ebay_search_manipulation_policy",
        "url": (
            "https://www.ebay.com/help/policies/listing-policies/"
            "search-manipulation-policy?id=4243"
        ),
    },
]

GOV_SOURCES = [
    {
        "source_id": "gov_export_return_tax_2026",
        "url": "https://www.gov.cn/zhengce/zhengceku/202602/content_7057580.htm",
        "published_at": "2026-02-10",
        "publisher": "财政部 海关总署 税务总局",
    },
    {
        "source_id": "gov_overseas_warehouse_tax_2025",
        "url": "https://www.gov.cn/zhengce/zhengceku/202501/content_7001563.htm",
        "published_at": "2025-01-28",
        "publisher": "国家税务总局",
    },
    {
        "source_id": "gov_customs_export_2024",
        "url": "https://www.gov.cn/zhengce/zhengceku/202411/content_6989668.htm",
        "published_at": "2024-11-28",
        "publisher": "海关总署",
    },
    {
        "source_id": "gov_import_list_2022",
        "url": "https://www.gov.cn/zhengce/zhengceku/2022-02/21/content_5674854.htm",
        "published_at": "2022-02-21",
        "publisher": "财政部 发展改革委 工业和信息化部 生态环境部 农业农村部 "
        "商务部 海关总署 濒危物种进出口管理办公室",
    },
    {
        "source_id": "gov_retail_supervision_2018",
        "url": "https://www.gov.cn/zhengce/zhengceku/2018-12/31/content_5447414.htm",
        "published_at": "2018-12-31",
        "publisher": "海关总署",
    },
]


def clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u200b", "").replace("\xa0", " ")).strip()


def dedupe_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    for raw in lines:
        line = clean_line(raw)
        if not line:
            continue
        if result and line == result[-1]:
            continue
        result.append(line)
    return result


def fetch_text(url: str, session: requests.Session) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=45)
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == "iso-8859-1":
                response.encoding = response.apparent_encoding
            return response.text
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch {url}: {last_error}")


def fetch_bytes(url: str, session: requests.Session) -> bytes:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            return response.content
        except Exception as exc:
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Unable to download {url}: {last_error}")


def article_title(soup: BeautifulSoup, suffix: str = "") -> str:
    if not soup.title:
        return "Untitled"
    value = clean_line(soup.title.get_text(" ", strip=True))
    if suffix and suffix in value:
        value = value.split(suffix, 1)[0]
    return value


def extract_amazon(text: str) -> tuple[str, str]:
    soup = BeautifulSoup(text, "html.parser")
    title = article_title(soup, "_Amazon亚马逊")
    candidates = soup.select("div.has-max-width")
    container = None
    article_candidates: list[tuple[int, Any]] = []
    for candidate in candidates:
        candidate_text = clean_line(candidate.get_text(" ", strip=True))
        if len(candidate_text) < 800:
            continue
        if "新手开店" in candidate_text[:30]:
            continue
        if not re.search(r"20\d{2}年\d{1,2}月\d{1,2}日", candidate_text):
            continue
        article_candidates.append((len(candidate_text), candidate))
    if article_candidates:
        article_candidates.sort(key=lambda item: item[0], reverse=True)
        container = article_candidates[0][1]
    if container is None:
        raise ValueError(f"Amazon article body not found for {title}")
    lines = dedupe_lines(container.get_text("\n").splitlines())
    if len(" ".join(lines)) < 500:
        raise ValueError(f"Amazon article body too short for {title}")
    return title, "\n\n".join(lines)


def extract_ebay(text: str) -> tuple[str, str]:
    soup = BeautifulSoup(text, "html.parser")
    title = article_title(soup)
    if "Security Measure" in title:
        raise ValueError("eBay returned a captcha page")
    main = soup.select_one("main") or soup.select_one("#mainContent")
    if main is None:
        raise ValueError(f"eBay main content missing for {title}")
    blocks = main.select("h1, h2, h3, p, li")
    start = 0
    for index, block in enumerate(blocks):
        if block.name == "h1":
            start = index
            break
    lines = dedupe_lines([block.get_text(" ", strip=True) for block in blocks[start:]])
    if len(" ".join(lines)) < 500:
        raise ValueError(f"eBay article body too short for {title}")
    return title, "\n\n".join(lines)


def extract_gov(text: str, page_url: str) -> tuple[BeautifulSoup, str, str, list[str]]:
    soup = BeautifulSoup(text, "html.parser")
    title = article_title(soup, "_国务院部门文件_中国政府网")
    container = (
        soup.select_one(".pages_content.mhide")
        or soup.select_one(".pages_content")
        or soup.select_one(".TRS_Editor")
    )
    if container is None:
        raise ValueError(f"Government article body not found for {title}")
    lines = dedupe_lines(container.get_text("\n").splitlines())
    if len(" ".join(lines)) < 100:
        raise ValueError(f"Government article body too short for {title}")
    pdf_urls: list[str] = []
    for anchor in soup.select("a[href]"):
        href = urljoin(page_url, anchor.get("href", ""))
        if ".pdf" in href.lower() and href not in pdf_urls:
            pdf_urls.append(href)
    return soup, title, "\n\n".join(lines), pdf_urls


def write_markdown(
    source_id: str,
    title: str,
    body: str,
    url: str,
    publisher: str,
    published_at: str,
    lang: str,
) -> Path:
    target = HTML_DIR / f"{source_id}.md"
    content = (
        "---\n"
        f"source_id: {source_id}\n"
        f"title: {json.dumps(title, ensure_ascii=False)}\n"
        f"url: {url}\n"
        f"publisher: {json.dumps(publisher, ensure_ascii=False)}\n"
        f"published_at: {published_at}\n"
        f"captured_at: {CAPTURED_AT}\n"
        f"lang: {lang}\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{body}\n"
    )
    target.write_text(content, encoding="utf-8")
    return target


def render_pdf_from_body(
    source_id: str, title: str, body: str, url: str, publisher: str
) -> Path:
    target = PDF_DIR / f"{source_id}.pdf"
    if not EDGE.exists():
        raise FileNotFoundError(f"Microsoft Edge not found: {EDGE}")
    paragraphs = "\n".join(
        f"<p>{html.escape(line)}</p>" for line in body.splitlines() if line.strip()
    )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
@page {{ size: A4; margin: 18mm; }}
body {{ font-family: "Microsoft YaHei", SimSun, sans-serif; font-size: 10.5pt; line-height: 1.65; color: #111; }}
h1 {{ font-size: 18pt; line-height: 1.35; }}
p {{ margin: 0 0 7pt; }}
.meta {{ color: #555; margin-bottom: 16pt; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p class="meta">{html.escape(publisher)}<br>{html.escape(url)}</p>
{paragraphs}
</body>
</html>"""
    with tempfile.TemporaryDirectory(
        prefix="official_pdf_",
        dir=ROOT,
        ignore_cleanup_errors=True,
    ) as temp_dir:
        temp = Path(temp_dir)
        html_path = temp / "source.html"
        html_path.write_text(document, encoding="utf-8")
        log_path = temp / "edge.log"
        command = [
            str(EDGE),
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={temp / 'profile'}",
            f"--print-to-pdf={target}",
            html_path.as_uri(),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        log_path.write_text(
            (completed.stdout or "") + "\n" + (completed.stderr or ""),
            encoding="utf-8",
        )
        for _ in range(120):
            if target.exists() and target.stat().st_size > 4:
                break
            time.sleep(0.5)
    if not target.exists() or target.read_bytes()[:4] != b"%PDF":
        details = (completed.stdout or "") + "\n" + (completed.stderr or "")
        raise RuntimeError(f"PDF rendering failed for {source_id}: {details[-1000:]}")
    return target


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "docs").mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    new_records: list[dict[str, Any]] = []

    for source in AMAZON_SOURCES:
        print(f"Fetching {source['source_id']}")
        title, body = extract_amazon(fetch_text(source["url"], session))
        path = write_markdown(
            source["source_id"],
            title,
            body,
            source["url"],
            "Amazon",
            source["published_at"],
            "zh",
        )
        new_records.append(
            {
                "source_id": source["source_id"],
                "title": title,
                "source": path.name,
                "kind": "html",
                "format": "markdown",
                "lang": "zh",
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "url": source["url"],
                "publisher": "Amazon",
                "authority": "primary",
                "published_at": source["published_at"],
                "updated_at": source["published_at"],
                "captured_at": CAPTURED_AT,
                "page_unit": "section",
                "sha256": sha256(path),
                "content_chars": len(body),
                "quality_notes": "Amazon 官方正文；图片内文字需后续 OCR 才能检索。",
            }
        )

    for source in EBAY_SOURCES:
        print(f"Fetching {source['source_id']}")
        title, body = extract_ebay(fetch_text(source["url"], session))
        path = write_markdown(
            source["source_id"],
            title,
            body,
            source["url"],
            "eBay",
            "",
            "en",
        )
        new_records.append(
            {
                "source_id": source["source_id"],
                "title": title,
                "source": path.name,
                "kind": "html",
                "format": "markdown",
                "lang": "en",
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "url": source["url"],
                "publisher": "eBay",
                "authority": "primary",
                "published_at": "",
                "updated_at": CAPTURED_AT,
                "captured_at": CAPTURED_AT,
                "page_unit": "section",
                "sha256": sha256(path),
                "content_chars": len(body),
                "quality_notes": "eBay 官方政策正文；页面未提供明确发布日期。",
            }
        )

    for source in GOV_SOURCES:
        print(f"Fetching {source['source_id']}")
        _soup, title, body, pdf_urls = extract_gov(
            fetch_text(source["url"], session),
            source["url"],
        )
        if pdf_urls:
            path = PDF_DIR / f"{source['source_id']}.pdf"
            path.write_bytes(fetch_bytes(pdf_urls[0], session))
            if path.read_bytes()[:4] != b"%PDF":
                raise RuntimeError(f"Downloaded file is not a PDF: {pdf_urls[0]}")
            pdf_origin = "official_attachment"
        else:
            path = render_pdf_from_body(
                source["source_id"],
                title,
                body,
                source["url"],
                source["publisher"],
            )
            pdf_origin = "rendered_from_official_page"
        pdf_reader = PdfReader(str(path))
        page_count = len(pdf_reader.pages)
        content_chars = sum(
            len((page.extract_text() or "").strip()) for page in pdf_reader.pages
        )
        new_records.append(
            {
                "source_id": source["source_id"],
                "title": title,
                "source": path.name,
                "kind": "pdf",
                "format": "pdf",
                "lang": "zh",
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "url": source["url"],
                "publisher": source["publisher"],
                "authority": "primary",
                "published_at": source["published_at"],
                "updated_at": source["published_at"],
                "captured_at": CAPTURED_AT,
                "page_unit": "page",
                "sha256": sha256(path),
                "page_count": page_count,
                "content_chars": content_chars,
                "pdf_origin": pdf_origin,
                "quality_notes": "中国政府网公开政策正文；PDF 为官方附件或官方正文快照。",
            }
        )

    existing: list[dict[str, Any]] = []
    if MANIFEST.exists():
        existing = [
            json.loads(line)
            for line in MANIFEST.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    merged = [
        record
        for record in existing
        if not record["source_id"].startswith(("amazon_", "ebay_", "gov_"))
    ]
    merged.extend(new_records)
    merged.sort(key=lambda record: record["source_id"])
    MANIFEST.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in merged) + "\n",
        encoding="utf-8",
    )

    summary_lines = [
        "# Official Source Snapshot",
        "",
        f"Captured at: {CAPTURED_AT}",
        "",
        "| Source ID | Publisher | Title | URL | Local file |",
        "|---|---|---|---|---|",
    ]
    for record in sorted(new_records, key=lambda item: item["source_id"]):
        title = record.get("title", record["source_id"])
        summary_lines.append(
            f"| `{record['source_id']}` | {record['publisher']} | "
            f"{title.replace('|', '/')} | {record['url']} | `{record['path']}` |"
        )
    SUMMARY.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for record in merged:
        counts[record["kind"]] = counts.get(record["kind"], 0) + 1
    print(f"Completed: {len(new_records)} official sources")
    print(f"Manifest counts: {counts}")


if __name__ == "__main__":
    main()
