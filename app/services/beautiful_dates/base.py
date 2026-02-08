"""Base class for beautiful date strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class BeautifulDateCandidate:
    """A candidate beautiful date produced by a strategy."""

    target_date: date
    interval_value: int
    interval_unit: str  # "days", "weeks", "months", "years"
    label_ru: str
    label_en: str
    compound_parts: dict | None = None  # For compound strategies


class BaseStrategy(ABC):
    """Abstract base for all beautiful date calculation strategies."""

    @abstractmethod
    def calculate(
        self, event_date: date, event_title: str, params: dict
    ) -> list[BeautifulDateCandidate]:
        """Calculate all beautiful dates for an event.

        Args:
            event_date: The date of the event.
            event_title: Event title (for label generation).
            params: Strategy-specific parameters from DB.

        Returns:
            List of beautiful date candidates.
        """
        ...
