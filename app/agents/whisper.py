"""Whisper transcription node."""

import logging
import time

from openai import AsyncOpenAI

from app.agents.ai_logger import log_whisper_call
from app.agents.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

# Telegram sends voice as OGG Opus
_MIME_TYPES = {
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "webm": "audio/webm",
    "flac": "audio/flac",
}


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def transcribe_audio(audio_data: bytes, filename: str = "voice.ogg", user_id: int = 0) -> str:
    """Transcribe audio bytes using Whisper API."""
    client = _get_client()
    audio_size = len(audio_data)
    start = time.monotonic()

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "ogg"
    mime = _MIME_TYPES.get(ext, "audio/ogg")

    logger.info("[whisper] user=%s uploading %d bytes as %s (%s)", user_id, audio_size, filename, mime)

    try:
        transcription = await client.audio.transcriptions.create(
            model=settings.openai_whisper_model,
            file=(filename, audio_data, mime),
        )

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info("[whisper] user=%s transcribed in %dms: %r", user_id, latency_ms, transcription.text[:200])
        await log_whisper_call(user_id, audio_size, transcription.text, latency_ms)
        return transcription.text
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error("[whisper] user=%s FAILED in %dms: %s", user_id, latency_ms, e)
        await log_whisper_call(user_id, audio_size, "", latency_ms, error=str(e))
        raise


async def whisper_node(state: AgentState) -> AgentState:
    """LangGraph node: transcribe voice if needed."""
    if not state.is_voice or not state.raw_text:
        state.transcribed_text = state.raw_text
        return state

    # raw_text contains base64 audio data for voice messages
    # In practice, the handler will call transcribe_audio directly
    # and put the result in transcribed_text
    state.transcribed_text = state.raw_text
    return state
