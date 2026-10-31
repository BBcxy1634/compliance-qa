#!/usr/bin/env python3
"""Prepare the local corpus, chunks and vector collections."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args: str) -> None:
    command = [PYTHON, *args]
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def count_files(directory: Path, pattern: str) -> int:
    return len(list(directory.glob(pattern)))


def collection_count(name: str) -> int:
    import chromadb

    client = chromadb.PersistentClient(path=str(ROOT / "chroma_db"))
    try:
        return client.get_collection(name).count()
    except Exception:
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also build the B0 fixed-split collection used by ablation.",
    )
    parser.add_argument(
        "--with-reranker",
        action="store_true",
        help="Pre-download the B3 reranker model.",
    )
    parser.add_argument(
        "--force-embed",
        action="store_true",
        help="Rebuild Chroma collections even when counts match.",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Use existing official HTML/PDF files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if sys.version_info < (3, 10):
        raise RuntimeError("Python 3.10 or newer is required")

    html_count = count_files(ROOT / "data" / "raw" / "html", "*.md")
    pdf_count = count_files(ROOT / "data" / "raw" / "pdf", "*.pdf")
    if not args.skip_fetch and (html_count < 10 or pdf_count < 3):
        run("scripts/fetch_official_sources.py")

    run(
        "-m",
        "src.ingest",
        "--strategy",
        "semantic",
        "--output",
        "data/processed/chunks.jsonl",
    )
    run(
        "-m",
        "src.ingest",
        "--strategy",
        "fixed",
        "--max-chars",
        "512",
        "--output",
        "data/processed/chunks_b0.jsonl",
    )

    semantic_count = collection_count("bge_m3_semantic")
    if args.force_embed or semantic_count != 271:
        run(
            "-m",
            "src.embed",
            "--chunks",
            "data/processed/chunks.jsonl",
            "--collection",
            "bge_m3_semantic",
            "--batch-size",
            "8",
        )

    if args.full:
        b0_count = collection_count("bge_m3_b0")
        if args.force_embed or b0_count != 334:
            run(
                "-m",
                "src.embed",
                "--chunks",
                "data/processed/chunks_b0.jsonl",
                "--collection",
                "bge_m3_b0",
                "--batch-size",
                "8",
            )

    if args.with_reranker:
        run(
            "-c",
            "from huggingface_hub import snapshot_download; "
            "snapshot_download(repo_id='BAAI/bge-reranker-v2-m3')",
        )

    run("scripts/validate_sources.py")
    run("scripts/validate_eval.py")
    run("scripts/check_environment.py", "--require-data")
    print("Bootstrap completed.")


if __name__ == "__main__":
    main()
