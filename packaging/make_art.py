"""Generates DropDial's artwork in the "Midnight & Champagne" style:

    python packaging/make_art.py [--font-dir DIR] [--preview OUT.png]

  dropdial/assets/dropdial.{png,icns,ico}       app icon (a gold dial on a dark glass tile)
  packaging/mac/dmg-background{,@2x}.png        the window people see when they open the .dmg
  installer/wizard-large{,@2x}.bmp,             artwork for the Windows installer
  installer/wizard-small{,@2x}.bmp

Text is set in the Inter typeface (SIL Open Font License); pass --font-dir if it isn't
installed. The outputs are committed, so builds never need to run this."""
from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QGuiApplication, QImage,  # noqa: E402
                           QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
                           QRadialGradient)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dropdial import CREDIT, __version__  # noqa: E402

APP = "DropDial"
GOLD = ["#fbeccd", "#c9a25c", "#8c6529", "#e9cf98", "#fff3d9", "#b8904a", "#7d5a22", "#e2c58b", "#fbeccd"]
GOLD_TOP, GOLD_MID, GOLD_LOW = (247, 231, 193), (216, 173, 98), (168, 122, 52)


# ---------------------------------------------------------------- Qt <-> PIL
def qimage(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    return img


def to_pil(img: QImage) -> Image.Image:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombuffer("RGBA", (img.width(), img.height()), bytes(img.constBits()), "raw", "RGBA", 0, 1).copy()


def painter(img: QImage) -> QPainter:
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    return p


def shadow_of(img: QImage, blur: float, alpha: float, dy: float, color=(0, 0, 0)) -> Image.Image:
    """Soft shadow/glow from a painted silhouette."""
    a = to_pil(img).getchannel("A").filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha))
    out = Image.new("RGBA", a.size, (*color, 0))
    out.putalpha(a)
    shifted = Image.new("RGBA", a.size, (0, 0, 0, 0))
    shifted.alpha_composite(out, (0, int(dy)))
    return shifted


# ---------------------------------------------------------------- shapes
def squircle_path(x: float, y: float, size: float, n: float = 5.0) -> QPainterPath:
    """macOS-style continuous-corner tile."""
    c, r = size / 2, size / 2
    pts = []
    for i in range(1440):
        a = 2 * math.pi * i / 1440
        ca, sa = math.cos(a), math.sin(a)
        pts.append(QPointF(x + c + r * math.copysign(abs(ca) ** (2 / n), ca),
                           y + c + r * math.copysign(abs(sa) ** (2 / n), sa)))
    path = QPainterPath()
    path.addPolygon(QPolygonF(pts))
    path.closeSubpath()
    return path


def circle(c: QPointF, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(c, r, r)
    return path


def sector(c: QPointF, r0: float, r1: float, a0: float, a1: float) -> QPainterPath:
    """Annular sector, degrees in Qt's convention (0 = 3 o'clock, counter-clockwise)."""
    path = QPainterPath()
    path.arcMoveTo(QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1), a0)
    path.arcTo(QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1), a0, a1 - a0)
    path.arcTo(QRectF(c.x() - r0, c.y() - r0, 2 * r0, 2 * r0), a1, a0 - a1)
    path.closeSubpath()
    return path


def metal(c: QPointF, angle: float = 112) -> QBrush:
    g = QConicalGradient(c, angle)
    for i, col in enumerate(GOLD):
        g.setColorAt(i / (len(GOLD) - 1), QColor(col))
    return QBrush(g)


