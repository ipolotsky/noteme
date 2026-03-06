from io import BytesIO

from PIL import Image

from app.services.share_image import generate_share_image


class TestShareImage:
    def test_generates_png_bytes(self):
        result = generate_share_image(
            label="100 дней",
            event_title="Свадьба с Машей",
            target_date_formatted="6 марта 2026",
            relative_date="Через 3 дня",
            person_names=["Маша"],
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:8] == b"\x89PNG\r\n\x1a\n"

    def test_image_dimensions(self):
        result = generate_share_image(
            label="1000 days",
            event_title="Wedding",
            target_date_formatted="March 6, 2026",
            relative_date="In 3 days",
            person_names=[],
        )
        image = Image.open(BytesIO(result))
        assert image.size == (1080, 1920)

    def test_long_event_title(self):
        result = generate_share_image(
            label="777 дней",
            event_title="Очень длинное название события которое не влезает в одну строку на картинке",
            target_date_formatted="6 марта 2026",
            relative_date="Через 3 дня",
            person_names=["Маша", "Вика", "Дима"],
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_empty_person_names(self):
        result = generate_share_image(
            label="365 days",
            event_title="Birthday",
            target_date_formatted="January 1, 2027",
            relative_date="In 300 days",
            person_names=[],
        )
        assert len(result) > 0

    def test_cyrillic_and_latin(self):
        for label in ["100 дней", "100 days", "1 год", "1 year"]:
            result = generate_share_image(
                label=label,
                event_title="Test",
                target_date_formatted="01.01.2027",
                relative_date="Soon",
                person_names=[],
            )
            assert isinstance(result, bytes)
            assert len(result) > 0
