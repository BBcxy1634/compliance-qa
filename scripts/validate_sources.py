#!/usr/bin/env python3
"""Validate the local D1 source files and sources.jsonl manifest."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "raw" / "sources.jsonl"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    if not MANIFEST.exists():
        print(f"ERROR: manifest missing: {MANIFEST}")
        return 1

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        MANIFEST.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(errors, f"line {line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            fail(errors, f"line {line_number}: record is not an object")
            continue
        records.append(value)

    ids = [record.get("source_id") for record in records]
    if len(ids) != len(set(ids)):
        fail(errors, "source_id values are not unique")

    required = {
        "source_id",
        "title",
        "source",
        "kind",
        "lang",
        "path",
        "url",
        "publisher",
        "authority",
        "updated_at",
        "captured_at",
        "page_unit",
        "sha256",
    }
    for record in records:
        source_id = record.get("source_id", "<unknown>")
        missing = sorted(required - record.keys())
        if missing:
            fail(errors, f"{source_id}: missing fields: {', '.join(missing)}")
            continue
        if record["lang"] not in {"zh", "en", "mixed"}:
            fail(errors, f"{source_id}: unsupported lang {record['lang']!r}")
        path = (ROOT / record["path"]).resolve()
        if ROOT.resolve() not in path.parents:
            fail(errors, f"{source_id}: path escapes the project directory")
            continue
        if not path.exists():
            fail(errors, f"{source_id}: file missing: {record['path']}")
            continue
        if file_hash(path) != record["sha256"]:
            fail(errors, f"{source_id}: SHA256 mismatch")
        if record["kind"] in {"html", "pdf"}:
            parsed = urlparse(str(record["url"]))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                fail(errors, f"{source_id}: invalid source URL")
        if record["kind"] == "pdf":
            try:
                pages = len(PdfReader(str(path)).pages)
            except Exception as exc:
                fail(errors, f"{source_id}: cannot read PDF: {exc}")
            else:
                if pages < 1:
                    fail(errors, f"{source_id}: PDF has no pages")
                elif pages != record.get("page_count"):
                    fail(errors, f"{source_id}: page count mismatch")
                if not record.get("content_chars"):
                    fail(errors, f"{source_id}: PDF contains no extractable text")

    counts = Counter(record.get("kind") for record in records)
    expected = {"ppt": 7}
    for kind, count in expected.items():
        if counts[kind] != count:
            fail(errors, f"{kind}: expected {count}, found {counts[kind]}")
    if not 10 <= counts["html"] <= 15:
        fail(errors, f"html: expected 10-15, found {counts['html']}")
    if not 3 <= counts["pdf"] <= 5:
        fail(errors, f"pdf: expected 3-5, found {counts['pdf']}")

    for kind, directory, suffix in (
        ("ppt", ROOT / "data" / "raw" / "ppt", ".pptx"),
        ("html", ROOT / "data" / "raw" / "html", ".md"),
        ("pdf", ROOT / "data" / "raw" / "pdf", ".pdf"),
    ):
        actual = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in directory.glob(f"*{suffix}")
            if path.is_file()
        }
        registered = {
            record["path"] for record in records if record.get("kind") == kind
        }
        for path in sorted(actual - registered):
            fail(errors, f"unregistered {kind} file: {path}")
        for path in sorted(registered - actual):
            fail(errors, f"registered {kind} file missing: {path}")

    print(f"records={len(records)} counts={dict(counts)}")
    if errors:
        print("VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
