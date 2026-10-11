"""Draw 1200x630 share images (og:image) for every game page, plus the default one.

Run after site/build.py, which writes _site/og/cards.json. Needs Pillow (the build itself stays stdlib-only):
    pip install pillow && python3 site/og.py
Fonts are Space Grotesk and Inter (SIL Open Font License, see og_assets/OFL.txt).
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "_site" / "og"
ASSETS = HERE / "og_assets"
W, H = 1200, 630
NAVY, INK, SOFT, CORAL, CHIP = "#10142b", "#ffffff", "#c9cff5", "#ff8a8d", "#3b4270"
PILL = {"yes": "#22c55e", "no": "#ff5a5f", "ended": "#f5b83d", "partial": "#f5b83d"}


def font(name, size, weight):
    f = ImageFont.truetype(str(ASSETS / name), size)
    try:
        f.set_variation_by_axes([weight] if name.startswith("Space") else [size if size < 32 else 32, weight])
    except (OSError, ValueError):
        pass
    return f


def background():
    img = Image.new("RGB", (W, H), NAVY)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse((-220, -260, 420, 380), fill=(58, 91, 255, 60))
    d.ellipse((860, 330, 1420, 890), fill=(255, 90, 95, 50))
    img.paste(glow.filter(ImageFilter.GaussianBlur(4)), (0, 0), glow.filter(ImageFilter.GaussianBlur(4)))
    return img


def fit_title(d, text, max_w, sizes=(92, 84, 76, 68, 60, 54, 48)):
    """Largest size at which the title fits in two lines."""
    for size in sizes:
        f = font("SpaceGrotesk.ttf", size, 700)
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if d.textlength(trial, font=f) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) <= 2 and all(d.textlength(x, font=f) <= max_w for x in lines):
            return f, lines
    f = font("SpaceGrotesk.ttf", sizes[-1], 700)
    line = text
    while d.textlength(line + "…", font=f) > max_w:
        line = line[:-1]
    return f, [line + "…"]


def draw(card, mark):
    img = background()
    d = ImageDraw.Draw(img)
    x = 72
    img.paste(mark, (x, 56), mark)
    d.text((x + 84, 66), "Crossplay Guide", font=font("SpaceGrotesk.ttf", 34, 700), fill=INK)
    d.text((x, 176), card.get("kicker", "Is it crossplay?"), font=font("Inter.ttf", 32, 500), fill=SOFT)
    tf, lines = fit_title(d, card["title"], W - 2 * x)
    y = 222
    for line in lines:
        d.text((x, y), line, font=tf, fill=INK)
        y += int(tf.size * 1.08)
    y += 22
    if card.get("word"):
        pf = font("SpaceGrotesk.ttf", 40, 700)
        tw = d.textlength(card["word"], font=pf)
        d.rounded_rectangle((x, y, x + tw + 56, y + 68), radius=34, fill=PILL.get(card["kind"], "#f5b83d"))
        d.text((x + 28, y + 10), card["word"], font=pf, fill=NAVY)
        y += 96
    cf = font("Inter.ttf", 26, 500)
    cx = x
    chips = [] if card.get("kind") == "no" or y + 50 > H - 30 else card.get("platforms", [])
    for p in chips:
        tw = d.textlength(p, font=cf)
        if cx + tw + 40 > W - x:
            break
        d.rounded_rectangle((cx, y, cx + tw + 36, y + 50), radius=12, outline=CHIP, width=2)
        d.text((cx + 18, y + 9), p, font=cf, fill=SOFT)
        cx += tw + 50
    uf = font("SpaceGrotesk.ttf", 30, 700)
    d.text((W - x - d.textlength("crossplayguide.com", font=uf), 72), "crossplayguide.com", font=uf, fill=CORAL)
    return img


def main():
    mark = Image.open(ASSETS / "mark.png").convert("RGBA").resize((68, 68), Image.LANCZOS)
    cards = json.loads((OUT / "cards.json").read_text())
    for c in cards:
        draw(c, mark).save(OUT / f"{c['slug']}.png", optimize=True)
    default = {"kicker": "Crossplay answers for every platform", "title": "Can you play together?", "kind": "",
               "word": "", "platforms": ["PC", "PS5", "Xbox", "Switch 2", "Mobile"]}
    draw(default, mark).save(OUT / "default.png", optimize=True)
    (OUT / "cards.json").unlink()
    print(f"Drew {len(cards) + 1} share images → {OUT}")


if __name__ == "__main__":
    main()
