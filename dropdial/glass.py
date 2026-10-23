"""Liquid-glass look: frosted blur, specular highlights and an iridescent (rainbow)
rim. Used by the radial menu and every editor window."""
from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)

# "Midnight & Champagne": graphite glass, champagne-gold accents, a pearl/gold rim
# instead of a rainbow. Every colour in the UI comes from here.
IRIDESCENT = ["#f4dfb2", "#fffaf0", "#cfd6e4", "#e6c27e", "#fff3dc", "#b8c1d6", "#f4dfb2"]
_CHAMPAGNE_RIM = list(IRIDESCENT)

TEXT = "#f7f4ee"
TEXT_DIM = "rgba(247,244,238,0.62)"
ACCENT_A = "#f7e7c1"      # champagne highlight
ACCENT_B = "#d8ad62"      # gold
ACCENT_C = "#a87a34"      # deep gold
ON_ACCENT = "#1a1408"     # text on gold
GOLD = "#e3be7a"
SURFACE = "#14151c"       # menus, popups
MIDNIGHT = (13, 14, 20)   # glass tint base


# accent palettes: (highlight, mid, deep, text-accent, text on accent)
ACCENTS = {
    "champagne": ("#f7e7c1", "#d8ad62", "#a87a34", "#e3be7a", "#1a1408"),
    "rose": ("#ffdbe3", "#e88ba1", "#b4506b", "#f2a5b7", "#2a0d16"),
    "ocean": ("#d6ecff", "#62a9e9", "#2f6fb3", "#8fc5f3", "#061a2c"),
    "emerald": ("#d8f6e6", "#4fc48e", "#1f8a5c", "#82d8aa", "#06200f"),
    "violet": ("#e8deff", "#9d86f1", "#6a4fc9", "#baa8f8", "#140a2e"),
    "silver": ("#f5f7fb", "#c5cbd6", "#8b94a4", "#d9dee8", "#12151b"),
}
ACCENT_NAMES = {"champagne": "Champagne", "rose": "Rose", "ocean": "Ocean", "emerald": "Emerald",
                "violet": "Violet", "silver": "Silver"}
ACCENT = "champagne"


def set_accent(name: str) -> None:
    """Switch the accent colour. Windows opened afterwards (and the dial) use it."""
    global ACCENT, ACCENT_A, ACCENT_B, ACCENT_C, GOLD, ON_ACCENT, IRIDESCENT, QSS
    if name not in ACCENTS:
        name = "champagne"
    ACCENT = name
    ACCENT_A, ACCENT_B, ACCENT_C, GOLD, ON_ACCENT = ACCENTS[name]
    if globals().get("THEME") == "light":
        GOLD = ACCENT_C              # the light accent would vanish on pale glass: use the deep one
    IRIDESCENT = (_CHAMPAGNE_RIM if name == "champagne" else
                  [ACCENT_A, "#fffaf0", "#cfd6e4", ACCENT_B, "#fff3dc", "#b8c1d6", ACCENT_A])
    QSS = build_qss()


THEME = "dark"            # "dark" or "light" (windows, toasts and the dial)
DIAL_OPACITY = 1.0        # 0.4 … 1.0: how solid the dial's glass is (labels stay fully opaque)
_DARK = dict(TEXT="#f7f4ee", TEXT_DIM="rgba(247,244,238,0.62)", SURFACE="#14151c", MIDNIGHT=(13, 14, 20))
_LIGHT = dict(TEXT="#1f1c17", TEXT_DIM="rgba(31,28,23,0.62)", SURFACE="#f6f3ee", MIDNIGHT=(244, 241, 235))


def set_theme(name: str) -> None:
    """'dark' or 'light'. Windows opened afterwards use it; the dial picks it up on its next show."""
    global THEME, TEXT, TEXT_DIM, SURFACE, MIDNIGHT, QSS
    THEME = "light" if name == "light" else "dark"
    v = _LIGHT if THEME == "light" else _DARK
    TEXT, TEXT_DIM, SURFACE, MIDNIGHT = v["TEXT"], v["TEXT_DIM"], v["SURFACE"], v["MIDNIGHT"]
    set_accent(ACCENT)              # recomputes the text accent for this theme and rebuilds QSS


