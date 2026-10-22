# Adding a file format

DropDial's newer file families (spreadsheets, data, subtitles, archives, fonts, 3D models, map data,
pro images…) are plug-ins: one module in [`dropdial/formats/`](../dropdial/formats/) each. A module
says which extensions it reads, what each one can become, and how. The dial, the command line,
watch folders and `dropdial formats` pick it up with no other changes.

## 1. Write the module

Create `dropdial/formats/<name>.py` and add `<name>` to `MODULES` in
[`dropdial/formats/__init__.py`](../dropdial/formats/__init__.py). A complete, minimal example that
turns `.foo` files into plain text or upper-case text:

```python
"""Foo files (.foo): plain text with a 4-byte header."""
from __future__ import annotations

from pathlib import Path

from ..util import UserError, sibling
from . import Family, Tool, register

EXTS = {".foo"}


def _read(src: Path) -> str:
    data = src.read_bytes()
    if not data.startswith(b"FOO1"):
        raise UserError("This doesn't look like a Foo file.")
    return data[4:].decode("utf-8", errors="replace")


def targets(src_ext: str) -> list[str]:
    return ["TXT"]


def convert(src: Path, target: str) -> list[Path]:
    if target != "TXT":
        raise UserError(f"Foo files can't become {target}.")
    out = sibling(src, ext=".txt")          # next to the original, never overwrites
    out.write_text(_read(src), encoding="utf-8")
    return [out]


def shout(srcs: list[Path]) -> list[Path]:
    out = sibling(srcs[0], "Upper", ".txt")
    out.write_text(_read(srcs[0]).upper(), encoding="utf-8")
    return [out]


register(Family(
    category="foo", label="Foo", exts=EXTS, targets=targets, convert=convert,
    hints={"TXT": "Plain text"},
    tools=[Tool("Upper", "A", "Shout it", shout, working="Shouting…")],
))
```

What the fields mean:

| Field | |
|---|---|
| `category` | Short id used everywhere (`dropdial convert`, history, recipes). |
| `exts` | Lower-case extensions with the dot. The first family to claim an extension wins, so plug-ins can take over e.g. `.csv` from the plain-text family. |
| `targets(src_ext)` | Target names for one source extension, most useful first. The dial shows the first 8; the rest go on its **More formats** side. Leave out the source's own format. |
| `convert(src, target)` | Writes the result(s) and returns their paths. |
| `hints` | One short line under each slice (≤ 22 characters). |
| `tools` | Optional second ring. A tool takes files and writes files; it never opens a dialog. `multi=True` runs it once with every dropped file (e.g. "Combine"), otherwise once per file. |
| `combine` | Optional `{target: fn(all files)}` for targets that turn several files into one. |
| `available()` | Return `False` to hide the family when an optional library is missing. |

## 2. Rules

- **Import heavy libraries inside functions.** Every module is imported when DropDial starts.
- **Write outputs with `util.sibling(src, label, ext)`.** It follows Settings → Save results, and
  never overwrites anything.
- **Inputs are untrusted.** Never execute anything from a file. Parse XML with entity expansion off.
  Check archive member paths. Refuse absurd sizes.
- **Errors the user can fix** raise `util.UserError("One friendly sentence.")`. Anything else is a
  bug and shows a generic message.
- **Long jobs** call `util.report_progress(0..1)` so the toast shows a percentage.
- **New dependencies** must have wheels for Windows x64, macOS (arm64 + x86_64) and Linux x64, and a
  permissive licence. Add them to `requirements.txt`, to [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md),
  and if PyInstaller misses them, to `hiddenimports` in [`DropDial.spec`](../DropDial.spec).

## 3. Test it

Add `tests/test_fmt_<name>.py`. Build sample files inside the test (in `tmp_path`); don't commit
binary fixtures. Check the **content** of every output with an independent reader, not just that a
file appeared: parse it back, compare values, count pages or glyphs, compare pixels.

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_fmt_<name>.py
python -m dropdial convert sample.foo --to txt
python -m dropdial formats
```

Then drag a real file onto the dial on your own desktop and try every slice once.
