"""Home: a drop zone, recent conversions with thumbnails, and the way to everything else.

Opens from the tray / menu-bar icon. Dropping files here (or clicking the zone to pick them)
shows the dial right there, so DropDial works without the Shift-drag too.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import CREDIT, __version__, glass, history
from .util import category
from .window import GlassWindow

THUMB = QSize(148, 104)
GLYPH = {"image": "▧", "pdf": "▤", "docx": "¶", "text": "≡", "vector": "◇", "ebook": "❒", "video": "▶",
         "audio": "♫", "sheet": "▦", "data": "{ }", "markup": "¶", "subtitle": "❝", "archive": "▤",
         "font": "Aa", "model": "◆", "geo": "⌖", "rawimage": "▧", "email": "✉"}


def thumbnail(path: Path) -> QPixmap | None:
    """A small picture of the file: images, PDFs and SVGs; None for everything else."""
    try:
        cat = category(path)
        if cat in ("image", "rawimage") and path.suffix.lower() not in (".dng", ".cr2", ".cr3", ".nef", ".arw"):
            from .convert import open_preview
            im = open_preview(path, max_side=320).convert("RGBA")
            q = QImage(im.tobytes(), im.width, im.height, im.width * 4, QImage.Format_RGBA8888).copy()
            return QPixmap.fromImage(q)
        if cat == "pdf":
            import fitz
            with fitz.open(str(path)) as doc:
                if doc.needs_pass or not len(doc):
                    return None
                pix = doc[0].get_pixmap(dpi=40, alpha=False)
                q = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                return QPixmap.fromImage(q)
        if cat == "vector":
            from .convert import svg_to_image
            im = svg_to_image(path).convert("RGBA")
            im.thumbnail((320, 320))
            q = QImage(im.tobytes(), im.width, im.height, im.width * 4, QImage.Format_RGBA8888).copy()
            return QPixmap.fromImage(q)
    except Exception:  # noqa: BLE001 - a thumbnail is a nicety, never an error
        return None
    return None


class DropZone(QWidget):
    """The big dashed target. Drop files on it, or click to choose them."""
    dropped = Signal(list, object)    # local paths, QMimeData (for browser drags)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)
        self.setCursor(Qt.PointingHandCursor)
        self.hot = False

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(r, 16, 16)
        p.fillPath(path, glass.accent("hi", 46 if self.hot else 16))
        pen = QPen(glass.gold(230 if self.hot else 150), 1.6, Qt.DashLine)
        pen.setDashPattern([5, 4])
        p.setPen(pen)
        p.drawPath(path)
        c = QPointF(r.center().x(), r.center().y() - 22)
        p.setPen(QPen(glass.gold(220), 2))
        p.drawEllipse(c, 18, 18)
        p.drawEllipse(c, 6, 6)
        f = QFont()
        f.setPixelSize(16)
        f.setBold(True)
        p.setFont(f)
        p.setPen(glass.fg())
        p.drawText(QRectF(r.left(), c.y() + 24, r.width(), 24), Qt.AlignCenter,
                   "Drop files here" if not self.hot else "Release to open the dial")
        f.setPixelSize(12)
        f.setBold(False)
        p.setFont(f)
        p.setPen(glass.fg(150))
        p.drawText(QRectF(r.left(), c.y() + 48, r.width(), 20), Qt.AlignCenter,
                   "or click to choose · or Shift-drag a file anywhere")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage() or md.hasHtml():
            self.hot = True
            self.update()
            e.setDropAction(Qt.CopyAction)
            e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        e.setDropAction(Qt.CopyAction)
        e.accept()

    def dragLeaveEvent(self, e):
        self.hot = False
        self.update()

    def dropEvent(self, e):
        self.hot = False
        self.update()
        md = e.mimeData()
        paths = [u.toLocalFile() for u in md.urls() if u.isLocalFile() and u.toLocalFile()]
        e.setDropAction(Qt.CopyAction)
        e.accept()
        self.dropped.emit(paths, md)


class RecentCard(QWidget):
    """One recent result: thumbnail, name, what was done. Click to open; right-click for more."""

    def __init__(self, entry: history.Entry, actions: dict):
        super().__init__()
        self.entry, self.actions = entry, actions
        self.out = entry.existing_outs[0]
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(THUMB.width() + 16)
        self.setToolTip(f"{self.out.name}\n{entry.title} · {entry.detail}\nClick to open · right-click for more")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        self.pic = QLabel()
        self.pic.setFixedSize(THUMB)
        self.pic.setAlignment(Qt.AlignCenter)
        o = glass.ov(16)
        self.pic.setStyleSheet(f"background: rgba({o.red()},{o.green()},{o.blue()},0.06); border-radius: 10px;"
                               f"color: {glass.GOLD}; font-size: 26px;")
        self.pic.setText(GLYPH.get(category(self.out) or "", "◌"))
        lay.addWidget(self.pic)
        name = QLabel(self._elide(self.out.name, 22))
        name.setStyleSheet("font-weight: 600;")
        lay.addWidget(name)
        sub = QLabel(f"{entry.title} · {entry.when()}")
        sub.setObjectName("dim")
        lay.addWidget(sub)

    @staticmethod
    def _elide(s: str, n: int) -> str:
        return s if len(s) <= n else s[: n - 8] + "…" + s[-7:]

    def load_thumb(self):
        pm = thumbnail(self.out)
        if pm is not None:
            pm = pm.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.pic.setPixmap(pm)

    def enterEvent(self, e):
        c = glass.accent("hi")
        self.setStyleSheet(f"RecentCard {{ background: rgba({c.red()},{c.green()},{c.blue()},0.08);"
                           " border-radius: 12px; }")

    def leaveEvent(self, e):
        self.setStyleSheet("")

    def paintEvent(self, e):    # let the hover stylesheet paint on a plain QWidget subclass
        from PySide6.QtWidgets import QStyle, QStyleOption
        o = QStyleOption()
        o.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, o, p, self)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.actions["open"](self.out)
        elif e.button() == Qt.RightButton:
            m = QMenu(self)
            m.setStyleSheet(glass.QSS)
            m.addAction("Open", lambda: self.actions["open"](self.out))
            m.addAction("Show in folder", lambda: self.actions["reveal"](self.out))
            m.addAction("Convert again…", lambda: self.actions["dial"]([str(self.out)]))
            m.addAction("Copy", lambda: self.actions["copy"]([self.out]))
            m.addSeparator()
            m.addAction("Move to " + ("Recycle Bin" if sys.platform == "win32" else "Trash"),
                        lambda: self.actions["trash"]([self.out]))
            m.exec(QCursor.pos())


class HomeWindow(GlassWindow):
    def __init__(self, app):
        super().__init__("DropDial", size=(720, 640))
        self.app = app
        head = QLabel(f"Drag. Shift. Drop.  <span style='color:{glass.GOLD}'>Done.</span>")
        head.setTextFormat(Qt.RichText)
        head.setStyleSheet("font-size: 20px; font-weight: 700;")
        self.body.addWidget(head)

        self.update_bar = QPushButton()
        self.update_bar.setObjectName("primary")
        self.update_bar.hide()
        self.update_bar.clicked.connect(self._open_update)
        self.body.addWidget(self.update_bar)

        self.zone = DropZone()
        self.zone.clicked.connect(app.open_dialog)
        self.zone.dropped.connect(self._dropped)
        self.body.addWidget(self.zone)

        row = QHBoxLayout()
        lab = QLabel("RECENT")
        lab.setObjectName("section")
        row.addWidget(lab)
        row.addStretch(1)
        all_btn = QPushButton("All history")
        all_btn.clicked.connect(app.open_history)
        row.addWidget(all_btn)
        self.body.addLayout(row)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.grid_host)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollArea > QWidget > QWidget { background: transparent; }")
        self.body.addWidget(scroll, 1)

        foot = QHBoxLayout()
        for text, slot in (("Recipes", app.open_recipes), ("Watch folders", app.open_watch),
                           ("Settings", app.open_settings), ("How to use", app.show_welcome)):
            b = QPushButton(text)
            b.clicked.connect(slot)
            foot.addWidget(b)
        foot.addStretch(1)
        credit = QLabel(f"DropDial {__version__} · {CREDIT}")
        credit.setObjectName("good")
        foot.addWidget(credit)
        self.body.addLayout(foot)
        self.reload()
        self.show_update(getattr(app, "update", None))

    # ---- content
    def reload(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        from .toasts import copy_files, open_file, reveal, trash
        actions = {"open": open_file, "reveal": reveal, "copy": copy_files,
                   "dial": self.app.show_click_menu,
                   "trash": lambda ps: (trash(ps), QTimer.singleShot(300, self.reload))}
        cards, seen = [], set()
        for e in history.entries():
            outs = e.existing_outs
            if not outs or str(outs[0]) in seen:
                continue
            seen.add(str(outs[0]))
            cards.append(RecentCard(e, actions))
            if len(cards) >= 12:
                break
        cols = 4
        for i, c in enumerate(cards):
            self.grid.addWidget(c, i // cols, i % cols, Qt.AlignTop | Qt.AlignLeft)
        if not cards:
            empty = QLabel("Nothing yet. Results show up here, with a preview.")
            empty.setObjectName("dim")
            self.grid.addWidget(empty, 0, 0)
        self.grid.setColumnStretch(cols, 1)
        self.grid.setRowStretch(len(cards) // cols + 1, 1)
        # thumbnails one at a time so the window opens instantly
        for k, c in enumerate(cards):
            QTimer.singleShot(30 + 25 * k, c.load_thumb)

    def show_update(self, upd):
        if upd is None:
            self.update_bar.hide()
            return
        self.update_bar.setText(f"DropDial {upd.version} is available. Click to download")
        self.update_bar.show()

    def _open_update(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        upd = getattr(self.app, "update", None)
        if upd is not None:
            QDesktopServices.openUrl(QUrl(upd.url))

    def _dropped(self, paths: list[str], md):
        if paths:
            self.app.show_click_menu(paths)
            return
        self.app.open_web_drop(md)
