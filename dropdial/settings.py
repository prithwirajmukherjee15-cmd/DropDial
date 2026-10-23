"""Persistent settings + the Settings and Welcome windows."""
from __future__ import annotations

import sys

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout)

from . import CREDIT, __version__, glass
from .util import CONFIG
from .window import GlassWindow

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
APP = "DropDial"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULTS = {
    "output": "next",
    "jpg_quality": 90,
    "pdf_dpi": 200,
    "trigger": "shift",
    "welcomed": False,
    "watch_toasts": True,
    "check_updates": True,
    "accent": "champagne",
    "theme": "dark",            # dark | light | system
    "dial_opacity": 100,        # % of the dial's glass (labels stay solid)
    "hotkey": True,             # Ctrl+Alt+D opens Home
    "update_seen": "",
}


class Settings:
    def __init__(self):
        self.q = QSettings(APP, APP)

    def get(self, key):
        v = self.q.value(key, DEFAULTS[key])
        d = DEFAULTS[key]
        if isinstance(d, bool):
            return v in (True, "true", "1", 1)
        if isinstance(d, int):
            try:
                return int(v)
            except (TypeError, ValueError):
                return d
        return v

    def set(self, key, value):
        self.q.setValue(key, value)
        self.apply()

    def apply(self):
        for k in ("output", "jpg_quality", "pdf_dpi"):
            CONFIG[k] = self.get(k)

    def apply_look(self):
        """Theme, accent and dial opacity (needs a QApplication for 'system')."""
        from . import glass
        theme = self.get("theme")
        glass.set_theme(glass.system_theme() if theme == "system" else theme)
        glass.set_accent(self.get("accent"))
        glass.DIAL_OPACITY = max(0.4, min(1.0, self.get("dial_opacity") / 100))


# ---------------------------------------------------------------- autostart (Windows)
def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --quiet'
    return f'"{sys.executable}" -m dropdial --quiet'


def autostart_enabled() -> bool:
    if IS_LINUX:
        from . import platform_linux
        return platform_linux.autostart_enabled()
    if IS_MAC:
        from . import platform_mac
        return platform_mac.autostart_enabled()
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def set_autostart(on: bool):
    if IS_LINUX:
        from . import platform_linux
        platform_linux.set_autostart(on)
        return
    if IS_MAC:
        from . import platform_mac
        platform_mac.set_autostart(on)
        return
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


TRIGGERS = ([("shift", "Shift ⇧"), ("ctrl", "Control ⌃"), ("alt", "Option ⌥")] if IS_MAC
            else [("shift", "Shift"), ("ctrl", "Ctrl"), ("alt", "Alt")])
OUTPUTS = [("next", "Next to the original"), ("folder", "In a “DropDial” subfolder")]
THEMES = [("dark", "Dark glass"), ("light", "Light glass"), ("system", "Match my system")]
DPIS = [(150, "150 dpi · small"), (200, "200 dpi · balanced"), (300, "300 dpi · print")]


