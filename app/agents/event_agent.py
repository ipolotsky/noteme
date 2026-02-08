"""Event agent — extracts event details from user message."""

import json
import logging
from datetime import date, datetime

from langchain_openai import ChatOpenAI

from app.agents.ai_logger import AICallLogger
from app.agents.prompts import EVENT_AGENT_SYSTEM
from app.agents.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


async def event_agent_node(state: AgentState) -> AgentState:
    """LangGraph node: extract event data from message."""
    text = state.transcribed_text or state.raw_text

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=300,
    )

    system = EVENT_AGENT_SYSTEM.format(today=date.today().isoformat())

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]

    al = AICallLogger("event_agent", settings.openai_model, state.user_id)
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
        # Extract JSON from response (may be wrapped in markdown)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)

        state.event_title = data.get("title", "")
        if data.get("date"):
            state.event_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        state.event_description = data.get("description", "")
        state.tag_names = data.get("tags", [])
        state.needs_confirmation = True
        logger.info(
            "[event_agent] user=%s title=%r date=%s tags=%r desc=%r",
            state.user_id, state.event_title, state.event_date, state.tag_names, state.event_description,
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("[event_agent] user=%s PARSE ERROR: %s content=%r", state.user_id, e, content)
        state.error = "parse_error"

    return state
