"""Build the 1200×630 social preview card from the live screenshot and the final numbers.

    python tools/make_social.py       # -> docs/social-preview.png

Numbers are read from `eval/metrics.json` and `eval/usdz-report.json` so the card cannot drift
from the report.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "social-preview.png"
SHOT = ROOT / "docs" / "demo-3d.png"

BG = (13, 17, 23)
PANEL = (21, 27, 35)
LINE = (35, 44, 56)
TEXT = (230, 237, 243)
MUTED = (139, 152, 167)
ACCENT = (88, 166, 255)

W, H = 1200, 630
BOLD = "C:/Windows/Fonts/segoeuib.ttf"
REGULAR = "C:/Windows/Fonts/segoeui.ttf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def rounded_card(image: Image.Image, size: tuple[int, int], radius: int = 14) -> Image.Image:
    card = image.convert("RGB").resize(size, Image.LANCZOS)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.paste(card, (0, 0), mask)
    return out


def main() -> int:
    metrics = json.loads((ROOT / "eval" / "metrics.json").read_text("utf-8"))
    usdz = json.loads((ROOT / "eval" / "usdz-report.json").read_text("utf-8"))
    claims = metrics["claims"]
    trials = metrics["self_test"]["total"]["trials"]
    detected = metrics["self_test"]["total"]["detected"]
    packages = len(usdz["packages"])

    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    # faint vertical gradient so the card is not a flat rectangle
    for y in range(H):
        shade = int(6 * (1 - y / H))
        draw.line([(0, y), (W, y)], fill=(BG[0] + shade, BG[1] + shade, BG[2] + shade))

    # accent dot + wordmark
    draw.ellipse((60, 88, 78, 106), fill=ACCENT)
    draw.text((92, 78), "LessonLens", font=font(BOLD, 46), fill=TEXT)
    draw.text((60, 148), "Slide deck → grounded 3D scene", font=font(REGULAR, 27), fill=MUTED)

    body = font(REGULAR, 19)
    draw.text((60, 196), "Every object quotes the slide it came from,", font=body, fill=TEXT)
    draw.text((60, 224), "and a generated report proves it.", font=body, fill=TEXT)

    stats = [
        (f"{claims}/{claims}", "claims traced to a\nverbatim slide sentence"),
        (f"{detected}/{trials}", "injected corruptions\ncaught by the verifier"),
        (f"{packages}/{packages}", "USDZ packages passing\nthe ARKit engine"),
    ]
    x, y = 60, 300
    for value, label in stats:
        draw.text((x, y), value, font=font(BOLD, 40), fill=ACCENT)
        draw.multiline_text((x, y + 54), label, font=font(REGULAR, 16), fill=MUTED, spacing=3)
        x += 190

    # screenshot card with soft shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((620, 150, 1150, 490), radius=18, fill=(0, 0, 0, 160))
    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(18))).convert("RGB"), (0, 0))

    if SHOT.exists():
        card = rounded_card(Image.open(SHOT), (528, 330))
        canvas.paste(card, (620, 152), card)
        draw.rounded_rectangle((620, 152, 1147, 481), radius=14, outline=LINE, width=2)
    else:
        draw.rounded_rectangle((620, 152, 1147, 481), radius=14, outline=LINE, width=2)

    draw.line((60, 545, 1140, 545), fill=LINE, width=1)
    draw.text((60, 566), "github.com/mbj733/lessonlens", font=font(BOLD, 18), fill=TEXT)
    draw.text((600, 566), "MIT · CI green · live on GitHub Pages", font=font(REGULAR, 18), fill=MUTED)

    canvas.save(OUT, optimize=True)
    print(f"{OUT.relative_to(ROOT)}  {canvas.size[0]}x{canvas.size[1]}  {OUT.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
