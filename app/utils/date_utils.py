"""Date formatting and parsing utilities."""

from datetime import date

from app.i18n import t
from app.utils.declension import decline


def format_relative_date(target: date, lang: str = "ru") -> str:
    """Format target date relative to today.

    Returns: 'Сегодня', 'Завтра', 'Через 3 дня', 'Через неделю', etc.
    """
    today = date.today()
    delta = (target - today).days

    if delta == 0:
        return t("feed.today", lang)
    if delta == 1:
        return t("feed.tomorrow", lang)
    if delta == 7:
        return t("feed.in_week", lang)
    if delta > 0:
        return t("feed.in_days", lang, days=decline(delta, "day", lang))

    # Past dates
    return format_date(target, lang)


def format_date(d: date, lang: str = "ru") -> str:
    """Format date for display."""
    if lang == "ru":
        months = [
            "", "января", "февраля", "марта", "апреля", "мая", "июня",
            "июля", "августа", "сентября", "октября", "ноября", "декабря",
        ]
        return f"{d.day} {months[d.month]} {d.year}"
    return d.strftime("%B %d, %Y")


def parse_date(text: str) -> date | None:
    """Parse date from DD.MM.YYYY format."""
    text = text.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def days_between(d1: date, d2: date) -> int:
    """Return absolute number of days between two dates."""
    return abs((d2 - d1).days)
