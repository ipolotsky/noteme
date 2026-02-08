"""Repdigits strategy — numbers with all identical digits (111, 222, etc.)."""

from datetime import date, timedelta

from app.services.beautiful_dates.base import BaseStrategy, BeautifulDateCandidate
from app.utils.declension import decline


def _is_repdigit(n: int) -> bool:
    s = str(n)
    return len(s) >= 3 and len(set(s)) == 1


class RepdigitsStrategy(BaseStrategy):
    def calculate(
        self, event_date: date, event_title: str, params: dict
    ) -> list[BeautifulDateCandidate]:
        exclude = set(params.get("exclude", []))
        max_days = params.get("max_days", 100000)
        unit = params.get("unit", "days")

        results: list[BeautifulDateCandidate] = []

        for n in range(111, max_days + 1):
            if _is_repdigit(n) and n not in exclude:
                if unit == "days":
                    target = event_date + timedelta(days=n)
                else:
                    continue

                results.append(BeautifulDateCandidate(
                    target_date=target,
                    interval_value=n,
                    interval_unit=unit,
                    label_ru=f"{decline(n, 'day', 'ru')} с «{event_title}»",
                    label_en=f"{decline(n, 'day', 'en')} since \"{event_title}\"",
                ))

        return results
