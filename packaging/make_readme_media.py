"""Renders the README's media from the real app (offscreen):

    python packaging/make_readme_media.py

  docs/banner.png          header banner (1280x640, also works as the GitHub social preview)
  docs/demo.gif            drag a photo, press Shift, pick a slice, see the result
  docs/btn-*.svg           download buttons
  docs/toast.png           a result card
"""
from __future__ import annotations

import importlib.util
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = Path(tempfile.mkdtemp(prefix="dropdial-media-"))
os.environ["DROPDIAL_HOME"] = str(TMP / "home")

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QThreadPool  # noqa: E402
from PySide6.QtGui import QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

APP_Q = QApplication.instance() or QApplication(sys.argv[:1])

from dropdial import glass, imaging  # noqa: E402
from dropdial.app import DropDialApp  # noqa: E402
from dropdial.radial import R_IN, R_OUT, SIZE, RadialMenu, angles  # noqa: E402
from dropdial.report import Result  # noqa: E402
from dropdial.toasts import ToastStack  # noqa: E402

spec = importlib.util.spec_from_file_location("make_art", ROOT / "packaging" / "make_art.py")
art = importlib.util.module_from_spec(spec)
spec.loader.exec_module(art)
FONTS = ["/usr/share/fonts/opentype/inter", "/Library/Fonts", str(Path.home() / "Library/Fonts")]
DOCS = ROOT / "docs"


def pump(t=0.15):
    import time
    end = time.time() + t
    while time.time() < end:
        APP_Q.processEvents()
        time.sleep(0.01)


def wallpaper(w, h) -> Image.Image:
    """A soft, colourful desktop so the glass has something to refract."""
    wp = imaging.gradient((w, h), ["#0e2340", "#1b4a68", "#33285a"], 125)
    d = ImageDraw.Draw(wp)
    for fx, fy, fr, col in [(0.2, 0.25, 0.28, "#e08a4b"), (0.8, 0.72, 0.33, "#2a8c9c"),
                            (0.58, 0.18, 0.2, "#c25a7a"), (0.32, 0.82, 0.25, "#5a6fd8")]:
        r = fr * w
        d.ellipse((fx * w - r, fy * h - r, fx * w + r, fy * h + r), fill=col)
    return wp.filter(ImageFilter.GaussianBlur(w * 0.075))


def sample_photo() -> Path:
    p = TMP / "photo.jpg"
    im = imaging.gradient((1200, 800), ["#ffb36b", "#ff5f6d", "#7b5cff"], 135)
    d = ImageDraw.Draw(im)
    d.ellipse((760, 120, 1040, 400), fill="#ffe2a8")                    # sun
    d.polygon([(0, 800), (380, 380), (700, 800)], fill="#2b2140")         # mountains
    d.polygon([(420, 800), (860, 300), (1200, 800)], fill="#3b2c58")
    im.save(p, quality=92)
    return p


# ---------------------------------------------------------------- menu rendering
class Menu:
    def __init__(self, photo: Path, backdrop: Image.Image):
        self.m = RadialMenu(lambda paths: DropDialApp.build_rings(None, paths), lambda paths: "2.4 MB")
        self.m.popup(QPoint(800, 500), [str(photo)])
        pump()
        self.set_backdrop(backdrop)

    def set_backdrop(self, crop: Image.Image):
        m = self.m
        m._serial += 1
        m._raw_backdrop = crop.convert("RGB")
        m.backdrop = glass.blur_pixmap(QPixmap.fromImage(glass.qimage_from_pil(m._raw_backdrop)), 24)
        m.liquid = {}
        for items in m.rings.values():
            m._render(len(items))
        QThreadPool.globalInstance().waitForDone(10000)
        pump(0.3)

    def frame(self, t=1.0, swap=1.0, hover=-1, cursor=None) -> Image.Image:
        m = self.m
        m.anim.stop()
        m.swap_anim.stop()
        m._t, m._swap = t, swap
        if hover != m.hover:
            m.hover = hover
        if cursor is not None:
            m.cursor_pos = QPointF(*cursor)
        m._tick()
        m.repaint()
        return glass.pil_from_qimage(m.grab().toImage()).convert("RGBA")

    def ring(self, idx):
        self.m.ring_idx = idx
        self.m.spring = [0.0] * len(self.m.items)

    def petal_center(self, i) -> tuple[float, float]:
        n = len(self.m.items)
        a0, a1 = angles(n, i)
        mid = math.radians((a0 + a1) / 2)
        r = (R_IN + R_OUT) / 2
        return SIZE / 2 + r * math.cos(mid), SIZE / 2 - r * math.sin(mid)


