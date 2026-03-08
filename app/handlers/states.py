from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_language = State()
    waiting_first_event = State()
    waiting_first_wish = State()


class EventCreateStates(StatesGroup):
    waiting_title = State()
    waiting_date = State()
    waiting_description = State()
    waiting_people = State()


class EventEditStates(StatesGroup):
    waiting_title = State()
    waiting_date = State()
    waiting_description = State()
    waiting_people = State()


class WishCreateStates(StatesGroup):
    waiting_text = State()
    waiting_people = State()


class WishEditStates(StatesGroup):
    waiting_text = State()
    waiting_people = State()


class PersonCreateStates(StatesGroup):
    waiting_name = State()


class PersonRenameStates(StatesGroup):
    waiting_name = State()


class MediaWishStates(StatesGroup):
    waiting_person = State()
    waiting_new_person_name = State()


class SettingsStates(StatesGroup):
    waiting_timezone = State()
    waiting_day_before_time = State()
    waiting_week_before_time = State()
    waiting_digest_time = State()
