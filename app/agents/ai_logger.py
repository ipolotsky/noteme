"""AI call logger — logs to stdout and pushes to Redis for async DB persistence."""

import json
import logging
import time
import uuid

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("ai_logger")

REDIS_AI_LOG_KEY = "ai_logs:queue"

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url)
    return _redis


class AICallLogger:
    """Context manager for logging a single AI call."""

    def __init__(self, agent_name: str, model: str, user_id: int) -> None:
        self.agent_name = agent_name
        self.model = model
        self.user_id = user_id
        self.request_messages: list[dict] | None = None
        self.request_text: str | None = None
        self.response_text: str | None = None
        self.tokens_prompt: int | None = None
        self.tokens_completion: int | None = None
        self.tokens_total: int | None = None
        self.error: str | None = None
        self._start_time: float = 0
        self._latency_ms: int = 0

    def set_request(
        self,
        messages: list[dict] | None = None,
        text: str | None = None,
    ) -> None:
        self.request_messages = messages
        self.request_text = text

    def set_response(
        self,
        text: str | None = None,
        tokens_prompt: int | None = None,
        tokens_completion: int | None = None,
        tokens_total: int | None = None,
    ) -> None:
        self.response_text = text
        self.tokens_prompt = tokens_prompt
        self.tokens_completion = tokens_completion
        self.tokens_total = tokens_total

    def set_error(self, error: str) -> None:
        self.error = error

    def start_timer(self) -> None:
        self._start_time = time.monotonic()

    def stop_timer(self) -> None:
        if self._start_time:
            self._latency_ms = int((time.monotonic() - self._start_time) * 1000)

    async def flush(self) -> None:
        """Log to stdout and push to Redis queue."""
        self.stop_timer()

        # Stdout log
        req_preview = (self.request_text or "")[:200]
        resp_preview = (self.response_text or "")[:200]
        tokens_info = f"tokens={self.tokens_total}" if self.tokens_total else "tokens=?"
        error_info = f" ERROR: {self.error}" if self.error else ""

        logger.info(
            "[%s] user=%s model=%s %s latency=%dms | req: %s | resp: %s%s",
            self.agent_name,
            self.user_id,
            self.model,
            tokens_info,
            self._latency_ms,
            req_preview,
            resp_preview,
            error_info,
        )

        # Push to Redis for async DB persistence
        record = {
            "id": str(uuid.uuid4()),
            "user_id": self.user_id,
            "agent_name": self.agent_name,
            "model": self.model,
            "request_messages": self.request_messages,
            "request_text": self.request_text,
            "response_text": self.response_text,
            "tokens_prompt": self.tokens_prompt,
            "tokens_completion": self.tokens_completion,
            "tokens_total": self.tokens_total,
            "latency_ms": self._latency_ms,
            "error": self.error,
        }
        try:
            r = _get_redis()
            await r.rpush(REDIS_AI_LOG_KEY, json.dumps(record, ensure_ascii=False))
        except Exception:
            logger.warning("Failed to push AI log to Redis", exc_info=True)


async def log_llm_call(
    agent_name: str,
    user_id: int,
    messages: list[dict],
    response,
) -> None:
    """Convenience: log a completed langchain ChatOpenAI call."""
    al = AICallLogger(agent_name, settings.openai_model, user_id)
    al.set_request(
        messages=messages,
        text=messages[-1]["content"] if messages else None,
    )

    content = response.content if hasattr(response, "content") else str(response)
    usage = getattr(response, "usage_metadata", None) or {}

    al.set_response(
        text=content,
        tokens_prompt=usage.get("input_tokens") if isinstance(usage, dict) else getattr(usage, "input_tokens", None),
        tokens_completion=usage.get("output_tokens") if isinstance(usage, dict) else getattr(usage, "output_tokens", None),
        tokens_total=usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, "total_tokens", None),
    )
    al._latency_ms = 0  # Set by caller if needed
    await al.flush()


async def log_whisper_call(
    user_id: int,
    audio_size: int,
    transcribed_text: str,
    latency_ms: int,
    error: str | None = None,
) -> None:
    """Log a Whisper transcription call."""
    al = AICallLogger("whisper", settings.openai_whisper_model, user_id)
    al.set_request(text=f"[audio {audio_size} bytes]")
    al.set_response(text=transcribed_text)
    if error:
        al.set_error(error)
    al._latency_ms = latency_ms
    await al.flush()
