"""Plug-in file families.

Each module in this package handles one family of files (spreadsheets, archives, fonts…) and
registers itself with `register(Family(...))`. The rest of the app (the dial, the command line,
watch folders, `dropdial formats`) asks this registry what a file is and what it can become, so
adding a family never means touching app.py or convert.py. See docs/ADDING-A-CONVERTER.md.

Rules for a module:
* import heavy libraries *inside* functions: every module is imported when the app starts;
* write outputs with `util.sibling(src, ext=...)` (respects Settings and never overwrites);
* raise `util.UserError` with a short, friendly sentence for anything the user can fix;
* return the list of files written.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# modules loaded at start-up, in the order their extensions are claimed
MODULES = ("sheets", "data", "markup", "subtitles", "archives", "fonts", "models", "geo", "rawimages")


@dataclass
class Tool:
    name: str
    glyph: str
    hint: str
    run: Callable[[list[Path]], list[Path]]   # all dropped files of this family -> files written
    multi: bool = False                        # True: run once with every file, else once per file
    working: str = "Working…"


@dataclass
class Family:
    category: str                               # short id, e.g. "sheet"
    label: str                                  # "Spreadsheet"
    exts: set[str]                              # {".xlsx", ".csv"}, lower case with the dot
    targets: Callable[[str], list[str]]          # source extension ("csv") -> target names ("XLSX", …)
    convert: Callable[[Path, str], list[Path]]   # (source, target) -> files written
    hints: dict[str, str] = field(default_factory=dict)   # target/tool name -> one-line hint
    tools: list[Tool] = field(default_factory=list)
    available: Callable[[], bool] = lambda: True          # False hides the family (missing library)
    combine: dict[str, Callable[[list[Path]], list[Path]]] = field(default_factory=dict)
    # ^ targets that turn several files into one (e.g. "ZIP"): target -> fn(all files)


FAMILIES: dict[str, Family] = {}
_EXT: dict[str, Family] = {}
_loaded = False


def register(fam: Family) -> Family:
    FAMILIES[fam.category] = fam
    for e in fam.exts:
        _EXT.setdefault(e.lower(), fam)
    return fam


def load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for name in MODULES:
        try:
            importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError as e:
            if e.name and e.name.startswith(f"{__name__}."):
                continue           # module not written yet
            import traceback
            traceback.print_exc()
        except Exception:  # a broken module must never break the app
            import traceback
            traceback.print_exc()


def family_for(path: str | Path) -> Family | None:
    load()
    fam = _EXT.get(Path(path).suffix.lower())
    if fam is None:
        return None
    try:
        return fam if fam.available() else None
    except Exception:
        return None


def family(cat: str) -> Family | None:
    load()
    return FAMILIES.get(cat)


def all_families() -> list[Family]:
    load()
    out = []
    for f in FAMILIES.values():
        try:
            if f.available():
                out.append(f)
        except Exception:
            pass
    return out