def system_theme() -> str:
    """The OS appearance (Qt 6.5+), 'dark' if unknown."""
    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import Qt
        hints = QGuiApplication.styleHints()
        return "light" if hints.colorScheme() == Qt.ColorScheme.Light else "dark"
    except Exception:  # noqa: BLE001
        return "dark"


def is_light() -> bool:
    return THEME == "light"


def fg(alpha: int = 255) -> QColor:
    """Text colour for hand-painted widgets."""
    c = QColor(TEXT)
    c.setAlpha(alpha)
    return c


def ov(alpha: int) -> QColor:
    """A faint overlay that lifts a surface: white on dark glass, ink on light glass."""
    return QColor(255, 255, 255, alpha) if THEME == "dark" else QColor(20, 18, 14, alpha)


def accent(which: str = "gold", alpha: int = 255) -> QColor:
    """The current accent as a QColor: 'hi' (light), 'mid', 'deep' or 'gold' (text accent)."""
    c = QColor({"hi": ACCENT_A, "mid": ACCENT_B, "deep": ACCENT_C, "gold": GOLD}[which])
    c.setAlpha(alpha)
    return c


def glass_tint(alpha: int, lift: int = 0) -> QColor:
    """The glass tint: near-black midnight (or warm pearl in the light theme), lifted a little."""
    r, g, b = MIDNIGHT
    if THEME == "light":
        return QColor(r - lift, g - lift, b - lift, min(255, alpha + 10))
    return QColor(r + lift, g + lift, b + lift + 4, alpha)


def gold(alpha: int = 255) -> QColor:
    c = QColor(GOLD)
    c.setAlpha(alpha)
    return c


def iridescent_pen(center: QPointF, width: float, alpha: int = 200, angle: float = 30) -> QPen:
    g = QConicalGradient(center, angle)
    n = len(IRIDESCENT) - 1
    for i, c in enumerate(IRIDESCENT):
        col = QColor(c)
        col.setAlpha(alpha)
        g.setColorAt(i / n, col)
    return QPen(QBrush(g), width)


def iridescent_brush(rect: QRectF, alpha: int = 60) -> QBrush:
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    n = len(IRIDESCENT) - 1
    for i, c in enumerate(IRIDESCENT):
        col = QColor(c)
        col.setAlpha(alpha)
        g.setColorAt(i / n, col)
    return QBrush(g)


def blur_pixmap(pm: QPixmap, radius: int = 18) -> QPixmap:
    """Fast frosted blur: downscale, light box blur via repeated scaling, upscale."""
    if pm.isNull():
        return pm
    w, h = pm.width(), pm.height()
    f = max(2, radius // 3)
    small = pm.scaled(max(1, w // f), max(1, h // f), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.scaled(max(1, w // (f * 2)), max(1, h // (f * 2)), Qt.IgnoreAspectRatio,
                         Qt.SmoothTransformation)
    return small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def paint_glass(p: QPainter, path: QPainterPath, backdrop: QPixmap | None = None,
                backdrop_offset: QPointF = QPointF(0, 0), tint: QColor | None = None,
                rim: bool = True, rainbow_alpha: int = 170, highlight: float = 1.0) -> None:
    """Paint a liquid-glass surface filling `path`."""
    rect = path.boundingRect()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setClipPath(path)

    # 1. frosted backdrop (blurred desktop snapshot), slightly magnified = refraction
    if backdrop is not None and not backdrop.isNull():
        p.save()
        c = rect.center()
        p.translate(c)
        p.scale(1.04, 1.04)
        p.translate(-c)
        p.drawPixmap(backdrop_offset, backdrop)
        p.restore()

    # 2. tint – keeps white text readable on any wallpaper
    p.fillPath(path, tint if tint is not None else glass_tint(105))

    # 3. faint pearl wash across the body
    p.fillPath(path, iridescent_brush(rect, 14))

    # 4. top specular sheen
    sheen = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + rect.height() * 0.55))
    sheen.setColorAt(0.0, QColor(255, 255, 255, int(70 * highlight)))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillPath(path, sheen)

    # 5. soft caustic glow lower-right
    glow = QRadialGradient(QPointF(rect.right() - rect.width() * 0.2, rect.bottom() - rect.height() * 0.15),
                           max(rect.width(), rect.height()) * 0.55)
    glow.setColorAt(0.0, QColor(255, 255, 255, int(22 * highlight)))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillPath(path, glow)
    p.restore()

    if rim:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        # inner bezel glow: a wide, soft white stroke clipped to the inside of the shape
        p.setClipPath(path)
        for w, a in ((14, 10), (7, 16), (3, 26)):
            p.setPen(QPen(QColor(255, 255, 255, int(a * highlight)), w))
            p.drawPath(path)
        p.setClipping(False)
        # specular rim: bright on the edge facing the light (top-left), softer opposite
        spec = QLinearGradient(rect.topLeft(), rect.bottomRight())
        spec.setColorAt(0.0, QColor(255, 255, 255, int(235 * min(1.0, highlight))))
        spec.setColorAt(0.35, QColor(255, 255, 255, 60))
        spec.setColorAt(0.65, QColor(255, 255, 255, 35))
        spec.setColorAt(1.0, QColor(255, 255, 255, 150))
        p.setPen(QPen(QBrush(spec), 1.3))
        p.drawPath(path)
        # iridescent dispersion just outside the rim
        p.setPen(iridescent_pen(rect.center(), 1.4, rainbow_alpha))
        p.drawPath(path.translated(0.0, 0.0))
        p.restore()


