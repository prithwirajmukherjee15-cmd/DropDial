"""Turns 'what just happened' into a short, useful summary for the notification:
sizes saved, new dimensions, pages, fields removed…"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .i18n import tr, trn
from .util import category, file_size, human_size


@dataclass
class Result:
    title: str
    detail: str
    outs: list[Path]
    srcs: list[Path] = field(default_factory=list)
    good: str = ""     # highlighted figure, e.g. "−75%"

    @property
    def thumb(self) -> Path | None:
        for o in self.outs:
            if category(o) == "image":
                return o
        return None


def dims(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def pages(path: Path) -> int | None:
    try:
        from .convert import fitz
        with fitz.open(path) as d:
            return d.page_count
    except Exception:
        return None


def size_change(before: int, after: int) -> tuple[str, str]:
    """('2.4 MB → 610 KB', '75% smaller') — second part empty if no meaningful change."""
    text = f"{human_size(before)} → {human_size(after)}"
    if before <= 0:
        return text, ""
    pct = (1 - after / before) * 100
    if pct >= 1:
        return text, tr("{pct}% smaller", pct=f"{pct:.0f}")
    if pct <= -1:
        return text, tr("{pct}% larger", pct=f"{-pct:.0f}")
    return text, tr("same size")


def _smaller(before: int, after: int) -> bool:
    """At least 1% smaller (what size_change calls "N% smaller")."""
    return before > 0 and (1 - after / before) * 100 >= 1


def media_str(path: Path) -> str:
    """'0:42 · 1280×720' for video/audio outputs (empty if ffmpeg can't read it)."""
    if category(path) not in ("video", "audio"):
        return ""
    try:
        from .media import describe
        return describe(path)
    except Exception:
        return ""


def _dim_str(d) -> str:
    return f"{d[0]}×{d[1]}" if d else ""


def summarize(action: str, srcs: list, outs: list, extra: str = "") -> Result:
    srcs = [Path(s) for s in srcs]
    outs = [Path(o) for o in outs if o]
    if not outs:
        return Result(action, extra or tr("Nothing was written"), [], srcs)
    src = srcs[0] if srcs else outs[0]
    before = sum(file_size(s) for s in srcs if s.is_file())
    after = sum(file_size(o) if o.is_file() else sum(file_size(f) for f in o.rglob("*") if f.is_file())
                for o in outs if o.exists())
    kind, _, name = action.partition(":")
    o0 = outs[0]
    good = ""

    if kind == "convert":
        fmt = name
        if len(srcs) > 1 and len(outs) == 1:
            title = tr("{n} files → 1 {fmt}", n=len(srcs), fmt=fmt)
        elif len(outs) > 1 and len(srcs) == 1:
            n = pages(src)
            title = tr("{n} pages → {m} {fmt}s", n=n or len(outs), m=len(outs), fmt=fmt)
        elif len(outs) > 1:
            title = tr("{n} files → {fmt}", n=len(outs), fmt=fmt)
        else:
            title = f"{src.suffix.lstrip('.').upper()} → {fmt}"
        bits = [o0.name if len(outs) == 1 else f"{o0.parent.name}/{o0.name} …"]
        d = dims(o0) if category(o0) == "image" else None
        if d:
            bits.append(_dim_str(d))
        m = media_str(o0)
        if m:
            bits.append(m)
        if o0.suffix.lower() == ".pdf":
            n = pages(o0)
            if n:
                bits.append(trn("{n} page", "{n} pages", n))
        bits.append(human_size(after))
        return Result(title, " · ".join(bits), outs, srcs)

    if name == "Compress":
        sizes, verdict = size_change(before, after)
        title = tr("Compressed {n} files", n=len(srcs)) if len(srcs) > 1 else tr("Compressed")
        if before > 0 and not _smaller(before, after):
            verdict = tr("already well compressed")
        return Result(title, sizes + (f" · {extra}" if extra else ""), outs, srcs, good=verdict)

    if name in ("Crop", "Resize", "Edit"):
        d0, d1 = dims(src), dims(o0)
        verb = {"Crop": tr("Cropped"), "Resize": tr("Resized"), "Edit": tr("Edited")}[name]
        if len(outs) > 1:
            many = {"Crop": tr("Cropped {n} images", n=len(outs)), "Resize": tr("Resized {n} images", n=len(outs)),
                    "Edit": tr("Edited {n} images", n=len(outs))}[name]
            return Result(many, f"{human_size(before)} → {human_size(after)}", outs, srcs)
        detail = f"{_dim_str(d0)} → {_dim_str(d1)}" if d0 and d1 and d0 != d1 else _dim_str(d1)
        if extra:
            detail += f" · {extra}"
        return Result(verb, f"{detail} · {o0.name}", outs, srcs)

    if name == "Add BG":
        return Result(tr("Background added"), f"{_dim_str(dims(o0))} PNG · {human_size(after)} · {o0.name}", outs, srcs)

    if name == "Annotate":
        return Result(tr("Annotated"), f"{extra} · {o0.name}" if extra else o0.name, outs, srcs)

    if name == "Redact":
        return Result(tr("Redacted"), f"{extra} · {o0.name}" if extra else o0.name, outs, srcs,
                      good=tr("burned into pixels"))

    if name == "Metadata":
        return Result(tr("Metadata removed"), f"{extra} · {o0.name}" if extra else o0.name, outs, srcs,
                      good=tr("private copy"))

    if name == "Split":
        return Result(tr("Split into {n} PDFs", n=len(outs)), f"{o0.name} …", outs, srcs)

    if name == "Merge":
        n = pages(o0)
        return Result(tr("Merged {n} PDFs", n=len(srcs)),
                      f"{trn('{n} page', '{n} pages', n or 0)} · {human_size(after)} · {o0.name}", outs, srcs)

    if kind == "recipe":
        sizes, verdict = size_change(before, after)
        n = len(outs)
        from .recipes import display_name
        shown = display_name(name)
        title = shown if n == 1 else f"{shown} · {trn('{n} file', '{n} files', n)}"
        detail = (f"{extra} · " if extra else "") + (o0.name if n == 1 else sizes)
        return Result(title, detail, outs, srcs, good=verdict if _smaller(before, after) else "")

    if name == "Audio":
        return Result(tr("Audio extracted"), " · ".join(b for b in (media_str(o0), human_size(after), o0.name) if b),
                      outs, srcs)

    if name == "Mute":
        return Result(tr("Sound removed"), f"{o0.name} · {human_size(after)}", outs, srcs, good=tr("silent copy"))

    if name == "Frame":
        return Result(tr("Frame saved"), f"{_dim_str(dims(o0))} · {o0.name}", outs, srcs)

    if name in ("Normalize", "Trim silence"):
        title = tr("Loudness normalized") if name == "Normalize" else tr("Silence trimmed")
        return Result(title, " · ".join(b for b in (media_str(o0), o0.name) if b), outs, srcs,
                      good="-16 LUFS" if name == "Normalize" else "")

    if name == "Numbers":
        n = pages(o0)
        return Result(tr("Page numbers added"), f"{trn('{n} page', '{n} pages', n or 0)} · {o0.name}", outs, srcs)

    if name == "Watermark":
        return Result(tr("Watermarked"), f"{extra} · {o0.name}" if extra else o0.name, outs, srcs)

    if name == "Unlock":
        return Result(tr("Password removed"), o0.name, outs, srcs, good=tr("unlocked"))

    if name == "Rotate" and category(o0) == "video":
        return Result(tr("Rotated 90°"), " · ".join(b for b in (media_str(o0), o0.name) if b), outs, srcs)

    if name == "Rotate":
        n = pages(o0)
        return Result(tr("Rotated 90°"), f"{trn('{n} page', '{n} pages', n or 0)} · {o0.name}", outs, srcs)

    if name == "Protect":
        return Result(tr("Password protected"), f"AES-256 · {o0.name}", outs, srcs, good=tr("encrypted"))

    if name == "Extract":
        return Result(trn("Extracted {n} image", "Extracted {n} images", len(outs)),
                      f"{o0.parent.name}/ · {human_size(after)}", outs, srcs)

    # generic
    return Result(tr(name) if name else action, f"{o0.name} · {human_size(after)}", outs, srcs)
