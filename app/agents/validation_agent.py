"""Validation agent — checks if the message is in scope."""

import logging

from langchain_openai import ChatOpenAI

from app.agents.ai_logger import AICallLogger
from app.agents.prompts import VALIDATION_SYSTEM
from app.agents.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


async def validation_node(state: AgentState) -> AgentState:
    """LangGraph node: validate if message is in-scope."""
    text = state.transcribed_text or state.raw_text
    if not text:
        state.is_valid = False
        state.rejection_reason = "Empty message"
        return state

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=100,
    )

    messages = [
        {"role": "system", "content": VALIDATION_SYSTEM},
        {"role": "user", "content": text},
    ]

    al = AICallLogger("validation", settings.openai_model, state.user_id)
    al.set_request(messages=messages, text=text)
    al.start_timer()

    try:
        response = await llm.ainvoke(messages)
    except Exception as e:
        al.set_error(str(e))
        await al.flush()
        raise

    result = response.content.strip().lower()  # type: ignore[union-attr]
    usage = getattr(response, "usage_metadata", None) or {}
    al.set_response(
        text=result,
        tokens_prompt=usage.get("input_tokens") if isinstance(usage, dict) else getattr(usage, "input_tokens", None),
        tokens_completion=usage.get("output_tokens") if isinstance(usage, dict) else getattr(usage, "output_tokens", None),
        tokens_total=usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, "total_tokens", None),
    )
    await al.flush()

    lines = result.split("\n", 1)

    if lines[0] == "valid":
        state.is_valid = True
    else:
        state.is_valid = False
        state.rejection_reason = lines[1] if len(lines) > 1 else ""

    logger.info("[validation] user=%s valid=%s reason=%r", state.user_id, state.is_valid, state.rejection_reason)
    return state