# ---------------------------------------------------------------- icon
def make_icon(S: int = 1024) -> Image.Image:
    k = S / 1024
    c = QPointF(S / 2, S / 2)
    tile = squircle_path(100 * k, 100 * k, 824 * k)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # 1. tile shadow
    sil = qimage(S)
    p = painter(sil)
    p.fillPath(tile, QColor(0, 0, 0))
    p.end()
    out.alpha_composite(shadow_of(sil, 22 * k, 0.55, 14 * k))

    layer = qimage(S)
    p = painter(layer)
    # 2. tile: deep graphite with a soft top light
    g = QLinearGradient(0, 100 * k, 0, 924 * k)
    g.setColorAt(0, QColor("#30333f"))
    g.setColorAt(0.55, QColor("#16181f"))
    g.setColorAt(1, QColor("#08090c"))
    p.fillPath(tile, g)
    rg = QRadialGradient(QPointF(S / 2, 140 * k), 620 * k)
    rg.setColorAt(0, QColor(255, 255, 255, 34))
    rg.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(tile, rg)
    p.end()
    out.alpha_composite(to_pil(layer))

    R_BEZEL, R_FACE = 330 * k, 276 * k

    # 3. dial shadow on the tile
    sil = qimage(S)
    p = painter(sil)
    p.fillPath(circle(c, R_BEZEL), QColor(0, 0, 0))
    p.end()
    out.alpha_composite(shadow_of(sil, 26 * k, 0.75, 20 * k))

    layer = qimage(S)
    p = painter(layer)
    # 4. brushed-gold bezel
    p.fillPath(circle(c, R_BEZEL).subtracted(circle(c, R_FACE)), metal(c))
    p.setPen(QPen(QColor(255, 246, 225, 150), 2 * k))
    p.drawEllipse(c, R_BEZEL - 1 * k, R_BEZEL - 1 * k)
    p.setPen(QPen(QColor(40, 26, 6, 160), 2.5 * k))
    p.drawEllipse(c, R_FACE + 1 * k, R_FACE + 1 * k)
    # engraved minute ticks, longer every fifth (a watch bezel)
    for i in range(60):
        a = math.radians(i * 6)
        long = i % 5 == 0
        r0, r1 = (R_FACE + 12 * k, R_BEZEL - 12 * k) if long else (R_FACE + 22 * k, R_BEZEL - 14 * k)
        p0 = QPointF(c.x() + r0 * math.sin(a), c.y() - r0 * math.cos(a))
        p1 = QPointF(c.x() + r1 * math.sin(a), c.y() - r1 * math.cos(a))
        p.setPen(QPen(QColor(54, 36, 10, 190 if long else 120), (5 if long else 2.4) * k, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(p0, p1)
        p.setPen(QPen(QColor(255, 244, 220, 70), 1.2 * k))
        p.drawLine(p0 + QPointF(1.4 * k, 1.4 * k), p1 + QPointF(1.4 * k, 1.4 * k))

    # 5. the face: deep glass
    fg = QRadialGradient(QPointF(c.x(), c.y() - 70 * k), R_FACE * 1.15)
    fg.setColorAt(0, QColor("#262934"))
    fg.setColorAt(0.7, QColor("#12141a"))
    fg.setColorAt(1, QColor("#08090c"))
    p.fillPath(circle(c, R_FACE), fg)
    # slice dividers (the menu's eight slices)
    for i in range(8):
        a = math.radians(i * 45 + 22.5)
        p.setPen(QPen(QColor(255, 255, 255, 22), 2 * k))
        p.drawLine(QPointF(c.x() + 96 * k * math.sin(a), c.y() - 96 * k * math.cos(a)),
                   QPointF(c.x() + (R_FACE - 18 * k) * math.sin(a), c.y() - (R_FACE - 18 * k) * math.cos(a)))
    p.end()
    out.alpha_composite(to_pil(layer))

    # 6. one lit slice at the top: where you drop
    lit_path = sector(c, 104 * k, R_FACE - 20 * k, 90 - 20, 90 + 20)
    glow = qimage(S)
    p = painter(glow)
    p.fillPath(lit_path, QColor(*GOLD_MID))
    p.end()
    out.alpha_composite(shadow_of(glow, 28 * k, 0.85, 0, GOLD_MID))
    layer = qimage(S)
    p = painter(layer)
    lg = QLinearGradient(0, c.y() - R_FACE, 0, c.y() - 104 * k)
    lg.setColorAt(0, QColor("#fff1d2"))
    lg.setColorAt(0.5, QColor("#e3be7a"))
    lg.setColorAt(1, QColor("#a87a34"))
    p.fillPath(lit_path, lg)
    p.setPen(QPen(QColor(255, 248, 230, 200), 2 * k))
    p.drawPath(lit_path)
    p.end()
    out.alpha_composite(to_pil(layer))

    # 7. needle + hub, with their own shadow
    needle = QPainterPath()
    tip = QPointF(c.x(), c.y() - 214 * k)
    needle.moveTo(tip)
    needle.lineTo(c.x() + 15 * k, c.y() - 30 * k)
    needle.lineTo(c.x() - 15 * k, c.y() - 30 * k)
    needle.closeSubpath()
    hub = circle(c, 64 * k)
    sil = qimage(S)
    p = painter(sil)
    p.fillPath(needle.united(hub), QColor(0, 0, 0))
    p.end()
    out.alpha_composite(shadow_of(sil, 12 * k, 0.8, 10 * k))
    layer = qimage(S)
    p = painter(layer)
    ng = QLinearGradient(c.x() - 15 * k, 0, c.x() + 15 * k, 0)
    ng.setColorAt(0, QColor("#fff3d9"))
    ng.setColorAt(0.5, QColor("#d8ad62"))
    ng.setColorAt(1, QColor("#7d5a22"))
    p.fillPath(needle, ng)
    p.fillPath(hub, metal(c, 60))
    dome = QRadialGradient(QPointF(c.x() - 18 * k, c.y() - 22 * k), 60 * k)
    dome.setColorAt(0, QColor(255, 255, 255, 150))
    dome.setColorAt(0.5, QColor(255, 255, 255, 20))
    dome.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(circle(c, 52 * k), dome)
    p.setPen(QPen(QColor(60, 40, 10, 170), 2 * k))
    p.drawEllipse(c, 64 * k, 64 * k)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#16181f"))
    p.drawEllipse(c, 13 * k, 13 * k)

    # 8. glass dome over the face
    hl = circle(c, R_FACE - 4 * k).intersected(
        circle(QPointF(c.x(), c.y() - R_FACE * 0.95), R_FACE * 1.05))
    hg = QLinearGradient(0, c.y() - R_FACE, 0, c.y() - R_FACE * 0.42)   # gone before the arc's edge
    hg.setColorAt(0, QColor(255, 255, 255, 40))
    hg.setColorAt(0.6, QColor(255, 255, 255, 12))
    hg.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillPath(hl, hg)
    # tile rim light
    rim = QLinearGradient(0, 100 * k, 0, 924 * k)
    rim.setColorAt(0, QColor(255, 255, 255, 70))
    rim.setColorAt(0.25, QColor(255, 255, 255, 10))
    rim.setColorAt(1, QColor(255, 255, 255, 18))
    p.setPen(QPen(QBrush(rim), 2.5 * k))
    p.setBrush(Qt.NoBrush)
    p.drawPath(tile)
    p.end()
    out.alpha_composite(to_pil(layer))
    return out


# ---------------------------------------------------------------- text helpers (PIL)
def font(dirs, name, px):
    for d in dirs:
        f = Path(d) / name
        if f.exists():
            return ImageFont.truetype(str(f), px)
    try:
        return ImageFont.truetype(name, px)
    except OSError:
        return ImageFont.load_default(size=px)


def vgradient(size, stops) -> Image.Image:
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


def gold_text(bg: Image.Image, xy, text, f):
    mask = Image.new("L", bg.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255)
    g = vgradient(bg.size, [(0, GOLD_TOP), (0.5, GOLD_MID), (1, GOLD_LOW)]).convert("RGBA")
    g.putalpha(mask)
    bg.alpha_composite(g)


def spaced(d: ImageDraw.ImageDraw, cx, y, text, f, fill, spacing):
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill)
        x += w + spacing
    return total


def dark_backdrop(W, H, s) -> Image.Image:
    bg = vgradient((W, H), [(0, (24, 25, 33)), (1, (8, 9, 13))]).convert("RGBA")
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W * 0.15, H * 0.2, W * 0.85, H * 0.9), fill=56)
    glow = glow.filter(ImageFilter.GaussianBlur(70 * s))
    tint = Image.new("RGBA", (W, H), (*GOLD_MID, 0))
    tint.putalpha(glow)
    bg.alpha_composite(tint)
    return bg


