"""Powers of two strategy — 256, 512, 1024, etc. days/weeks."""

from datetime import date, timedelta

from app.services.beautiful_dates.base import BaseStrategy, BeautifulDateCandidate
from app.utils.declension import decline


class PowersOfTwoStrategy(BaseStrategy):
    def calculate(
        self, event_date: date, event_title: str, params: dict
    ) -> list[BeautifulDateCandidate]:
        min_power = params.get("min_power", 8)
        max_power = params.get("max_power", 20)
        units = params.get("units", ["days"])

        results: list[BeautifulDateCandidate] = []

        for power in range(min_power, max_power + 1):
            n = 2**power
            for unit in units:
                try:
                    if unit == "days":
                        target = event_date + timedelta(days=n)
                    elif unit == "weeks":
                        target = event_date + timedelta(weeks=n)
                    else:
                        continue
                except (OverflowError, ValueError):
                    continue

                singular = unit.rstrip("s")
                results.append(BeautifulDateCandidate(
                    target_date=target,
                    interval_value=n,
                    interval_unit=unit,
                    label_ru=f"{decline(n, singular, 'ru')} с «{event_title}»",
                    label_en=f"{decline(n, singular, 'en')} since \"{event_title}\"",
                ))

        return results
