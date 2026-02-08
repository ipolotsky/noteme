"""Tests for beautiful dates calculation strategies."""

from datetime import date, timedelta

import pytest

from app.services.beautiful_dates.anniversary import AnniversaryStrategy
from app.services.beautiful_dates.compound import CompoundStrategy
from app.services.beautiful_dates.multiples import MultiplesStrategy
from app.services.beautiful_dates.powers_of_two import PowersOfTwoStrategy
from app.services.beautiful_dates.repdigits import RepdigitsStrategy
from app.services.beautiful_dates.sequence import SequenceStrategy
from app.services.beautiful_dates.special import SpecialStrategy

EVENT_DATE = date(2022, 8, 17)  # "Свадьба"
EVENT_TITLE = "Свадьба"


class TestMultiplesStrategy:
    strategy = MultiplesStrategy()

    def test_tens_of_days(self):
        params = {"base": 10, "min": 10, "max": 50, "unit": "days"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 5  # 10, 20, 30, 40, 50
        assert results[0].target_date == EVENT_DATE + timedelta(days=10)
        assert results[0].interval_value == 10
        assert results[0].interval_unit == "days"
        assert "10" in results[0].label_ru
        assert results[4].target_date == EVENT_DATE + timedelta(days=50)

    def test_hundreds_of_days(self):
        params = {"base": 100, "min": 100, "max": 300, "unit": "days"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 3  # 100, 200, 300

    def test_weeks(self):
        params = {"base": 10, "min": 10, "max": 20, "unit": "weeks"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 2  # 10, 20 weeks
        assert results[0].target_date == EVENT_DATE + timedelta(weeks=10)

    def test_months(self):
        params = {"base": 10, "min": 10, "max": 20, "unit": "months"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 2  # 10, 20 months
        # 10 months from 2022-08-17 = 2023-06-17
        assert results[0].target_date == date(2023, 6, 17)


class TestRepdigitsStrategy:
    strategy = RepdigitsStrategy()

    def test_repdigits(self):
        params = {"exclude": [333, 666], "max_days": 2000, "unit": "days"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        values = [r.interval_value for r in results]
        assert 111 in values
        assert 222 in values
        assert 333 not in values  # excluded
        assert 444 in values
        assert 555 in values
        assert 666 not in values  # excluded
        assert 777 in values
        assert 888 in values
        assert 999 in values
        assert 1111 in values

    def test_111_days(self):
        params = {"exclude": [], "max_days": 200, "unit": "days"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert results[0].interval_value == 111
        assert results[0].target_date == EVENT_DATE + timedelta(days=111)


class TestSequenceStrategy:
    strategy = SequenceStrategy()

    def test_sequences(self):
        params = {"sequences": [123, 1234, 12345], "unit": "days"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 3
        assert results[0].interval_value == 123
        assert results[0].target_date == EVENT_DATE + timedelta(days=123)
        assert results[1].interval_value == 1234
        assert results[2].interval_value == 12345


class TestSpecialStrategy:
    strategy = SpecialStrategy()

    def test_69_days(self):
        params = {"numbers": [69], "unit": "days"}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 1
        assert results[0].interval_value == 69
        assert results[0].target_date == EVENT_DATE + timedelta(days=69)


class TestCompoundStrategy:
    strategy = CompoundStrategy()

    def test_days_weeks_months(self):
        params = {"parts": ["days", "weeks", "months"], "min_n": 1, "max_n": 3}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 3  # n=1,2,3

        # n=1: 1 day + 1 week + 1 month from event date
        r = results[0]
        assert r.compound_parts == {"days": 1, "weeks": 1, "months": 1}
        assert r.interval_unit == "compound"

    def test_days_months_years(self):
        params = {"parts": ["days", "months", "years"], "min_n": 3, "max_n": 3}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 1
        r = results[0]
        assert r.compound_parts == {"days": 3, "months": 3, "years": 3}

    def test_label_format(self):
        params = {"parts": ["days", "weeks", "months"], "min_n": 1, "max_n": 1}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        r = results[0]
        # Russian: "1 день 1 неделя 1 месяц с «Свадьба»"
        assert "1 день" in r.label_ru
        assert "1 неделя" in r.label_ru
        assert "1 месяц" in r.label_ru
        # English
        assert "1 day" in r.label_en
        assert "1 week" in r.label_en
        assert "1 month" in r.label_en


class TestAnniversaryStrategy:
    strategy = AnniversaryStrategy()

    def test_anniversaries(self):
        params = {"years": [1, 2, 5, 10, 25, 50]}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 6

        # 1st anniversary
        assert results[0].target_date == date(2023, 8, 17)
        assert results[0].interval_value == 1

        # 10th anniversary
        r10 = next(r for r in results if r.interval_value == 10)
        assert r10.target_date == date(2032, 8, 17)

    def test_label_declension(self):
        params = {"years": [1, 2, 5]}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert "1 год" in results[0].label_ru
        assert "2 года" in results[1].label_ru
        assert "5 лет" in results[2].label_ru


class TestPowersOfTwoStrategy:
    strategy = PowersOfTwoStrategy()

    def test_powers_days(self):
        params = {"min_power": 8, "max_power": 10, "units": ["days"]}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 3  # 2^8=256, 2^9=512, 2^10=1024
        assert results[0].interval_value == 256
        assert results[1].interval_value == 512
        assert results[2].interval_value == 1024

    def test_powers_days_and_weeks(self):
        params = {"min_power": 8, "max_power": 8, "units": ["days", "weeks"]}
        results = self.strategy.calculate(EVENT_DATE, EVENT_TITLE, params)
        assert len(results) == 2  # 256 days + 256 weeks
        assert results[0].interval_unit == "days"
        assert results[1].interval_unit == "weeks"
        assert results[0].target_date == EVENT_DATE + timedelta(days=256)
        assert results[1].target_date == EVENT_DATE + timedelta(weeks=256)


class TestEngineIntegration:
    """Test the engine's recalculate function (requires DB)."""

    @pytest.mark.asyncio
    async def test_recalculate_for_event(self, session):
        """Test full recalculation pipeline."""
        from app.models.event import Event
        from app.models.user import User
        from app.services.beautiful_dates.engine import recalculate_for_event
        from app.utils.seed import STRATEGIES

        # Create user and event
        user = User(id=123456789, first_name="Test")
        session.add(user)
        await session.flush()

        event = Event(
            user_id=user.id,
            title="Свадьба",
            event_date=date(2022, 8, 17),
        )
        session.add(event)
        await session.flush()

        # Create strategies
        from app.models.beautiful_date_strategy import BeautifulDateStrategy
        for data in STRATEGIES[:3]:  # Just first 3 strategies for speed
            s = BeautifulDateStrategy(**data)
            session.add(s)
        await session.flush()

        # Recalculate
        count = await recalculate_for_event(session, event)
        assert count > 0

        # Verify dates are in DB
        from sqlalchemy import select

        from app.models.beautiful_date import BeautifulDate
        result = await session.execute(
            select(BeautifulDate).where(BeautifulDate.event_id == event.id)
        )
        dates = list(result.scalars().all())
        assert len(dates) == count
        # All dates should be in the future (or today)
        today = date.today()
        for bd in dates:
            assert bd.target_date >= today
