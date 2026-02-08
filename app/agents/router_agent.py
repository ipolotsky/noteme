"""Router agent — classifies user intent."""

import logging

from langchain_openai import ChatOpenAI

from app.agents.ai_logger import AICallLogger
from app.agents.prompts import ROUTER_SYSTEM
from app.agents.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)

VALID_INTENTS = {
    "create_event",
    "edit_event",
    "delete_event",
    "create_note",
    "edit_note",
    "delete_note",
    "view_events",
    "view_notes",
    "view_feed",
    "view_tags",
    "settings",
    "help",
}


async def router_node(state: AgentState) -> AgentState:
    """LangGraph node: classify intent."""
    text = state.transcribed_text or state.raw_text

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=50,
    )

    messages = [
        {"role": "system", "content": ROUTER_SYSTEM},
        {"role": "user", "content": text},
    ]

    al = AICallLogger("router", settings.openai_model, state.user_id)
    al.set_request(messages=messages, text=text)
    al.start_timer()

    try:
        response = await llm.ainvoke(messages)
    except Exception as e:
        al.set_error(str(e))
        await al.flush()
        raise

    intent = response.content.strip().lower()  # type: ignore[union-attr]
    usage = getattr(response, "usage_metadata", None) or {}
    al.set_response(
        text=intent,
        tokens_prompt=usage.get("input_tokens") if isinstance(usage, dict) else getattr(usage, "input_tokens", None),
        tokens_completion=usage.get("output_tokens") if isinstance(usage, dict) else getattr(usage, "output_tokens", None),
        tokens_total=usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, "total_tokens", None),
    )
    await al.flush()

    if intent in VALID_INTENTS:
        state.intent = intent
    else:
        state.intent = "create_note"  # Default fallback
        logger.warning("Unknown intent '%s', defaulting to create_note", intent)

    logger.info("[router] user=%s intent=%s (raw=%r)", state.user_id, state.intent, intent)
    return state
