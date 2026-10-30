"""Parse source files, clean their text and build retrieval chunks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml
from pptx import Presentation
from pypdf import PdfReader

from src.config import (
    DEFAULT_CHUNKS_PATH,
    FIXED_MAX_CHARS,
    MANIFEST_PATH,
    PROCESSED_DIR,
    ROOT,
    SEMANTIC_MAX_CHARS,
    SEMANTIC_OVERLAP,
)
from src.schemas import Chunk, ExtractedUnit


TEMPLATE_PATTERNS = (
    re.compile(r"第一PPT", re.IGNORECASE),
    re.compile(r"1ppt\.com", re.IGNORECASE),
    re.compile(r"模板来自"),
    re.compile(r"制作人\s*[:：]"),
    re.compile(r"汇报人\s*[:：]"),
    re.compile(r"在此输入公司名称"),
    re.compile(r"感谢各位?的?聆听"),
    re.compile(r"^感谢[！!]?$"),
    re.compile(r"^CONTENTS$", re.IGNORECASE),
)
NAVIGATION_LINES = {
    "Home",
    "Customer Service",
    "Suggested Articles",
    "Suggested queries",
    "On this page",
    "Go to Help home",
    "Recently Viewed",
    "Summary",
    "Skip to main content",
}
NAVIGATION_PATTERNS = (
    re.compile(r"^\d+\s*(?:min|mins|minute|minutes)\s+article$", re.IGNORECASE),
    re.compile(r"^This is search service rlogid", re.IGNORECASE),
    re.compile(r"^Search service rlogid\s*=", re.IGNORECASE),
)
SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+")


def normalize_text(value: str) -> str:
    """Normalize Unicode, whitespace and common invisible characters."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\u200b", "").replace("\xa0", " ")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line)


def is_template_line(line: str) -> bool:
    return any(
        pattern.search(line)
        for pattern in (*TEMPLATE_PATTERNS, *NAVIGATION_PATTERNS)
    )


def clean_lines(
    lines: Iterable[str],
    *,
    kind: str = "",
    source_id: str = "",
) -> list[str]:
    """Remove boilerplate and unsafe slide advice while preserving content order."""
    result: list[str] = []
    for raw in lines:
        line = normalize_text(raw).strip()
        if not line or line in NAVIGATION_LINES or is_template_line(line):
            continue
        if len(line) <= 3 and line.isdigit():
            continue
        if kind == "ppt" and source_id == "ppt_04_compliance":
            if "好评返现" in line or "返现券" in line:
                continue
        if result and result[-1] == line:
            continue
        result.append(line)
    return result


def clean_text(value: str, *, kind: str = "", source_id: str = "") -> str:
    return "\n".join(clean_lines(value.splitlines(), kind=kind, source_id=source_id))


def parse_front_matter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) != 3:
        return {}, text
    metadata = yaml.safe_load(parts[1]) or {}
    return metadata, parts[2].strip()


def extract_pptx(record: dict[str, Any]) -> list[ExtractedUnit]:
    path = ROOT / record["path"]
    presentation = Presentation(str(path))
    units: list[ExtractedUnit] = []

    for slide_number, slide in enumerate(presentation.slides, 1):
        if slide_number == 1:
            continue
        lines: list[str] = []
        title = ""
        if slide.shapes.title and slide.shapes.title.text.strip():
            title = normalize_text(slide.shapes.title.text).splitlines()[0]

        for shape in slide.shapes:
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [
                        normalize_text(cell.text).replace("\n", " ")
                        for cell in row.cells
                    ]
                    if any(cells):
                        lines.append(" | ".join(cells))
                continue
            if getattr(shape, "has_text_frame", False):
                lines.extend(shape.text_frame.text.splitlines())

        cleaned = clean_lines(
            lines,
            kind="ppt",
            source_id=record["source_id"],
        )
        if title:
            cleaned = [line for line in cleaned if line != title]
        body = "\n".join(cleaned)
        if len(re.sub(r"\s", "", body)) < 20:
            continue
        if any(
            phrase in body
            for phrase in ("目录", "开店流程", "安全经营", "总结")
        ) and len(body) < 50:
            continue
        text = f"{title}\n{body}".strip() if title else body
        units.append(
            ExtractedUnit(
                source_id=record["source_id"],
                source=record["source"],
                title=record.get("title", record["source"]),
                kind="ppt",
                lang=record["lang"],
                page=slide_number,
                page_label=f"s{slide_number:02d}",
                section_title=title or f"Slide {slide_number}",
                text=text,
                url=record.get("url", ""),
                updated_at=record["updated_at"],
                authority=record["authority"],
            )
        )
    return units


