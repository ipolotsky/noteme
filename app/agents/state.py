from dataclasses import dataclass, field
from datetime import date


@dataclass
class AgentState:
    user_id: int = 0
    user_language: str = "ru"
    raw_text: str = ""
    is_voice: bool = False

    transcribed_text: str = ""

    is_valid: bool = True
    rejection_reason: str = ""

    intent: str = ""  # create_event, create_wish, view_events, etc.

    event_title: str = ""
    event_date: date | None = None
    event_description: str = ""
    person_names: list[str] = field(default_factory=list)
    wish_text: str = ""
    wish_reminder_date: date | None = None
    query_type: str = ""  # "events", "wishes", "feed", "people"

    target_entity_id: str = ""

    response_text: str = ""
    needs_confirmation: bool = False
    error: str = ""
