"""Tray panels: History, Recipes (builder) and Watch folders."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from . import history, recipes, watch
from .i18n import N_, error_text, tr, trn
from .util import UserError, human_size
from .window import GlassWindow

IS_WIN = sys.platform == "win32"


def _dim(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("dim")
    l.setWordWrap(True)
    return l


def _section(text: str) -> QLabel:
    l = QLabel(text.upper())
    l.setObjectName("section")
    return l


def _list() -> QListWidget:
    l = QListWidget()
    l.setWordWrap(True)
    l.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    return l


def _button(text: str, slot, primary: bool = False, tip: str = "") -> QPushButton:
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    if tip:
        b.setToolTip(tip)
    b.clicked.connect(slot)
    return b


# ================================================================ History
class HistoryWindow(GlassWindow):
    """Everything DropDial made: search it, open it, show it, undo it."""

    def __init__(self):
        super().__init__(tr("History"), size=(660, 600))
        self.stats = QLabel()
        self.stats.setObjectName("dim")
        self.body.addWidget(self.stats)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search by file name or action…"))
        self.search.textChanged.connect(self._fill)
        self.body.addWidget(self.search)
        self.list = _list()
        self.list.itemDoubleClicked.connect(lambda _: self.open())
        self.list.currentItemChanged.connect(lambda *_: self._sync())
        self.body.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.b_open = _button(tr("Open"), self.open)
        self.b_show = _button(tr("Show in folder"), self.show_in_folder)
        self.b_copy = _button(tr("Copy"), self.copy, tip=tr("Copy the file so you can paste it anywhere"))
        self.b_undo = _button(tr("Undo"), self.undo, tip=tr("Move the results to the Recycle Bin") if IS_WIN
                              else tr("Move the results to the Trash"))
        for b in (self.b_open, self.b_show, self.b_copy, self.b_undo):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(_button(tr("Clear history"), self.clear, tip=tr("Forget the list (files are kept)")))
        self.body.addLayout(row)
        self.entries: list[history.Entry] = []
        self.reload()

    def reload(self):
        self.entries = history.entries()
        st = history.stats()
        bits = [trn("{n} file made", "{n} files made", st["files"])]
        if st["saved"]:
            bits.append(tr("{size} saved by compressing", size=human_size(st["saved"])))
        self.stats.setText(" · ".join(bits) if self.entries else tr("Nothing yet. Results show up here."))
        self._fill()

    def _fill(self):
        q = self.search.text().strip().lower()
        self.list.clear()
        for e in self.entries:
            hay = " ".join([e.title, e.detail, e.action, *map(lambda p: Path(p).name, e.srcs + e.outs)]).lower()
            if q and q not in hay:
                continue
            gone = not e.existing_outs
            src = Path(e.srcs[0]).name if e.srcs else ""
            via = {"watch": tr("watch folder"), "cli": tr("command line")}.get(e.source)
            it = QListWidgetItem(f"{e.title}    {e.when()}{' · ' + via if via else ''}\n{src}  →  {e.detail}"
                                 + (f"   ({tr('moved or deleted')})" if gone else ""))
            it.setData(Qt.UserRole, e)
            if gone:
                it.setForeground(Qt.gray)
            self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._sync()

    def _current(self) -> history.Entry | None:
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _sync(self):
        e = self._current()
        have = bool(e and e.existing_outs)
        for b in (self.b_open, self.b_show, self.b_copy, self.b_undo):
            b.setEnabled(have)

    def open(self):
        from .toasts import open_file
        e = self._current()
        if e and e.existing_outs:
            open_file(e.existing_outs[0])

    def show_in_folder(self):
        from .toasts import reveal
        e = self._current()
        if e and e.existing_outs:
            reveal(e.existing_outs[0])

    def copy(self):
        from .toasts import copy_files
        e = self._current()
        if e and e.existing_outs:
            copy_files(e.existing_outs)
            self.stats.setText(trn("Copied {n} file: paste it into a folder, chat or email.",
                                   "Copied {n} files: paste them into a folder, chat or email.", len(e.existing_outs)))

    def undo(self):
        from .toasts import trash
        e = self._current()
        if e and e.existing_outs:
            n = trash(e.existing_outs)
            self.stats.setText(trn("Moved {n} file to the Recycle Bin.", "Moved {n} files to the Recycle Bin.", n)
                               if IS_WIN else trn("Moved {n} file to the Trash.", "Moved {n} files to the Trash.", n))
            QTimer.singleShot(1500, self.reload)
            self._fill()

    def clear(self):
        history.clear()
        self.reload()


# ================================================================ Recipes
CHOICE_LABELS = {"long": N_("Longest side (px)"), "pct": N_("Percent"), "w": N_("Width (px)"),
                 "h": N_("Height (px)"), "bottom-right": N_("Bottom right"), "bottom-left": N_("Bottom left"),
                 "top-right": N_("Top right"), "top-left": N_("Top left"), "center": N_("Centre"),
                 "tile": N_("Tiled"), "bottom-center": N_("Bottom centre"), "top-center": N_("Top centre"),
                 "90": N_("90° clockwise"), "180": "180°", "270": N_("90° anticlockwise"), "Auto": N_("Auto")}
CAT_NAMES = {"image": N_("images"), "pdf": N_("PDFs"), "docx": N_("Word files"), "text": N_("text files"),
             "vector": N_("SVGs"), "ebook": N_("e-books"), "video": N_("videos"), "audio": N_("audio")}
GLYPH_CHOICES = ["★", "⚡", "✉", "⛨", "♥", "⎙", "⚠", "▶", "♫", "▦", "◆", "●", "✿", "☀", "⚙", "✦"]


class ParamForm(QWidget):
    """Widgets for one step's parameters; emits `changed` with the new values."""
    changed = Signal(dict)

    def __init__(self, st: recipes.StepType, values: dict):
        super().__init__()
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        self.getters = {}
        if not st.params:
            grid.addWidget(_dim(tr("No settings: this step just runs.")), 0, 0)
        for r, prm in enumerate(st.params):
            v = values.get(prm.name, prm.default)
            if prm.kind == "bool":
                w = QCheckBox(tr(prm.label))
                w.setChecked(bool(v))
                w.toggled.connect(self._emit)
                self.getters[prm.name] = w.isChecked
                grid.addWidget(w, r, 1)
                continue
            grid.addWidget(QLabel(tr(prm.label)), r, 0)
            if prm.kind == "int":
                w = QSpinBox()
                w.setRange(prm.lo, prm.hi)
                w.setValue(int(v or 0))
                w.valueChanged.connect(self._emit)
                self.getters[prm.name] = w.value
            elif prm.kind == "choice":
                w = QComboBox()
                for c in prm.choices:
                    w.addItem(tr(CHOICE_LABELS.get(c, str(c))), c)
                idx = w.findData(v)
                w.setCurrentIndex(max(0, idx if idx >= 0 else w.findText(str(v))))
                w.currentIndexChanged.connect(self._emit)
                self.getters[prm.name] = w.currentData
            else:  # text / size
                w = QLineEdit(str(v or ""))
                if prm.kind == "size":
                    w.setPlaceholderText(tr("e.g. 500KB (blank = use quality)"))
                w.textChanged.connect(self._emit)
                self.getters[prm.name] = w.text
            grid.addWidget(w, r, 1)
        grid.setColumnStretch(1, 1)

    def values(self) -> dict:
        return {k: g() for k, g in self.getters.items()}

    def _emit(self, *_):
        self.changed.emit(self.values())