def toast_image(photo: Path) -> Image.Image:
    card = ToastStack().new()
    card.done(Result("Compressed", "2.4 MB → 610 KB · photo Compressed.jpg", [photo], [photo], good="75% smaller"))
    pump(0.2)
    im = glass.pil_from_qimage(card.grab().toImage()).convert("RGBA")
    card.hide()
    return im


# ---------------------------------------------------------------- overlays
def cursor_img(scale=1.0) -> Image.Image:
    s = 4
    pts = [(0, 0), (0, 17), (4.3, 13.2), (7.2, 19.6), (9.8, 18.5), (7, 12.3), (12.5, 12.3)]
    im = Image.new("RGBA", (int(20 * s), int(24 * s)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    big = [(x * s + 2 * s, y * s + 2 * s) for x, y in pts]
    d.polygon(big, fill=(0, 0, 0, 255))
    inner = [(x * s * 0.84 + 2 * s + 1.1 * s, y * s * 0.84 + 2 * s + 1.8 * s) for x, y in pts]
    d.polygon(inner, fill=(255, 255, 255, 255))
    w = int(22 * scale)
    return im.resize((w, int(w * 1.2)), Image.LANCZOS)


def drag_card(photo: Path) -> Image.Image:
    """What a file looks like while you drag it: a thumbnail and its name."""
    s = 2
    W, H = 92 * s, 96 * s
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    th = Image.open(photo).convert("RGBA")
    th.thumbnail((72 * s, 52 * s))
    mask = Image.new("L", th.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, th.width - 1, th.height - 1), 6 * s, fill=255)
    im.paste(th, ((W - th.width) // 2, 6 * s), mask)
    d = ImageDraw.Draw(im, "RGBA")
    f = art.font(FONTS, "Inter-Medium.otf", 11 * s)
    label = "photo.jpg"
    tw = d.textlength(label, font=f)
    d.rounded_rectangle(((W - tw) / 2 - 7 * s, 64 * s, (W + tw) / 2 + 7 * s, 82 * s), 9 * s, fill=(10, 96, 230, 235))
    d.text(((W - tw) / 2, 66 * s), label, font=f, fill="white")
    im = im.resize((W // s, H // s), Image.LANCZOS)
    a = im.getchannel("A").point(lambda v: int(v * 0.88))
    im.putalpha(a)
    return im


def keycap(text="⇧  shift") -> Image.Image:
    s = 2
    f = art.font(FONTS, "Inter-SemiBold.otf", 15 * s)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    w = int(probe.textlength(text, font=f)) + 34 * s
    h = 40 * s
    im = Image.new("RGBA", (w + 8 * s, h + 10 * s), (0, 0, 0, 0))
    sh = Image.new("L", im.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle((4 * s, 8 * s, w + 4 * s, h + 8 * s), 10 * s, fill=150)
    im.putalpha(sh.filter(ImageFilter.GaussianBlur(5 * s)))
    im = Image.merge("RGBA", (*[Image.new("L", im.size, 0)] * 3, im.getchannel("A")))
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle((4 * s, 2 * s, w + 4 * s, h + 2 * s), 10 * s, fill=(22, 23, 30, 240),
                        outline=(227, 190, 122, 220), width=2 * s)
    d.text((4 * s + 17 * s, 2 * s + 9 * s), text, font=f, fill=(247, 231, 193, 255))
    return im.resize((im.width // s, im.height // s), Image.LANCZOS)


def ease(t):
    return t * t * (3 - 2 * t)


def out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def with_alpha(im: Image.Image, a: float) -> Image.Image:
    if a >= 1:
        return im
    out = im.copy()
    out.putalpha(im.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return out


# ---------------------------------------------------------------- demo GIF
def make_demo(photo: Path):
    W, H = 760, 470
    wp = wallpaper(W, H)
    mc = (W // 2, H // 2 - 4)                      # menu centre on the canvas
    tl = (mc[0] - SIZE // 2, mc[1] - SIZE // 2)
    menu = Menu(photo, wp.crop((tl[0], tl[1], tl[0] + SIZE, tl[1] + SIZE)))
    toast = toast_image(photo)
    toast = toast.resize((int(toast.width * 0.86), int(toast.height * 0.86)), Image.LANCZOS)
    card, cur, key = drag_card(photo), cursor_img(), keycap()

    # timeline: (frames, what happens)
    frames: list[Image.Image] = []
    pos = [130.0, 360.0]

    def compose(menu_img=None, menu_alpha=1.0, key_alpha=0.0, toast_t=None, show_card=True):
        fr = wp.convert("RGBA").copy()
        if menu_img is not None:
            fr.alpha_composite(with_alpha(menu_img, menu_alpha), tl)
        if key_alpha > 0:
            fr.alpha_composite(with_alpha(key, key_alpha), ((W - key.width) // 2, H - key.height - 14))
        if toast_t is not None:
            tx = W - toast.width - 16
            ty = int(H - 16 - toast.height * ease(min(1, toast_t)))
            fr.alpha_composite(with_alpha(toast, min(1, toast_t * 1.4)), (tx, max(ty, H - toast.height - 16)))
        x, y = int(pos[0]), int(pos[1])
        if show_card:
            fr.alpha_composite(card, (x - card.width // 2 + 4, y + 8))
        fr.alpha_composite(cur, (x - 3, y - 3))
        frames.append(fr.convert("RGB"))

    def glide(to, n, **kw):
        sx, sy = pos
        for i in range(1, n + 1):
            k = ease(i / n)
            pos[0], pos[1] = sx + (to[0] - sx) * k, sy + (to[1] - sy) * k
            yield i, n

    def local(p):
        return p[0] - tl[0], p[1] - tl[1]

    def petal(i):
        lx, ly = menu.petal_center(i)
        return lx + tl[0], ly + tl[1]

    # 1. drag the photo towards the middle
    for _ in range(4):
        compose()
    for _ in glide(mc, 14):
        compose()
    # 2. press Shift: the dial opens
    menu.ring(0)
    for i in range(8):
        k = min(1.0, i / 6)
        compose(menu.frame(t=max(0.0, out_back(k)) if i else 0.0, cursor=local(pos)), key_alpha=min(1, i / 3))
    # 3. look around the Convert ring
    for target in (2, 5):
        tgt = petal(target)
        for _ in glide(tgt, 7):
            compose(menu.frame(hover=menu.m.hit(QPointF(*local(pos))), cursor=local(pos)), key_alpha=0.0)
        for _ in range(5):
            compose(menu.frame(hover=target, cursor=local(pos)))
    # 4. tap Shift: switch to Tools
    for _ in glide(mc, 6):
        compose(menu.frame(hover=-1, cursor=local(pos)))
    menu.ring(1)
    for i in range(1, 8):
        compose(menu.frame(swap=ease(min(1, i / 6)), hover=-1, cursor=local(pos)), key_alpha=1.0 if i < 6 else 0.5)
    # 5. hover Compress and drop
    tgt = petal(0)
    for _ in glide(tgt, 8):
        compose(menu.frame(hover=menu.m.hit(QPointF(*local(pos))), cursor=local(pos)))
    for _ in range(7):
        compose(menu.frame(hover=0, cursor=local(pos)))
    last = menu.frame(hover=0, cursor=local(pos))
    for i in range(1, 6):
        compose(last, menu_alpha=1 - i / 5, show_card=i < 2)
    # 6. the result
    for i in range(1, 9):
        compose(toast_t=i / 8, show_card=False)
    for _ in range(26):
        compose(toast_t=1.0, show_card=False)
    for i in range(1, 6):
        compose(toast_t=1.0, show_card=False)
        frames[-1] = Image.blend(frames[-1], frames[0], i / 5)   # dissolve back to the start: seamless loop

    # one shared palette keeps the gold and glass smooth and the file small
    master = Image.new("RGB", (W, H * 4))
    for j, k in enumerate((0, len(frames) // 3, len(frames) // 2, len(frames) - 30)):
        master.paste(frames[k], (0, H * j))
    pal = master.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    durations = [55] * len(q)
    q[0].save(DOCS / "demo.gif", save_all=True, append_images=q[1:], duration=durations, loop=0,
              optimize=True, disposal=1)
    menu.m.hide()
    return len(q)


# ---------------------------------------------------------------- banner
def make_banner(photo: Path):
    W, H = 1280, 640
    bg = art.dark_backdrop(W, H, 2)
    # a pool of colour on the right for the glass to refract
    pool = wallpaper(W, H)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse((W * 0.52, H * 0.0, W * 1.08, H * 1.02), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(90))
    bg.paste(pool.convert("RGBA"), (0, 0), mask)
    mc = (int(W * 0.765), H // 2 + 6)
    tl = (mc[0] - SIZE // 2, mc[1] - SIZE // 2)
    menu = Menu(photo, bg.crop((tl[0], tl[1], tl[0] + SIZE, tl[1] + SIZE)))
    menu.ring(1)
    cx, cy = menu.petal_center(7)
    img = None
    for _ in range(14):
        img = menu.frame(hover=7, cursor=(cx, cy))
    bg.alpha_composite(img, tl)
    menu.m.hide()

    icon = Image.open(ROOT / "dropdial" / "assets" / "dropdial.png").convert("RGBA").resize((148, 148), Image.LANCZOS)
    bg.alpha_composite(icon, (92, 120))
    d = ImageDraw.Draw(bg, "RGBA")
    title = art.font(FONTS, "InterDisplay-SemiBold.otf", 96)
    art.gold_text(bg, (88, 276), "DropDial", title)
    tag = art.font(FONTS, "Inter-Regular.otf", 27)
    d.text((94, 400), "Drag a file. Press Shift. Drop it on the dial.", font=tag, fill=(247, 244, 238, 230))
    d.text((94, 438), "Convert, compress and edit anything in a second.", font=tag, fill=(247, 244, 238, 150))
    chip_f = art.font(FONTS, "Inter-Medium.otf", 17)
    chips = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # own layer: translucent fills blend correctly
    cd = ImageDraw.Draw(chips)
    x = 94
    for label in ("macOS", "Windows", "Linux"):
        tw = cd.textlength(label, font=chip_f)
        cd.rounded_rectangle((x, 500, x + tw + 30, 534), 17, fill=(255, 255, 255, 16), outline=(227, 190, 122, 160),
                             width=1)
        cd.text((x + 15, 507), label, font=chip_f, fill=(247, 231, 193, 255))
        x += tw + 42
    bg.alpha_composite(chips)
    sig = art.font(FONTS, "Inter-Medium.otf", 14)
    art.spaced(d, 94 + 150, 584, "MADE BY PRITHWIRAJ MUKHERJEE", sig, (227, 190, 122, 200), 2.0)
    bg.convert("RGB").save(DOCS / "banner.png", optimize=True)


# ---------------------------------------------------------------- buttons
BUTTON = """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="56" viewBox="0 0 {w} 56">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#262833"/><stop offset="1" stop-color="#0d0e13"/>
    </linearGradient>
    <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#f7e7c1"/><stop offset="0.55" stop-color="#d8ad62"/><stop offset="1" stop-color="#a87a34"/>
    </linearGradient>
  </defs>
  <rect x="1" y="1" width="{iw}" height="54" rx="14" fill="url(#bg)" stroke="url(#gold)" stroke-width="1.5"/>
  <g transform="translate(18 14)" fill="url(#gold)">{icon}</g>
  <text x="58" y="25" font-family="-apple-system, 'Segoe UI', Inter, Helvetica, Arial, sans-serif" font-size="11"
        fill="#e3be7a" letter-spacing="1.2">{small}</text>
  <text x="58" y="43" font-family="-apple-system, 'Segoe UI', Inter, Helvetica, Arial, sans-serif" font-size="17"
        font-weight="600" fill="#f7f4ee">{big}</text>
</svg>
"""
ICONS = {
    # simplified platform marks, drawn in a 28x28 box
    "apple": '<path d="M19.6 14.9c0-2.6 2.1-3.8 2.2-3.9-1.2-1.8-3.1-2-3.7-2-1.6-.2-3.1.9-3.9.9-.8 0-2-.9-3.4-.9-1.7 0-3.3 1-4.2 2.6-1.8 3.1-.5 7.7 1.3 10.2.9 1.2 1.9 2.6 3.2 2.6 1.3-.1 1.8-.8 3.3-.8 1.6 0 2 .8 3.4.8 1.4 0 2.3-1.3 3.1-2.5 1-1.4 1.4-2.8 1.4-2.9-.1 0-2.7-1-2.7-4.1zM17 7.3c.7-.9 1.2-2.1 1.1-3.3-1 0-2.3.7-3 1.6-.7.8-1.2 2-1.1 3.2 1.2.1 2.3-.6 3-1.5z"/>',
    "windows": '<path d="M3 6.5l9-1.3v8.6H3zM13.2 5l11.8-1.7v10.5H13.2zM3 15.1h9v8.7l-9-1.3zM13.2 15.1H25v10.6L13.2 24z"/>',
    "linux": '<path d="M14 3c-2.6 0-4 2.2-4 5 0 1.5.3 2.6-.6 4.1-1.2 2-3.2 4.4-3.2 7.3 0 1 .3 1.8.8 2.4-.9.5-2 .9-2 1.9 0 1.2 1.6 1.3 3.4 1.7 1.6.3 2.7 1.1 3.6 1.1 1 0 1.5-.6 2-.6s1 .6 2 .6c.9 0 2-.8 3.6-1.1 1.8-.4 3.4-.5 3.4-1.7 0-1-1.1-1.4-2-1.9.5-.6.8-1.4.8-2.4 0-2.9-2-5.3-3.2-7.3-.9-1.5-.6-2.6-.6-4.1 0-2.8-1.4-5-4-5zm-1.7 4.6c.5 0 .8.6.8 1.2s-.3 1.1-.8 1.1-.8-.5-.8-1.1.3-1.2.8-1.2zm3.4 0c.5 0 .8.6.8 1.2s-.3 1.1-.8 1.1-.8-.5-.8-1.1.3-1.2.8-1.2zM14 11.2c1.1 0 2.3.7 2.3 1.2s-1.2 1.2-2.3 1.2-2.3-.7-2.3-1.2 1.2-1.2 2.3-1.2z"/>',
}


def make_buttons():
    for name, icon, small, big, w in [
        ("mac-arm", "apple", "MACOS · APPLE SILICON", "Download .dmg", 236),
        ("mac-intel", "apple", "MACOS · INTEL", "Download .dmg", 236),
        ("win", "windows", "WINDOWS · INSTALLER", "Download .exe", 236),
        ("linux", "linux", "LINUX · DEBIAN / UBUNTU", "Download .deb", 236),
    ]:
        (DOCS / f"btn-{name}.svg").write_text(BUTTON.format(w=w, iw=w - 2, icon=ICONS[icon], small=small, big=big),
                                              encoding="utf-8")


def make_toast_shot(photo: Path):
    t = toast_image(photo)
    bg = wallpaper(t.width + 60, t.height + 60).convert("RGBA")
    bg.alpha_composite(t, (30, 30))
    bg.convert("RGB").save(DOCS / "toast.png", optimize=True)


def main():
    photo = sample_photo()
    make_buttons()
    make_toast_shot(photo)
    make_banner(photo)
    n = make_demo(photo)
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"wrote banner, buttons and a {n}-frame demo")


if __name__ == "__main__":
    main()
