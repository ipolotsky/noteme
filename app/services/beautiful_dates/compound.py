"""Compound strategy — N days + N weeks + N months, etc."""

from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from app.services.beautiful_dates.base import BaseStrategy, BeautifulDateCandidate
from app.utils.declension import decline

# Unit singular forms for declension
_UNIT_MAP = {
    "days": "day",
    "weeks": "week",
    "months": "month",
    "years": "year",
}


class CompoundStrategy(BaseStrategy):
    def calculate(
        self, event_date: date, event_title: str, params: dict
    ) -> list[BeautifulDateCandidate]:
        parts = params["parts"]  # e.g., ["days", "weeks", "months"]
        min_n = params.get("min_n", 1)
        max_n = params.get("max_n", 12)

        results: list[BeautifulDateCandidate] = []

        for n in range(min_n, max_n + 1):
            target = _compute_compound_date(event_date, n, parts)
            if target is None:
                continue

            total_days = (target - event_date).days
            if total_days <= 0:
                continue

            parts_dict = {unit: n for unit in parts}
            label_ru = _format_label_ru(n, parts, event_title)
            label_en = _format_label_en(n, parts, event_title)

            results.append(BeautifulDateCandidate(
                target_date=target,
                interval_value=total_days,
                interval_unit="compound",
                label_ru=label_ru,
                label_en=label_en,
                compound_parts=parts_dict,
            ))

        return results


def _compute_compound_date(start: date, n: int, parts: list[str]) -> date | None:
    """Compute target date by adding N of each unit."""
    try:
        result = start
        for unit in parts:
            if unit == "days":
                result += timedelta(days=n)
            elif unit == "weeks":
                result += timedelta(weeks=n)
            elif unit == "months":
                result += relativedelta(months=n)
            elif unit == "years":
                result += relativedelta(years=n)
        return result
    except (OverflowError, ValueError):
        return None


def _format_label_ru(n: int, parts: list[str], title: str) -> str:
    items = [decline(n, _UNIT_MAP[p], "ru") for p in parts]
    return " ".join(items) + f" с «{title}»"


def _format_label_en(n: int, parts: list[str], title: str) -> str:
    items = [decline(n, _UNIT_MAP[p], "en") for p in parts]
    return " ".join(items) + f" since \"{title}\""
