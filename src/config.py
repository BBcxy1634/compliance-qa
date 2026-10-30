"""Project paths and runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".cache"
HF_HOME = CACHE_DIR / "huggingface"
os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CHROMA_DIR = ROOT / "chroma_db"
MANIFEST_PATH = RAW_DIR / "sources.jsonl"
DEFAULT_CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
MODEL_CACHE_DIR = HF_HOME / "hub" / f"models--{EMBEDDING_MODEL.replace('/', '--')}"
if MODEL_CACHE_DIR.exists():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

EMBEDDING_MAX_SEQ_LENGTH = int(os.getenv("EMBEDDING_MAX_SEQ_LENGTH", "1024"))
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

DEFAULT_TOP_K = 5
SEMANTIC_MAX_CHARS = 800
SEMANTIC_OVERLAP = 64
FIXED_MAX_CHARS = 512


def resolve_embedding_model(model_name: str = EMBEDDING_MODEL) -> str:
    """Return the local snapshot when the configured model is already cached."""
    if model_name != EMBEDDING_MODEL:
        return model_name
    ref_path = MODEL_CACHE_DIR / "refs" / "main"
    if not ref_path.exists():
        return model_name
    ref = ref_path.read_text(encoding="utf-8").strip()
    snapshot = MODEL_CACHE_DIR / "snapshots" / ref
    return str(snapshot) if snapshot.exists() else model_name
