from aiogram.filters.callback_data import CallbackData


class MenuCb(CallbackData, prefix="menu"):
    action: str  # "feed", "events", "wishes", "people", "settings"


class EventCb(CallbackData, prefix="ev"):
    action: str  # "list", "view", "create", "edit", "delete", "confirm_delete", "dates"
    id: str = ""
    page: int = 0


class EventEditCb(CallbackData, prefix="ev_edit"):
    field: str  # "title", "date", "description", "people"
    id: str


class WishCb(CallbackData, prefix="ws"):
    action: str  # "list", "view", "create", "edit", "delete", "confirm_delete"
    id: str = ""
    page: int = 0


class WishEditCb(CallbackData, prefix="ws_edit"):
    field: str  # "text", "reminder", "people"
    id: str


class PersonCb(CallbackData, prefix="pp"):
    action: (
        str  # "list", "view", "create", "rename", "delete", "confirm_delete", "events", "wishes"
    )
    id: str = ""
    page: int = 0


class MediaPersonCb(CallbackData, prefix="mp"):
    action: str  # "select", "create", "cancel"
    id: str = ""


class SettingsCb(CallbackData, prefix="set"):
    action: str
    value: str = ""


class FeedCb(CallbackData, prefix="feed"):
    action: str  # "list", "view", "share"
    id: str = ""
    page: int = 0


class PageCb(CallbackData, prefix="pg"):
    target: str  # "events", "wishes", "people", "feed"
    page: int


class ConfirmCb(CallbackData, prefix="cfm"):
    action: str  # "yes", "no"
    context: str = ""


class LangCb(CallbackData, prefix="lang"):
    code: str  # "ru", "en"


class OnboardCb(CallbackData, prefix="onb"):
    action: str  # "skip", "continue"


class SubscribeCb(CallbackData, prefix="sub"):
    action: str  # "plans", "buy", "referral"
    id: str = ""
