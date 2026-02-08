"""Tests for i18n loader and translations."""

from app.i18n.loader import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, t


class TestI18nLoader:
    def test_supported_languages(self):
        assert "ru" in SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES

    def test_default_language_is_russian(self):
        assert DEFAULT_LANGUAGE == "ru"

    def test_basic_key_exists(self):
        """Basic welcome key should exist in both languages."""
        ru_val = t("welcome", "ru", name="Test")
        en_val = t("welcome", "en", name="Test")
        assert ru_val != "welcome"  # Key should be resolved
        assert en_val != "welcome"

    def test_missing_key_returns_key(self):
        result = t("nonexistent.key.that.does.not.exist", "ru")
        assert result == "nonexistent.key.that.does.not.exist"

    def test_interpolation(self):
        result = t("welcome", "ru", name="Илья")
        assert "Илья" in result

    def test_fallback_to_default_language(self):
        """If key missing in target lang, falls back to default."""
        # Get a key that exists in ru
        ru_val = t("welcome", "ru", name="Test")
        # Try a fake language, should fall back to ru
        fallback_val = t("welcome", "xx", name="Test")
        assert fallback_val == ru_val

    def test_nested_keys(self):
        """Nested keys like 'events.title' work."""
        result = t("events.title", "ru")
        assert result != "events.title"  # Should be resolved

    def test_all_essential_keys_exist(self):
        """All essential UI keys exist in both languages."""
        essential_keys = [
            "welcome",
            "welcome_back",
            "choose_language",
            "language_set",
            "events.title",
            "events.empty",
            "notes.title",
            "notes.empty",
            "settings.title",
            "feed.empty",
        ]
        for key in essential_keys:
            for lang in ("ru", "en"):
                val = t(key, lang, name="X", max="10")
                assert val != key, f"Key '{key}' missing for lang '{lang}'"
