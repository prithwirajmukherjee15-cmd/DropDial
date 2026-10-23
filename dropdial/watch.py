"""Watch folders: new files dropped into a folder are processed automatically.

    ~/Screenshots  →  recipe "Web-ready"      (results in ~/Screenshots/DropDial/)
    ~/Downloads    →  convert to PDF

Polling (every couple of seconds) is used instead of OS notifications: it works the same
on every platform and on network drives, and a file is only picked up once its size has
stopped changing, so half-copied downloads are never touched. Files that were already in
the folder when watching started are left alone. No Qt in here: the app drives `poll()`
from a timer and the command line drives it from a loop."""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .i18n import tr
from .util import UserError, category, data_dir, output_override

SUBFOLDER = "DropDial"


@dataclass
class WatchRule:
    folder: str
    action: str                 # "recipe:<name>" or "convert:<FORMAT>"
    enabled: bool = True
    output: str = "subfolder"   # "subfolder" (<folder>/DropDial) or "beside"

    @property
    def label(self) -> str:
        kind, _, name = self.action.partition(":")
        if kind == "recipe":
            from .recipes import display_name
            return display_name(name)
        return tr("Convert to {fmt}", fmt=name)

    def out_dir(self) -> Path:
        f = Path(self.folder)
        return f / SUBFOLDER if self.output == "subfolder" else f

    def accepts(self, path: Path) -> bool:
        """Should this file be processed by this rule?"""
        name = path.name
        if name.startswith((".", "~", ".~")) or name.endswith((".part", ".crdownload", ".tmp", ".download")):
            return False
        cat = category(path)
        if cat is None:
            return False
        kind, _, name_ = self.action.partition(":")
        if kind == "convert":
            from .recipes import _targets
            ext = path.suffix.lower().lstrip(".").upper()
            ext = {"JPEG": "JPG", "TIF": "TIFF"}.get(ext, ext)
            return ext != name_.upper() and name_.upper() in _targets(cat)
        if kind == "recipe":
            from . import recipes
            try:
                r = recipes.find(name_)
            except UserError:
                return False
            if path.stem.endswith(" " + r.name.replace("→", "to")):
                return False          # one of our own results (when saving beside the originals)
            return r.applies_to(cat)
        return False

    def process(self, path: str | Path) -> list[Path]:
        """Run the rule on one file; returns the files written."""
        path = Path(path)
        kind, _, name = self.action.partition(":")
        with output_override(self.out_dir()):
            if kind == "recipe":
                from . import recipes
                return recipes.run(recipes.find(name), [path]).outputs
            from . import convert
            return convert.convert(path, category(path), name)

    @classmethod
    def from_json(cls, d: dict) -> "WatchRule":
        return cls(folder=str(d["folder"]), action=str(d["action"]), enabled=bool(d.get("enabled", True)),
                   output="beside" if d.get("output") == "beside" else "subfolder")


class FolderScanner:
    """Finds files that are new in `rule.folder` and have finished being written."""

    def __init__(self, rule: WatchRule, settle: float = 1.5, clock: Callable[[], float] = time.monotonic):
        self.rule = rule
        self.settle = settle
        self.clock = clock
        self.seen: set[str] = set(self._listing())       # existing files are never processed
        self.pending: dict[str, tuple[int, float, float]] = {}   # name -> (size, mtime, stable since)

    def _listing(self) -> list[str]:
        try:
            with os.scandir(self.rule.folder) as it:
                return [e.name for e in it if e.is_file(follow_symlinks=False)]
        except OSError:
            return []

    def poll(self) -> list[Path]:
        ready: list[Path] = []
        now = self.clock()
        names = self._listing()
        present = set(names)
        for name in names:
            if name in self.seen:
                continue
            p = Path(self.rule.folder) / name
            try:
                st = p.stat()
            except OSError:
                continue
            sig = (st.st_size, st.st_mtime)
            prev = self.pending.get(name)
            if prev is None or (prev[0], prev[1]) != sig:
                self.pending[name] = (sig[0], sig[1], now)
                continue
            if st.st_size > 0 and now - prev[2] >= self.settle:
                self.seen.add(name)
                self.pending.pop(name, None)
                if self.rule.accepts(p):
                    ready.append(p)
        for name in list(self.pending):
            if name not in present:
                self.pending.pop(name)
        self.seen &= present   # a deleted-then-recreated file counts as new
        return ready

    def ignore(self, paths) -> None:
        """Mark files we wrote ourselves so they're never picked up."""
        for p in paths:
            p = Path(p)
            if p.parent == Path(self.rule.folder):
                self.seen.add(p.name)


# ---------------------------------------------------------------- storage
def store_path() -> Path:
    return data_dir() / "watch.json"


def load_rules() -> list[WatchRule]:
    p = store_path()
    if not p.exists():
        return []
    try:
        return [WatchRule.from_json(d) for d in json.loads(p.read_text(encoding="utf-8")).get("rules", [])]
    except Exception:
        return []


def save_rules(rules: list[WatchRule]) -> None:
    p = store_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps({"rules": [asdict(r) for r in rules]}, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    tmp.replace(p)


def run_forever(rules: list[WatchRule], interval: float = 2.0,
                log: Callable[[str], None] = print) -> None:
    """Headless loop used by `dropdial watch` (Ctrl+C to stop)."""
    scanners = [FolderScanner(r) for r in rules if r.enabled]
    for s in scanners:
        log(f"Watching {s.rule.folder} → {s.rule.label} (results in {s.rule.out_dir()})")
    while True:
        for s in scanners:
            for f in s.poll():
                try:
                    outs = s.rule.process(f)
                    s.ignore(outs)
                    log(f"✓ {f.name} → {', '.join(o.name for o in outs)}")
                except UserError as e:
                    log(f"✗ {f.name}: {e}")
                except Exception as e:  # noqa: BLE001
                    log(f"✗ {f.name}: {e.__class__.__name__}: {e}")
        time.sleep(interval)
