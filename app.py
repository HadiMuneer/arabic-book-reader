"""Web UI:  streamlit run app.py"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from ocr import load_pages_from_bytes, pdf_page_count  # noqa: E402
from pipeline import for_speech, ocr_pages  # noqa: E402
from tts import ElevenLabs  # noqa: E402

st.set_page_config(page_title="Arabic Book Reader", page_icon="📖", layout="wide")
st.markdown(
    """<style>
    textarea { direction: rtl; text-align: right; font-size: 1.15rem !important; line-height: 1.9 !important; }
    </style>""",
    unsafe_allow_html=True,
)
st.title("📖 Arabic Book Reader")

# ---------------------------------------------------------------- settings
with st.sidebar:
    st.header("Settings")
    anth_key = st.text_input("Anthropic API key", os.environ.get("ANTHROPIC_API_KEY", ""), type="password")
    el_key = st.text_input("ElevenLabs API key", os.environ.get("ELEVENLABS_API_KEY", ""), type="password")
    if anth_key:
        os.environ["ANTHROPIC_API_KEY"] = anth_key
    engine = st.radio("OCR engine", ["claude", "tesseract"],
                      format_func={"claude": "Claude vision (best for Arabic)",
                                   "tesseract": "Tesseract (offline, weaker)"}.get)

    voice_id = model_id = None
    if el_key:
        try:
            el = ElevenLabs(el_key)
            if "voices" not in st.session_state:
                st.session_state.voices = el.voices()
                st.session_state.models = el.arabic_models() or ["eleven_v4"]
            voices = {v["name"]: v["voice_id"] for v in st.session_state.voices}
            names = list(voices)
            default = next((i for i, n in enumerate(names)
                            if voices[n] == os.environ.get("ELEVENLABS_VOICE_ID")), 0)
            voice_id = voices[st.selectbox("Voice", names, index=default)]
            models = st.session_state.models
            forced = os.environ.get("ELEVENLABS_MODEL_ID")
            model_id = st.selectbox("Voice model", models, index=models.index(forced) if forced in models else 0)
        except Exception as e:
            st.error(f"ElevenLabs: {e}")

# ---------------------------------------------------------------- input
upload = st.file_uploader("Upload a book (PDF) or page images",
                          type=["pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"])
if not upload:
    st.info("Upload a PDF or an image of a page to start.")
    st.stop()

data = upload.getvalue()
first, last = 1, None
if upload.name.lower().endswith(".pdf"):
    total = pdf_page_count(data)
    c1, c2 = st.columns(2)
    first = c1.number_input("From page", 1, total, 1)
    last = c2.number_input("To page", first, total, min(first + 9, total))
    st.caption(f"{total} pages in this PDF. Start small: OCR costs per page.")

doc_key = (upload.name, len(data), first, last, engine)
if st.button("1 · Extract text", type="primary"):
    pages = load_pages_from_bytes(data, upload.name, first, last)
    progress = st.progress(0.0, "Reading pages…")
    try:
        ocr_pages(pages, engine, on_progress=lambda i, n: progress.progress(i / n, f"Page {i}/{n}"))
    except Exception as e:
        st.error(f"OCR failed: {e}")
        st.stop()
    st.session_state.doc_key = doc_key
    st.session_state.pages = pages
    st.session_state.audio = {}
    st.session_state.book_audio = None

if st.session_state.get("doc_key") != doc_key:
    st.stop()

pages = st.session_state.pages

# ---------------------------------------------------------------- review + read
st.subheader("2 · Review the text")
st.caption("Fix any OCR mistakes before generating audio. Text after a '---' line (footnotes) is not read aloud.")
for page in pages:
    left, right = st.columns([1, 2])
    with left:
        st.image(page.png, caption=f"Page {page.number}", use_container_width=True)
    with right:
        page.text = st.text_area(f"Page {page.number}", page.text, height=420, key=f"t{page.number}")
        if voice_id and st.button("🔊 Read this page", key=f"a{page.number}"):
            with st.spinner("Generating audio…"):
                try:
                    st.session_state.audio[page.number] = ElevenLabs(el_key).speak_long(
                        for_speech(page.text), voice_id, model_id)
                except Exception as e:
                    st.error(str(e))
        if page.number in st.session_state.audio:
            st.audio(st.session_state.audio[page.number], format="audio/mp3")

full_text = "\n\n".join(p.text for p in pages if p.text.strip())
st.download_button("⬇ Download text (.txt)", full_text, file_name=Path(upload.name).stem + ".txt")

st.subheader("3 · Read the whole selection")
if not voice_id:
    st.warning("Add your ElevenLabs API key in the sidebar to generate audio.")
elif st.button("🎧 Generate audiobook", type="primary"):
    speech = "\n\n".join(for_speech(p.text) for p in pages if p.text.strip())
    st.caption(f"{len(speech):,} characters will be sent to ElevenLabs ({model_id}).")
    progress = st.progress(0.0, "Generating…")
    try:
        st.session_state.book_audio = ElevenLabs(el_key).speak_long(
            speech, voice_id, model_id, on_progress=lambda i, n: progress.progress(i / n, f"Chunk {i}/{n}"))
    except Exception as e:
        st.error(str(e))

if st.session_state.get("book_audio"):
    st.audio(st.session_state.book_audio, format="audio/mp3")
    st.download_button("⬇ Download audiobook (.mp3)", st.session_state.book_audio,
                       file_name=Path(upload.name).stem + ".mp3", mime="audio/mpeg")