class RecipesWindow(GlassWindow):
    """Pick which recipes show in the menu, and build your own."""

    def __init__(self):
        super().__init__(tr("Recipes"), size=(880, 660))
        self.body.addWidget(_dim(tr("Recipes run several steps with one drop. Ticked recipes appear in the "
                                    "menu's third ring (tap the trigger key twice while dragging).")))
        cols = QHBoxLayout()
        cols.setSpacing(14)
        left = QVBoxLayout()
        self.list = _list()
        self.list.setMinimumWidth(275)
        self.list.currentItemChanged.connect(lambda *_: self._load_current())
        self.list.itemChanged.connect(self._toggled)
        left.addWidget(self.list, 1)
        lrow = QHBoxLayout()
        lrow.addWidget(_button(tr("New"), self.new))
        lrow.addWidget(_button(tr("Import…"), self.import_json, tip=tr("Load a recipe .json file")))
        lrow.addStretch(1)
        left.addLayout(lrow)
        cols.addLayout(left, 0)

        right = QVBoxLayout()
        head = QHBoxLayout()
        self.glyph = QComboBox()
        for g in GLYPH_CHOICES:
            self.glyph.addItem(g)
        self.glyph.setFixedWidth(64)
        self.glyph.currentIndexChanged.connect(self._dirty)
        head.addWidget(self.glyph)
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr("Recipe name"))
        self.name.textChanged.connect(self._dirty)
        head.addWidget(self.name, 1)
        right.addLayout(head)
        self.applies = _dim("")
        right.addWidget(self.applies)
        right.addWidget(_section(tr("Steps")))
        self.steps = _list()
        self.steps.setMaximumHeight(170)
        self.steps.currentRowChanged.connect(lambda _: self._load_step())
        right.addWidget(self.steps)
        srow = QHBoxLayout()
        self.b_add = QPushButton("＋ " + tr("Add step"))
        menu = QMenu(self.b_add)
        menu.setStyleSheet(self.styleSheet())
        for st in recipes.STEPS.values():
            cats = ", ".join(tr(CAT_NAMES[c]) for c in st.cats) if len(st.cats) < 6 else tr("any file")
            menu.addAction(f"{tr(st.label)}   ({cats})", lambda key=st.key: self.add_step(key))
        self.b_add.setMenu(menu)
        srow.addWidget(self.b_add)
        srow.addWidget(_button("↑", lambda: self.move_step(-1), tip=tr("Move up")))
        srow.addWidget(_button("↓", lambda: self.move_step(1), tip=tr("Move down")))
        srow.addWidget(_button(tr("Remove"), self.remove_step))
        srow.addStretch(1)
        right.addLayout(srow)
        right.addWidget(_section(tr("Step settings")))
        self.form_holder = QVBoxLayout()
        right.addLayout(self.form_holder)
        right.addStretch(1)
        self.msg = _dim("")
        right.addWidget(self.msg)
        foot = QHBoxLayout()
        self.b_delete = _button(tr("Delete"), self.delete)
        self.b_export = _button(tr("Export…"), self.export_json,
                                tip=tr("Save as .json to share or use from the command line"))
        foot.addWidget(self.b_delete)
        foot.addWidget(self.b_export)
        foot.addStretch(1)
        self.b_save = _button(tr("Save"), self.save, primary=True)
        foot.addWidget(self.b_save)
        right.addLayout(foot)
        cols.addLayout(right, 1)
        self.body.addLayout(cols, 1)

        self.editing: recipes.Recipe | None = None
        self.work: list[dict] = []
        self._loading = False
        self.refresh()

    # ------------------------------------------------------------ list
    def refresh(self, select: str | None = None):
        self._loading = True
        cur = select or (self.editing.name if self.editing else None)
        self.list.clear()
        hidden = recipes.hidden()
        for r in recipes.all_recipes():
            tag = tr("built-in") if r.builtin else (tr("edited built-in") if any(
                recipes.slug(b.name) == recipes.slug(r.name) for b in recipes.BUILTIN) else tr("yours"))
            it = QListWidgetItem(f"{r.glyph}  {recipes.display_name(r)}\n     {tag}")
            it.setData(Qt.UserRole, r)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if r.name in hidden else Qt.Checked)
            it.setToolTip(recipes.display_description(r) or r.summary())
            self.list.addItem(it)
            if cur and recipes.slug(r.name) == recipes.slug(cur):
                self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._loading = False
        self._load_current()

    def _toggled(self, it: QListWidgetItem):
        if self._loading:
            return
        r = it.data(Qt.UserRole)
        recipes.set_hidden(r.name, it.checkState() != Qt.Checked)

    def _load_current(self):
        if self._loading:
            return
        it = self.list.currentItem()
        if it is None:
            return
        self.edit(it.data(Qt.UserRole))

    # ------------------------------------------------------------ editor
    def edit(self, r: recipes.Recipe):
        self._loading = True
        self.editing = r
        self.work = [dict(s) for s in r.steps]
        self.name.setText(recipes.display_name(r))
        i = self.glyph.findText(r.glyph)
        if i < 0:
            self.glyph.addItem(r.glyph)
            i = self.glyph.count() - 1
        self.glyph.setCurrentIndex(i)
        self._loading = False
        self._fill_steps(0)
        is_custom = any(recipes.slug(c.name) == recipes.slug(r.name) for c in recipes.custom_recipes())
        is_builtin_name = any(recipes.slug(b.name) == recipes.slug(r.name) for b in recipes.BUILTIN)
        self.b_delete.setEnabled(is_custom)
        self.b_delete.setText(tr("Reset to built-in") if is_custom and is_builtin_name else tr("Delete"))
        self.msg.setText(tr("Built-in: saving keeps your changes as your own version.") if r.builtin else "")
        self.b_save.setEnabled(False)

    def _fill_steps(self, row: int):
        self.steps.clear()
        for s in self.work:
            st = recipes.STEPS.get(s.get("step"))
            label = st.describe({k: v for k, v in s.items() if k != "step"}) if st else s.get("step")
            self.steps.addItem(f"{self.steps.count() + 1}.  {label}")
        if self.work:
            self.steps.setCurrentRow(min(max(0, row), len(self.work) - 1))
        else:
            self._load_step()
        self._update_applies()

    def _update_applies(self):
        r = self._built()
        cats = [c for c in recipes.ALL_CATS if r.applies_to(c)]
        self.applies.setText(tr("Works on: {kinds}", kinds=", ".join(tr(CAT_NAMES[c]) for c in cats)) if cats
                             else tr("Works on: nothing yet"))

    def _load_step(self):
        while self.form_holder.count():
            w = self.form_holder.takeAt(0).widget()
            if w:
                w.deleteLater()
        row = self.steps.currentRow()
        if not (0 <= row < len(self.work)):
            self.form_holder.addWidget(_dim(tr("Add a step to get started.")))
            return
        s = self.work[row]
        st = recipes.STEPS.get(s.get("step"))
        if st is None:
            self.form_holder.addWidget(_dim(tr("Unknown step {step}", step=repr(s.get("step")))))
            return
        form = ParamForm(st, s)
        form.changed.connect(lambda vals, row=row: self._step_changed(row, vals))
        self.form_holder.addWidget(form)

    def _step_changed(self, row: int, vals: dict):
        self.work[row].update(vals)
        st = recipes.STEPS[self.work[row]["step"]]
        it = self.steps.item(row)
        if it:
            it.setText(f"{row + 1}.  {st.describe(vals)}")
        self._update_applies()
        self._dirty()

    def _dirty(self, *_):
        if not self._loading:
            self.b_save.setEnabled(True)
            self._update_applies()

    def add_step(self, key: str):
        st = recipes.STEPS[key]
        self.work.append({"step": key, **st.defaults()})
        self._fill_steps(len(self.work) - 1)
        self._dirty()

    def move_step(self, d: int):
        i = self.steps.currentRow()
        j = i + d
        if 0 <= i < len(self.work) and 0 <= j < len(self.work):
            self.work[i], self.work[j] = self.work[j], self.work[i]
            self._fill_steps(j)
            self._dirty()

    def remove_step(self):
        i = self.steps.currentRow()
        if 0 <= i < len(self.work):
            del self.work[i]
            self._fill_steps(i)
            self._dirty()

    def new(self):
        self.edit(recipes.Recipe(tr("My recipe"), [{"step": "resize", **recipes.STEPS["resize"].defaults()}], "★"))
        self.list.clearSelection()
        self.b_delete.setEnabled(False)
        self.b_save.setEnabled(True)
        self.name.setFocus()
        self.name.selectAll()

    def _built(self) -> recipes.Recipe:
        prev = self.editing
        return recipes.Recipe(recipes.builtin_name(self.name.text().strip()), [dict(s) for s in self.work],
                              self.glyph.currentText(),
                              description=prev.description if prev else "",
                              inputs=list(prev.inputs) if prev else [])

    def save(self):
        r = self._built()
        try:
            prev = self.editing.name if self.editing and not self.editing.builtin else None
            recipes.save_recipe(r, replace=prev)
        except UserError as e:
            self.msg.setText(error_text(e))
            return
        self.editing = r
        self.msg.setText(tr("Saved “{name}”.", name=recipes.display_name(r)))
        self.refresh(select=r.name)

    def delete(self):
        if not self.editing:
            return
        name = self.editing.name
        recipes.delete_recipe(name)
        self.editing = None
        self.refresh(select=name)

    def export_json(self):
        r = self._built()
        path, _ = QFileDialog.getSaveFileName(self, tr("Export recipe"), f"{recipes.slug(r.name) or 'recipe'}.json",
                                              tr("Recipe") + " (*.json)")
        if path:
            Path(path).write_text(json.dumps(r.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")
            self.msg.setText(tr("Exported to {name}. Run it with: {command}", name=Path(path).name,
                                command=f'dropdial recipe run "{path}" FILES'))

    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Import recipe"), "", tr("Recipe") + " (*.json)")
        if not path:
            return
        try:
            r = recipes.Recipe.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
            recipes.save_recipe(r)
        except (UserError, ValueError, OSError) as e:
            self.msg.setText(tr("Couldn't import: {error}", error=error_text(e)))
            return
        self.refresh(select=r.name)
        self.msg.setText(tr("Imported “{name}”.", name=recipes.display_name(r)))


# ================================================================ Watch folders
CONVERT_CHOICES = ["JPG", "PNG", "WEBP", "PDF", "DOCX", "MP4", "MP3"]


class WatchWindow(GlassWindow):
    changed = Signal()

    def __init__(self):
        super().__init__(tr("Watch folders"), size=(700, 580))
        self.body.addWidget(_dim(tr("New files that land in a watched folder are processed automatically: "
                                    "screenshots to WebP, scans to PDF, downloads made private… Files already "
                                    "there are left alone, and originals are never changed.")))
        self.list = _list()
        self.list.itemChanged.connect(self._toggled)
        self.body.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addWidget(_button(tr("Remove"), self.remove))
        row.addStretch(1)
        self.toasts = QCheckBox(tr("Show a notification for each file"))
        self.store = QSettings("DropDial", "DropDial")
        self.toasts.setChecked(self.store.value("watch_toasts", True) in (True, "true", "1", 1))
        self.toasts.toggled.connect(lambda on: self.store.setValue("watch_toasts", on))
        row.addWidget(self.toasts)
        self.body.addLayout(row)

        self.body.addWidget(_section(tr("Add a folder")))
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.addWidget(QLabel(tr("Folder")), 0, 0)
        self.folder = QLineEdit()
        self.folder.setPlaceholderText(tr("Choose a folder…"))
        g.addWidget(self.folder, 0, 1)
        g.addWidget(_button(tr("Browse…"), self.browse), 0, 2)
        g.addWidget(QLabel(tr("Then")), 1, 0)
        self.action = QComboBox()
        for r in recipes.all_recipes():
            self.action.addItem(f"{r.glyph}  " + tr("Run “{name}”", name=recipes.display_name(r)), f"recipe:{r.name}")
        for t in CONVERT_CHOICES:
            self.action.addItem("⇄  " + tr("Convert to {fmt}", fmt=t), f"convert:{t}")
        g.addWidget(self.action, 1, 1, 1, 2)
        g.addWidget(QLabel(tr("Save to")), 2, 0)
        self.output = QComboBox()
        self.output.addItem(tr("A “DropDial” subfolder"), "subfolder")
        self.output.addItem(tr("The same folder"), "beside")
        g.addWidget(self.output, 2, 1, 1, 2)
        g.setColumnStretch(1, 1)
        self.body.addLayout(g)
        self.msg = _dim("")
        self.body.addWidget(self.msg)
        foot = QHBoxLayout()
        foot.addStretch(1)
        foot.addWidget(_button(tr("Done"), self.close))
        foot.addWidget(_button(tr("Add"), self.add, primary=True))
        self.body.addLayout(foot)
        self.rules = watch.load_rules()
        self._fill()

    def _fill(self):
        self.list.blockSignals(True)
        self.list.clear()
        for r in self.rules:
            where = (tr("results in the {name}/ subfolder", name=watch.SUBFOLDER) if r.output == "subfolder"
                     else tr("results in the same folder"))
            missing = "" if Path(r.folder).is_dir() else f"   ({tr('folder not found')})"
            shown = r.folder.replace(str(Path.home()), "~", 1)
            it = QListWidgetItem(f"{shown}{missing}\n     → {r.label} · {where}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if r.enabled else Qt.Unchecked)
            self.list.addItem(it)
        if not self.rules:
            it = QListWidgetItem(tr("No watch folders yet. Add one below."))
            it.setFlags(Qt.NoItemFlags)
            self.list.addItem(it)
        self.list.blockSignals(False)

    def _save(self):
        watch.save_rules(self.rules)
        self.changed.emit()

    def _toggled(self, it: QListWidgetItem):
        i = self.list.row(it)
        if 0 <= i < len(self.rules):
            self.rules[i].enabled = it.checkState() == Qt.Checked
            self._save()

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, tr("Folder to watch"), self.folder.text() or str(Path.home()))
        if d:
            self.folder.setText(d)

    def add(self):
        folder = self.folder.text().strip()
        if not folder or not Path(folder).expanduser().is_dir():
            self.msg.setText(tr("Choose a folder that exists."))
            return
        folder = str(Path(folder).expanduser().resolve())
        rule = watch.WatchRule(folder, self.action.currentData(), True, self.output.currentData())
        if any(r.folder == rule.folder and r.action == rule.action for r in self.rules):
            self.msg.setText(tr("That folder already does this."))
            return
        self.rules.append(rule)
        self._save()
        self._fill()
        self.folder.clear()
        self.msg.setText(tr("Watching {name}. Drop a file in to try it.", name=Path(folder).name))

    def remove(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.rules):
            del self.rules[i]
            self._save()
            self._fill()
