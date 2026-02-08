"""Multiples strategy — round numbers of days/weeks/months."""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from app.services.beautiful_dates.base import BaseStrategy, BeautifulDateCandidate
from app.utils.declension import decline


class MultiplesStrategy(BaseStrategy):
    def calculate(
        self, event_date: date, event_title: str, params: dict
    ) -> list[BeautifulDateCandidate]:
        base = params["base"]
        min_val = params["min"]
        max_val = params["max"]
        unit = params["unit"]

        results: list[BeautifulDateCandidate] = []
        n = min_val

        while n <= max_val:
            target = _add_interval(event_date, n, unit)
            if target is not None:
                results.append(BeautifulDateCandidate(
                    target_date=target,
                    interval_value=n,
                    interval_unit=unit,
                    label_ru=f"{decline(n, _unit_singular(unit), 'ru')} с «{event_title}»",
                    label_en=f"{decline(n, _unit_singular(unit), 'en')} since \"{event_title}\"",
                ))
            n += base

        return results


def _unit_singular(unit: str) -> str:
    """Convert plural unit to singular for declension: 'days' -> 'day'."""
    return unit.rstrip("s")


def _add_interval(start: date, n: int, unit: str) -> date | None:
    """Add n units to a start date."""
    try:
        if unit == "days":
            return start + timedelta(days=n)
        if unit == "weeks":
            return start + timedelta(weeks=n)
        if unit == "months":
            return start + relativedelta(months=n)
        if unit == "years":
            return start + relativedelta(years=n)
    except (OverflowError, ValueError):
        return None
    return None
