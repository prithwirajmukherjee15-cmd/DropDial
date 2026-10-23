"""Recipes: several steps in a row, applied with one drop.

    "Web-ready"  = resize to 2048 px (only if bigger) → remove metadata → WebP

A step that doesn't apply to a file is skipped for that file, so one recipe can handle
photos, PDFs and videos alike ("Email size" shrinks all three). Steps work on temporary
copies; only the final result is written next to the original, named
"<name> <Recipe>.<ext>". The original is never touched.

Recipes are plain JSON, so they can be shared and run from the command line:

    {"name": "Thumbs", "glyph": "▦", "steps": [{"step": "resize", "mode": "long", "value": 400},
                                               {"step": "convert", "to": "JPG", "quality": 80}]}
No Qt in here."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .i18n import N_, tr
from .imaging import BG_PRESETS
from .util import (BESIDE, UserError, category, data_dir, output_dir, output_override, parse_size,
                   current_progress, progress_hook, unique_path)

ALL_CATS = ("image", "pdf", "docx", "text", "vector", "ebook", "video", "audio")


# ---------------------------------------------------------------- step catalogue
@dataclass
class Param:
    name: str
    kind: str                 # int | choice | text | bool | size
    default: object
    label: str = ""
    choices: tuple = ()
    lo: int = 0
    hi: int = 100


@dataclass
class StepType:
    key: str
    label: str
    cats: tuple[str, ...]
    params: list[Param]
    fn: Callable                                   # (path, params) -> list[Path]   or (paths, params) if multi
    multi: bool = False
    out_cat: Callable[[str, dict], str] | None = None
    summary: Callable[[dict], str] | None = None
    accepts: Callable[[str, dict], bool] | None = None   # finer check than `cats`

    def applies(self, cat: str | None, params: dict) -> bool:
        if cat not in self.cats:
            return False
        return self.accepts(cat, {**self.defaults(), **params}) if self.accepts else True

    def defaults(self) -> dict:
        return {p.name: p.default for p in self.params}

    def describe(self, params: dict) -> str:
        merged = {**self.defaults(), **params}
        return self.summary(merged) if self.summary else tr(self.label)


def _same(path: Path) -> list[Path]:
    return [path]


def _ext_of(path: Path) -> str:
    from .imaging import target_for
    return target_for(path)


def _convert(path: Path, p: dict) -> list[Path]:
    from . import convert
    cat = category(path)
    to = str(p["to"]).upper()
    cur = path.suffix.lower().lstrip(".").upper()
    if {"JPEG": "JPG", "TIF": "TIFF", "HEIF": "HEIC"}.get(cur, cur) == to:
        return _same(path)
    if cat == "image" and int(p.get("quality") or 0) > 0 and to in ("JPG", "WEBP", "AVIF", "HEIC"):
        from .convert import open_image, save_image
        from .util import sibling
        out = sibling(path, ext="." + to.lower())
        save_image(open_image(path), out, to, quality=int(p["quality"]))
        return [out]
    if to not in _targets(cat):
        return _same(path)
    return convert.convert(path, cat, to)


def _targets(cat: str | None) -> set[str]:
    from . import convert
    if cat is None:
        return set()
    if cat == "image":
        return set(convert.IMAGE_TARGETS) | {"JPG", "PNG"}
    if cat in ("video", "audio"):
        from . import media
        return set(media.VIDEO_TARGETS if cat == "video" else media.AUDIO_TARGETS)
    return set(convert.targets_for(cat, ".x"))


def _convert_out(cat: str, p: dict) -> str:
    to = str(p["to"]).upper()
    if to not in _targets(cat):
        return cat
    return category("x." + {"JPG": "jpg", "TIFF": "tif"}.get(to, to.lower())) or cat


def _resize(path: Path, p: dict) -> list[Path]:
    from . import imaging
    from PIL import Image
    with Image.open(path) as im:
        size = im.size
        if im.getexif().get(0x0112, 1) in (5, 6, 7, 8):
            size = (size[1], size[0])
    mode, value = p["mode"], int(p["value"])
    dims = imaging.resize_dims(size, mode, value)
    if p.get("only_shrink", True) and (dims[0] >= size[0] or dims[1] >= size[1]):
        return _same(path)
    return [imaging.resize_image(path, dims)]


def _compress(path: Path, p: dict) -> list[Path]:
    from . import imaging
    try:
        return _compress_inner(path, p)
    except imaging.NotSmaller:
        return _same(path)          # already as small as this step can make it


def _compress_inner(path: Path, p: dict) -> list[Path]:
    from . import imaging
    cat = category(path)
    q = int(p.get("quality", 75))
    if cat == "image":
        target = imaging.lossy_target(path)
        limit = str(p.get("target") or "").strip()
        if limit:
            from .convert import open_image
            max_bytes = parse_size(limit)
            if path.stat().st_size <= max_bytes:
                return _same(path)
            q, side = imaging.plan_target_size(open_image(path), target, max_bytes)
            return [imaging.compress_to(path, q, side, target)]
        return [imaging.compress_to(path, q, None, target)]
    if cat == "pdf":
        return [imaging.compress_pdf(path, quality=q)]
    from . import media
    if cat == "video":
        crf = round(38 - q * 0.2)            # quality 100 → CRF 18, 50 → 28, 0 → 38
        mh = int(p.get("max_height") or 0) or None
        return [media.compress_video(path, crf=crf, max_height=mh)]
    if cat == "audio":
        return [media.compress_audio(path, kbps=max(48, min(256, q * 2)))]
    return _same(path)


def _strip(path: Path, p: dict) -> list[Path]:
    from . import imaging
    if category(path) == "pdf":
        return [imaging.strip_pdf_metadata(path)]
    if p.get("location_only"):
        return [imaging.strip_location(path)]
    return [imaging.strip_image_metadata(path)]


def _watermark(path: Path, p: dict) -> list[Path]:
    from . import imaging
    text = str(p.get("text") or "").strip()
    if not text:
        return _same(path)
    opacity = int(p.get("opacity", 50)) / 100
    if category(path) == "pdf":
        return [imaging.watermark_pdf(path, text, opacity=min(opacity, 0.6))]
    return [imaging.watermark_image_file(path, text, position=p.get("position", "bottom-right"),
                                         opacity=opacity)]


def _add_bg(path: Path, p: dict) -> list[Path]:
    from . import imaging
    from .convert import open_image
    colors = dict(imaging.BG_PRESETS).get(p.get("preset"), imaging.BG_PRESETS[0][1])
    bg = imaging.Background(colors=colors, aspect=p.get("aspect", "Auto"),
                            padding=int(p.get("padding", 12)) / 100)
    im = open_image(path)
    bg.radius = int(max(im.size) * 0.02)
    return [imaging.save_like(imaging.add_background(im, bg), path, "BG", ".png")]


def _adjust(path: Path, a) -> list[Path]:
    from . import imaging
    from .convert import open_image
    return [imaging.save_like(imaging.apply_adjust(open_image(path), a), path, "Edited")]


def _enhance(path: Path, p: dict) -> list[Path]:
    from . import imaging
    from .convert import open_image
    im = open_image(path)
    return [imaging.save_like(imaging.apply_adjust(im, imaging.auto_enhance(im)), path, "Edited")]


def _grayscale(path: Path, p: dict) -> list[Path]:
    from . import imaging
    return _adjust(path, imaging.Adjust(grayscale=True))


def _rotate(path: Path, p: dict) -> list[Path]:
    from . import imaging
    deg = int(p.get("degrees", 90)) % 360
    if not deg:
        return _same(path)
    cat = category(path)
    if cat == "pdf":
        return [imaging.rotate_pdf(path, deg)]
    if cat == "video":
        from . import media
        return [media.rotate_video(path, deg)]
    return _adjust(path, imaging.Adjust(rotate=deg))


def _numbers(path: Path, p: dict) -> list[Path]:
    from . import imaging
    return [imaging.pdf_page_numbers(path, p.get("style", "1 / N"), p.get("position", "bottom-center"))]


def _combine(paths: list[Path], p: dict) -> list[Path]:
    from . import convert, imaging
    imgs = [x for x in paths if category(x) == "image"]
    pdfs = [x for x in paths if category(x) == "pdf"]
    rest = [x for x in paths if category(x) not in ("image", "pdf")]
    out: list[Path] = []
    if imgs:
        out += convert.images_to_single_pdf(imgs)
    if len(pdfs) > 1:
        out.append(imaging.merge_pdfs(pdfs))
    else:
        out += pdfs
    return out + rest


def _extract_audio(path: Path, p: dict) -> list[Path]:
    from . import media
    return [media.extract_audio(path)]


def _normalize(path: Path, p: dict) -> list[Path]:
    from . import media
    return [media.normalize_audio(path)]


def _trim(path: Path, p: dict) -> list[Path]:
    from . import media
    return [media.trim_silence(path)]


def _frame(path: Path, p: dict) -> list[Path]:
    from . import media
    return [media.video_frame(path)]


_CONVERT_TO = ("JPG", "PNG", "WEBP", "AVIF", "HEIC", "TIFF", "GIF", "PDF", "DOCX", "TXT",
               "MP4", "WEBM", "MOV", "MP3", "M4A", "WAV", "FLAC", "OGG")
_POS = ("bottom-right", "bottom-left", "top-right", "top-left", "center", "tile")
RESIZE_BY = {"long": N_("resize long {value} px"), "w": N_("resize w {value} px"),
             "h": N_("resize h {value} px")}       # long = longest side, w = width, h = height

STEPS: dict[str, StepType] = {s.key: s for s in [
    StepType("convert", N_("Convert"), ALL_CATS,
             [Param("to", "choice", "WEBP", N_("Format"), _CONVERT_TO),
              Param("quality", "int", 0, N_("Quality (0 = Settings)"), lo=0, hi=100)],
             _convert, out_cat=_convert_out, summary=lambda p: tr("save as {fmt}", fmt=p["to"]),
             accepts=lambda c, p: str(p["to"]).upper() in _targets(c)),
    StepType("resize", N_("Resize"), ("image",),
             [Param("mode", "choice", "long", N_("By"), ("long", "pct", "w", "h")),
              Param("value", "int", 2048, N_("Value"), lo=1, hi=20000),
              Param("only_shrink", "bool", True, N_("Never enlarge"))],
             _resize, summary=lambda p: (tr("resize {pct}%", pct=p["value"]) if p["mode"] == "pct" else
                                         tr(RESIZE_BY[p["mode"]], value=p["value"]) if p["mode"] in RESIZE_BY
                                         else f"resize {p['mode']} {p['value']} px")),
    StepType("compress", N_("Compress"), ("image", "pdf", "video", "audio"),
             [Param("quality", "int", 75, N_("Quality"), lo=1, hi=100),
              Param("target", "size", "", N_("Images: under (e.g. 500KB)")),
              Param("max_height", "int", 1080, N_("Videos: max height"), lo=0, hi=4320)],
             _compress, summary=lambda p: (tr("compress (photos under {size})", size=p["target"]) if p["target"]
                                   else tr("compress"))),
    StepType("strip_metadata", N_("Remove metadata"), ("image", "pdf"),
             [Param("location_only", "bool", False, N_("Only remove location"))],
             _strip, summary=lambda p: tr("remove location") if p["location_only"] else tr("remove metadata")),
    StepType("watermark", N_("Watermark"), ("image", "pdf"),
             [Param("text", "text", "© Your Name", N_("Text")),
              Param("position", "choice", "bottom-right", N_("Position"), _POS),
              Param("opacity", "int", 55, N_("Opacity %"), lo=5, hi=100)],
             _watermark, summary=lambda p: tr("watermark “{text}”", text=p["text"])),
    StepType("add_bg", N_("Add background"), ("image",),
             [Param("preset", "choice", "Sunset", N_("Gradient"), tuple(n for n, _ in BG_PRESETS)),
              Param("aspect", "choice", "Auto", N_("Aspect"), ("Auto", "1:1", "4:3", "16:9", "9:16", "4:5")),
              Param("padding", "int", 12, N_("Padding %"), lo=0, hi=40)],
             _add_bg, summary=lambda p: tr("{preset} background {aspect}", preset=tr(p["preset"]).lower(),
                                                 aspect=tr(p["aspect"]))),
    StepType("auto_enhance", N_("Auto enhance"), ("image",), [], _enhance),
    StepType("grayscale", N_("Black & white"), ("image",), [], _grayscale),
    StepType("rotate", N_("Rotate"), ("image", "pdf", "video"),
             [Param("degrees", "choice", "90", N_("Degrees"), ("90", "180", "270"))],
             _rotate, summary=lambda p: tr("rotate {deg}°", deg=p["degrees"])),
    StepType("page_numbers", N_("Page numbers"), ("pdf",),
             [Param("style", "choice", "1 / N", N_("Style"), ("1", "1 / N", "Page 1", "Page 1 of N")),
              Param("position", "choice", "bottom-center", N_("Position"),
                    ("bottom-center", "bottom-right", "bottom-left", "top-center", "top-right", "top-left"))],
             _numbers, summary=lambda p: tr("page numbers")),
    StepType("combine", N_("Combine into one PDF"), ("image", "pdf"), [], _combine, multi=True,
             out_cat=lambda c, p: "pdf", summary=lambda p: tr("combine into one PDF")),
    StepType("extract_audio", N_("Extract audio"), ("video",), [], _extract_audio,
             out_cat=lambda c, p: "audio"),
    StepType("normalize", N_("Normalize loudness"), ("audio",), [], _normalize),
    StepType("trim_silence", N_("Trim silence"), ("audio",), [], _trim),
    StepType("frame", N_("Grab a frame"), ("video",), [], _frame, out_cat=lambda c, p: "image"),
]}


# ---------------------------------------------------------------- recipes
def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@dataclass
class Recipe:
    name: str
    steps: list[dict]
    glyph: str = "★"
    builtin: bool = False
    description: str = ""
    inputs: list[str] = field(default_factory=list)   # optional: only offer for these categories

    def validate(self) -> None:
        if not self.name.strip():
            raise UserError("Give the recipe a name.")
        if not self.steps:
            raise UserError("Recipe “{name}” has no steps.", name=self.name)
        for s in self.steps:
            if s.get("step") not in STEPS:
                raise UserError("Recipe “{name}”: unknown step {step}. Known steps: {known}.",
                                name=self.name, step=repr(s.get("step")), known=", ".join(STEPS))

    def flow(self, cat: str) -> tuple[list[str], str]:
        """(labels of the steps that would run for a file of `cat`, final category)."""
        ran = []
        for s in self.steps:
            st = STEPS.get(s.get("step"))
            params = {k: v for k, v in s.items() if k != "step"}
            if st is None or not st.applies(cat, params):
                continue
            params = {**st.defaults(), **params}
            ran.append(st.describe(params))
            if st.out_cat:
                cat = st.out_cat(cat, params)
        return ran, cat

    def applies_to(self, cat: str | None) -> bool:
        if not cat or (self.inputs and cat not in self.inputs):
            return False
        return bool(self.flow(cat)[0])

    def summary(self, cat: str | None = None) -> str:
        if cat:
            return " → ".join(self.flow(cat)[0])
        return " → ".join(STEPS[s["step"]].describe({k: v for k, v in s.items() if k != "step"})
                          for s in self.steps if s.get("step") in STEPS)

    def to_json(self) -> dict:
        d = {"name": self.name, "glyph": self.glyph, "steps": self.steps}
        if self.description:
            d["description"] = self.description
        if self.inputs:
            d["inputs"] = self.inputs
        return d

    @classmethod
    def from_json(cls, d: dict) -> "Recipe":
        if not isinstance(d, dict) or "name" not in d:
            raise UserError("A recipe needs at least a name and steps.")
        r = cls(name=str(d["name"]), steps=list(d.get("steps") or []), glyph=str(d.get("glyph") or "★"),
                description=str(d.get("description") or ""),
                inputs=[c for c in (d.get("inputs") or []) if c in ALL_CATS])
        r.validate()
        return r


BUILTIN: list[Recipe] = [
    Recipe(N_("Web-ready"), [{"step": "resize", "mode": "long", "value": 2048, "only_shrink": True},
                         {"step": "strip_metadata"},
                         {"step": "convert", "to": "WEBP", "quality": 82}],
           "⚡", True, N_("Resize to 2048 px, remove metadata, save as WebP"), ["image"]),
    Recipe(N_("Email size"), [{"step": "resize", "mode": "long", "value": 1600, "only_shrink": True},
                          {"step": "compress", "quality": 60, "target": "900KB", "max_height": 720}],
           "✉", True, N_("Small enough to attach: photos under 900 KB, PDFs and videos squeezed"),
           ["image", "pdf", "video"]),
    Recipe(N_("Private"), [{"step": "strip_metadata"}],
           "⛨", True, N_("Remove camera, GPS location and author details")),
    Recipe(N_("Social"), [{"step": "add_bg", "preset": "Sunset", "aspect": "4:5", "padding": 10},
                      {"step": "resize", "mode": "long", "value": 1350, "only_shrink": True},
                      {"step": "convert", "to": "JPG", "quality": 90}],
           "♥", True, N_("Gradient backdrop at 4:5, sized for Instagram"), ["image"]),
    Recipe(N_("Scan → PDF"), [{"step": "auto_enhance"}, {"step": "combine"},
                          {"step": "compress", "quality": 70}],
           "⎙", True, N_("Enhance photos of pages and combine them into one compact PDF"), ["image"]),
    Recipe(N_("Confidential"), [{"step": "watermark", "text": "CONFIDENTIAL", "position": "tile", "opacity": 30},
                            {"step": "page_numbers", "style": "Page 1 of N"}],
           "⚠", True, N_("Stamp CONFIDENTIAL across every page or image")),
    Recipe(N_("Share video"), [{"step": "compress", "quality": 50, "max_height": 720}],
           "▶", True, N_("720p H.264 MP4: small, plays everywhere"), ["video"]),
    Recipe(N_("Podcast"), [{"step": "convert", "to": "MP3"}, {"step": "trim_silence"}, {"step": "normalize"}],
           "♫", True, N_("MP3, silence trimmed, loudness at -16 LUFS"), ["video", "audio"]),
]


_BUILTIN_NAMES = {r.name for r in BUILTIN}


def display_name(r: "Recipe | str") -> str:
    """A recipe's name as shown: built-in names are translated, the user's own are kept."""
    name = r if isinstance(r, str) else r.name
    return tr(name) if name in _BUILTIN_NAMES else name


def builtin_name(shown: str) -> str:
    """Inverse of display_name for built-ins (so editing "Web-ready" in another language keeps it)."""
    return next((n for n in _BUILTIN_NAMES if tr(n) == shown), shown)


def display_description(r: "Recipe") -> str:
    return tr(r.description) if r.name in _BUILTIN_NAMES and r.description else r.description


# ---------------------------------------------------------------- storage
def store_path() -> Path:
    return data_dir() / "recipes.json"


def _load_store() -> dict:
    p = store_path()
    if not p.exists():
        return {"recipes": [], "hidden": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return {"recipes": list(data.get("recipes") or []), "hidden": list(data.get("hidden") or [])}
    except Exception:
        return {"recipes": [], "hidden": []}


def _save_store(data: dict) -> None:
    p = store_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def custom_recipes() -> list[Recipe]:
    out = []
    for d in _load_store()["recipes"]:
        try:
            out.append(Recipe.from_json(d))
        except UserError:
            continue
    return out


def all_recipes() -> list[Recipe]:
    custom = custom_recipes()
    names = {slug(r.name) for r in custom}
    return custom + [r for r in BUILTIN if slug(r.name) not in names]   # a custom one can replace a built-in


def hidden() -> set[str]:
    return set(_load_store()["hidden"])


def set_hidden(name: str, hide: bool) -> None:
    data = _load_store()
    h = set(data["hidden"])
    (h.add if hide else h.discard)(name)
    data["hidden"] = sorted(h)
    _save_store(data)


def save_recipe(r: Recipe, replace: str | None = None) -> None:
    r.validate()
    data = _load_store()
    drop = {slug(r.name)} | ({slug(replace)} if replace else set())
    data["recipes"] = [d for d in data["recipes"] if slug(str(d.get("name", ""))) not in drop]
    data["recipes"].append(r.to_json())
    _save_store(data)


def delete_recipe(name: str) -> None:
    data = _load_store()
    data["recipes"] = [d for d in data["recipes"] if slug(str(d.get("name", ""))) != slug(name)]
    _save_store(data)


def find(name: str) -> Recipe:
    """By name or slug ('web-ready'), or a path to a .json recipe file."""
    p = Path(name)
    if p.suffix.lower() == ".json" and p.is_file():
        return Recipe.from_json(json.loads(p.read_text(encoding="utf-8")))
    for r in all_recipes():
        if slug(r.name) == slug(name):
            return r
    raise UserError("No recipe called “{name}”. Try: {names}.", name=name,
                    names=", ".join(r.name for r in all_recipes()))


def menu_recipes(cat: str | None, limit: int = 8) -> list[Recipe]:
    """Recipes for the radial menu: those that apply to `cat` and aren't hidden."""
    hid = hidden()
    return [r for r in all_recipes() if r.name not in hid and r.applies_to(cat)][:limit]


