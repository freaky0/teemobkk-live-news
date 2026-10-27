"""Render the stable /thai/ link-preview card from the owned hero illustration.

Output: thai_platform/static/assets/share-home-v1.jpg (1200x630 JPEG, 4:1.1 safe).

Run from thai_platform/:

    uv run python scripts/generate_share_image.py

Bump the ``v1`` suffix in the file name (and in ``config/context.py``) when the
artwork changes, so messenger caches pick up the new URL.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ASSETS = Path(__file__).resolve().parent.parent / 'static' / 'assets'
SOURCE = ASSETS / 'cat-hero.webp'
TARGET = ASSETS / 'share-home-v1.jpg'
WIDTH, HEIGHT = 1200, 630

BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
REGULAR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
ACCENT = (245, 184, 60)
PAPER = (255, 255, 255)
MUTED = (203, 217, 227)
INK = (20, 33, 44)
LEFT = 68


def scrim(image):
    """Deep navy wash on the left so the Korean/Latin brand copy stays legible."""
    layer = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(layer)
    for x in range(WIDTH):
        if x <= 430:
            alpha = 240
        elif x <= 720:
            alpha = int(240 * (1 - (x - 430) / 290) ** 1.35)
        else:
            alpha = 0
        draw.line((x, 0, x, HEIGHT), fill=(9, 24, 38, max(0, alpha)))
    return Image.alpha_composite(image.convert('RGBA'), layer)


def render():
    source = Image.open(SOURCE).convert('RGB')
    # Trim the far-left edge of the hero art so the cat sits clear of the copy panel.
    source = source.crop((150, 0, source.width, source.height))
    art = scrim(ImageOps.fit(source, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS))
    draw = ImageDraw.Draw(art)
    draw.rounded_rectangle((LEFT, 74, LEFT + 150, 108), radius=17, fill=ACCENT)
    draw.text((LEFT + 17, 80), 'THAILAND', font=ImageFont.truetype(BOLD, 17), fill=INK)
    draw.text((LEFT, 168), "TEEMOBKK's", font=ImageFont.truetype(BOLD, 58), fill=PAPER)
    draw.text((LEFT - 3, 240), 'POST', font=ImageFont.truetype(BOLD, 104), fill=PAPER)
    draw.rectangle((LEFT, 398, LEFT + 74, 404), fill=ACCENT)
    draw.text((LEFT, 430), 'THAILAND NEWS', font=ImageFont.truetype(BOLD, 23), fill=PAPER)
    draw.text((LEFT, 468), '& EVERYDAY LIFE', font=ImageFont.truetype(REGULAR, 22), fill=MUTED)
    draw.text((LEFT, 556), 'teemobkk.io/thai', font=ImageFont.truetype(REGULAR, 19), fill=MUTED)
    art.convert('RGB').save(TARGET, quality=86, optimize=True, progressive=True)
    return TARGET


if __name__ == '__main__':
    print(render())
