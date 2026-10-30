"""Embed semantic chunks with BGE-M3 and persist them in Chroma."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.config import DEFAULT_CHUNKS_PATH
from src.retrieve import build_vector_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--collection", default="bge_m3_semantic")
    parser.add_argument("--batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks_path = args.chunks if args.chunks.is_absolute() else Path.cwd() / args.chunks
    count = build_vector_index(
        chunks_path,
        collection_name=args.collection,
        batch_size=args.batch_size,
    )
    print(f"Indexed {count} chunks into collection {args.collection!r}")


if __name__ == "__main__":
    main()
