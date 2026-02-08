"""Lightweight i18n loader with string interpolation."""

import json
from pathlib import Path

_translations: dict[str, dict[str, str]] = {}
_i18n_dir = Path(__file__).parent

SUPPORTED_LANGUAGES = ("ru", "en")
DEFAULT_LANGUAGE = "ru"


def _load_language(lang: str) -> dict[str, str]:
    """Load translations from JSON file."""
    file_path = _i18n_dir / f"{lang}.json"
    if not file_path.exists():
        return {}
    with open(file_path, encoding="utf-8") as f:
        return _flatten_dict(json.load(f))


def _flatten_dict(d: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested dict: {'a': {'b': 'c'}} -> {'a.b': 'c'}."""
    items: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, key))
        else:
            items[key] = str(v)
    return items


def _ensure_loaded(lang: str) -> dict[str, str]:
    """Load language if not already loaded."""
    if lang not in _translations:
        _translations[lang] = _load_language(lang)
    return _translations[lang]


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs: object) -> str:
    """Get translated string with interpolation.

    Usage:
        t('welcome', 'ru', name='Илья')
        t('events.created', 'en', title='Wedding')
    """
    translations = _ensure_loaded(lang)
    template = translations.get(key)

    if template is None:
        # Fallback to default language
        if lang != DEFAULT_LANGUAGE:
            fallback = _ensure_loaded(DEFAULT_LANGUAGE)
            template = fallback.get(key)
        if template is None:
            return key  # Return key as-is if not found

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template

    return template


def reload_translations() -> None:
    """Force reload all cached translations."""
    _translations.clear()
