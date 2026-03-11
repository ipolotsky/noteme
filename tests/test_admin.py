import sys
import types
from unittest.mock import MagicMock

_bot_module = types.ModuleType("app.bot")
_bot_module.bot = MagicMock()
if "app.bot" not in sys.modules:
    sys.modules["app.bot"] = _bot_module


class TestAdminViewsNoId:
    def test_user_admin_no_id_in_column_list(self):
        from app.admin.views import UserAdmin
        from app.models.user import User

        assert User.id not in UserAdmin.column_list

    def test_user_admin_id_in_details(self):
        from app.admin.views import UserAdmin
        from app.models.user import User

        assert User.id in UserAdmin.column_details_list

    def test_event_admin_no_id(self):
        from app.admin.views import EventAdmin
        from app.models.event import Event

        assert Event.id not in EventAdmin.column_list

    def test_wish_admin_no_id(self):
        from app.admin.views import WishAdmin
        from app.models.wish import Wish

        assert Wish.id not in WishAdmin.column_list

    def test_person_admin_no_id(self):
        from app.admin.views import PersonAdmin
        from app.models.person import Person

        assert Person.id not in PersonAdmin.column_list

    def test_strategy_admin_no_id(self):
        from app.admin.views import BeautifulDateStrategyAdmin
        from app.models.beautiful_date_strategy import BeautifulDateStrategy

        assert BeautifulDateStrategy.id not in BeautifulDateStrategyAdmin.column_list

    def test_beautiful_date_admin_no_id(self):
        from app.admin.views import BeautifulDateAdmin
        from app.models.beautiful_date import BeautifulDate

        assert BeautifulDate.id not in BeautifulDateAdmin.column_list

    def test_notification_log_admin_no_id(self):
        from app.admin.views import NotificationLogAdmin
        from app.models.notification_log import NotificationLog

        assert NotificationLog.id not in NotificationLogAdmin.column_list

    def test_ai_log_admin_no_id(self):
        from app.admin.views import AILogAdmin
        from app.models.ai_log import AILog

        assert AILog.id not in AILogAdmin.column_list

    def test_user_action_log_admin_no_id(self):
        from app.admin.views import UserActionLogAdmin
        from app.models.user_action_log import UserActionLog

        assert UserActionLog.id not in UserActionLogAdmin.column_list

    def test_subscription_plan_admin_no_id(self):
        from app.admin.views import SubscriptionPlanAdmin
        from app.models.subscription_plan import SubscriptionPlan

        assert SubscriptionPlan.id not in SubscriptionPlanAdmin.column_list

    def test_subscription_admin_no_id(self):
        from app.admin.views import SubscriptionAdmin
        from app.models.subscription import Subscription

        assert Subscription.id not in SubscriptionAdmin.column_list

    def test_payment_admin_no_id(self):
        from app.admin.views import PaymentAdmin
        from app.models.payment import Payment

        assert Payment.id not in PaymentAdmin.column_list

    def test_referral_reward_admin_no_id(self):
        from app.admin.views import ReferralRewardAdmin
        from app.models.referral_reward import ReferralReward

        assert ReferralReward.id not in ReferralRewardAdmin.column_list

    def test_media_link_admin_no_id(self):
        from app.admin.views import MediaLinkAdmin
        from app.models.media_link import MediaLink

        assert MediaLink.id not in MediaLinkAdmin.column_list


class TestUserAdminFormatter:
    def test_username_formatter_has_action_buttons(self):
        from app.admin.views import UserAdmin
        from app.models.user import User

        formatter = UserAdmin.column_formatters[User.username]
        user = MagicMock()
        user.id = 123
        user.username = "test_user"
        result = str(formatter(user, None))
        assert "test_user" in result
        assert "test-notify/123" in result
        assert "grant-premium/123" in result

    def test_username_formatter_handles_none(self):
        from app.admin.views import UserAdmin
        from app.models.user import User

        formatter = UserAdmin.column_formatters[User.username]
        user = MagicMock()
        user.id = 456
        user.username = None
        result = str(formatter(user, None))
        assert "-" in result
        assert "test-notify/456" in result
