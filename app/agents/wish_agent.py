import json
import logging
from datetime import datetime

from langchain_openai import ChatOpenAI

from app.agents.ai_logger import AICallLogger
from app.agents.prompts import WISH_AGENT_SYSTEM
from app.agents.state import AgentState
from app.config import settings

logger = logging.getLogger(__name__)


async def wish_agent_node(state: AgentState) -> AgentState:
    text = state.transcribed_text or state.raw_text

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=300,
    )

    messages = [
        {"role": "system", "content": WISH_AGENT_SYSTEM},
        {"role": "user", "content": text},
    ]

    al = AICallLogger("wish_agent", settings.openai_model, state.user_id)
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

        state.wish_text = data.get("text", text)
        state.person_names = data.get("people", [])
        if data.get("reminder_date"):
            state.wish_reminder_date = datetime.strptime(
                data["reminder_date"], "%Y-%m-%d"
            ).date()
        state.needs_confirmation = True
        logger.info("[wish_agent] user=%s text=%r people=%r", state.user_id, state.wish_text[:100], state.person_names)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("[wish_agent] user=%s PARSE ERROR: %s content=%r", state.user_id, e, content)
        state.wish_text = text
        state.needs_confirmation = True

    return state
