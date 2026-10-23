"""Shared helpers: output paths, file categories, sizes."""
from __future__ import annotations

import os
import threading
from pathlib import Path

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".tif", ".tiff",
              ".avif", ".bmp", ".gif", ".ico"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
TEXT_EXTS = {".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm"}
VECTOR_EXTS = {".svg"}
EBOOK_EXTS = {".epub", ".mobi", ".fb2", ".xps", ".oxps", ".cbz"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv", ".mpg", ".mpeg", ".3gp"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".aif"}

CATEGORIES = (("image", IMAGE_EXTS), ("pdf", PDF_EXTS), ("docx", DOCX_EXTS), ("text", TEXT_EXTS),
              ("vector", VECTOR_EXTS), ("ebook", EBOOK_EXTS), ("video", VIDEO_EXTS),
              ("audio", AUDIO_EXTS))


def category(path: str | Path) -> str | None:
    """'image', 'pdf', … or a plug-in family ('sheet', 'archive', …; see dropdial/formats)."""
    from . import formats       # plug-in families win: they handle e.g. .csv and .json better
    fam = formats.family_for(path)
    if fam is not None:
        return fam.category
    ext = Path(path).suffix.lower()
    for name, exts in CATEGORIES:
        if ext in exts:
            return name
    return None


def all_extensions() -> set[str]:
    from . import formats
    exts = set().union(*(exts for _, exts in CATEGORIES))
    for fam in formats.all_families():
        exts |= fam.exts
    return exts


def unique_path(path: str | Path) -> Path:
    """Return `path`, or `name (1).ext`, `name (2).ext`... if it already exists."""
    p = Path(path)
    if not p.exists():
        return p
    i = 1
    while True:
        cand = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not cand.exists():
            return cand
        i += 1


class UserError(Exception):
    """An error with a message that's fine to show the user as-is. Values go in as named fields
    so the sentence stays translatable (i18n.error_text):
    UserError("Recipe “{name}” has no steps.", name=r.name)."""

    def __init__(self, message: str = "", **fmt):
        self.template, self.fmt = message, fmt
        super().__init__(message.format(**fmt) if fmt else message)


class NotSmaller(UserError):
    """Compressing produced a file that isn't smaller than the original (it was removed)."""


# Runtime options (filled from Settings at start-up; plain values so worker threads can read them)
CONFIG = {
    "output": "next",        # "next" = beside the original, "folder" = a "DropDial" subfolder
    "jpg_quality": 90,
    "pdf_dpi": 200,
    "out_dir": None,         # explicit folder (command line --out, watch folders); wins over "output"
}


_LOCAL = threading.local()
BESIDE = "beside"   # output_override value: always next to the source, ignoring Settings


class output_override:
    """Per-thread output location: a folder, BESIDE, or None (use Settings).
    Thread-local so a watch folder or recipe running in the background can't
    redirect a conversion running at the same time."""

    def __init__(self, where):
        self.where = where

    def __enter__(self):
        self.prev = getattr(_LOCAL, "out", None)
        _LOCAL.out = self.where
        return self

    def __exit__(self, *exc):
        _LOCAL.out = self.prev


class progress_hook:
    """Per-thread progress callback (0..1) that long jobs (ffmpeg, recipes) report to."""

    def __init__(self, fn):
        self.fn = fn

    def __enter__(self):
        self.prev = getattr(_LOCAL, "progress", None)
        _LOCAL.progress = self.fn
        return self

    def __exit__(self, *exc):
        _LOCAL.progress = self.prev


def current_progress():
    return getattr(_LOCAL, "progress", None)


def report_progress(fraction: float) -> None:
    fn = getattr(_LOCAL, "progress", None)
    if fn is not None:
        try:
            fn(max(0.0, min(1.0, fraction)))
        except Exception:
            pass


def output_dir(src: str | Path) -> Path:
    local = getattr(_LOCAL, "out", None)
    if local == BESIDE:
        return Path(src).parent
    if local:
        d = Path(local)
        d.mkdir(parents=True, exist_ok=True)
        return d
    if CONFIG.get("out_dir"):
        d = Path(CONFIG["out_dir"])
        d.mkdir(parents=True, exist_ok=True)
        return d
    d = Path(src).parent
    if CONFIG.get("output") == "folder":
        d = d / "DropDial"
        d.mkdir(exist_ok=True)
    return d


def data_dir() -> Path:
    """Per-user folder for recipes, history and logs."""
    import sys
    override = os.environ.get("DROPDIAL_HOME")
    if override:
        d = Path(override)
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "DropDial"
    elif sys.platform == "win32":
        d = Path(os.environ.get("APPDATA") or Path.home()) / "DropDial"
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "DropDial"
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_size(text: str) -> int:
    """'500KB', '1.5 mb', '800k', '2000000' -> bytes."""
    t = text.strip().lower().replace(" ", "")
    mult = 1
    for suf, m in (("gb", 1024 ** 3), ("mb", 1024 ** 2), ("kb", 1024), ("g", 1024 ** 3),
                   ("m", 1024 ** 2), ("k", 1024), ("b", 1)):
        if t.endswith(suf):
            t, mult = t[: -len(suf)], m
            break
    try:
        n = float(t)
    except ValueError:
        raise UserError("Can't read the size {size}. Try something like 500KB or 2MB.", size=repr(text)) from None
    if n <= 0:
        raise UserError("The size must be bigger than zero.")
    return int(n * mult)


def sibling(src: str | Path, suffix_label: str = "", ext: str | None = None) -> Path:
    """Output path for `src`. sibling('a.jpg', 'Cropped') -> 'a Cropped.jpg' (never overwrites)."""
    s = output_dir(src) / Path(src).name
    stem = f"{s.stem} {suffix_label}".strip() if suffix_label else s.stem
    new_ext = ext if ext is not None else s.suffix
    if not new_ext.startswith("."):
        new_ext = "." + new_ext
    return unique_path(s.with_name(stem + new_ext))


def human_size(n: int | float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def file_size(path: str | Path) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# ---------------------------------------------------------------- background job lifetime
# QThreadPool runs a QRunnable in C++, but the Python object (and the QObject carrying its
# signals) can be garbage-collected while it's still running: results then never arrive,
# or the app crashes. Keep every job alive until its result has been handled.
ALIVE: set = set()


def keep(job):
    job.setAutoDelete(False)
    ALIVE.add(job)
    return job


def release(job):
    ALIVE.discard(job)
