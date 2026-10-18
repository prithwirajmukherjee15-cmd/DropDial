"""DropDial: Shift+drag any file to convert or edit it from a radial liquid-glass menu."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QDir, QObject, QPointF, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QColor, QCursor, QDesktopServices, QGuiApplication, QIcon, QPainter,
                           QPixmap)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon, QWidget

from . import CREDIT, __version__, convert, glass, history, imaging, media, panels, recipes, report, tools, watch
from .radial import Item, RadialMenu
from .settings import Settings, SettingsWindow, WelcomeWindow, TRIGGERS
from .toasts import ToastStack
from .trigger import DropDialWatcher
from .util import (UserError, category, current_progress, file_size, human_size, keep, progress_hook,
                   release)

APP_NAME = "DropDial"
PROJECT_URL = "https://github.com/prithwirajmukherjee15-cmd/dragshift"
VERSION = __version__
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
from .handoff import ipc_name
IPC_NAME = ipc_name()

GLYPHS = {"Compress": "⇲", "Metadata": "ⓘ", "Redact": "▮", "Crop": "⌗", "Edit": "☼",
          "Annotate": "✎", "Add BG": "▣", "Resize": "⤢", "Split": "✂", "Rotate": "⟳",
          "Merge": "⧉", "Protect": "⚿", "Extract": "⧈", "Watermark": "©", "Numbers": "#",
          "Unlock": "⚷", "Audio": "♪", "Mute": "∅", "Frame": "▭", "Normalize": "≋",
          "Trim silence": "⇥"}

HINTS = {
    "Compress": "Shrink file size", "Metadata": "View · remove GPS", "Redact": "Hide private info",
    "Crop": "Trim to a ratio", "Edit": "Light · colour · rotate", "Annotate": "Arrows · text · steps",
    "Add BG": "Gradient backdrop", "Resize": "Change dimensions", "Split": "One PDF per page",
    "Rotate": "Turn pages 90°", "Merge": "Join into one PDF", "Protect": "Add a password",
    "Extract": "Save embedded images", "Watermark": "Stamp your name", "Numbers": "Number the pages",
    "Unlock": "Remove the password", "Audio": "Save the sound as MP3", "Mute": "Remove the sound",
    "Frame": "Save a still image", "Normalize": "Even out loudness", "Trim silence": "Cut quiet ends",
}
VIDEO_HINTS = {"Compress": "Smaller MP4 · ≤1080p", "Rotate": "Turn 90° clockwise"}
AUDIO_HINTS = {"Compress": "96 kbps MP3"}
FORMAT_HINTS = {"JPG": "Small, universal", "PNG": "Lossless · transparency", "WEBP": "Smallest for web",
                "HEIC": "iPhone format", "TIFF": "Print · archival", "AVIF": "Next-gen, tiny",
                "BMP": "Uncompressed", "PDF": "Document", "ICO": "Windows icon", "GIF": "Legacy web",
                "DOCX": "Editable Word", "TXT": "Plain text", "MP4": "Plays everywhere",
                "WEBM": "Small web video", "MOV": "Apple · editing", "MP3": "Universal audio",
                "M4A": "Apple audio", "WAV": "Uncompressed", "FLAC": "Lossless audio", "OGG": "Open format"}
CAT_FORMAT_HINTS = {("video", "GIF"): "Animated · first 30 s", ("video", "MP3"): "Just the sound",
                    ("vector", "PNG"): "Crisp 2048 px", ("vector", "PDF"): "Stays vector",
                    ("ebook", "PDF"): "Readable anywhere"}
RECIPE_HINTS = {"Web-ready": "WebP · no metadata", "Email size": "Fits in an email",
                "Private": "Strip GPS · camera", "Social": "4:5 gradient post", "Scan → PDF": "Pages → one PDF",
                "Confidential": "Stamp every page", "Share video": "720p MP4", "Podcast": "MP3 · −16 LUFS"}

IMAGE_TOOLS = ["Compress", "Resize", "Crop", "Edit", "Annotate", "Redact", "Add BG", "Watermark", "Metadata"]
PDF_TOOLS = ["Compress", "Split", "Rotate", "Numbers", "Watermark", "Protect", "Extract", "Metadata"]


# ---------------------------------------------------------------- background jobs
class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(float)


class Job(QRunnable):
    def __init__(self, action: str, srcs: list, fn, extra: str = ""):
        super().__init__()
        self.action, self.srcs, self.fn, self.extra = action, srcs, fn, extra
        self.sig = _Sig()
        self._last = -1.0

    def _progress(self, f: float):
        if f - self._last >= 0.01 or f >= 1.0:   # don't flood the UI thread
            self._last = f
            try:
                self.sig.progress.emit(f)
            except RuntimeError:
                pass

    def run(self):
        try:
            with progress_hook(self._progress):
                outs = self.fn() or []
            self.sig.done.emit(report.summarize(self.action, self.srcs, outs, self.extra))
        except UserError as e:
            self.sig.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sig.failed.emit(friendly_error(e))


def friendly_error(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    low = msg.lower()
    if isinstance(e, PermissionError) or "permission denied" in low:
        return "No permission to write next to this file. Try a folder you own, or set Settings → Save results → subfolder."
    if "cannot identify image" in low:
        return "This file doesn't look like an image DropDial can read."
    if isinstance(e, FileNotFoundError):
        return "The file was moved or deleted."
    return msg


# ---------------------------------------------------------------- icon
def make_tray_icon() -> QIcon:
    """macOS menu bar wants a monochrome 'template' image; Windows gets the colour icon."""
    if not IS_MAC:
        return make_icon()
    pm = QPixmap(44, 44)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtGui import QPen
    p.setPen(QPen(QColor(0, 0, 0), 4.5))
    p.drawEllipse(QPointF(22, 22), 14, 14)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0))
    p.drawEllipse(QPointF(22, 22), 5, 5)
    for a in range(0, 360, 45):  # petal gaps
        import math
        x, y = 22 + 14 * math.cos(math.radians(a + 22.5)), 22 + 14 * math.sin(math.radians(a + 22.5))
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.drawEllipse(QPointF(x, y), 2.2, 2.2)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.end()
    pm.setDevicePixelRatio(2.0)
    icon = QIcon(pm)
    icon.setIsMask(True)
    return icon


def make_icon() -> QIcon:
    ico = Path(__file__).with_name("assets") / "dropdial.ico"
    if ico.exists():
        return QIcon(str(ico))
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(glass.iridescent_pen(QPointF(32, 32), 7, 255))
    p.drawEllipse(QPointF(32, 32), 24, 24)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- the app
class DropDialApp(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.settings = Settings()
        self.settings.apply()
        self.pool = QThreadPool.globalInstance()
        self.windows: list[QWidget] = []
        self.toasts = ToastStack()
        self.menu = RadialMenu(self.build_rings, self.describe)
        self.menu.activated.connect(self.run_item)

        # the watcher only manages menus it opened (drag mode); click-mode menus (tray, right-click,
        # Send To) must not be closed just because no mouse button is held
        self.watcher = DropDialWatcher(lambda: self.menu.isVisible() and not self.menu.click_mode,
                                        lambda: self.menu.got_drag, self)
        self.watcher.set_key(self.settings.get("trigger"))
        self.watcher.show_menu.connect(lambda pos: self.menu.popup(pos))
        self.watcher.toggle_ring.connect(self.menu.next_ring)
        self.watcher.hide_menu.connect(self.menu.close_menu)
        self.watcher.start()

        # files handed over by "Send to", the right-click menu, or a second launch
        self._pending: list[str] = []
        self._pending_timer = QTimer(self, singleShot=True, interval=280, timeout=self._flush_pending)
        self.server = QLocalServer(self)
        QLocalServer.removeServer(IPC_NAME)
        self.server.listen(IPC_NAME)
        self.server.newConnection.connect(self._ipc)

        self.tray = QSystemTrayIcon(make_tray_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} — press {self.trigger_label()} while dragging a file")
        m = QMenu()
        m.setStyleSheet(glass.QSS)
        credit = m.addAction(f"{APP_NAME} {VERSION}  ·  {CREDIT}")
        credit.setEnabled(False)          # a signature line, styled gold by the stylesheet
        m.addSeparator()
        self.act_enabled = QAction("Enabled", m, checkable=True, checked=True)
        self.act_enabled.toggled.connect(lambda on: setattr(self.watcher, "enabled", on))
        m.addAction(self.act_enabled)
        m.addAction("Open a file…", self.open_dialog)
        m.addAction("History…", self.open_history)
        m.addSeparator()
        m.addAction("Recipes…", self.open_recipes)
        self.act_watch = m.addAction("Watch folders…", self.open_watch)
        m.addAction("Settings…", self.open_settings)
        m.addSeparator()
        m.addAction("How to use", self.show_welcome)
        m.addAction(f"About {APP_NAME}…", lambda: QDesktopServices.openUrl(QUrl(PROJECT_URL)))
        m.addSeparator()
        m.addAction(f"Quit {APP_NAME}", self.qapp.quit)
        self.tray_menu = m
        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._tray_click)
        self.tray.show()

        # watch folders: poll every 2 s (see watch.py for why polling)
        self.scanners: list[watch.FolderScanner] = []
        self.watch_timer = QTimer(self, interval=2000, timeout=self._watch_tick)
        self.reload_watch()

    def trigger_label(self) -> str:
        return dict(TRIGGERS).get(self.settings.get("trigger"), "Shift")

    # ------------------------------------------------------------ IPC
    def _ipc(self):
        sock = self.server.nextPendingConnection()
        if sock is None:
            return
        buf = bytearray()
        done = {"v": False}

        def consume():
            if done["v"]:
                return
            try:
                buf.extend(bytes(sock.readAll()))
            except RuntimeError:
                pass
            try:
                data = json.loads(buf.decode("utf-8"))
            except Exception:
                return  # incomplete: wait for more
            done["v"] = True
            files = [f for f in data.get("files", []) if os.path.exists(f)]
            print(f"IPC: {len(files)} file(s) handed over", flush=True)
            if files:
                self.queue_files(files)
            elif data.get("show"):
                self.toasts.info("DropDial is already running",
                                 f"Drag any file and press {self.trigger_label()}. It lives in the tray.")
            sock.disconnectFromServer()
            sock.deleteLater()

        # Windows pipes: the sender may already be gone, so read on every signal + a fallback timer
        sock.readyRead.connect(consume)
        sock.disconnected.connect(consume)
        for ms in (0, 50, 200, 600):
            QTimer.singleShot(ms, consume)

    def queue_files(self, files: list[str]):
        """Explorer's right-click menu launches once per file: gather them, then show one menu."""
        for f in files:
            if f not in self._pending:
                self._pending.append(f)
        self._pending_timer.start()

    def _flush_pending(self):
        files, self._pending = self._pending, []
        if files:
            self.show_click_menu(files)

    # ------------------------------------------------------------ menu contents
    def describe(self, paths: list[str]) -> str:
        if len(paths) > 1:
            return f"{len(paths)} files"
        return human_size(file_size(paths[0]))

    def build_rings(self, paths: list[str]) -> dict[str, list[Item]]:
        # NB: also called unbound (self=None) by the e2e scripts, so it must not touch `self`
        cat = category(paths[0])
        if cat is None:
            return {"Unsupported": []}
        ext = Path(paths[0]).suffix
        same = [p for p in paths if category(p) == cat]
        if cat == "pdf" and imaging.pdf_is_locked(paths[0]):
            return {"Tools": [Item("Unlock", GLYPHS["Unlock"], key="tool:Unlock", hint=HINTS["Unlock"])]}
        convert_items = []
        for t in convert.targets_for(cat, ext):
            hint = CAT_FORMAT_HINTS.get((cat, t)) or FORMAT_HINTS.get(t, "")
            if cat == "image" and t == "PDF" and len(same) > 1:
                hint = f"{len(same)} images → 1 PDF"
            convert_items.append(Item(t, key=f"convert:{t}", hint=hint))
        rings: dict[str, list[Item]] = {"Convert": convert_items}

        def tools(names, hints=None):
            hints = hints or {}
            return [Item(n, GLYPHS[n], key=f"tool:{n}", hint=hints.get(n) or HINTS[n]) for n in names]

        if cat == "image":
            rings["Tools"] = tools(IMAGE_TOOLS)
        elif cat == "pdf":
            rings["Tools"] = tools(PDF_TOOLS[:3] + (["Merge"] if len(same) > 1 else []) + PDF_TOOLS[3:])
        elif cat == "video":
            rings["Tools"] = tools(media.VIDEO_TOOLS, VIDEO_HINTS)
        elif cat == "audio":
            rings["Tools"] = tools(media.AUDIO_TOOLS, AUDIO_HINTS)
        try:
            menu_recipes = recipes.menu_recipes(cat)
        except Exception:  # a broken recipes.json must never break the menu
            traceback.print_exc()
            menu_recipes = []
        if menu_recipes:
            rings["Recipes"] = [Item(r.name, r.glyph, key=f"recipe:{r.name}",
                                     hint=RECIPE_HINTS.get(r.name) if r.builtin else
                                     f"{len(r.flow(cat)[0])} steps")
                                for r in menu_recipes]
        return rings

    # ------------------------------------------------------------ actions
    def run_item(self, item: Item, paths: list[str]):
        cat = category(paths[0])
        kind, name = item.key.split(":", 1)
        if kind == "recipe":
            self.run_recipe(name, paths)
            return
        paths = [p for p in paths if category(p) == cat]
        if cat == "pdf" and name == "Unlock":
            self.open_window(tools.UnlockWindow(paths[0], self.notify))
            return
        if cat in ("video", "audio") and kind == "tool":
            self.run_media_tool(cat, name, paths)
            return
        if kind == "convert":
            if cat == "image" and name == "PDF" and len(paths) > 1:
                self.submit(f"convert:{name}", paths, lambda: convert.images_to_single_pdf(paths),
                            f"Combining {len(paths)} images…")
            else:
                verb = f"Converting to {name}…"
                self.submit(f"convert:{name}", paths,
                            lambda: [o for p in paths for o in convert.convert(p, cat, name)], verb)
            return
        if cat == "pdf":
            if name == "Merge":
                self.submit("tool:Merge", paths, lambda: [imaging.merge_pdfs(paths)], "Merging…")
            elif name == "Metadata":
                self.open_window(tools.MetadataWindow(paths[0], self.notify, is_pdf=True))
            elif name == "Protect":
                self.open_window(tools.ProtectWindow(paths[0], self.notify))
            elif name == "Watermark":
                self.open_window(tools.WatermarkWindow(paths, self.notify, is_pdf=True))
            else:
                fns = {"Compress": lambda p: [imaging.compress_pdf(p)], "Split": imaging.split_pdf,
                       "Rotate": lambda p: [imaging.rotate_pdf(p)], "Extract": imaging.extract_pdf_images,
                       "Numbers": lambda p: [imaging.pdf_page_numbers(p)]}
                f = fns[name]
                self.submit(f"tool:{name}", paths, lambda: [o for p in paths for o in f(p)],
                            {"Compress": "Compressing…", "Split": "Splitting…", "Rotate": "Rotating…",
                             "Extract": "Extracting images…", "Numbers": "Numbering pages…"}[name])
            return
        if cat != "image":
            return
        windows = {"Crop": tools.CropWindow, "Add BG": tools.AddBgWindow, "Annotate": tools.AnnotateWindow,
                   "Redact": tools.RedactWindow, "Edit": tools.EditWindow, "Metadata": tools.MetadataWindow}
        try:
            if name == "Compress":
                self.open_window(tools.CompressWindow(paths, self.notify))
            elif name == "Resize":
                self.open_window(tools.ResizeWindow(paths, self.notify))
            elif name == "Watermark":
                self.open_window(tools.WatermarkWindow(paths, self.notify))
            else:
                self.open_window(windows[name](paths[0], self.notify))
        except UserError as e:
            self.toasts.error(f"Couldn't open {name}", str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.toasts.error(f"Couldn't open {name}", friendly_error(e))

    def open_window(self, w: QWidget):
        if hasattr(w, "submit"):
            w.submit = self.submit
        self.windows.append(w)
        w.destroyed.connect(lambda *_: self.windows.remove(w) if w in self.windows else None)
        if hasattr(w, "present"):
            w.present()
        else:
            w.show()

    def submit(self, action: str, srcs: list, fn, working: str = "Working…", extra: str = "",
               source: str = "menu", on_done=None, toast: bool = True):
        """Run in the background. A spinner card appears only if it takes > 150 ms."""
        state = {"card": None, "finished": False, "pct": None}
        names = Path(srcs[0]).name if len(srcs) == 1 else f"{len(srcs)} files"

        def show_spinner():
            if not state["finished"] and toast:
                state["card"] = self.toasts.new()
                pct = state["pct"]
                state["card"].working(working, names if pct is None else f"{pct}% · {names}")

        QTimer.singleShot(150, show_spinner)
        job = Job(action, srcs, fn, extra)

        def progress(f):
            state["pct"] = int(f * 100)
            if state["card"] is not None and not state["finished"]:
                state["card"].working(working, f"{state['pct']}% · {names}")

        def done(r):
            release(job)
            state["finished"] = True
            try:
                history.add(r, action, source)
            except OSError:
                traceback.print_exc()
            if on_done:
                on_done(r)
            if toast or state["card"]:
                card = state["card"] or self.toasts.new()
                card.done(r)
            self.history_changed()

        def failed(msg):
            release(job)
            state["finished"] = True
            card = state["card"] or self.toasts.new()
            card.error("Couldn't finish", msg)

        job.sig.done.connect(done)
        job.sig.failed.connect(failed)
        job.sig.progress.connect(progress)
        self.pool.start(keep(job))

    def notify(self, action: str, srcs: list, outs: list, extra: str = ""):
        """Called by tool windows after they save."""
        r = report.summarize(action, srcs, outs, extra)
        try:
            history.add(r, action)
        except OSError:
            traceback.print_exc()
        self.toasts.new().done(r)
        self.history_changed()

    def history_changed(self):
        for w in self.windows:
            if isinstance(w, panels.HistoryWindow):
                w.reload()

    # ------------------------------------------------------------ recipes & media
    def run_recipe(self, name: str, paths: list[str]):
        try:
            r = recipes.find(name)
        except UserError as e:
            self.toasts.error("Recipe not found", str(e))
            return
        todo = [p for p in paths if r.applies_to(category(p))]
        if not todo:
            self.toasts.error(f"“{r.name}” doesn't fit", "None of these files work with this recipe.")
            return
        cat = category(todo[0])
        combine = any(s.get("step") == "combine" for s in r.steps)

        def work():
            if combine:
                return recipes.run(r, todo).outputs
            outs, errors = [], []
            for i, p in enumerate(todo):
                outer = current_progress()
                # each file is a slice of the overall bar
                with progress_hook(lambda f, i=i: outer and outer((i + f) / len(todo))):
                    try:
                        outs += recipes.run(r, [p]).outputs
                    except UserError as e:
                        errors.append(f"{Path(p).name}: {e}")
            if not outs and errors:
                raise UserError(errors[0])
            return outs
        self.submit(f"recipe:{r.name}", todo, work, f"{r.glyph} {r.name}…", r.summary(cat))

    def run_media_tool(self, cat: str, name: str, paths: list[str]):
        if not media.available():
            self.toasts.error("ffmpeg is missing", "Video and audio need ffmpeg. Install it, or "
                              "`pip install imageio-ffmpeg`, then try again.")
            return
        fns = {
            ("video", "Compress"): (media.compress_video, "Compressing video…"),
            ("video", "Audio"): (media.extract_audio, "Extracting audio…"),
            ("video", "Mute"): (media.mute_video, "Removing sound…"),
            ("video", "Frame"): (media.video_frame, "Grabbing a frame…"),
            ("video", "Rotate"): (media.rotate_video, "Rotating video…"),
            ("audio", "Normalize"): (media.normalize_audio, "Normalizing…"),
            ("audio", "Trim silence"): (media.trim_silence, "Trimming silence…"),
            ("audio", "Compress"): (media.compress_audio, "Compressing audio…"),
        }
        fn, verb = fns[(cat, name)]

        def work():
            outs = []
            for i, p in enumerate(paths):
                outer = current_progress()
                with progress_hook(lambda f, i=i: outer and outer((i + f) / len(paths))):
                    outs.append(fn(p))
            return outs
        self.submit(f"tool:{name}", paths, work, verb)

    # ------------------------------------------------------------ misc
    def _tray_click(self, reason):
        # macOS: a click on the menu-bar icon shows the menu; Windows: click opens a file
        if not IS_MAC and reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_dialog()

    def open_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(None, "Choose file(s) for DropDial", QDir.homePath())
        if files:
            self.show_click_menu(files)

    def show_click_menu(self, files: list[str]):
        g = (QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()).availableGeometry()
        pos = QCursor.pos() if g.contains(QCursor.pos()) else g.center()
        self.menu.popup(pos, files)
        self.menu.activateWindow()

    def open_settings(self):
        w = SettingsWindow(self.settings)
        w.changed.connect(self._settings_changed)
        self.open_window(w)

    def _settings_changed(self):
        self.watcher.set_key(self.settings.get("trigger"))
        self.tray.setToolTip(f"{APP_NAME} — press {self.trigger_label()} while dragging a file")

    def show_welcome(self):
        self.open_window(WelcomeWindow(self.settings, self.trigger_label()))

    def _single(self, cls, *args):
        """Bring an already-open panel forward instead of opening a second copy."""
        for w in self.windows:
            if isinstance(w, cls):
                w.raise_()
                w.activateWindow()
                return w
        w = cls(*args)
        self.open_window(w)
        return w

    def open_history(self):
        self._single(panels.HistoryWindow)

    def open_recipes(self):
        self._single(panels.RecipesWindow)

    def open_watch(self):
        w = self._single(panels.WatchWindow)
        try:
            w.changed.connect(self.reload_watch, Qt.UniqueConnection)
        except (RuntimeError, TypeError):
            pass

    # ------------------------------------------------------------ watch folders
    def reload_watch(self):
        rules = [r for r in watch.load_rules() if r.enabled and os.path.isdir(r.folder)]
        old = {(s.rule.folder, s.rule.action, s.rule.output): s for s in self.scanners}
        # keep existing scanners (and what they've already seen) for unchanged rules
        self.scanners = [old.get((r.folder, r.action, r.output)) or watch.FolderScanner(r) for r in rules]
        n = len(self.scanners)
        self.act_watch.setText(f"Watch folders… ({n} on)" if n else "Watch folders…")
        if n:
            self.watch_timer.start()
        else:
            self.watch_timer.stop()

    def _watch_tick(self):
        for sc in list(self.scanners):
            for f in sc.poll():
                rule = sc.rule
                print(f"watch: {f} → {rule.action}", flush=True)
                self.submit(rule.action, [str(f)], lambda f=f, rule=rule: rule.process(f),
                            f"{rule.label}…", source="watch",
                            on_done=lambda r, sc=sc: sc.ignore(r.outs),
                            toast=self.settings.get("watch_toasts"))


class DropDialQApplication(QApplication):
    """macOS delivers files from Finder's "Open With", the Dock and `open -a` as FileOpen
    events (not argv)."""
    file_opened = Signal(str)

    def __init__(self, argv):
        super().__init__(argv)
        self.early_files: list[str] = []

    def event(self, e):
        from PySide6.QtCore import QEvent
        if e.type() == QEvent.FileOpen:
            f = e.file()
            if f:
                self.early_files.append(f)
                self.file_opened.emit(f)
            return True
        return super().event(e)


def mac_setup(qapp):
    from PySide6.QtGui import QFont
    for fam in ("Segoe UI Variable Display", "Segoe UI Variable Text", "Segoe UI"):
        QFont.insertSubstitutions(fam, [".AppleSystemUIFont", "SF Pro Display", "Helvetica Neue"])
    try:
        from . import platform_mac
        platform_mac.become_accessory()
    except Exception:
        pass


def send_to_running(payload: dict) -> bool:
    s = QLocalSocket()
    s.connectToServer(IPC_NAME)
    if not s.waitForConnected(300):
        return False
    s.write(json.dumps(payload).encode("utf-8"))
    s.flush()
    s.waitForBytesWritten(500)
    s.disconnectFromServer()
    return True


def setup_logging():
    """Errors go to %LOCALAPPDATA%\\DropDial\\log.txt (pythonw / the .exe have no console)."""
    import faulthandler
    if IS_MAC:
        base = Path.home() / "Library" / "Logs" / "DropDial"
    else:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "DropDial"
    base.mkdir(parents=True, exist_ok=True)
    path = base / "log.txt"
    if path.exists() and path.stat().st_size > 1_000_000:
        path.replace(base / "log.old.txt")
    f = open(path, "a", encoding="utf-8", buffering=1)
    f.write(f"\n==== DropDial {VERSION} started {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
    if sys.stderr is None or getattr(sys, "frozen", False) or sys.executable.lower().endswith("pythonw.exe"):
        sys.stdout = sys.stderr = f
    faulthandler.enable(f)

    def hook(t, v, tb):
        f.write("Unhandled: " + "".join(traceback.format_exception(t, v, tb)))
    sys.excepthook = hook
    return path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    try:
        setup_logging()
    except Exception:
        pass
    if IS_WIN:
        try:  # crisp taskbar/tray icon grouping
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DropDial.App")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = DropDialQApplication(argv)
    if IS_MAC:
        mac_setup(qapp)
    qapp.setApplicationName(APP_NAME)
    qapp.setApplicationVersion(VERSION)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setWindowIcon(make_icon())

    if "--selftest" in argv:
        return selftest()
    files = [os.path.abspath(a) for a in argv[1:] if not a.startswith("-") and os.path.exists(a)]
    # already running? hand over and exit (instant: no second UI start-up)
    if send_to_running({"files": files} if files else {"show": "--quiet" not in argv}):
        return 0
    app = DropDialApp(qapp)
    qapp.file_opened.connect(lambda f: app.queue_files([f]))
    if qapp.early_files:
        app.queue_files(list(qapp.early_files))
    if files:  # e.g. "Send to → DropDial" or drag onto the .exe
        QTimer.singleShot(120, lambda: app.queue_files(files))
    elif not app.settings.get("welcomed"):
        QTimer.singleShot(300, app.show_welcome)
    elif "--quiet" not in argv:
        QTimer.singleShot(400, lambda: app.toasts.info(
            "DropDial is running", f"Drag any file, then press {app.trigger_label()}."))
    return qapp.exec()


def selftest() -> int:
    """Used by CI on the frozen .exe: exercise every library and build the UI, then exit."""
    import tempfile
    from PIL import Image
    try:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "t.png"
            Image.new("RGBA", (64, 48), (255, 100, 80, 255)).save(src)
            for t in convert.targets_for("image", ".png"):
                convert.convert(src, "image", t)
            pdf = convert.convert(src, "image", "PDF")[0]
            for t in convert.PDF_TARGETS:
                convert.convert(pdf, "pdf", t)
            (Path(d) / "n.txt").write_text("hello")
            docx = convert.convert(Path(d) / "n.txt", "text", "DOCX")[0]
            convert.convert(docx, "docx", "TXT")
            imaging.add_background(convert.open_image(src), imaging.Background())
            imaging.compress_pdf(pdf)
            imaging.protect_pdf(pdf, "pw")
            from . import liquid
            liquid.render(Image.new("RGB", (80, 80)), liquid.sdf_circle(80, 80, 40, 40, 30))
            imaging.pdf_page_numbers(pdf)
            imaging.watermark_pdf(pdf, "DRAFT")
            svg = Path(d) / "v.svg"
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
                           '<circle cx="10" cy="10" r="8" fill="red"/></svg>')
            convert.convert(svg, "vector", "PNG")
            os.environ.setdefault("DROPDIAL_HOME", str(Path(d) / "home"))
            recipes.run(recipes.find("Private"), [src])
            if media.available():
                print("selftest: ffmpeg at", media.ffmpeg_path())
            else:
                print("selftest: ffmpeg not found (video/audio disabled)")
            menu = RadialMenu(lambda p: {"Convert": [Item("PNG")]}, lambda p: "1 KB")
            menu._load([str(src)])
            n = lambda *a, **k: None
            for w in (tools.CropWindow(str(src), n), tools.AddBgWindow(str(src), n), tools.EditWindow(str(src), n),
                      tools.AnnotateWindow(str(src), n), tools.RedactWindow(str(src), n),
                      tools.MetadataWindow(str(src), n), tools.CompressWindow([str(src)], n),
                      tools.ResizeWindow([str(src)], n), tools.ProtectWindow(str(pdf), n),
                      tools.WatermarkWindow([str(src)], n), tools.WatermarkWindow([str(pdf)], n, is_pdf=True),
                      tools.UnlockWindow(str(pdf), n), panels.HistoryWindow(), panels.RecipesWindow(),
                      panels.WatchWindow()):
                w.close()
            ToastStack().info("ok", "ok").dismiss()
        print("SELFTEST OK")
        return 0
    except Exception:
        traceback.print_exc()
        print("SELFTEST FAILED")
        return 1