# ---------------------------------------------------------------- running
@dataclass
class _Work:
    path: Path
    origin: Path          # the user's file this came from (decides where the result goes)
    stem: str             # name the result keeps
    changed: bool = False # False while no step has produced a new file from it


@dataclass
class RunResult:
    outputs: list[Path] = field(default_factory=list)
    steps_run: list[str] = field(default_factory=list)


def _apply(st: StepType, params: dict, todo: list, fresh) -> list:
    """Run one step over the files it applies to; returns the new work items."""
    if st.multi:
        outs = st.fn([w.path for w in todo], params)
        first = todo[0]
        new = []
        for o in outs:
            match = next((w for w in todo if w.path == o), None)
            stem = first.stem if len(outs) == 1 else o.stem
            new.append(match or _Work(fresh(o, stem), first.origin, stem, True))
    else:
        new = []
        for w in todo:
            outs = st.fn(w.path, params)
            if outs == [w.path]:
                new.append(w)
                continue
            for o in outs:
                stem = w.stem if len(outs) == 1 else o.stem
                new.append(_Work(fresh(o, stem), w.origin, stem, True))
    return new


def run(recipe: Recipe, srcs: list, progress: Callable[[int, int, str], None] | None = None) -> RunResult:
    """Apply `recipe` to `srcs`; return the files written (next to the originals)."""
    recipe.validate()
    srcs = [Path(s) for s in srcs]
    for s in srcs:
        if not s.is_file():
            raise UserError("{name} was moved or deleted.", name=s.name)
    if not any(recipe.applies_to(category(s)) for s in srcs):
        raise UserError("“{name}” doesn't apply to {ext} files.", name=recipe.name, ext=srcs[0].suffix) \
            if srcs[0].suffix else UserError("“{name}” doesn't apply to this file.", name=recipe.name)
    root = Path(tempfile.mkdtemp(prefix="dropdial-recipe-"))
    counter = [0]

    def fresh(path: Path, stem: str) -> Path:
        """Move `path` into its own folder as '<stem><ext>' so names never pile up labels."""
        counter[0] += 1
        d = root / str(counter[0])
        d.mkdir()
        dst = d / f"{stem}{path.suffix.lower()}"
        if path.parent.is_relative_to(root):
            shutil.move(str(path), dst)
        else:
            shutil.copy2(path, dst)
        return dst

    ran: list[str] = []
    try:
        items = [_Work(fresh(s, s.stem), s, s.stem) for s in srcs]
        outer = current_progress()

        def overall(f: float) -> None:
            if outer is not None:
                outer(max(0.0, min(1.0, f)))

        with output_override(BESIDE):
            for i, step in enumerate(recipe.steps):
                st = STEPS[step["step"]]
                params = {**st.defaults(), **{k: v for k, v in step.items() if k != "step"}}
                todo = [w for w in items if st.applies(category(w.path), params)]
                if not todo:
                    continue
                if progress:
                    progress(i, len(recipe.steps), st.describe(params))
                n_steps = len(recipe.steps)
                overall(i / n_steps)
                ran.append(st.describe(params))
                keep = [w for w in items if w not in todo]
                # a step's own progress (e.g. ffmpeg) becomes a slice of the whole recipe
                step_hook = progress_hook(lambda f, i=i: overall((i + f) / n_steps))
                with step_hook:
                    new = _apply(st, params, todo, fresh)
                items = keep + new
        if progress:
            progress(len(recipe.steps), len(recipe.steps), "Saving")
        done = [w for w in items if w.changed]
        if not done:
            raise UserError("Nothing to change: already fits “{name}”.", name=recipe.name)
        label = re.sub(r'[\\/:*?"<>|]', "-", recipe.name.replace("→", "to"))
        results = []
        for w in done:
            dest = unique_path(output_dir(w.origin) / f"{w.stem} {label}{w.path.suffix.lower()}")
            shutil.move(str(w.path), dest)
            results.append(dest)
        return RunResult(results, ran)
    finally:
        shutil.rmtree(root, ignore_errors=True)