# ---------------------------------------------------------------- DMG background
def make_dmg_background(scale: int, fonts) -> Image.Image:
    W, H, s = 660 * scale, 420 * scale, scale
    bg = dark_backdrop(W, H, s)
    d = ImageDraw.Draw(bg, "RGBA")
    title = font(fonts, "InterDisplay-SemiBold.otf", 34 * s)
    gold_text(bg, ((W - d.textlength(APP, font=title)) / 2, 34 * s), APP, title)
    sub = font(fonts, "Inter-Regular.otf", 13 * s)
    line = "Drag the app into Applications to install"
    d.text(((W - d.textlength(line, font=sub)) / 2, 80 * s), line, font=sub, fill=(247, 244, 238, 165))
    y, x0, x1 = 215 * s, 238 * s, 422 * s          # arrow between the two icons
    for i in range(int(x0), int(x1 - 14 * s), int(9 * s)):
        d.ellipse((i, y - 1.6 * s, i + 3.2 * s, y + 1.6 * s), fill=(*GOLD_MID, 210))
    d.polygon([(x1, y), (x1 - 14 * s, y - 8 * s), (x1 - 14 * s, y + 8 * s)], fill=(*GOLD_TOP, 235))
    sig_f = font(fonts, "Inter-Medium.otf", 12 * s)
    ys = 352 * s
    w = spaced(d, W / 2, ys, CREDIT.upper(), sig_f, (*GOLD_TOP, 230), 2.2 * s)
    lx = (W - w) / 2
    for xa, xb in ((lx - 70 * s, lx - 16 * s), (lx + w + 16 * s, lx + w + 70 * s)):
        d.line((xa, ys + 8 * s, xb, ys + 8 * s), fill=(*GOLD_MID, 150), width=max(1, s))
    ver = font(fonts, "Inter-Regular.otf", 10 * s)
    v = f"Version {__version__}"
    d.text(((W - d.textlength(v, font=ver)) / 2, 376 * s), v, font=ver, fill=(247, 244, 238, 90))
    return bg.convert("RGB")


