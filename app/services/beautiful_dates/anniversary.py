"""Anniversary strategy — yearly milestones."""

from datetime import date

from dateutil.relativedelta import relativedelta

from app.services.beautiful_dates.base import BaseStrategy, BeautifulDateCandidate
from app.utils.declension import decline


class AnniversaryStrategy(BaseStrategy):
    def calculate(
        self, event_date: date, event_title: str, params: dict
    ) -> list[BeautifulDateCandidate]:
        years_list = params.get("years", [])

        results: list[BeautifulDateCandidate] = []

        for n in years_list:
            try:
                target = event_date + relativedelta(years=n)
            except (OverflowError, ValueError):
                continue

            results.append(BeautifulDateCandidate(
                target_date=target,
                interval_value=n,
                interval_unit="years",
                label_ru=f"{decline(n, 'year', 'ru')} с «{event_title}»",
                label_en=f"{decline(n, 'year', 'en')} since \"{event_title}\"",
            ))

        return results
