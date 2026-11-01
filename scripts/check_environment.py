#!/usr/bin/env python3
"""Check installed dependencies and prepared RAG artifacts."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_MODULES = (
    "bs4",
    "chromadb",
    "gradio",
    "jieba",
    "openai",
    "pptx",
    "pypdf",
    "rank_bm25",
    "sentence_transformers",
    "torch",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-data", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    errors: list[str] = []
    warnings: list[str] = []
    modules: dict[str, str] = {}

    if sys.version_info < (3, 12):
        errors.append("Python 3.12 or newer is required")

    for name in REQUIRED_MODULES:
        try:
            module = importlib.import_module(name)
            modules[name] = getattr(module, "__version__", "ok")
        except Exception as exc:
            errors.append(f"missing dependency {name}: {exc}")

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key or api_key == "your_key":
        errors.append("DEEPSEEK_API_KEY is not configured in .env")

    manifest = ROOT / "data" / "raw" / "sources.jsonl"
    chunks = ROOT / "data" / "processed" / "chunks.jsonl"
    collection_counts: dict[str, int] = {}
    if args.require_data:
        if not manifest.exists():
            errors.append("data/raw/sources.jsonl is missing")
        if not chunks.exists():
            errors.append("data/processed/chunks.jsonl is missing")
        html_count = len(list((ROOT / "data" / "raw" / "html").glob("*.md")))
        pdf_count = len(list((ROOT / "data" / "raw" / "pdf").glob("*.pdf")))
        if html_count < 10:
            errors.append(f"official HTML sources are incomplete: {html_count}")
        if pdf_count < 3:
            errors.append(f"official PDF sources are incomplete: {pdf_count}")
        if chunks.exists():
            chunk_count = sum(
                1
                for line in chunks.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
            if not 200 <= chunk_count <= 400:
                errors.append(f"unexpected semantic chunk count: {chunk_count}")
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
            for name in ("bge_m3_semantic", "bge_m3_b0"):
                try:
                    collection_counts[name] = client.get_collection(name).count()
                except Exception:
                    collection_counts[name] = 0
            if collection_counts.get("bge_m3_semantic", 0) not in range(200, 401):
                errors.append("Chroma collection bge_m3_semantic is not ready")
            elif collection_counts.get("bge_m3_b0", 0) == 0:
                warnings.append("B0 collection is absent; use bootstrap.py --full")
        except Exception as exc:
            errors.append(f"cannot check Chroma: {exc}")

    try:
        import torch

        cuda_available = torch.cuda.is_available()
    except Exception:
        cuda_available = False

    report = {
        "python": sys.version.split()[0],
        "modules": modules,
        "deepseek_key_configured": bool(api_key and api_key != "your_key"),
        "cuda_available": cuda_available,
        "torch_device": os.getenv("TORCH_DEVICE", "auto"),
        "chunks": str(chunks.relative_to(ROOT)) if chunks.exists() else None,
        "collections": collection_counts,
        "errors": errors,
        "warnings": warnings,
    }
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Python: {report['python']}")
        print(
            "DeepSeek key: "
            + ("configured" if report["deepseek_key_configured"] else "missing")
        )
        print(f"CUDA: {'available' if cuda_available else 'not available'}")
        print(f"Torch device preference: {report['torch_device']}")
        print(f"Chroma collections: {collection_counts}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        for error in errors:
            print(f"ERROR: {error}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
