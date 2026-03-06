from markupsafe import Markup
from sqladmin import ModelView

from app.models.ai_log import AILog
from app.models.beautiful_date import BeautifulDate
from app.models.beautiful_date_strategy import BeautifulDateStrategy
from app.models.event import Event
from app.models.media_link import MediaLink
from app.models.notification_log import NotificationLog
from app.models.person import Person
from app.models.user import User
from app.models.user_action_log import UserActionLog
from app.models.wish import Wish


class UserAdmin(ModelView, model=User):
    column_list = [
        User.id,
        User.username,
        User.first_name,
        User.language,
        User.is_active,
        User.onboarding_completed,
        User.created_at,
    ]
    column_details_list = [
        User.id,
        User.username,
        User.first_name,
        User.language,
        User.timezone,
        User.is_active,
        User.onboarding_completed,
        User.notifications_enabled,
        User.notification_time,
        User.notification_count,
        User.spoiler_enabled,
        User.max_events,
        User.max_wishes,
        User.created_at,
    ]
    column_searchable_list = [User.username, User.first_name]
    column_sortable_list = [User.id, User.created_at]
    column_default_sort = ("created_at", True)
    form_excluded_columns = [User.people, User.events, User.wishes]
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-users"

    column_formatters = {
        User.id: lambda m, _: Markup(
            f'{m.id} <a href="/admin/test-notify/{m.id}" '
            f'style="margin-left:8px;padding:2px 8px;background:#0d6efd;color:#fff;'
            f'border-radius:4px;text-decoration:none;font-size:12px">'
            f'\U0001f514 Test</a>'
        ),
    }


class EventAdmin(ModelView, model=Event):
    column_list = [
        Event.id,
        Event.user_id,
        Event.title,
        Event.event_date,
        Event.is_system,
        Event.created_at,
    ]
    column_searchable_list = [Event.title]
    column_sortable_list = [Event.event_date, Event.created_at]
    column_default_sort = ("created_at", True)
    form_excluded_columns = [Event.people, Event.beautiful_dates]
    name = "Event"
    name_plural = "Events"
    icon = "fa-solid fa-calendar"


class WishAdmin(ModelView, model=Wish):
    column_list = [
        Wish.id,
        Wish.user_id,
        Wish.text,
        Wish.reminder_date,
        Wish.reminder_sent,
        Wish.created_at,
    ]
    column_searchable_list = [Wish.text]
    column_sortable_list = [Wish.created_at]
    column_default_sort = ("created_at", True)
    form_excluded_columns = [Wish.people, Wish.media_link]
    name = "Wish"
    name_plural = "Wishes"
    icon = "fa-solid fa-gift"


class PersonAdmin(ModelView, model=Person):
    column_list = [Person.id, Person.user_id, Person.name, Person.created_at]
    column_searchable_list = [Person.name]
    column_sortable_list = [Person.name, Person.created_at]
    form_excluded_columns = [Person.events, Person.wishes]
    name = "Person"
    name_plural = "People"
    icon = "fa-solid fa-users"


class BeautifulDateStrategyAdmin(ModelView, model=BeautifulDateStrategy):
    column_list = [
        BeautifulDateStrategy.id,
        BeautifulDateStrategy.name_en,
        BeautifulDateStrategy.strategy_type,
        BeautifulDateStrategy.is_active,
        BeautifulDateStrategy.priority,
    ]
    column_sortable_list = [BeautifulDateStrategy.priority]
    column_default_sort = "priority"
    form_excluded_columns = [BeautifulDateStrategy.beautiful_dates]
    name = "Strategy"
    name_plural = "Strategies"
    icon = "fa-solid fa-wand-magic-sparkles"
    list_template = "strategy_list.html"


class BeautifulDateAdmin(ModelView, model=BeautifulDate):
    column_list = [
        BeautifulDate.id,
        BeautifulDate.event_id,
        BeautifulDate.target_date,
        BeautifulDate.label_en,
        BeautifulDate.interval_value,
        BeautifulDate.interval_unit,
    ]
    column_sortable_list = [BeautifulDate.target_date]
    column_default_sort = "target_date"
    can_create = False
    can_edit = False
    name = "Beautiful Date"
    name_plural = "Beautiful Dates"
    icon = "fa-solid fa-crystal-ball"


class MediaLinkAdmin(ModelView, model=MediaLink):
    column_list = [
        MediaLink.id,
        MediaLink.wish_id,
        MediaLink.media_type,
        MediaLink.is_deleted,
    ]
    name = "Media Link"
    name_plural = "Media Links"
    icon = "fa-solid fa-image"


class NotificationLogAdmin(ModelView, model=NotificationLog):
    column_list = [
        NotificationLog.id,
        NotificationLog.user_id,
        NotificationLog.notification_type,
        NotificationLog.sent_at,
    ]
    column_sortable_list = [NotificationLog.sent_at]
    column_default_sort = ("sent_at", True)
    can_create = False
    can_edit = False
    can_delete = False
    name = "Notification Log"
    name_plural = "Notification Logs"
    icon = "fa-solid fa-bell"


class AILogAdmin(ModelView, model=AILog):
    column_list = [
        AILog.id,
        AILog.user_id,
        AILog.agent_name,
        AILog.model,
        AILog.request_text,
        AILog.response_text,
        AILog.tokens_total,
        AILog.latency_ms,
        AILog.error,
        AILog.created_at,
    ]
    column_searchable_list = [AILog.agent_name, AILog.request_text, AILog.response_text]
    column_sortable_list = [AILog.created_at, AILog.agent_name, AILog.latency_ms, AILog.tokens_total]
    column_default_sort = ("created_at", True)
    column_labels = {
        AILog.agent_name: "Agent",
        AILog.request_text: "Request",
        AILog.response_text: "Response",
        AILog.tokens_total: "Tokens",
        AILog.latency_ms: "Latency (ms)",
    }
    can_create = False
    can_edit = False
    can_delete = False
    page_size = 50
    name = "AI Log"
    name_plural = "AI Logs"
    icon = "fa-solid fa-robot"


class UserActionLogAdmin(ModelView, model=UserActionLog):
    column_list = [
        UserActionLog.id,
        UserActionLog.user_id,
        UserActionLog.action,
        UserActionLog.detail,
        UserActionLog.created_at,
    ]
    column_searchable_list = [UserActionLog.action, UserActionLog.detail]
    column_sortable_list = [UserActionLog.created_at, UserActionLog.action, UserActionLog.user_id]
    column_default_sort = ("created_at", True)
    column_labels = {
        UserActionLog.action: "Action",
        UserActionLog.detail: "Detail",
    }
    can_create = False
    can_edit = False
    can_delete = False
    page_size = 50
    name = "User Action"
    name_plural = "User Actions"
    icon = "fa-solid fa-list-check"
