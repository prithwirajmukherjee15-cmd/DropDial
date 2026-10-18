"""Command line: everything the menu does, scriptable. Qt is never imported here.

    dragshift convert *.heic --to jpg
    dragshift compress photo.jpg --target 500KB
    dragshift recipe run web-ready ~/Pictures/*.png --out ~/Desktop/web
    dragshift watch ~/Screenshots --recipe web-ready
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .util import CONFIG, UserError, category, human_size

COMMANDS = {"convert", "compress", "resize", "strip", "watermark", "pdf", "media", "recipe",
            "info", "formats", "watch"}


def is_cli(argv: list[str]) -> bool:
    """True if argv asks for a command (`dragshift --out x convert …`), not the menu app."""
    args = iter(argv[1:])
    for tok in args:
        if tok in ("-h", "--help", "--version", "help") or tok in COMMANDS:
            return True
        if tok == "--out":
            next(args, None)
        elif not tok.startswith("-"):
            return False          # a file path: open it in the menu
    return False


def _attach_windows_console() -> None:
    """The Windows build is a GUI app: borrow the parent console so output is visible."""
    if sys.platform != "win32" or (sys.stdout is not None and sys.stdout.isatty()):
        return
    try:
        import ctypes
        if ctypes.windll.kernel32.AttachConsole(-1):
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
    except Exception:
        pass


# ---------------------------------------------------------------- output
class Out:
    def __init__(self, as_json: bool, quiet: bool):
        self.as_json, self.quiet = as_json, quiet
        self.records: list[dict] = []
        self.failed = 0

    def ok(self, action: str, srcs: list, outs: list, extra: str = "") -> None:
        from . import history, report
        r = report.summarize(action, srcs, outs, extra)
        try:
            history.add(r, action, source="cli")
        except OSError:
            pass
        self.records.append({"ok": True, "action": action, "sources": [str(s) for s in srcs],
                             "outputs": [str(o) for o in r.outs], "title": r.title, "detail": r.detail,
                             "note": r.good})
        if not self.as_json and not self.quiet:
            note = f"  ({r.good})" if r.good else ""
            print(f"✓ {r.title}{note} · {r.detail}")
            for o in r.outs:
                print(f"    {o}")

    def fail(self, src, msg: str) -> None:
        self.failed += 1
        self.records.append({"ok": False, "sources": [str(src)], "error": msg})
        if not self.as_json:
            print(f"✗ {Path(str(src)).name}: {msg}", file=sys.stderr)

    def finish(self) -> int:
        if self.as_json:
            print(json.dumps(self.records, indent=2, ensure_ascii=False))
        return 1 if self.failed else 0


def _each(out: Out, files: list[str], action: str, fn) -> None:
    """Run fn(path) -> list[Path] per file, reporting each result or error."""
    for f in files:
        p = Path(f)
        if not p.is_file():
            out.fail(f, "file not found")
            continue
        try:
            out.ok(action, [p], fn(p))
        except UserError as e:
            out.fail(f, str(e))
        except Exception as e:  # noqa: BLE001
            out.fail(f, f"{e.__class__.__name__}: {e}")


def _need_cat(p: Path, *cats: str) -> str:
    cat = category(p)
    if cat not in cats:
        raise UserError(f"expected {' or '.join(cats)}, got {p.suffix or 'no extension'}")
    return cat


# ---------------------------------------------------------------- commands
def cmd_convert(a, out: Out) -> None:
    from . import convert
    to = a.to.upper().lstrip(".")
    to = {"JPEG": "JPG", "TIF": "TIFF", "HEIF": "HEIC"}.get(to, to)
    files = [Path(f) for f in a.files]
    if a.combine:
        imgs = [f for f in files if category(f) == "image"]
        if to != "PDF" or not imgs:
            raise UserError("--combine joins images into one PDF: use it with --to pdf and images.")
        out.ok(f"convert:{to}", imgs, convert.images_to_single_pdf(imgs))
        return

    def one(p: Path):
        cat = category(p)
        if cat is None:
            raise UserError("unsupported file type")
        if to not in convert.targets_for(cat, p.suffix):
            raise UserError(f"can't convert {p.suffix} to {to}. Options: {', '.join(convert.targets_for(cat, p.suffix))}")
        return convert.convert(p, cat, to)
    _each(out, a.files, f"convert:{to}", one)


def cmd_compress(a, out: Out) -> None:
    from . import imaging, media
    from .convert import open_image
    from .util import parse_size

    def one(p: Path):
        cat = _need_cat(p, "image", "pdf", "video", "audio")
        if cat == "pdf":
            return [imaging.compress_pdf(p, quality=a.quality)]
        if cat == "video":
            return [media.compress_video(p, crf=round(38 - a.quality * 0.2), max_height=a.max_height or None)]
        if cat == "audio":
            return [media.compress_audio(p, kbps=a.kbps)]
        target = "WEBP" if a.webp else imaging.lossy_target(p)
        if a.target:
            q, side = imaging.plan_target_size(open_image(p), target, parse_size(a.target))
            return [imaging.compress_to(p, q, side, target)]
        return [imaging.compress_to(p, a.quality, a.max_side, target)]
    _each(out, a.files, "tool:Compress", one)


def cmd_resize(a, out: Out) -> None:
    from PIL import Image
    from . import imaging
    mode, value = next((m, v) for m, v in (("long", a.long), ("pct", a.pct), ("w", a.width), ("h", a.height))
                       if v)

    def one(p: Path):
        _need_cat(p, "image")
        with Image.open(p) as im:
            size = im.size
        dims = imaging.resize_dims(size, mode, value)
        if not a.allow_enlarge and (dims[0] > size[0] or dims[1] > size[1]):
            raise UserError(f"already smaller than that ({size[0]}×{size[1]}); add --allow-enlarge")
        return [imaging.resize_image(p, dims)]
    _each(out, a.files, "tool:Resize", one)


def cmd_strip(a, out: Out) -> None:
    from . import imaging

    def one(p: Path):
        cat = _need_cat(p, "image", "pdf")
        if cat == "pdf":
            return [imaging.strip_pdf_metadata(p)]
        return [imaging.strip_location(p) if a.location_only else imaging.strip_image_metadata(p)]
    _each(out, a.files, "tool:Metadata", one)


def cmd_watermark(a, out: Out) -> None:
    from . import imaging

    def one(p: Path):
        cat = _need_cat(p, "image", "pdf")
        if cat == "pdf":
            return [imaging.watermark_pdf(p, a.text, opacity=a.opacity / 100, color=a.color)]
        return [imaging.watermark_image_file(p, a.text, position=a.position, opacity=a.opacity / 100,
                                             color=a.color)]
    _each(out, a.files, "tool:Watermark", one)


def cmd_pdf(a, out: Out) -> None:
    from . import imaging
    op = a.op
    if op == "merge":
        files = [Path(f) for f in a.files]
        if len(files) < 2:
            raise UserError("merge needs at least two PDFs")
        for f in files:
            _need_cat(f, "pdf")
        out.ok("tool:Merge", files, [imaging.merge_pdfs(files)])
        return
    fns = {
        "split": lambda p: imaging.split_pdf(p),
        "rotate": lambda p: [imaging.rotate_pdf(p, a.degrees)],
        "number": lambda p: [imaging.pdf_page_numbers(p, a.style, a.position)],
        "protect": lambda p: [imaging.protect_pdf(p, _password(a))],
        "unlock": lambda p: [imaging.unlock_pdf(p, _password(a))],
        "extract": lambda p: imaging.extract_pdf_images(p),
        "compress": lambda p: [imaging.compress_pdf(p, quality=a.quality)],
    }
    names = {"split": "Split", "rotate": "Rotate", "number": "Numbers", "protect": "Protect",
             "unlock": "Unlock", "extract": "Extract", "compress": "Compress"}

    def one(p: Path):
        _need_cat(p, "pdf")
        return fns[op](p)
    _each(out, a.files, f"tool:{names[op]}", one)


def _password(a) -> str:
    if a.password:
        return a.password
    import getpass
    pw = getpass.getpass("PDF password: ")
    if not pw:
        raise UserError("no password given")
    return pw


def cmd_media(a, out: Out) -> None:
    from . import media
    fns = {"audio": ("Audio", ("video",), lambda p: [media.extract_audio(p)]),
           "mute": ("Mute", ("video",), lambda p: [media.mute_video(p)]),
           "frame": ("Frame", ("video",), lambda p: [media.video_frame(p, a.at)]),
           "gif": ("GIF", ("video",), lambda p: [media.gif_from_video(p, a.fps, a.width, a.max_seconds)]),
           "rotate": ("Rotate", ("video",), lambda p: [media.rotate_video(p, a.degrees)]),
           "normalize": ("Normalize", ("audio",), lambda p: [media.normalize_audio(p)]),
           "trim-silence": ("Trim silence", ("audio",), lambda p: [media.trim_silence(p)])}
    name, cats, fn = fns[a.op]
    action = "convert:GIF" if a.op == "gif" else f"tool:{name}"
    _each(out, a.files, action, lambda p: (_need_cat(p, *cats), fn(p))[1])


def cmd_recipe(a, out: Out) -> None:
    from . import recipes
    if a.op == "list":
        rs = recipes.all_recipes()
        if out.as_json:
            out.records = [{**r.to_json(), "builtin": r.builtin} for r in rs]
            return
        for r in rs:
            cats = ", ".join(c for c in recipes.ALL_CATS if r.applies_to(c))
            print(f"{r.glyph} {r.name:<14} {r.description or r.summary()}")
            print(f"  {'':<14} for: {cats}{'' if r.builtin else '   (custom)'}")
        return
    if a.op == "steps":
        for st in recipes.STEPS.values():
            ps = ", ".join(f"{p.name}={p.default!r}" for p in st.params)
            print(f"{st.key:<15} {st.label:<22} [{', '.join(st.cats)}]  {ps}")
        return
    if not a.name:
        raise UserError("which recipe? e.g. `dragshift recipe run web-ready photo.jpg`")
    r = recipes.find(a.name)
    if a.op == "show":
        print(json.dumps(r.to_json(), indent=2, ensure_ascii=False))
        return
    if a.op == "add":
        recipes.save_recipe(r)
        print(f"Saved “{r.name}”. It now shows in the menu's Recipes ring.")
        return
    if a.op == "delete":
        recipes.delete_recipe(r.name)
        print(f"Deleted “{r.name}”." if not r.builtin else f"“{r.name}” is built in; hide it in Settings instead.")
        return
    files = [Path(f) for f in a.files]
    missing = [f for f in files if not f.is_file()]
    for f in missing:
        out.fail(f, "file not found")
    files = [f for f in files if f.is_file()]
    if not files:
        return
    # combining recipes take all files at once; otherwise one run per file so one bad file
    # doesn't stop the rest
    groups = [files] if any(s.get("step") == "combine" for s in r.steps) else [[f] for f in files]
    for g in groups:
        try:
            res = recipes.run(r, g)
            out.ok(f"recipe:{r.name}", g, res.outputs, " → ".join(res.steps_run))
        except UserError as e:
            out.fail(g[0], str(e))
        except Exception as e:  # noqa: BLE001
            out.fail(g[0], f"{e.__class__.__name__}: {e}")


def cmd_info(a, out: Out) -> None:
    from . import imaging, media
    for f in a.files:
        p = Path(f)
        cat = category(p)
        info: dict = {"file": str(p), "type": cat or "unknown", "size": human_size(p.stat().st_size) if p.is_file() else "missing"}
        try:
            if cat == "image":
                info.update(imaging.metadata_summary(p))
                n, gps = imaging.count_metadata(p)
                info["Metadata entries"] = str(n)
            elif cat == "pdf":
                if imaging.pdf_is_locked(p):
                    info["Locked"] = "yes (password-protected)"
                else:
                    info.update(imaging.read_pdf_metadata(p))
            elif cat in ("video", "audio"):
                m = media.probe(p)
                info["Duration"] = media.describe(p).split(" · ")[0]
                if m.has_video:
                    info["Video"] = f"{m.vcodec} {m.width}×{m.height}" + (f" @ {m.fps:g} fps" if m.fps else "")
                if m.has_audio:
                    info["Audio"] = m.acodec
        except Exception as e:  # noqa: BLE001
            info["error"] = str(e)
        from . import convert
        if cat:
            info["Converts to"] = ", ".join(convert.targets_for(cat, p.suffix))
        if out.as_json:
            out.records.append(info)
        else:
            print(p.name)
            for k, v in info.items():
                if k != "file":
                    print(f"  {k:<18} {v}")


def cmd_formats(a, out: Out) -> None:
    from . import convert, media
    from .util import CATEGORIES
    rows = []
    for cat, exts in CATEGORIES:
        targets = sorted({t for e in exts for t in convert.targets_for(cat, e)})
        rows.append((cat, " ".join(sorted(e.lstrip(".") for e in exts)), ", ".join(targets)))
    if out.as_json:
        out.records = [{"type": c, "extensions": e.split(), "targets": t.split(", ")} for c, e, t in rows]
        return
    for c, e, t in rows:
        print(f"{c:<7} {e}\n        → {t}\n")
    if not media.available():
        print("(video/audio need ffmpeg: pip install imageio-ffmpeg)")


def cmd_watch(a, out: Out) -> None:
    from . import watch
    if a.folder:
        if not (a.recipe or a.to):
            raise UserError("say what to do: --recipe NAME or --to FORMAT")
        folder = Path(a.folder).expanduser().resolve()
        if not folder.is_dir():
            raise UserError(f"{folder} is not a folder")
        action = f"recipe:{a.recipe}" if a.recipe else f"convert:{a.to.upper()}"
        if a.recipe:
            from . import recipes
            recipes.find(a.recipe)  # fail early on a typo
        rules = [watch.WatchRule(str(folder), action, True, "beside" if a.beside else "subfolder")]
    else:
        rules = [r for r in watch.load_rules() if r.enabled]
        if not rules:
            raise UserError("no watch folders set up. Give a folder: dragshift watch ~/Inbox --recipe web-ready")
    print("Press Ctrl+C to stop.")
    try:
        watch.run_forever(rules, log=lambda s: print(s, flush=True))
    except KeyboardInterrupt:
        print("\nStopped.")


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    # SUPPRESS: these options work before or after the command without one copy resetting the other
    common = argparse.ArgumentParser(add_help=False, argument_default=argparse.SUPPRESS)
    common.add_argument("--out", metavar="DIR", help="write results here instead of next to the originals")
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("-q", "--quiet", action="store_true", help="only print errors")

    p = argparse.ArgumentParser(prog="dragshift", description="Convert and edit files. Run without a "
                                "command to start the menu app.", parents=[common])
    p.add_argument("--version", action="version", version=f"DragShift {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="COMMAND")

    s = sub.add_parser("convert", parents=[common], help="convert to another format")
    s.add_argument("files", nargs="+")
    s.add_argument("--to", required=True, metavar="FORMAT", help="jpg, png, webp, pdf, docx, mp4, mp3…")
    s.add_argument("--combine", action="store_true", help="images → one PDF")
    s.set_defaults(fn=cmd_convert)

    s = sub.add_parser("compress", parents=[common], help="shrink images, PDFs, videos, audio")
    s.add_argument("files", nargs="+")
    s.add_argument("--quality", type=int, default=72, help="1-100 (default 72)")
    s.add_argument("--target", metavar="SIZE", help="images: fit under a size, e.g. 500KB")
    s.add_argument("--max-side", type=int, help="images: also limit the longest side (px)")
    s.add_argument("--webp", action="store_true", help="images: write WebP")
    s.add_argument("--max-height", type=int, default=1080, help="videos: downscale above this (0 = keep)")
    s.add_argument("--kbps", type=int, default=96, help="audio: MP3 bitrate")
    s.set_defaults(fn=cmd_compress)

    s = sub.add_parser("resize", parents=[common], help="resize images")
    s.add_argument("files", nargs="+")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--long", type=int, metavar="PX", help="longest side")
    g.add_argument("--pct", type=int, metavar="N", help="percent")
    g.add_argument("--width", type=int, metavar="PX")
    g.add_argument("--height", type=int, metavar="PX")
    s.add_argument("--allow-enlarge", action="store_true")
    s.set_defaults(fn=cmd_resize)

    s = sub.add_parser("strip", parents=[common], help="remove metadata (EXIF, GPS, PDF author…)")
    s.add_argument("files", nargs="+")
    s.add_argument("--location-only", action="store_true", help="images: keep camera info, drop GPS")
    s.set_defaults(fn=cmd_strip)

    s = sub.add_parser("watermark", parents=[common], help="stamp text on images or PDFs")
    s.add_argument("files", nargs="+")
    s.add_argument("--text", required=True)
    s.add_argument("--position", default="bottom-right",
                   choices=["bottom-right", "bottom-left", "top-right", "top-left", "center", "tile"])
    s.add_argument("--opacity", type=int, default=55, help="percent")
    s.add_argument("--color", default="#ffffff")
    s.set_defaults(fn=cmd_watermark)

    s = sub.add_parser("pdf", parents=[common], help="PDF tools")
    s.add_argument("op", choices=["merge", "split", "rotate", "number", "protect", "unlock", "extract", "compress"])
    s.add_argument("files", nargs="+")
    s.add_argument("--degrees", type=int, default=90, choices=[90, 180, 270])
    s.add_argument("--style", default="1 / N", choices=["1", "1 / N", "Page 1", "Page 1 of N"])
    s.add_argument("--position", default="bottom-center")
    s.add_argument("--password", help="for protect/unlock (asked for if omitted)")
    s.add_argument("--quality", type=int, default=70)
    s.set_defaults(fn=cmd_pdf)

    s = sub.add_parser("media", parents=[common], help="video & audio tools")
    s.add_argument("op", choices=["audio", "mute", "frame", "gif", "rotate", "normalize", "trim-silence"])
    s.add_argument("files", nargs="+")
    s.add_argument("--at", type=float, help="frame: seconds in")
    s.add_argument("--fps", type=int, default=12)
    s.add_argument("--width", type=int, default=640)
    s.add_argument("--max-seconds", type=float, default=30)
    s.add_argument("--degrees", type=int, default=90, choices=[90, 180, 270])
    s.set_defaults(fn=cmd_media)

    s = sub.add_parser("recipe", parents=[common], help="multi-step recipes")
    s.add_argument("op", choices=["list", "steps", "show", "run", "add", "delete"])
    s.add_argument("name", nargs="?", help="recipe name (or a .json file)")
    s.add_argument("files", nargs="*")
    s.set_defaults(fn=cmd_recipe)

    s = sub.add_parser("info", parents=[common], help="show metadata / media info")
    s.add_argument("files", nargs="+")
    s.set_defaults(fn=cmd_info)

    s = sub.add_parser("formats", parents=[common], help="list supported conversions")
    s.set_defaults(fn=cmd_formats)

    s = sub.add_parser("watch", parents=[common], help="process new files in a folder automatically")
    s.add_argument("folder", nargs="?", help="omit to use the folders saved in the app")
    s.add_argument("--recipe")
    s.add_argument("--to", metavar="FORMAT")
    s.add_argument("--beside", action="store_true", help="save next to the new files (default: DragShift/ subfolder)")
    s.set_defaults(fn=cmd_watch)
    return p


def main(argv: list[str] | None = None) -> int:
    _attach_windows_console()
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["help"]:
        argv = ["--help"]
    parser = build_parser()
    a = parser.parse_args(argv)
    if not getattr(a, "fn", None):
        parser.print_help()
        return 2
    if getattr(a, "out", None):
        CONFIG["out_dir"] = str(Path(a.out).expanduser())
    out = Out(getattr(a, "json", False), getattr(a, "quiet", False))
    try:
        a.fn(a, out)
        return out.finish()
    except UserError as e:
        print(f"dragshift: {e}", file=sys.stderr)
        return 1
    except BrokenPipeError:            # e.g. `dragshift recipe list | head`
        import os
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
