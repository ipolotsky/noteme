"""Callback data factories for inline keyboards."""

from aiogram.filters.callback_data import CallbackData


# --- Navigation ---
class MenuCb(CallbackData, prefix="menu"):
    action: str  # "feed", "events", "notes", "tags", "settings"


# --- Events ---
class EventCb(CallbackData, prefix="ev"):
    action: str  # "list", "view", "create", "edit", "delete", "confirm_delete", "dates"
    id: str = ""  # UUID as string
    page: int = 0


class EventEditCb(CallbackData, prefix="ev_edit"):
    field: str  # "title", "date", "description", "tags"
    id: str


# --- Notes ---
class NoteCb(CallbackData, prefix="nt"):
    action: str  # "list", "view", "create", "edit", "delete", "confirm_delete"
    id: str = ""
    page: int = 0


class NoteEditCb(CallbackData, prefix="nt_edit"):
    field: str  # "text", "reminder", "tags"
    id: str


# --- Tags ---
class TagCb(CallbackData, prefix="tg"):
    action: str  # "list", "view", "create", "rename", "delete", "confirm_delete"
    id: str = ""
    page: int = 0


# --- Settings ---
class SettingsCb(CallbackData, prefix="set"):
    action: str  # "view", "language", "timezone", "notif_toggle", "notif_time", "notif_count", "spoiler"
    value: str = ""


# --- Feed ---
class FeedCb(CallbackData, prefix="feed"):
    action: str  # "list", "view", "share"
    id: str = ""
    page: int = 0


# --- Pagination ---
class PageCb(CallbackData, prefix="pg"):
    target: str  # "events", "notes", "tags", "feed"
    page: int


# --- Confirm/Cancel ---
class ConfirmCb(CallbackData, prefix="cfm"):
    action: str  # "yes", "no"
    context: str = ""  # e.g., "delete_event:{uuid}"


# --- Language selection ---
class LangCb(CallbackData, prefix="lang"):
    code: str  # "ru", "en"


# --- Onboarding ---
class OnboardCb(CallbackData, prefix="onb"):
    action: str  # "skip", "continue"