class SettingsWindow(GlassWindow):
    changed = Signal()

    def __init__(self, settings: Settings):
        super().__init__("Settings", size=(560, 640))
        self.s = settings
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        r = 0

        def combo(options, current):
            c = QComboBox()
            for v, label in options:
                c.addItem(label, v)
            idx = max(0, [v for v, _ in options].index(current) if current in [v for v, _ in options] else 0)
            c.setCurrentIndex(idx)
            return c

        grid.addWidget(QLabel("Open the menu with"), r, 0)
        self.trigger = combo(TRIGGERS, self.s.get("trigger"))
        self.trigger.currentIndexChanged.connect(lambda _: self._save("trigger", self.trigger.currentData()))
        grid.addWidget(self.trigger, r, 1)
        r += 1
        hint = QLabel("…pressed while you’re dragging a file")
        hint.setObjectName("dim")
        grid.addWidget(hint, r, 1)
        r += 1

        grid.addWidget(QLabel("Save results"), r, 0)
        self.output = combo(OUTPUTS, self.s.get("output"))
        self.output.currentIndexChanged.connect(lambda _: self._save("output", self.output.currentData()))
        grid.addWidget(self.output, r, 1)
        r += 1

        grid.addWidget(QLabel("JPG / WebP quality"), r, 0)
        row = QHBoxLayout()
        self.q = QSlider(Qt.Horizontal)
        self.q.setRange(60, 100)
        self.q.setValue(self.s.get("jpg_quality"))
        self.qv = QLabel(str(self.q.value()))
        self.qv.setObjectName("dim")
        self.qv.setFixedWidth(30)
        self.q.valueChanged.connect(lambda v: (self.qv.setText(str(v)), self._save("jpg_quality", v)))
        row.addWidget(self.q)
        row.addWidget(self.qv)
        grid.addLayout(row, r, 1)
        r += 1

        grid.addWidget(QLabel("PDF → image resolution"), r, 0)
        self.dpi = combo(DPIS, self.s.get("pdf_dpi"))
        self.dpi.currentIndexChanged.connect(lambda _: self._save("pdf_dpi", self.dpi.currentData()))
        grid.addWidget(self.dpi, r, 1)
        r += 1

        grid.addWidget(QLabel("Appearance"), r, 0)
        self.theme = combo(THEMES, self.s.get("theme"))
        self.theme.currentIndexChanged.connect(lambda _: self._look("theme", self.theme.currentData()))
        grid.addWidget(self.theme, r, 1)
        r += 1

        grid.addWidget(QLabel("Dial glass"), r, 0)
        orow = QHBoxLayout()
        self.op = QSlider(Qt.Horizontal)
        self.op.setRange(40, 100)
        self.op.setValue(self.s.get("dial_opacity"))
        self.op.setToolTip("How solid the dial's glass looks. The labels always stay readable.")
        self.opv = QLabel(f"{self.op.value()}%")
        self.opv.setObjectName("dim")
        self.opv.setFixedWidth(38)
        self.op.valueChanged.connect(lambda v: (self.opv.setText(f"{v}%"), self._look("dial_opacity", v)))
        orow.addWidget(self.op)
        orow.addWidget(self.opv)
        grid.addLayout(orow, r, 1)
        r += 1

        grid.addWidget(QLabel("Accent colour"), r, 0)
        sw_row = QHBoxLayout()
        sw_row.setSpacing(8)
        self.swatches = []
        for key, (hi, mid, deep, _gold, _on) in glass.ACCENTS.items():
            b = QPushButton()
            b.setObjectName("swatch")
            b.setCheckable(True)
            b.setChecked(key == self.s.get("accent"))
            b.setToolTip(glass.ACCENT_NAMES[key])
            b.setStyleSheet(f"QPushButton#swatch {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                            f" stop:0 {hi}, stop:0.5 {mid}, stop:1 {deep}); }}")
            b.clicked.connect(lambda _=False, k=key: self._accent(k))
            sw_row.addWidget(b)
            self.swatches.append((key, b))
        sw_row.addStretch(1)
        grid.addLayout(sw_row, r, 1)
        r += 1

        if IS_WIN or IS_MAC or IS_LINUX:
            self.auto = QCheckBox("Start DropDial with Windows" if IS_WIN else "Open DropDial at login")
            self.auto.setChecked(autostart_enabled())
            self.auto.toggled.connect(set_autostart)
            grid.addWidget(self.auto, r, 1)
            r += 1
        keys = "⌃⌥D" if IS_MAC else "Ctrl+Alt+D"
        self.hot = QCheckBox(f"{keys} opens Home from anywhere")
        self.hot.setChecked(self.s.get("hotkey"))
        self.hot.toggled.connect(lambda on: self._save("hotkey", on))
        grid.addWidget(self.hot, r, 1)
        r += 1
        self.upd = QCheckBox("Check for updates automatically")
        self.upd.setToolTip("Asks GitHub once every few hours whether a newer DropDial exists. "
                            "Nothing about you or your files is sent.")
        self.upd.setChecked(self.s.get("check_updates"))
        self.upd.toggled.connect(lambda on: self._save("check_updates", on))
        grid.addWidget(self.upd, r, 1)
        r += 1
        if IS_MAC:
            from . import platform_mac
            if not platform_mac.has_screen_recording():
                glass_btn = QPushButton("Enable full liquid glass…")
                glass_btn.setToolTip("Lets the glass refract the windows behind it (Screen Recording permission)")
                glass_btn.clicked.connect(platform_mac.request_screen_recording)
                grid.addWidget(glass_btn, r, 1)
                r += 1
        self.body.addLayout(grid)
        self.body.addStretch(1)
        about = QLabel(f"DropDial {__version__}  ·  {CREDIT}")
        about.setObjectName("credit")
        foot = QHBoxLayout()
        foot.addWidget(about)
        foot.addStretch(1)
        done = QPushButton("Done")
        done.setObjectName("primary")
        done.clicked.connect(self.close)
        foot.addWidget(done)
        self.body.addLayout(foot)

    def _save(self, key, value):
        self.s.set(key, value)
        self.changed.emit()

    def _look(self, key, value):
        self.s.q.setValue(key, value)
        self.s.apply_look()
        self.setStyleSheet(glass.QSS)       # this window updates at once; others as they open
        self.update()
        self.changed.emit()

    def _accent(self, key: str):
        for k, b in self.swatches:
            b.setChecked(k == key)
        glass.set_accent(key)
        self.setStyleSheet(glass.QSS)       # this window updates at once; others as they open
        self._save("accent", key)