# ---------------------------------------------------------------- Qt stylesheet
def _rgba(hex_color: str, a: float) -> str:
    c = QColor(hex_color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


def build_qss() -> str:
    qss = _qss_dark()
    return _light_qss(qss) if THEME == "light" else qss


def _qss_dark() -> str:
    return f"""
* {{ color: {TEXT}; font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif; font-size: 10pt; }}
QWidget#glassRoot {{ background: transparent; }}
QLabel#title {{ font-size: 11pt; font-weight: 600; letter-spacing: 0.3px; }}
QLabel#dim, QLabel.dim {{ color: {TEXT_DIM}; font-size: 9pt; }}
QLabel#section {{ color: {GOLD}; font-size: 8pt; font-weight: 700; letter-spacing: 1.6px; }}
QLabel#credit {{ color: {_rgba(GOLD, 0.85)}; font-size: 8.5pt; letter-spacing: 0.6px; }}
QPushButton {{
  background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.16);
  border-top-color: rgba(255,255,255,0.30); border-bottom-color: rgba(255,255,255,0.08);
  border-radius: 15px; padding: 6px 15px; min-height: 18px;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.13); border-color: {_rgba(GOLD, 0.55)}; }}
QPushButton:pressed {{ background: rgba(255,255,255,0.04); }}
QPushButton:disabled {{ color: rgba(247,244,238,0.35); border-color: rgba(255,255,255,0.08); }}
QPushButton:checked {{
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {ACCENT_A}, stop:0.5 {ACCENT_B}, stop:1 {ACCENT_C});
  color: {ON_ACCENT}; font-weight: 600; border: 1px solid {_rgba(ACCENT_A, 0.75)};
}}
QPushButton#primary {{
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {ACCENT_A}, stop:0.45 {ACCENT_B}, stop:1 {ACCENT_C});
  color: {ON_ACCENT}; border: 1px solid {_rgba(ACCENT_A, 0.7)}; border-top-color: rgba(255,250,235,0.95);
  font-weight: 700; padding: 7px 22px; border-radius: 16px; letter-spacing: 0.3px;
}}
QPushButton#primary:hover {{ border: 1px solid #fff6e2; }}
QPushButton#primary:disabled {{ background: {_rgba(ACCENT_B, 0.30)}; color: {_rgba(ON_ACCENT, 0.55)}; }}
QPushButton#chrome {{ background: transparent; border: none; padding: 2px 8px; font-size: 11pt; border-radius: 6px; }}
QPushButton#chrome:hover {{ background: rgba(255,255,255,0.12); color: {GOLD}; }}
QPushButton#swatch {{ border-radius: 12px; padding: 0; min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }}
QPushButton#swatch:checked {{ border: 2px solid {GOLD}; }}
QSlider::groove:horizontal {{ height: 3px; background: rgba(255,255,255,0.14); border-radius: 1px; }}
QSlider::sub-page:horizontal {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT_C}, stop:1 {ACCENT_A}); border-radius: 1px;
}}
QSlider::handle:horizontal {{
  background: qradialgradient(cx:0.4, cy:0.35, radius:0.8, stop:0 #ffffff, stop:1 #e9dcc4);
  width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; border: 1px solid {_rgba(ACCENT_C, 0.6)};
}}
QSpinBox, QLineEdit, QComboBox {{
  background: rgba(0,0,0,0.28); border: 1px solid rgba(255,255,255,0.12);
  border-bottom-color: rgba(255,255,255,0.22);
  border-radius: 10px; padding: 4px 8px; selection-background-color: {ACCENT_B}; selection-color: {ON_ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 1px solid {_rgba(GOLD, 0.75)}; }}
QFrame#card {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.10); border-radius: 14px; }}
QLabel#big {{ font-size: 17pt; font-weight: 700; }}
QLabel#good {{ color: {GOLD}; font-weight: 600; }}
QLabel#warn {{ color: #f0b46a; font-weight: 600; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid {_rgba(GOLD, 0.35)};
  selection-background-color: {_rgba(ACCENT_B, 0.28)}; selection-color: {TEXT}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid rgba(255,255,255,0.35); background: rgba(255,255,255,0.06); }}
QCheckBox::indicator:checked {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {ACCENT_A}, stop:1 {ACCENT_C}); border: 1px solid {_rgba(ACCENT_A, 0.7)}; }}
QTableWidget {{ background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; gridline-color: rgba(255,255,255,0.06); }}
QHeaderView {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QHeaderView::section {{ background: rgba(255,255,255,0.06); color: {GOLD}; border: none; padding: 4px; font-weight: 600; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.22); border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: rgba(255,255,255,0.22); border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {_rgba(GOLD, 0.4)}; border-radius: 6px; padding: 4px; }}
QMenu {{ background: {SURFACE}; border: 1px solid {_rgba(GOLD, 0.28)}; border-radius: 10px; padding: 5px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {_rgba(ACCENT_B, 0.22)}; color: #fff6e2; }}
QMenu::item:disabled {{ color: {_rgba(GOLD, 0.75)}; }}
QMenu::separator {{ height: 1px; background: rgba(255,255,255,0.08); margin: 4px 8px; }}
QListWidget {{ background: rgba(0,0,0,0.22); border: 1px solid rgba(255,255,255,0.10); border-radius: 12px;
  padding: 4px; outline: 0; }}
QListWidget::item {{ padding: 7px 8px; border-radius: 8px; }}
QListWidget::item:hover {{ background: rgba(255,255,255,0.05); }}
QListWidget::item:selected {{ background: {_rgba(ACCENT_B, 0.20)}; color: {TEXT}; border: 1px solid {_rgba(GOLD, 0.35)}; }}
"""


QSS = build_qss()


def _light_qss(qss: str) -> str:
    """The light theme's stylesheet: the dark one with its lifts and shades inverted."""
    for a, b in (("rgba(255,255,255,", "\x00INK"), ("rgba(0,0,0,", "rgba(255,255,255,"),
                 ("\x00INK", "rgba(20,18,14,"), ("rgba(247,244,238,", "rgba(31,28,23,")):
        qss = qss.replace(a, b)
    return qss


# ---------------------------------------------------------------- Windows acrylic
class _ACCENT(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _WCAD(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]


def enable_acrylic(hwnd: int, tint_abgr: int = 0x40281E28) -> bool:
    """Real blur-behind for a frameless translucent window (Windows 10/11).
    Returns False elsewhere so callers can fall back to a painted frost."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        accent = _ACCENT(4, 2, tint_abgr, 0)  # 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND
        data = _WCAD(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
        ok = bool(user32.SetWindowCompositionAttribute(ctypes.c_void_p(hwnd), ctypes.byref(data)))
        try:  # rounded corners on Windows 11
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 33,
                                                       ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        return ok
    except Exception:
        return False


def qimage_from_pil(im) -> QImage:
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qi = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888)
    return qi.copy()  # detach from the Python buffer


def pil_from_qimage(qi: QImage):
    from PIL import Image
    qi = qi.convertToFormat(QImage.Format_RGBA8888)
    ptr = qi.constBits()
    return Image.frombuffer("RGBA", (qi.width(), qi.height()), bytes(ptr), "raw", "RGBA",
                            qi.bytesPerLine(), 1).copy()


def rounded_rect_path(r: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    return path


# ---------------------------------------------------------------- live liquid backing
def exclude_from_capture(hwnd: int) -> bool:
    """Hide a window from screen capture (Windows 10 2004+), so we can re-capture what's
    behind it while it's visible. Skipped while recording demos (it would hide us)."""
    import os
    if sys.platform == "darwin":
        from . import platform_mac
        return platform_mac.OK      # macOS: we capture "below our window" instead
    if sys.platform != "win32" or os.environ.get("DROPDIAL_RECORDING"):
        return False
    try:
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), 0x11))
    except Exception:
        return False


