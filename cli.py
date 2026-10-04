"""Command line: OCR an Arabic book and turn it into an MP3.

  python cli.py book.pdf --pages 1-20 --voice <voice_id>
  python cli.py page.jpg --text-only
  python cli.py --list-voices
"""
from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from ocr import load_pages  # noqa: E402
from pipeline import for_speech, ocr_pages  # noqa: E402
from tts import ElevenLabs  # noqa: E402


def bar(label):
    return lambda i, n: print(f"\r{label}: {i}/{n}", end="\n" if i == n else "", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file", nargs="?")
    p.add_argument("--pages", help="page range for PDFs, e.g. 5-12")
    p.add_argument("--engine", choices=["claude", "tesseract"], default="claude")
    p.add_argument("--voice", help="ElevenLabs voice id (or ELEVENLABS_VOICE_ID)")
    p.add_argument("--model", help="ElevenLabs model id (default: newest Arabic-capable, e.g. eleven_v4)")
    p.add_argument("--text-only", action="store_true", help="only OCR, skip audio")
    p.add_argument("--list-voices", action="store_true")
    args = p.parse_args()

    if args.list_voices:
        for v in ElevenLabs().voices():
            print(f"{v['voice_id']}  {v['name']}")
        return
    if not args.file:
        p.error("file is required")

    first, last = 1, None
    if args.pages:
        a, _, b = args.pages.partition("-")
        first, last = int(a), int(b or a)

    src = Path(args.file)
    pages = load_pages(src, first, last)
    ocr_pages(pages, args.engine, on_progress=bar("OCR"))

    text = "\n\n".join(pg.text for pg in pages if pg.text)
    txt_out = src.with_suffix(".txt")
    txt_out.write_text(text, encoding="utf-8")
    print(f"Text saved to {txt_out}")
    if args.text_only:
        return

    import os
    voice = args.voice or os.environ.get("ELEVENLABS_VOICE_ID")
    if not voice:
        p.error("pass --voice <id> or set ELEVENLABS_VOICE_ID (see --list-voices)")
    el = ElevenLabs()
    model = args.model or el.pick_model()
    print(f"Voice model: {model}")
    speech = "\n\n".join(for_speech(pg.text) for pg in pages if pg.text)
    audio = el.speak_long(speech, voice, model, on_progress=bar("Audio"))
    mp3_out = src.with_suffix(".mp3")
    mp3_out.write_bytes(audio)
    print(f"Audio saved to {mp3_out}")


if __name__ == "__main__":
    main()
