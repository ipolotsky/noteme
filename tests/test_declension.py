"""Tests for declension helpers."""

from app.utils.declension import decline, decline_en, decline_ru


class TestRussianDeclension:
    def test_day_one(self):
        assert decline_ru(1, "day") == "1 день"

    def test_day_few(self):
        assert decline_ru(2, "day") == "2 дня"
        assert decline_ru(3, "day") == "3 дня"
        assert decline_ru(4, "day") == "4 дня"

    def test_day_many(self):
        assert decline_ru(5, "day") == "5 дней"
        assert decline_ru(10, "day") == "10 дней"
        assert decline_ru(100, "day") == "100 дней"
        assert decline_ru(1000, "day") == "1000 дней"

    def test_day_teens(self):
        assert decline_ru(11, "day") == "11 дней"
        assert decline_ru(12, "day") == "12 дней"
        assert decline_ru(14, "day") == "14 дней"

    def test_day_21(self):
        assert decline_ru(21, "day") == "21 день"
        assert decline_ru(31, "day") == "31 день"
        assert decline_ru(101, "day") == "101 день"

    def test_week(self):
        assert decline_ru(1, "week") == "1 неделя"
        assert decline_ru(2, "week") == "2 недели"
        assert decline_ru(5, "week") == "5 недель"

    def test_month(self):
        assert decline_ru(1, "month") == "1 месяц"
        assert decline_ru(3, "month") == "3 месяца"
        assert decline_ru(6, "month") == "6 месяцев"

    def test_year(self):
        assert decline_ru(1, "year") == "1 год"
        assert decline_ru(2, "year") == "2 года"
        assert decline_ru(5, "year") == "5 лет"
        assert decline_ru(10, "year") == "10 лет"


class TestEnglishDeclension:
    def test_singular(self):
        assert decline_en(1, "day") == "1 day"
        assert decline_en(1, "week") == "1 week"

    def test_plural(self):
        assert decline_en(2, "day") == "2 days"
        assert decline_en(100, "week") == "100 weeks"
        assert decline_en(5, "year") == "5 years"


class TestDeclineDispatch:
    def test_russian(self):
        assert decline(1000, "day", "ru") == "1000 дней"

    def test_english(self):
        assert decline(1000, "day", "en") == "1000 days"
