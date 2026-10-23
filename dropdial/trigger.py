"""Watches for "left button held + mouse moved + Shift pressed" anywhere on screen, which
is what a Shift+drag of a file looks like. Polling global input state is simple, needs no
admin rights and can't stall the system the way a broken hook can.
Windows: GetAsyncKeyState. macOS: NSEvent.pressedMouseButtons / modifierFlags (no
Accessibility or Input Monitoring permission required)."""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor

VK_LBUTTON, VK_SHIFT, VK_ESCAPE = 0x01, 0x10, 0x1B
DRAG_THRESHOLD = 10   # px the mouse must travel with the button held
NO_DRAG_TIMEOUT = 50  # ticks (≈ 0.75 s) to wait for a file drag to enter before hiding


class DropDialWatcher(QObject):
    show_menu = Signal(QPoint, list)   # cursor, files being dragged (if the OS can tell us)
    toggle_ring = Signal()
    hide_menu = Signal()
    open_home = Signal()                 # Ctrl+Alt+D (⌃⌥D on a Mac), anywhere

    def __init__(self, menu_visible, menu_got_drag, parent=None):
        super().__init__(parent)
        self.menu_visible = menu_visible
        self.menu_got_drag = menu_got_drag
        self.enabled = True
        self.vk = VK_SHIFT
        self.key_name = "shift"
        self._down_at: QPoint | None = None
        self._shift_was = False
        self._fired = False
        self._idle_ticks = 0
        self._shown_at = QPoint()
        self._drag_cc = -1
        self.hotkey = True
        self._hot_was = False
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None
        self._mac = None
        if sys.platform == "darwin":
            from . import platform_mac
            self._mac = platform_mac if platform_mac.OK else None
        elif sys.platform.startswith("linux"):
            from . import platform_linux
            # same interface as platform_mac: left_button_down / key_down / escape_down
            self._mac = platform_linux if platform_linux.available() else None
        self.timer = QTimer(self, interval=15, timeout=self._tick)

    def set_key(self, name: str):
        self.key_name = name
        self.vk = {"shift": VK_SHIFT, "ctrl": 0x11, "alt": 0x12}.get(name, VK_SHIFT)

    def start(self):
        if self._user32 is not None or self._mac is not None:
            self.timer.start()

    def _down(self, vk: int) -> bool:
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def _state(self) -> tuple[bool, bool, bool]:
        """(left button, trigger key, escape)"""
        if self._mac is not None:
            m = self._mac
            return m.left_button_down(), m.key_down(self.key_name), m.escape_down()
        return self._down(VK_LBUTTON), self._down(self.vk), self._down(VK_ESCAPE)

    def _drag_count(self) -> int:
        f = getattr(self._mac, "drag_change_count", None)
        return f() if f else -1

    def _dragged_files(self) -> list[str]:
        """Files of the drag that started after this mouse press (macOS), else []."""
        f = getattr(self._mac, "drag_files", None)
        if f is None or self._drag_cc < 0 or self._drag_count() == self._drag_cc:
            return []   # no new drag since the button went down: an old pasteboard, not this drag
        try:
            return [p for p in f() if p]
        except Exception:
            return []

    def _hotkey(self) -> bool:
        if self._mac is not None:
            f = getattr(self._mac, "hotkey_down", None)
            return bool(f and f())
        if self._user32 is not None:
            return self._down(0x11) and self._down(0x12) and self._down(0x44)   # Ctrl, Alt, D
        return False

    def _tick(self):
        if self.hotkey and self.enabled:
            hot = self._hotkey()
            if hot and not self._hot_was:
                self.open_home.emit()
            self._hot_was = hot
        lbtn, shift, esc = self._state()
        pos = QCursor.pos()

        if self.menu_visible():
            if not lbtn or esc:
                # drop happened (or was cancelled) – give the drop event a moment to land
                QTimer.singleShot(120, self.hide_menu.emit)
            elif shift and not self._shift_was and self.menu_got_drag():
                self.toggle_ring.emit()       # tap Shift again to flip Convert ⇄ Tools
            elif not self.menu_got_drag() and (pos - self._shown_at).manhattanLength() > 6:
                # the cursor is moving over us but no file drag arrived: it's a window
                # move or text selection, so get out of the way
                self._idle_ticks += 1
                if self._idle_ticks > NO_DRAG_TIMEOUT:
                    self.hide_menu.emit()
        else:
            if lbtn:
                if self._down_at is None:
                    self._down_at = pos
                    self._fired = False
                    self._drag_cc = self._drag_count()
                moved = (pos - self._down_at).manhattanLength() >= DRAG_THRESHOLD
                if self.enabled and moved and shift and not self._fired:
                    self._fired = True
                    self._idle_ticks = 0
                    self._shown_at = pos
                    self.show_menu.emit(pos, self._dragged_files())
            else:
                self._down_at = None
                self._fired = False
        self._shift_was = shift
