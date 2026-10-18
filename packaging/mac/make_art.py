"""Generates the app icon and the DMG background in the "Midnight & Champagne" style.

    python packaging/mac/make_art.py [--font-dir DIR]

Writes dragshift/assets/dragshift.{png,icns,ico} and packaging/mac/dmg-background{,@2x}.png.
Text is set in Inter (https://rsms.me/inter, SIL Open Font License); pass --font-dir if it
isn't installed system-wide. The outputs are committed, so the build never needs to run this."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dragshift import CREDIT, __version__  # noqa: E402

GOLD_TOP, GOLD_MID, GOLD_LOW = (247, 231, 193), (216, 173, 98), (168, 122, 52)
MID_TOP, MID_LOW = (36, 38, 48), (10, 11, 16)


# ---------------------------------------------------------------- helpers
def vgradient(size, stops) -> Image.Image:
    """Vertical gradient through [(t, (r,g,b)), ...]."""
    w, h = size
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        t = y / max(1, h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                f = (t - t0) / max(1e-6, t1 - t0)
                px[0, y] = tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
                break
    return col.resize((w, h))


def squircle(size: int, inset: int, n: float = 5.0) -> Image.Image:
    """macOS-style superellipse mask."""
    m = Image.new("L", (size, size), 0)
    c, r = size / 2, size / 2 - inset
    pts = []
    for i in range(720):
        a = 2 * math.pi * i / 720
        ca, sa = math.cos(a), math.sin(a)
        pts.append((c + r * math.copysign(abs(ca) ** (2 / n), ca), c + r * math.copysign(abs(sa) ** (2 / n), sa)))
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return m


def gold_fill(size) -> Image.Image:
    return vgradient(size, [(0, GOLD_TOP), (0.5, GOLD_MID), (1, GOLD_LOW)])


def font(dirs, name, px):
    for d in dirs:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), px)
    try:
        return ImageFont.truetype(name, px)
    except OSError:
        return ImageFont.load_default(size=px)


# ---------------------------------------------------------------- icon
def make_icon(S: int = 2048) -> Image.Image:
    k = S / 1024
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = squircle(S, int(100 * k))
    # soft shadow under the tile
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(28 * k)).point(lambda v: int(v * 0.55)))
    canvas.alpha_composite(sh, (0, int(18 * k)))
    body = vgradient((S, S), [(0, MID_TOP), (1, MID_LOW)]).convert("RGBA")
    body.putalpha(mask)
    canvas.alpha_composite(body)

    c = S / 2
    # gold ring of 8 petals: the radial menu, seen from above
    ring = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(ring)
    r_out, r_in, gap = 318 * k, 214 * k, 7
    for i in range(8):
        a0 = -90 - 22.5 + i * 45 + gap / 2
        d.pieslice((c - r_out, c - r_out, c + r_out, c + r_out), a0, a0 + 45 - gap, fill=255)
    d.ellipse((c - r_in, c - r_in, c + r_in, c + r_in), fill=0)
    ring = ring.filter(ImageFilter.GaussianBlur(0.6 * k))
    glow = Image.new("RGBA", (S, S), (*GOLD_MID, 0))
    glow.putalpha(ring.filter(ImageFilter.GaussianBlur(26 * k)).point(lambda v: int(v * 0.45)))
    canvas.alpha_composite(glow)
    g = gold_fill((S, S)).convert("RGBA")
    g.putalpha(ring)
    canvas.alpha_composite(g)
    # one petal lit, like a hovered slice
    lit = Image.new("L", (S, S), 0)
    ImageDraw.Draw(lit).pieslice((c - r_out, c - r_out, c + r_out, c + r_out), -90 - 22.5 + gap / 2,
                                 -90 + 22.5 - gap / 2, fill=110)
    lit = ImageChops.multiply(lit, ring)
    canvas.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (S, S), 255)] * 3, lit)))

    # hub: dark glass with a gold edge and a champagne "drag up" arrow
    hub_r = 150 * k
    d = ImageDraw.Draw(canvas)
    d.ellipse((c - hub_r, c - hub_r, c + hub_r, c + hub_r), fill=(18, 19, 26, 255),
              outline=(*GOLD_MID, 255), width=int(5 * k))
    arrow = Image.new("L", (S, S), 0)
    ad = ImageDraw.Draw(arrow)
    ad.polygon([(c, c - 92 * k), (c - 78 * k, c - 4 * k), (c + 78 * k, c - 4 * k)], fill=255)
    ad.rounded_rectangle((c - 30 * k, c - 10 * k, c + 30 * k, c + 88 * k), radius=8 * k, fill=255)
    a = gold_fill((S, S)).convert("RGBA")
    a.putalpha(arrow)
    canvas.alpha_composite(a)

    # glass sheen on the upper half of the tile
    sheen = Image.new("L", (S, S), 0)
    ImageDraw.Draw(sheen).ellipse((-0.15 * S, -0.62 * S, 1.15 * S, 0.5 * S), fill=34)
    sheen = ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(40 * k)), mask)
    canvas.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (S, S), 255)] * 3, sheen)))
    # hairline rim
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(int(5 * k) | 1)))
    canvas.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (S, S), 255)] * 3, edge.point(lambda v: v * 40 // 255))))
    return canvas.resize((1024, 1024), Image.LANCZOS)


# ---------------------------------------------------------------- DMG background
def make_dmg_background(scale: int, fonts) -> Image.Image:
    W, H = 660 * scale, 420 * scale
    s = scale
    bg = vgradient((W, H), [(0, (24, 25, 33)), (1, (8, 9, 13))]).convert("RGBA")
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.18, H * 0.18, W * 0.82, H * 0.86), fill=60)
    glow = glow.filter(ImageFilter.GaussianBlur(70 * s))
    bg.alpha_composite(Image.merge("RGBA", (Image.new("L", (W, H), GOLD_MID[0]), Image.new("L", (W, H), GOLD_MID[1]),
                                            Image.new("L", (W, H), GOLD_MID[2]), glow)))
    d = ImageDraw.Draw(bg, "RGBA")   # blend translucent text instead of overwriting

    def centered(y, text, f, fill, spacing=0):
        if spacing:
            widths = [d.textlength(ch, font=f) for ch in text]
            total = sum(widths) + spacing * (len(text) - 1)
            x = (W - total) / 2
            for ch, w in zip(text, widths):
                d.text((x, y), ch, font=f, fill=fill)
                x += w + spacing
        else:
            d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)

    # title
    title = font(fonts, "InterDisplay-SemiBold.otf", 34 * s)
    tw = d.textlength("DragShift", font=title)
    tl = Image.new("L", (W, H), 0)
    ImageDraw.Draw(tl).text(((W - tw) / 2, 34 * s), "DragShift", font=title, fill=255)
    gt = gold_fill((W, H)).convert("RGBA")
    gt.putalpha(tl)
    bg.alpha_composite(gt)
    centered(80 * s, "Drag the app into Applications to install",
             font(fonts, "Inter-Regular.otf", 13 * s), (247, 244, 238, 165))

    # arrow from the app icon (x=165) to Applications (x=495), icons centred at y=215
    y = 215 * s
    x0, x1 = 238 * s, 422 * s
    for i in range(int(x0), int(x1 - 14 * s), int(9 * s)):        # dotted shaft
        d.ellipse((i, y - 1.6 * s, i + 3.2 * s, y + 1.6 * s), fill=(*GOLD_MID, 210))
    d.polygon([(x1, y), (x1 - 14 * s, y - 8 * s), (x1 - 14 * s, y + 8 * s)], fill=(*GOLD_TOP, 235))

    # signature
    sig_font = font(fonts, "Inter-Medium.otf", 12 * s)
    sig = CREDIT.upper()
    spacing = 2.2 * s
    widths = sum(d.textlength(ch, font=sig_font) for ch in sig) + spacing * (len(sig) - 1)
    ys = 352 * s
    centered(ys, sig, sig_font, (*GOLD_TOP, 230), spacing)
    lx = (W - widths) / 2
    for xa, xb in ((lx - 70 * s, lx - 16 * s), (lx + widths + 16 * s, lx + widths + 70 * s)):
        d.line((xa, ys + 8 * s, xb, ys + 8 * s), fill=(*GOLD_MID, 150), width=max(1, s))
    centered(376 * s, f"Version {__version__}", font(fonts, "Inter-Regular.otf", 10 * s), (247, 244, 238, 90))
    return bg.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", action="append", default=["/usr/share/fonts/opentype/inter",
                                                            "/Library/Fonts", str(Path.home() / "Library/Fonts")])
    a = ap.parse_args()
    assets = ROOT / "dragshift" / "assets"
    icon = make_icon()
    icon.save(assets / "dragshift.png")
    icon.save(assets / "dragshift.icns", sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256),
                                                 (512, 512), (1024, 1024)])
    icon.save(assets / "dragshift.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                               (128, 128), (256, 256)])
    out = ROOT / "packaging" / "mac"
    make_dmg_background(1, a.font_dir).save(out / "dmg-background.png")
    make_dmg_background(2, a.font_dir).save(out / "dmg-background@2x.png")
    print("wrote icon and DMG background")


if __name__ == "__main__":
    main()
