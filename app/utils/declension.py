"""Russian and English declension helpers."""

import inflect

_inflect_engine = inflect.engine()

# Russian plural forms by unit
_RU_FORMS: dict[str, tuple[str, str, str]] = {
    "day": ("день", "дня", "дней"),
    "week": ("неделя", "недели", "недель"),
    "month": ("месяц", "месяца", "месяцев"),
    "year": ("год", "года", "лет"),
}


def _ru_plural_form(n: int) -> int:
    """Return index 0/1/2 for Russian plural form of number n."""
    abs_n = abs(n)
    if abs_n % 10 == 1 and abs_n % 100 != 11:
        return 0  # один день
    if 2 <= abs_n % 10 <= 4 and not (12 <= abs_n % 100 <= 14):
        return 1  # два дня
    return 2  # пять дней


def decline_ru(n: int, unit: str) -> str:
    """Decline a number with Russian unit.

    Example: decline_ru(1000, 'day') -> '1000 дней'
    """
    forms = _RU_FORMS.get(unit)
    if forms is None:
        return f"{n} {unit}"
    idx = _ru_plural_form(n)
    return f"{n} {forms[idx]}"


def decline_en(n: int, unit: str) -> str:
    """Decline a number with English unit.

    Example: decline_en(1, 'day') -> '1 day', decline_en(5, 'day') -> '5 days'
    """
    word = _inflect_engine.plural(unit, n)
    return f"{n} {word}"


def decline(n: int, unit: str, lang: str = "ru") -> str:
    """Decline number with unit in given language."""
    if lang == "ru":
        return decline_ru(n, unit)
    return decline_en(n, unit)
