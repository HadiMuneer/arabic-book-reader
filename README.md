# 📖 Arabic Book Reader

Turn Arabic books (scanned PDFs, photos of pages, TIFF scans) into text and listen to them in a natural voice.

<div dir="rtl">

**قارئ الكتب العربية**: حوّل الكتب العربية (ملفات PDF الممسوحة، صور الصفحات) إلى نص، ثم استمع إليها بصوت طبيعي باستخدام أحدث نماذج ElevenLabs.

</div>

## How it works

1. **OCR**: each page is rendered to an image and transcribed.
   - **Claude vision** (default): strong on Arabic. It keeps printed diacritics, handles ligatures and two-column layouts, skips headers and page numbers, and moves footnotes to the end of the page.
   - **Tesseract** (optional): free and offline, but noticeably weaker on Arabic.
2. **Review**: fix any mistakes in an editor that displays right to left.
3. **Speech**: the text is split at paragraph and sentence boundaries and read by [ElevenLabs](https://elevenlabs.io). By default the tool picks the newest model that supports Arabic (`eleven_v4`, falling back to `eleven_v3` / `eleven_multilingual_v2`).

OCR results are cached in `cache/`, so re-running the same pages costs nothing.

## Setup

Requires Python 3.10+.

```bash
git clone https://github.com/HadiMuneer/arabic-book-reader.git
cd arabic-book-reader
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then put your keys in .env
```

You need:
- an **Anthropic API key**: https://console.anthropic.com (for Claude OCR)
- an **ElevenLabs API key**: https://elevenlabs.io/app/settings/api-keys

## Usage

### Web app

```bash
streamlit run app.py
```

Upload a PDF or an image, choose a page range, click **Extract text**, correct the text if needed, then play a single page or generate the whole selection as one MP3.

### Command line

```bash
python cli.py --list-voices                          # find a voice id
python cli.py book.pdf --pages 1-20 --voice <id>     # -> book.txt + book.mp3
python cli.py page.jpg --text-only                   # OCR only
python cli.py book.pdf --engine tesseract --text-only
```

| Option | Meaning |
|---|---|
| `--pages 5-12` | PDF page range (1-based, inclusive) |
| `--engine claude\|tesseract` | OCR engine |
| `--voice <id>` | ElevenLabs voice (or set `ELEVENLABS_VOICE_ID`) |
| `--model <id>` | ElevenLabs model (or set `ELEVENLABS_MODEL_ID`) |

### Using Tesseract (offline OCR)

Install [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) together with the Arabic language data (`ara`), and make sure `tesseract` is on your PATH.

## Costs

Both APIs are paid services, billed per use:
- **Claude OCR**: roughly one image plus the page's text per page. Try a few pages first.
- **ElevenLabs**: billed per character against your plan's quota. The web app shows the character count before you generate.

Only process books you have the right to use.

## Project layout

```
ocr.py       PDF/image loading + OCR engines
tts.py       ElevenLabs client, model picking, text chunking
pipeline.py  OCR cache, footnote stripping
app.py       Streamlit web UI
cli.py       command-line interface
```

## License

MIT
