"""Agent graph state definition."""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class AgentState:
    """State passed through the LangGraph agent pipeline."""

    # Input
    user_id: int = 0
    user_language: str = "ru"
    raw_text: str = ""
    is_voice: bool = False

    # After transcription
    transcribed_text: str = ""

    # After validation
    is_valid: bool = True
    rejection_reason: str = ""

    # After routing
    intent: str = ""  # create_event, create_note, view_events, etc.

    # After agent extraction
    event_title: str = ""
    event_date: date | None = None
    event_description: str = ""
    tag_names: list[str] = field(default_factory=list)
    note_text: str = ""
    note_reminder_date: date | None = None
    query_type: str = ""  # "events", "notes", "feed", "tags"

    # For edit/delete
    target_entity_id: str = ""

    # Output
    response_text: str = ""
    needs_confirmation: bool = False
    error: str = ""
