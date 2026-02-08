"""Query agent — handles view/list requests."""

import json
import logging

from langchain_openai import ChatOpenAI

from app.agents.ai_logger import AICallLogger
from app.agents.prompts import QUERY_AGENT_SYSTEM
from app.agents.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


async def query_agent_node(state: AgentState) -> AgentState:
    """LangGraph node: determine query type for view requests."""
    text = state.transcribed_text or state.raw_text

    # Simple keyword-based routing for common queries (0 AI calls)
    # Feed checked first — "красив" and "лент" are unambiguous feed keywords
    lower = text.lower()
    if any(w in lower for w in ["лент", "feed", "красив"]):
        state.query_type = "feed"
        return state
    if any(w in lower for w in ["событи", "event", "дат"]):
        state.query_type = "events"
        return state
    if any(w in lower for w in ["замет", "note", "запис"]):
        state.query_type = "notes"
        return state
    if any(w in lower for w in ["тег", "tag", "метк"]):
        state.query_type = "tags"
        return state

    # Fallback to LLM
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=100,
    )

    messages = [
        {"role": "system", "content": QUERY_AGENT_SYSTEM},
        {"role": "user", "content": text},
    ]

    al = AICallLogger("query_agent", settings.openai_model, state.user_id)
    al.set_request(messages=messages, text=text)
    al.start_timer()

    try:
        response = await llm.ainvoke(messages)
    except Exception as e:
        al.set_error(str(e))
        await al.flush()
        raise

    content = response.content.strip()  # type: ignore[union-attr]
    usage = getattr(response, "usage_metadata", None) or {}
    al.set_response(
        text=content,
        tokens_prompt=usage.get("input_tokens") if isinstance(usage, dict) else getattr(usage, "input_tokens", None),
        tokens_completion=usage.get("output_tokens") if isinstance(usage, dict) else getattr(usage, "output_tokens", None),
        tokens_total=usage.get("total_tokens") if isinstance(usage, dict) else getattr(usage, "total_tokens", None),
    )
    await al.flush()

    try:
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
        state.query_type = data.get("query_type", "events")
    except (json.JSONDecodeError, ValueError):
        state.query_type = "events"

    return state
