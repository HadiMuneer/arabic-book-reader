"""ElevenLabs text-to-speech for long Arabic text."""
from __future__ import annotations

import os
import re

import requests

API = "https://api.elevenlabs.io/v1"
PREFERRED_MODELS = ["eleven_v4", "eleven_v3", "eleven_multilingual_v2"]  # newest first
CHUNK_CHARS = 3000  # well under every model's per-request limit; shorter chunks also start playing sooner
OUTPUT_FORMAT = "mp3_44100_128"


class ElevenLabs:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is not set")
        self.session = requests.Session()
        self.session.headers["xi-api-key"] = self.api_key

    def _get(self, path: str, **params):
        r = self.session.get(f"{API}{path}", params=params, timeout=60)
        _raise_for(r)
        return r.json()

    def voices(self) -> list[dict]:
        """[{voice_id, name, ...}] available to this account."""
        return self._get("/voices")["voices"]

    def arabic_models(self) -> list[str]:
        """TTS model ids that list Arabic, newest-preferred first."""
        ids = [
            m["model_id"] for m in self._get("/models")
            if m.get("can_do_text_to_speech")
            and any(l.get("language_id") in ("ar", "ara") or "arab" in l.get("name", "").lower()
                    for l in m.get("languages", []))
        ]
        ranked = [m for m in PREFERRED_MODELS if m in ids]
        return ranked + [m for m in ids if m not in ranked]

    def pick_model(self) -> str:
        if os.environ.get("ELEVENLABS_MODEL_ID"):
            return os.environ["ELEVENLABS_MODEL_ID"]
        models = self.arabic_models()
        return models[0] if models else PREFERRED_MODELS[0]

    def speak(self, text: str, voice_id: str, model_id: str) -> bytes:
        """One request -> MP3 bytes."""
        r = self.session.post(
            f"{API}/text-to-speech/{voice_id}",
            params={"output_format": OUTPUT_FORMAT},
            json={"text": text, "model_id": model_id},
            timeout=300,
        )
        _raise_for(r)
        return r.content

    def speak_long(self, text: str, voice_id: str, model_id: str, on_progress=None) -> bytes:
        """Split long text into chunks, synthesize each, and join the MP3s."""
        chunks = split_text(text)
        audio = []
        for i, chunk in enumerate(chunks, 1):
            audio.append(self.speak(chunk, voice_id, model_id))
            if on_progress:
                on_progress(i, len(chunks))
        return b"".join(audio)  # MP3 frames concatenate cleanly for playback


def _raise_for(r: requests.Response):
    if r.ok:
        return
    try:
        detail = r.json().get("detail")
    except ValueError:
        detail = r.text
    raise RuntimeError(f"ElevenLabs {r.status_code}: {detail}")


_SENTENCE_END = re.compile(r"(?<=[.!?؟।…:؛])\s+")


def split_text(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Split on paragraphs, then sentences, so no chunk exceeds `limit`; never cuts mid-word."""
    chunks, current = [], ""

    def push(piece: str):
        nonlocal current
        if len(current) + len(piece) + 1 <= limit:
            current = f"{current}\n{piece}" if current else piece
        else:
            if current:
                chunks.append(current)
            current = piece

    for para in (p.strip() for p in re.split(r"\n\s*\n", text)):
        if not para:
            continue
        if len(para) <= limit:
            push(para)
            continue
        for sentence in _SENTENCE_END.split(para):
            while len(sentence) > limit:  # pathological: a sentence longer than the limit
                cut = sentence.rfind(" ", 0, limit)
                cut = cut if cut > 0 else limit
                push(sentence[:cut])
                sentence = sentence[cut:].strip()
            if sentence:
                push(sentence)
    if current:
        chunks.append(current)
    return chunks