def split_markdown_sections(body: str) -> list[tuple[str, str]]:
    current_title = ""
    current_lines: list[str] = []
    sections: list[tuple[str, str]] = []
    heading_pattern = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
    for line in body.splitlines():
        match = heading_pattern.match(line)
        if match:
            text = "\n".join(current_lines).strip()
            if text:
                sections.append((current_title, text))
            current_title = match.group(2).strip()
            current_lines = []
            continue
        current_lines.append(line)
    text = "\n".join(current_lines).strip()
    if text:
        sections.append((current_title, text))
    return sections


def extract_markdown(record: dict[str, Any]) -> list[ExtractedUnit]:
    path = ROOT / record["path"]
    metadata, body = parse_front_matter(path)
    if record["source_id"].startswith("ebay_"):
        cutoff = len(body)
        for index, line in enumerate(body.splitlines()):
            lowered = line.strip().lower()
            if (
                lowered.startswith("was this article helpful")
                or lowered.startswith("you might also be interested in")
            ):
                cutoff = len("\n".join(body.splitlines()[:index]))
                break
        body = body[:cutoff]
    sections = split_markdown_sections(body)
    units: list[ExtractedUnit] = []
    section_index = 0

    for section_title, raw_section in sections:
        lines = clean_lines(raw_section.splitlines())
        text = "\n".join(lines)
        if len(re.sub(r"\s", "", text)) < 50:
            continue
        section_index += 1
        units.append(
            ExtractedUnit(
                source_id=record["source_id"],
                source=record["source"],
                title=metadata.get("title", record.get("title", record["source"])),
                kind="html",
                lang=record["lang"],
                page=None,
                page_label=f"sec{section_index:02d}",
                section_title=section_title or "Document",
                text=text,
                url=record.get("url", ""),
                updated_at=record["updated_at"],
                authority=record["authority"],
            )
        )

    if not units:
        text = clean_text(body)
        if len(re.sub(r"\s", "", text)) >= 50:
            units.append(
                ExtractedUnit(
                    source_id=record["source_id"],
                    source=record["source"],
                    title=metadata.get("title", record.get("title", record["source"])),
                    kind="html",
                    lang=record["lang"],
                    page=None,
                    page_label="sec01",
                    section_title="Document",
                    text=text,
                    url=record.get("url", ""),
                    updated_at=record["updated_at"],
                    authority=record["authority"],
                )
            )
    return units


def extract_pdf(record: dict[str, Any]) -> list[ExtractedUnit]:
    path = ROOT / record["path"]
    reader = PdfReader(str(path))
    units: list[ExtractedUnit] = []
    for page_number, page in enumerate(reader.pages, 1):
        text = clean_text(page.extract_text() or "")
        if len(re.sub(r"\s", "", text)) < 30:
            continue
        units.append(
            ExtractedUnit(
                source_id=record["source_id"],
                source=record["source"],
                title=record.get("title", record["source"]),
                kind="pdf",
                lang=record["lang"],
                page=page_number,
                page_label=f"p{page_number:02d}",
                section_title=f"Page {page_number}",
                text=text,
                url=record.get("url", ""),
                updated_at=record["updated_at"],
                authority=record["authority"],
            )
        )
    return units


