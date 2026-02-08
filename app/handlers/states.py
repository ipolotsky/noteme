"""FSM states for multi-step flows."""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_language = State()
    waiting_first_event = State()
    waiting_first_note = State()


class EventCreateStates(StatesGroup):
    waiting_title = State()
    waiting_date = State()
    waiting_description = State()
    waiting_tags = State()


class EventEditStates(StatesGroup):
    waiting_title = State()
    waiting_date = State()
    waiting_description = State()
    waiting_tags = State()


class NoteCreateStates(StatesGroup):
    waiting_text = State()
    waiting_reminder = State()
    waiting_tags = State()


class NoteEditStates(StatesGroup):
    waiting_text = State()
    waiting_reminder = State()
    waiting_tags = State()


class TagCreateStates(StatesGroup):
    waiting_name = State()


class TagRenameStates(StatesGroup):
    waiting_name = State()


class SettingsStates(StatesGroup):
    waiting_timezone = State()
    waiting_notification_time = State()
    waiting_notification_count = State()
