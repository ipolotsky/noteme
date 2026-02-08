"""LangGraph agent graph assembly."""

import logging

from langgraph.graph import END, StateGraph

from app.agents.event_agent import event_agent_node
from app.agents.formatter_agent import formatter_node
from app.agents.note_agent import note_agent_node
from app.agents.query_agent import query_agent_node
from app.agents.router_agent import router_node
from app.agents.state import AgentState
from app.agents.validation_agent import validation_node
from app.agents.whisper import whisper_node

logger = logging.getLogger(__name__)


def _route_after_validation(state: AgentState) -> str:
    """Route based on validation result."""
    if not state.is_valid:
        return "formatter"
    return "router"


def _route_after_router(state: AgentState) -> str:
    """Route to the appropriate agent based on intent."""
    intent = state.intent

    if intent in ("create_event", "edit_event"):
        return "event_agent"
    if intent in ("create_note", "edit_note"):
        return "note_agent"
    if intent in ("view_events", "view_notes", "view_feed", "view_tags"):
        return "query_agent"
    # settings, help, delete_*, unknown → go directly to formatter
    return "formatter"


def build_graph() -> StateGraph:
    """Build and compile the agent graph.

    Flow:
        whisper -> validation -> router -> [event_agent | note_agent | query_agent] -> formatter
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("whisper", whisper_node)
    graph.add_node("validation", validation_node)
    graph.add_node("router", router_node)
    graph.add_node("event_agent", event_agent_node)
    graph.add_node("note_agent", note_agent_node)
    graph.add_node("query_agent", query_agent_node)
    graph.add_node("formatter", formatter_node)

    # Set entry point
    graph.set_entry_point("whisper")

    # Edges
    graph.add_edge("whisper", "validation")
    graph.add_conditional_edges("validation", _route_after_validation)
    graph.add_conditional_edges("router", _route_after_router)
    graph.add_edge("event_agent", "formatter")
    graph.add_edge("note_agent", "formatter")
    graph.add_edge("query_agent", "formatter")
    graph.add_edge("formatter", END)

    return graph


# Compiled graph singleton
_compiled_graph = None


def get_graph():
    """Get or create the compiled agent graph."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


async def process_message(
    text: str,
    user_id: int,
    user_language: str = "ru",
    is_voice: bool = False,
) -> AgentState:
    """Process a user message through the agent pipeline.

    Returns the final AgentState with response_text and extracted data.
    """
    graph = get_graph()

    initial_state = AgentState(
        user_id=user_id,
        user_language=user_language,
        raw_text=text,
        is_voice=is_voice,
    )

    logger.info("[pipeline] user=%s text=%r", user_id, text[:200])
    result = await graph.ainvoke(initial_state)

    # LangGraph ainvoke returns a dict — convert back to AgentState
    if isinstance(result, dict):
        state = AgentState(**result)
    else:
        state = result

    logger.info(
        "[pipeline] user=%s intent=%s title=%r date=%s note=%r error=%r response=%r",
        user_id, state.intent, state.event_title, state.event_date,
        state.note_text[:100] if state.note_text else "",
        state.error, state.response_text[:100] if state.response_text else "",
    )
    return state
