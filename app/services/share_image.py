import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONTS_DIR = Path(__file__).parent.parent / "static" / "fonts"

_WIDTH = 1080
_HEIGHT = 1080

_COLOR_TOP = (108, 60, 225)
_COLOR_BOTTOM = (37, 99, 235)

_WHITE = (255, 255, 255, 255)
_WHITE_80 = (255, 255, 255, 204)
_WHITE_60 = (255, 255, 255, 153)
_WHITE_40 = (255, 255, 255, 102)
_WHITE_20 = (255, 255, 255, 51)


@lru_cache(maxsize=8)
def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONTS_DIR / name), size)


def _make_gradient() -> Image.Image:
    strip = Image.new("RGB", (1, _HEIGHT))
    pixels = strip.load()
    for y in range(_HEIGHT):
        ratio = y / _HEIGHT
        r = int(_COLOR_TOP[0] + (_COLOR_BOTTOM[0] - _COLOR_TOP[0]) * ratio)
        g = int(_COLOR_TOP[1] + (_COLOR_BOTTOM[1] - _COLOR_TOP[1]) * ratio)
        b = int(_COLOR_TOP[2] + (_COLOR_BOTTOM[2] - _COLOR_TOP[2]) * ratio)
        pixels[0, y] = (r, g, b)
    return strip.resize((_WIDTH, _HEIGHT))


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        test = f"{current} {word}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return lines


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    overlay: Image.Image,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    max_width: int = 900,
) -> int:
    overlay_draw = ImageDraw.Draw(overlay)
    lines = _wrap_text(text, font, max_width, draw)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (_WIDTH - text_width) // 2
        overlay_draw.text((x, y), line, font=font, fill=fill)
        y += text_height + 10

    return y


def generate_share_image(
    label: str,
    event_title: str,
    target_date_formatted: str,
    relative_date: str,
    branding: str = "Not a date",
) -> bytes:
    font_label = _load_font("Inter-Bold.ttf", 80)
    font_title = _load_font("Inter-Regular.ttf", 44)
    font_date = _load_font("Inter-Regular.ttf", 38)
    font_relative = _load_font("Inter-Regular.ttf", 34)
    font_brand = _load_font("Inter-Bold.ttf", 28)

    image = _make_gradient()

    overlay = Image.new("RGBA", (_WIDTH, _HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    y = 200
    y = _draw_centered_text(draw, overlay, label, y, font_label, _WHITE)
    y += 25

    line_y = y
    line_x_start = (_WIDTH - 200) // 2
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.line(
        [(line_x_start, line_y), (line_x_start + 200, line_y)],
        fill=_WHITE_20,
        width=2,
    )
    y = line_y + 30

    y = _draw_centered_text(draw, overlay, event_title, y, font_title, _WHITE)
    y += 20

    y = _draw_centered_text(
        draw,
        overlay,
        target_date_formatted,
        y,
        font_date,
        _WHITE_80,
    )
    y += 15

    _draw_centered_text(
        draw,
        overlay,
        relative_date,
        y,
        font_relative,
        _WHITE_60,
    )

    brand_bbox = draw.textbbox((0, 0), branding, font=font_brand)
    brand_width = brand_bbox[2] - brand_bbox[0]
    brand_x = (_WIDTH - brand_width) // 2
    overlay_draw.text(
        (brand_x, _HEIGHT - 80),
        branding,
        font=font_brand,
        fill=_WHITE_40,
    )

    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    image = image.convert("RGB")

    buf = io.BytesIO()
    buf.name = "share.png"
    image.save(buf, format="PNG")
    return buf.getvalue()