from PySide6.QtCore import QObject, QRect, QRunnable, QThreadPool, QTimer, Signal  # noqa: E402


class _LiquidSig(QObject):
    done = Signal(int, QImage, bool)


class _LiquidJob(QRunnable):
    def __init__(self, serial, backdrop, w, h, radius, style):
        super().__init__()
        self.args = (serial, backdrop, w, h, radius, style)
        self.sig = _LiquidSig()

    def run(self):
        serial, backdrop, w, h, radius, style = self.args
        try:
            from . import liquid
            sdf = liquid.sdf_rounded_rect(w, h, 0.5, 0.5, w - 0.5, h - 0.5, radius)
            img, light = liquid.render(backdrop, sdf, style)
            try:
                self.sig.done.emit(serial, qimage_from_pil(img), light)
            except RuntimeError:
                pass  # window closed before the render finished
        except Exception:
            import traceback
            traceback.print_exc()


def grab_screen(x: int, y: int, w: int, h: int, below_window: int = 0):
    """Screen pixels under a rect (logical coords) as a PIL image of size w×h.
    macOS: native capture that leaves out the drag picture (and `below_window` and above)."""
    if sys.platform == "darwin":
        from . import platform_mac
        if platform_mac.OK:
            im = platform_mac.capture(x, y, w, h, below_window)
            if im is not None:
                return im
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication
    scr = QGuiApplication.screenAt(QPoint(x + w // 2, y + h // 2)) or QGuiApplication.primaryScreen()
    g = scr.geometry()
    try:
        shot = scr.grabWindow(0, x - g.x(), y - g.y(), w, h)
    except Exception:
        return None
    if shot.isNull():
        return None
    return pil_from_qimage(shot.toImage().scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))


class LiquidBacking(QObject):
    """Keeps a refracted snapshot of whatever is behind a rounded-rect window."""
    changed = Signal()

    def __init__(self, widget, radius: float, style=None):
        super().__init__(widget)
        from .liquid import GlassStyle
        self.w = widget
        self.radius = radius
        self.style = style or GlassStyle(blur=16, strength=14, bezel=20)
        self.image: QImage | None = None
        self.is_light = False
        self.excluded = False
        self._serial = 0
        self._debounce = QTimer(self, singleShot=True, interval=140, timeout=self.refresh)

    def capture_at(self, rect: QRect):
        """Grab the screen under `rect` (call before the window is shown, or when excluded)."""
        below = 0
        if sys.platform == "darwin" and self.w.isVisible():
            from . import platform_mac
            below = platform_mac.window_number(self.w)
        pil = grab_screen(rect.x(), rect.y(), rect.width(), rect.height(), below)
        if pil is None:
            return
        self._serial += 1
        job = _LiquidJob(self._serial, pil, rect.width(), rect.height(), self.radius, self.style)
        from .util import keep, release
        job.sig.done.connect(lambda *a, j=job: (release(j), self._done(*a)))
        QThreadPool.globalInstance().start(keep(job))

    def _done(self, serial, img, light):
        if serial == self._serial:
            self.image, self.is_light = img, light
            self.changed.emit()

    def moved(self):
        """Window moved/resized: refresh once it settles (only possible when excluded)."""
        if self.excluded:
            self.image = None if self.image is not None and self.image.size() != self.w.size() else self.image
            self._debounce.start()

    def refresh(self):
        if self.excluded and self.w.isVisible():
            self.capture_at(self.w.frameGeometry())


# ---------------------------------------------------------------- drag-image hiding
class hidden_drag_images:
    """While dragging, Windows draws a translucent picture of the file under the cursor.
    Hide it for the instant we capture the screen behind the menu, so it doesn't get frozen
    into the glass, then show it again. We hide every visible top-level window of another
    process that sits under the cursor and is layered + click-through (that is what drag
    images are), plus the known drag-image classes."""

    CLASSES = ("SysDragImage", "DragImageWindow", "DragWindow")
    WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x00080000, 0x00000020

    def __init__(self, point=None):
        self.point = point
        self.hwnds: list[int] = []
        self.info: list[str] = []
        self.rects: list[tuple[int, int, int, int]] = []   # screen px, for inpainting

    def __enter__(self):
        if sys.platform != "win32":
            return self
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetWindowLongW.restype = ctypes.c_long
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            mypid = os.getpid()
            found = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def cb(hwnd, _):
                h = ctypes.c_void_p(hwnd)
                if not user32.IsWindowVisible(h):
                    return True
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                near = r.left - 40 <= pt.x <= r.right + 40 and r.top - 40 <= pt.y <= r.bottom + 40
                if not near or (r.right - r.left) > 900 or (r.bottom - r.top) > 900:
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value == mypid:
                    return True
                buf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(h, buf, 64)
                ex = user32.GetWindowLongW(h, -20)  # GWL_EXSTYLE
                drag_like = (ex & self.WS_EX_LAYERED) and (ex & self.WS_EX_TRANSPARENT)
                if buf.value in self.CLASSES or drag_like:
                    found.append(hwnd)
                    self.rects.append((r.left, r.top, r.right, r.bottom))
                    self.info.append(f"{buf.value} ex=0x{ex & 0xffffffff:08x} {r.right - r.left}x{r.bottom - r.top}")
                return True
            user32.EnumWindows(WNDENUMPROC(cb), 0)
            for h in found:
                user32.ShowWindow(ctypes.c_void_p(h), 0)  # SW_HIDE
            self.hwnds = found
            if found:
                ctypes.windll.gdi32.GdiFlush()
                ctypes.windll.dwmapi.DwmFlush()  # wait for the compositor to drop them
                ctypes.windll.dwmapi.DwmFlush()
        except Exception as e:
            self.info.append(f"error: {e}")
        return self

    def __exit__(self, *exc):
        if self.hwnds:
            try:
                for h in self.hwnds:
                    ctypes.windll.user32.ShowWindow(ctypes.c_void_p(h), 8)  # SW_SHOWNA
            except Exception:
                pass
        return False


def inpaint_rects(im, rects, pad: int = 6):
    """Fill rectangles of a PIL image from their surroundings (normalised convolution):
    a smooth, colour-matched patch — invisible once refracted and blurred by the glass."""
    import numpy as np
    from PIL import Image, ImageFilter
    if not rects:
        return im
    rgb = im.convert("RGB")
    w, h = rgb.size
    mask = Image.new("L", (w, h), 255)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    any_hit = False
    for (x0, y0, x1, y1) in rects:
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
        if x1 > x0 and y1 > y0:
            d.rectangle((x0, y0, x1, y1), fill=0)
            any_hit = True
    if not any_hit:
        return im
    a = np.asarray(rgb, np.float32)
    m = np.asarray(mask, np.float32)[..., None] / 255
    radius = 28
    num = np.asarray(Image.fromarray(np.clip(a * m, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)), np.float32)
    den = np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)), np.float32)[..., None] / 255
    fill = num / np.maximum(den, 1e-3)
    fill = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)
    # feather the seam: the glass bezel magnifies any hard edge into a visible line
    soft = np.asarray(mask.filter(ImageFilter.GaussianBlur(12)), np.float32)[..., None] / 255
    soft = np.minimum(soft, m)  # never let the drag picture bleed back in
    out = a * soft + fill * (1 - soft)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- no-compositor mode (XFCE etc.)
_NO_COMP = None


def no_compositor() -> bool:
    """Linux/X11 without a compositing manager: translucency would render black, so glass
    surfaces are cut to their exact shape with a window mask instead (XShape)."""
    global _NO_COMP
    if _NO_COMP is None:
        _NO_COMP = False
        if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM", "").startswith("offscreen"):
            try:
                from . import platform_linux
                _NO_COMP = not platform_linux.composited()
            except Exception:
                _NO_COMP = False
    return _NO_COMP


def apply_shape(widget, path: QPainterPath):
    """Clip a top-level window to `path` when there's no compositor (no-op otherwise)."""
    if not no_compositor():
        return
    from PySide6.QtGui import QRegion
    region = QRegion()
    for poly in path.simplified().toFillPolygons():   # one polygon per separate piece
        region = region.united(QRegion(poly.toPolygon()))
    widget.setMask(region)