class WelcomeWindow(GlassWindow):
    def __init__(self, settings: Settings, trigger_label: str = "Shift"):
        super().__init__("Welcome to DropDial", size=(560, 430))
        self.s = settings
        steps = [
            ("1", "Start dragging any file", "in Finder or on the desktop" if IS_MAC else
             "in your file manager (Thunar, Nautilus…)" if IS_LINUX else "in File Explorer or on the desktop"),
            ("2", f"Press {trigger_label}", "the glass menu opens right under your cursor"),
            ("3", "Drop it on a slice", "the result is saved next to the original"),
            ("⇄", f"Tap {trigger_label} again", "or turn the mouse wheel, to flip to More formats, Tools, Recipes"),
        ]
        for n, head, sub in steps:
            row = QHBoxLayout()
            badge = QLabel(n)
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(34, 34)
            badge.setStyleSheet(f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {glass.ACCENT_A},"
                                f" stop:0.5 {glass.ACCENT_B}, stop:1 {glass.ACCENT_C}); color: {glass.ON_ACCENT};"
                                " border: 1px solid rgba(255,255,255,0.6);"
                                "border-radius: 17px; font-weight: 700; font-size: 12pt;")
            row.addWidget(badge)
            col = QVBoxLayout()
            col.setSpacing(0)
            h = QLabel(head)
            h.setStyleSheet("font-size: 12pt; font-weight: 600;")
            d = QLabel(sub)
            d.setObjectName("dim")
            col.addWidget(h)
            col.addWidget(d)
            row.addSpacing(8)
            row.addLayout(col, 1)
            self.body.addLayout(row)
        self.body.addStretch(1)
        if IS_MAC:
            from . import platform_mac
            if not platform_mac.has_screen_recording():
                note = QLabel("Optional: allow Screen Recording so the glass can refract the windows "
                              "behind it (otherwise it shows your wallpaper). DropDial never saves or sends it.")
                note.setObjectName("dim")
                note.setWordWrap(True)
                self.body.addWidget(note)
                b = QPushButton("Allow Screen Recording…")
                b.clicked.connect(platform_mac.request_screen_recording)
                self.body.addWidget(b, 0, Qt.AlignLeft)
        if IS_LINUX:
            from . import platform_linux
            if platform_linux.is_wayland():
                note = QLabel("You're on a Wayland session: the Shift-while-dragging trigger needs X11 (e.g. XFCE). "
                              "Right-click a file → Open With → DropDial still works.")
                note.setObjectName("warn")
                note.setWordWrap(True)
                self.body.addWidget(note)
        sig = QLabel(CREDIT)
        sig.setObjectName("credit")
        sig.setAlignment(Qt.AlignRight)
        self.body.addWidget(sig)
        foot = QHBoxLayout()
        if IS_WIN or IS_MAC or IS_LINUX:
            self.auto = QCheckBox("Start with Windows" if IS_WIN else "Open at login")
            self.auto.setChecked(True)
            foot.addWidget(self.auto)
        foot.addStretch(1)
        ok = QPushButton("Got it")
        ok.setObjectName("primary")
        ok.clicked.connect(self._done)
        foot.addWidget(ok)
        self.body.addLayout(foot)

    def _done(self):
        self.s.set("welcomed", True)
        if IS_WIN or IS_MAC or IS_LINUX:
            set_autostart(self.auto.isChecked())
        self.close()
