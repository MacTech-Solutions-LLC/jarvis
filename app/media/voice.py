"""The Jarvis voice — OpenAI text-to-speech with a fixed character.

`TextToSpeech` (app/media/tts.py) is the general-purpose TTS utility:
any voice, any model, writes a file. This module is narrower on
purpose. It defines how *Jarvis* sounds — one voice, one delivery
direction — and returns raw audio bytes so the Streamlit console can
play a reply without touching the filesystem.

OpenAI's `gpt-4o-mini-tts` accepts an `instructions` string that steers
delivery (pace, tone, affect). That is what makes this a character
rather than a voice picker. If the account cannot reach that model we
fall back to `tts-1-hd`, which ignores instructions but keeps the same
voice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx

from app.core.config import Config
from app.core.paths import Paths

# Deep and measured. Of OpenAI's voices this is the one that reads as a
# composed operations officer rather than a narrator or an assistant.
JARVIS_VOICE = "onyx"

# Steers delivery on gpt-4o-mini-tts. Kept short: long instruction
# blocks make the model over-perform and the result stops sounding
# like a colleague.
JARVIS_INSTRUCTIONS = (
    "Speak as a composed, competent operations officer briefing a "
    "colleague. Calm and precise, unhurried but never sluggish. Dry "
    "rather than cheerful — no exaggerated enthusiasm, no salesperson "
    "lilt. Land the ends of sentences with quiet confidence."
)

PRIMARY_MODEL = "gpt-4o-mini-tts"
FALLBACK_MODEL = "tts-1-hd"

# OpenAI's TTS endpoint rejects very long inputs. Spoken replies should
# be short anyway — a voice briefing that runs four minutes is a
# document, not a conversation.
MAX_INPUT_CHARS = 4000


class JarvisVoice:
    """Speaks as Jarvis. Returns MP3 bytes; optionally writes a file."""

    def __init__(self, config: Config, paths: Optional[Paths] = None):
        self.config = config
        self.paths = paths
        self.api_key = config.openai_api_key
        self.base_url = "https://api.openai.com/v1"

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def speak(
        self,
        text: str,
        speed: float = 1.0,
        instructions: Optional[str] = None,
    ) -> bytes:
        """Synthesize `text` in the Jarvis voice and return MP3 bytes."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured — Jarvis has no voice.")

        cleaned = _strip_for_speech(text)
        if not cleaned:
            raise ValueError("Nothing to speak.")
        if len(cleaned) > MAX_INPUT_CHARS:
            cleaned = cleaned[:MAX_INPUT_CHARS].rsplit(" ", 1)[0] + "…"

        payload = {
            "model": PRIMARY_MODEL,
            "input": cleaned,
            "voice": JARVIS_VOICE,
            "speed": speed,
            "instructions": instructions or JARVIS_INSTRUCTIONS,
            "response_format": "mp3",
        }

        with httpx.Client(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=90.0,
        ) as client:
            response = client.post(f"{self.base_url}/audio/speech", json=payload)

            # Older accounts / API versions may not have gpt-4o-mini-tts.
            # Retry once on the classic model, which has no `instructions`.
            if response.status_code in (400, 403, 404):
                fallback = {
                    "model": FALLBACK_MODEL,
                    "input": cleaned,
                    "voice": JARVIS_VOICE,
                    "speed": speed,
                    "response_format": "mp3",
                }
                response = client.post(f"{self.base_url}/audio/speech", json=fallback)

            response.raise_for_status()
            return response.content

    def speak_to_file(
        self,
        text: str,
        output_path: Optional[Path] = None,
        speed: float = 1.0,
    ) -> Path:
        """Synthesize and persist to disk. Used by the CLI."""
        audio = self.speak(text, speed=speed)

        if output_path is None:
            if self.paths is None:
                raise ValueError("No output path given and no Paths configured.")
            import time

            audio_dir = self.paths.data / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            output_path = audio_dir / f"jarvis_{int(time.time() * 1000)}.mp3"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio)
        return output_path


def _strip_for_speech(text: str) -> str:
    """Remove markdown scaffolding that a voice would read aloud badly.

    Code fences are dropped entirely — reading a shell command aloud
    character by character helps nobody, and the text is already on
    screen next to the audio.
    """
    import re

    without_code = re.sub(r"```.*?```", " (code omitted) ", text, flags=re.DOTALL)
    without_inline_code = re.sub(r"`([^`]*)`", r"\1", without_code)
    without_headers = re.sub(r"^#{1,6}\s*", "", without_inline_code, flags=re.MULTILINE)
    without_bullets = re.sub(r"^\s*[-*]\s+", "", without_headers, flags=re.MULTILINE)
    without_emphasis = re.sub(r"(\*\*|__|\*|_)", "", without_bullets)
    without_links = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", without_emphasis)
    collapsed = re.sub(r"\n{2,}", "\n", without_links)
    return collapsed.strip()
