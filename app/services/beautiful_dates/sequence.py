"""Sequence strategy — special number sequences (123, 1234, etc.)."""

from datetime import date, timedelta

from app.services.beautiful_dates.base import BaseStrategy, BeautifulDateCandidate
from app.utils.declension import decline


class SequenceStrategy(BaseStrategy):
    def calculate(
        self, event_date: date, event_title: str, params: dict
    ) -> list[BeautifulDateCandidate]:
        sequences = params.get("sequences", [])
        unit = params.get("unit", "days")

        results: list[BeautifulDateCandidate] = []

        for n in sequences:
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
