"""Shared glue: OCR with an on-disk cache so re-runs never pay twice for the same page."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ocr import Page, get_engine

CACHE_DIR = Path(__file__).parent / "cache"


def ocr_pages(pages: list[Page], engine_name: str, on_progress=None) -> list[Page]:
    engine = None  # created lazily, so a fully cached book needs no API key
    CACHE_DIR.mkdir(exist_ok=True)
    for i, page in enumerate(pages, 1):
        key = hashlib.sha256(page.png + engine_name.encode()).hexdigest()[:32]
        cached = CACHE_DIR / f"{key}.txt"
        if cached.exists():
            page.text = cached.read_text(encoding="utf-8")
        else:
            engine = engine or get_engine(engine_name)
            page.text = engine(page.png)
            cached.write_text(page.text, encoding="utf-8")
        if on_progress:
            on_progress(i, len(pages))
    return pages


def for_speech(text: str) -> str:
    """Drop the footnotes block (after a '---' line) so the narrator doesn't read it."""
    return text.split("\n---\n", 1)[0].strip()
