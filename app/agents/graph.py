import logging

from langgraph.graph import END, StateGraph

from app.agents.event_agent import event_agent_node
from app.agents.formatter_agent import formatter_node
from app.agents.query_agent import query_agent_node
from app.agents.router_agent import router_node
from app.agents.state import AgentState
from app.agents.validation_agent import validation_node
from app.agents.whisper import whisper_node
from app.agents.wish_agent import wish_agent_node

logger = logging.getLogger(__name__)


def _route_after_validation(state: AgentState) -> str:
    if not state.is_valid:
        return "formatter"
    return "router"


def _route_after_router(state: AgentState) -> str:
    intent = state.intent

    if intent in ("create_event", "edit_event"):
        return "event_agent"
    if intent in ("create_wish", "edit_wish"):
        return "wish_agent"
    if intent in ("view_events", "view_wishes", "view_feed", "view_people"):
        return "query_agent"
    return "formatter"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("whisper", whisper_node)
    graph.add_node("validation", validation_node)
    graph.add_node("router", router_node)
    graph.add_node("event_agent", event_agent_node)
    graph.add_node("wish_agent", wish_agent_node)
    graph.add_node("query_agent", query_agent_node)
    graph.add_node("formatter", formatter_node)

    graph.set_entry_point("whisper")

    graph.add_edge("whisper", "validation")
    graph.add_conditional_edges("validation", _route_after_validation)
    graph.add_conditional_edges("router", _route_after_router)
    graph.add_edge("event_agent", "formatter")
    graph.add_edge("wish_agent", "formatter")
    graph.add_edge("query_agent", "formatter")
    graph.add_edge("formatter", END)

    return graph


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


async def process_message(
    text: str,
    user_id: int,
    user_language: str = "ru",
    is_voice: bool = False,
    existing_people: list[str] | None = None,
) -> AgentState:
    graph = get_graph()

    initial_state = AgentState(
        user_id=user_id,
        user_language=user_language,
        raw_text=text,
        is_voice=is_voice,
        existing_people=existing_people or [],
    )

    logger.info("[pipeline] user=%s text=%r", user_id, text[:200])
    result = await graph.ainvoke(initial_state)

    state = AgentState(**result) if isinstance(result, dict) else result

    logger.info(
        "[pipeline] user=%s intent=%s title=%r date=%s wish=%r error=%r response=%r",
        user_id,
        state.intent,
        state.event_title,
        state.event_date,
        state.wish_text[:100] if state.wish_text else "",
        state.error,
        state.response_text[:100] if state.response_text else "",
    )
    return state