# ---------------------------------------------------------------- Windows installer art
def make_wizard_large(scale: int, icon: Image.Image, fonts) -> Image.Image:
    W, H, s = 164 * scale, 314 * scale, scale
    bg = dark_backdrop(W, H, s)
    ic = icon.resize((120 * s, 120 * s), Image.LANCZOS)
    bg.alpha_composite(ic, ((W - ic.width) // 2, 52 * s))
    d = ImageDraw.Draw(bg, "RGBA")
    t = font(fonts, "InterDisplay-SemiBold.otf", 22 * s)
    gold_text(bg, ((W - d.textlength(APP, font=t)) / 2, 182 * s), APP, t)
    f = font(fonts, "Inter-Medium.otf", 7 * s)
    spaced(d, W / 2, 282 * s, "MADE BY", f, (*GOLD_TOP, 170), 1.2 * s)
    f2 = font(fonts, "Inter-Medium.otf", 9 * s)
    name = CREDIT.replace("Made by ", "")
    d.text(((W - d.textlength(name, font=f2)) / 2, 294 * s), name, font=f2, fill=(*GOLD_TOP, 235))
    return bg.convert("RGB")


def make_wizard_small(scale: int, icon: Image.Image) -> Image.Image:
    n = 55 * scale
    bg = Image.new("RGBA", (n, n), (255, 255, 255, 255))   # the wizard's header is white
    ic = icon.resize((n, n), Image.LANCZOS)
    bg.alpha_composite(ic)
    return bg.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font-dir", action="append", default=["/usr/share/fonts/opentype/inter",
                                                            "/Library/Fonts", str(Path.home() / "Library/Fonts")])
    ap.add_argument("--preview", help="also write a contact sheet of the icon at several sizes")
    a = ap.parse_args()
    QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    big = make_icon(2048)                     # supersample, then downscale for crisp edges
    icon = big.resize((1024, 1024), Image.LANCZOS)
    assets = ROOT / "dropdial" / "assets"
    icon.save(assets / "dropdial.png")
    icon.save(assets / "dropdial.icns", sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256),
                                               (512, 512), (1024, 1024)])
    icon.save(assets / "dropdial.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                              (128, 128), (256, 256)])
    mac = ROOT / "packaging" / "mac"
    make_dmg_background(1, a.font_dir).save(mac / "dmg-background.png")
    make_dmg_background(2, a.font_dir).save(mac / "dmg-background@2x.png")
    inst = ROOT / "installer"
    make_wizard_large(1, icon, a.font_dir).save(inst / "wizard-large.bmp")
    make_wizard_large(2, icon, a.font_dir).save(inst / "wizard-large@2x.bmp")
    make_wizard_small(1, icon).save(inst / "wizard-small.bmp")
    make_wizard_small(2, icon).save(inst / "wizard-small@2x.bmp")
    if a.preview:
        sizes = [512, 256, 128, 64, 32]
        sheet = Image.new("RGBA", (sum(sizes) + 40 * len(sizes) + 40, 600), (236, 236, 240, 255))
        x = 40
        for sz in sizes:
            sheet.alpha_composite(icon.resize((sz, sz), Image.LANCZOS), (x, (600 - sz) // 2))
            x += sz + 40
        sheet.save(a.preview)
    print("wrote icon, DMG background and installer artwork")


if __name__ == "__main__":
    main()