def sentence_units(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    for paragraph in re.split(r"\n{2,}", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            pieces.append(paragraph)
            continue
        sentences = [part.strip() for part in SENTENCE_BOUNDARY.split(paragraph)]
        for sentence in sentences:
            if not sentence:
                continue
            if len(sentence) <= max_chars:
                pieces.append(sentence)
            else:
                pieces.extend(
                    sentence[start : start + max_chars]
                    for start in range(0, len(sentence), max_chars)
                )
    return pieces


def split_semantic(text: str, max_chars: int, overlap: int) -> list[str]:
    pieces = sentence_units(text, max_chars)
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for piece in pieces:
        addition = len(piece) + (1 if current else 0)
        if current and current_length + addition > max_chars:
            chunks.append("\n".join(current).strip())
            tail_budget = max(0, max_chars - len(piece) - 1)
            tail = chunks[-1][-min(overlap, tail_budget) :] if tail_budget else ""
            current = [tail, piece] if tail else [piece]
            current_length = len("\n".join(current))
        else:
            current.append(piece)
            current_length += addition
    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def split_fixed(text: str, max_chars: int) -> list[str]:
    return [
        text[start : start + max_chars].strip()
        for start in range(0, len(text), max_chars)
        if text[start : start + max_chars].strip()
    ]


def build_chunks(
    units: list[ExtractedUnit],
    strategy: str,
    max_chars: int,
    overlap: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for unit in units:
        if strategy == "fixed":
            pieces = split_fixed(unit.text, max_chars)
        else:
            pieces = split_semantic(unit.text, max_chars, overlap)
        for index, text in enumerate(pieces, 1):
            chunks.append(
                Chunk(
                    chunk_id=f"{unit.source_id}#{unit.page_label}#c{index:02d}",
                    source_id=unit.source_id,
                    source=unit.source,
                    title=unit.title,
                    kind=unit.kind,
                    lang=unit.lang,
                    page=unit.page,
                    page_label=unit.page_label,
                    section_title=unit.section_title,
                    text=text,
                    url=unit.url,
                    updated_at=unit.updated_at,
                    authority=unit.authority,
                    strategy=strategy,
                    chunk_index=index,
                    metadata={
                        "max_chars": max_chars,
                        "overlap": overlap if strategy != "fixed" else 0,
                    },
                )
            )
    return chunks


def write_jsonl(path: Path, chunks: list[Chunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        json.dumps(chunk.to_dict(), ensure_ascii=False) for chunk in chunks
    )
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def build_report(
    chunks: list[Chunk],
    units: list[ExtractedUnit],
    strategy: str,
    output_path: Path,
) -> dict[str, Any]:
    lengths = [len(chunk.text) for chunk in chunks]
    by_source = Counter(chunk.source_id for chunk in chunks)
    printable = "\n".join(chunk.text for chunk in chunks)
    digest = hashlib.sha256(printable.encode("utf-8")).hexdigest()
    return {
        "strategy": strategy,
        "output": str(output_path.relative_to(ROOT)).replace("\\", "/"),
        "units": len(units),
        "chunks": len(chunks),
        "sources": len(by_source),
        "chunks_by_source": dict(sorted(by_source.items())),
        "min_chars": min(lengths) if lengths else 0,
        "max_chars": max(lengths) if lengths else 0,
        "mean_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "content_sha256": digest,
    }


def ingest(
    manifest_path: Path,
    output_path: Path,
    strategy: str,
    max_chars: int,
    overlap: int,
) -> dict[str, Any]:
    records = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    units: list[ExtractedUnit] = []
    for record in records:
        if record["kind"] == "ppt":
            units.extend(extract_pptx(record))
        elif record["kind"] == "html":
            units.extend(extract_markdown(record))
        elif record["kind"] == "pdf":
            units.extend(extract_pdf(record))
        else:
            raise ValueError(f"Unsupported source kind: {record['kind']}")
    chunks = build_chunks(units, strategy, max_chars, overlap)
    write_jsonl(output_path, chunks)
    return build_report(chunks, units, strategy, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument(
        "--strategy",
        choices=("semantic", "fixed"),
        default="semantic",
    )
    parser.add_argument("--max-chars", type=int)
    parser.add_argument("--overlap", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    if args.strategy == "fixed":
        max_chars = args.max_chars or FIXED_MAX_CHARS
        overlap = 0
    else:
        max_chars = args.max_chars or SEMANTIC_MAX_CHARS
        overlap = args.overlap if args.overlap is not None else SEMANTIC_OVERLAP
    report = ingest(
        args.manifest,
        output_path,
        args.strategy,
        max_chars,
        overlap,
    )
    report_path = PROCESSED_DIR / f"ingest_report_{args.strategy}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
