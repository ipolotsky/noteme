import logging

from app.agents.state import AgentState
from app.i18n.loader import t

logger = logging.getLogger(__name__)


async def formatter_node(state: AgentState) -> AgentState:
    lang = state.user_language

    if state.error:
        logger.warning("[formatter] user=%s error=%r → not_understood", state.user_id, state.error)
        state.response_text = t("ai.not_understood", lang)
        return state

    if not state.is_valid:
        logger.info("[formatter] user=%s invalid → off_topic", state.user_id)
        state.response_text = t("ai.off_topic", lang)
        return state

    intent = state.intent

    if intent == "create_event":
        if state.event_title and state.event_date:
            state.response_text = t(
                "ai.confirm_create_event",
                lang,
                title=state.event_title,
                date=state.event_date.strftime("%d.%m.%Y"),
            )
            state.needs_confirmation = True
        elif state.event_title:
            state.response_text = t("events.create_date", lang)
        else:
            state.response_text = t("events.create_title", lang)

    elif intent == "create_wish":
        if state.wish_text:
            state.response_text = t("ai.confirm_create_wish", lang)
            state.needs_confirmation = True
        else:
            state.response_text = t("wishes.create_text", lang)

    elif (
        intent in ("view_events", "view_wishes", "view_feed", "view_people")
        or intent == "settings"
    ):
        state.response_text = ""

    elif intent == "help":
        state.response_text = t("ai.help", lang)

    else:
        state.response_text = t("ai.not_understood", lang)

    logger.info(
        "[formatter] user=%s intent=%s → response=%r",
        state.user_id,
        intent,
        state.response_text[:100],
    )
    return state
