"""Turn Arabic books (PDF / images) into clean page text.

Engines:
  - "claude": Claude vision. Best quality for Arabic (diacritics, ligatures, two-column layouts).
  - "tesseract": offline and free, noticeably weaker on Arabic. Needs the Tesseract binary + 'ara' data.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif"}
CLAUDE_MODEL = "claude-opus-5-5"
RENDER_DPI = 200
MAX_IMAGE_SIDE = 2400  # keep page images a sensible size for the vision model

OCR_PROMPT = """This is a page scanned from an Arabic book. Transcribe it so it can be read aloud by a text-to-speech engine.

Rules:
- Output ONLY the transcribed text, nothing else (no commentary, no markdown, no code fences).
- Keep the original Arabic exactly, including any diacritics (tashkeel) that are printed. Do not add or remove words, and do not translate.
- Follow the natural reading order (right to left; for two columns, read the right column first).
- Skip running headers, page numbers, and decorative elements. Put footnotes at the end, after a line containing only "---".
- Keep paragraph breaks as blank lines. Join lines that a paragraph was merely wrapped across.
- If the page is blank or has no readable text, output nothing."""


@dataclass
class Page:
    number: int          # 1-based page number within the source
    png: bytes | None    # rendered page image (None if text came from the PDF text layer)
    text: str = ""


def load_pages(path: str | Path, first: int = 1, last: int | None = None) -> list[Page]:
    """Load a PDF or an image as a list of page images (1-based, inclusive range)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _load_pdf(path.read_bytes(), first, last)
    if ext in IMAGE_EXTS:
        return _load_image(path.read_bytes())
    raise ValueError(f"Unsupported file type: {ext}")


def load_pages_from_bytes(data: bytes, filename: str, first: int = 1, last: int | None = None) -> list[Page]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _load_pdf(data, first, last)
    if ext in IMAGE_EXTS:
        return _load_image(data)
    raise ValueError(f"Unsupported file type: {ext}")


def pdf_page_count(data: bytes) -> int:
    pdf = pdfium.PdfDocument(data)
    try:
        return len(pdf)
    finally:
        pdf.close()


def _load_pdf(data: bytes, first: int, last: int | None) -> list[Page]:
    pages = []
    pdf = pdfium.PdfDocument(data)
    try:
        last = min(last or len(pdf), len(pdf))
        for i in range(max(first, 1) - 1, last):
            img = pdf[i].render(scale=RENDER_DPI / 72).to_pil()
            pages.append(Page(number=i + 1, png=_to_png(img)))
    finally:
        pdf.close()
    return pages


def _load_image(data: bytes) -> list[Page]:
    """Images (including multi-frame TIFFs) -> one Page per frame."""
    pages = []
    with Image.open(io.BytesIO(data)) as img:
        for frame in range(getattr(img, "n_frames", 1)):
            img.seek(frame)
            pages.append(Page(number=frame + 1, png=_to_png(img.convert("RGB"))))
    return pages


def _to_png(img: Image.Image) -> bytes:
    """Downscale oversized pages and encode as PNG."""
    if max(img.size) > MAX_IMAGE_SIDE:
        img = img.copy()
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- engines

class ClaudeOCR:
    def __init__(self):
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic()

    def __call__(self, png: bytes) -> str:
        response = self.client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            # Server-side fallback: if the request is declined, the API retries it on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.standard_b64encode(png).decode("ascii"),
                    }},
                    {"type": "text", "text": OCR_PROMPT},
                ],
            }],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"OCR request was declined (request id {response._request_id})")
        return "".join(b.text for b in response.content if b.type == "text").strip()


class TesseractOCR:
    def __init__(self):
        import pytesseract

        self.pytesseract = pytesseract
        if "ara" not in pytesseract.get_languages():
            raise RuntimeError("Tesseract is installed but the Arabic ('ara') language data is missing.")

    def __call__(self, png: bytes) -> str:
        with Image.open(io.BytesIO(png)) as img:
            return self.pytesseract.image_to_string(img, lang="ara", config="--psm 6").strip()


def get_engine(name: str):
    if name == "claude":
        return ClaudeOCR()
    if name == "tesseract":
        return TesseractOCR()
    raise ValueError(f"Unknown OCR engine: {name}")
