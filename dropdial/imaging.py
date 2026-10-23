"""Pure image/PDF processing used by the tools (no UI here, so it's testable)."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS

from .convert import atomic_save, fitz, flatten, open_image, open_pdf, save_image
from .i18n import N_
from .util import NotSmaller, UserError, sibling

EXT_TARGET = {".jpg": "JPG", ".jpeg": "JPG", ".png": "PNG", ".webp": "WEBP", ".tif": "TIFF",
              ".tiff": "TIFF", ".bmp": "BMP", ".heic": "HEIC", ".heif": "HEIC",
              ".avif": "AVIF", ".gif": "GIF", ".ico": "ICO"}


def target_for(path: str | Path) -> str:
    return EXT_TARGET.get(Path(path).suffix.lower(), "PNG")


def save_like(im: Image.Image, src: str | Path, label: str, force_ext: str | None = None) -> Path:
    """Save `im` next to `src` as '<name> <label>.<ext>' in the source's format."""
    ext = force_ext or Path(src).suffix.lower()
    if ext in (".gif", ".ico"):
        ext = ".png"
    out = sibling(src, label, ext)
    save_image(im, out, target_for(out))
    return out


# ---------------------------------------------------------------- compress
def compress_image(src: str | Path, quality: int = 72, max_side: int | None = None,
                   to_webp: bool = False) -> Path:
    im = open_image(src)
    if max_side and max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    ext = ".webp" if to_webp else Path(src).suffix.lower()
    out = sibling(src, "Compressed", ext)
    tgt = target_for(out)
    if tgt == "PNG":
        # lossy PNG: quantise to a palette (like pngquant), keeps transparency
        colors = max(16, min(256, int(quality * 2.56)))
        q = im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE,
                                        dither=Image.Dither.FLOYDSTEINBERG)
        atomic_save(lambda dst: q.save(dst, "PNG", optimize=True), out)
    elif tgt in ("BMP", "TIFF", "GIF", "ICO"):
        out = sibling(src, "Compressed", ".jpg")
        save_image(im, out, "JPG", quality=quality)
    else:
        save_image(im, out, tgt, quality=quality)
    return out


def _normalize_pdf_images(doc) -> int:
    """Convert CMYK and colour-profiled images (Display P3, Adobe RGB…) to plain sRGB before
    compressing. PyMuPDF's re-encoder turns their pixels into sRGB but keeps the old colour
    label, so viewers convert them twice: CMYK art comes out garbled and photos oversaturated.
    Plain sRGB images are left alone. Returns how many images were converted."""
    done = 0
    seen: set[int] = set()
    for page in doc:
        for img in page.get_images(full=True):
            xref, smask = img[0], img[1]
            if xref in seen:
                continue
            seen.add(xref)
            try:
                pix = fitz.Pixmap(doc, xref)
                cs = str(pix.colorspace)
                if pix.colorspace is None or (pix.n - pix.alpha < 4 and ("ICC" not in cs or "sRGB" in cs)):
                    continue
                gray = pix.colorspace.n == 1
                pix = fitz.Pixmap(fitz.csGRAY if gray else fitz.csRGB, pix)
                if pix.alpha:
                    pix = fitz.Pixmap(pix, 0)      # transparency lives in the separate mask
                if img[8] in ("DCTDecode", "JPXDecode"):
                    im = Image.frombytes("L" if gray else "RGB", (pix.width, pix.height), pix.samples)
                    buf = io.BytesIO()
                    im.save(buf, "JPEG", quality=92, subsampling=0)
                    page.replace_image(xref, stream=buf.getvalue())
                else:
                    page.replace_image(xref, pixmap=pix)
                if smask:
                    doc.xref_set_key(xref, "SMask", f"{smask} 0 R")   # replace_image drops it
                done += 1
            except Exception:
                continue
    return done


def compress_pdf(src: str | Path, image_dpi: int = 150, quality: int = 70) -> Path:
    out = sibling(src, "Compressed", ".pdf")
    with open_pdf(src) as doc:
        _normalize_pdf_images(doc)
        try:
            doc.rewrite_images(dpi_threshold=image_dpi + 10, dpi_target=image_dpi,
                               quality=quality, lossy=True, lossless=True, bitonal=True,
                               color=True, gray=True, set_to_gray=False)
        except Exception:
            pass  # older PyMuPDF: still get structural compression below
        doc.save(out, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True,
                 clean=True, use_objstms=1)
    return out


def encode_size(im: Image.Image, target: str, quality: int) -> int:
    """Bytes `im` would take saved as `target` at `quality` (PNG = palette-quantised)."""
    buf = io.BytesIO()
    if target == "PNG":
        colors = max(16, min(256, int(quality * 2.56)))
        im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE).save(buf, "PNG", optimize=True)
    else:
        save_image(im, buf, target, quality=quality)
    return buf.tell()


def lossy_target(src: str | Path, to_webp: bool = False) -> str:
    """Format a compressed copy is written in (BMP/TIFF/GIF/ICO become JPG)."""
    if to_webp:
        return "WEBP"
    t = target_for(src)
    return t if t in ("JPG", "PNG", "WEBP", "AVIF", "HEIC") else "JPG"


def plan_target_size(im: Image.Image, target: str, max_bytes: int) -> tuple[int, int | None]:
    """Find (quality, max_side) that fits under max_bytes: binary-search quality, then shrink."""
    side = None
    work = im
    for _ in range(8):
        lo, hi, best = 30, 92, None
        while lo <= hi:
            q = (lo + hi) // 2
            if encode_size(work, target, q) <= max_bytes:
                best, lo = q, q + 1
            else:
                hi = q - 1
        if best is not None:
            return best, side
        side = int(max(work.size) * 0.8)
        work = im.copy()
        work.thumbnail((side, side), Image.LANCZOS)
        if side < 200:
            return 30, side
    return 30, side


def ensure_smaller(src: str | Path, out: Path, resized: bool = False) -> Path:
    """A 'compressed' copy that's bigger than the original is worse than none: remove it."""
    same_format = Path(src).suffix.lower().replace("jpeg", "jpg") == out.suffix.lower().replace("jpeg", "jpg")
    if not resized and same_format and out.stat().st_size >= Path(src).stat().st_size:
        out.unlink()
        raise NotSmaller("{name} is already compressed as far as this setting goes. "
                         "Try a lower quality, a target size or WebP.", name=Path(src).name)
    return out


def compress_each(srcs: list, fn) -> list[Path]:
    """Run fn(src) for each file; skip the ones that can't get smaller, fail only if all do."""
    outs, skipped = [], []
    for s in srcs:
        try:
            outs.append(fn(s))
        except NotSmaller as e:
            skipped.append(e)
    if not outs and skipped:
        raise skipped[0] if len(skipped) == 1 else NotSmaller(
            "None of the {n} files could get smaller with this setting.", n=len(skipped))
    return outs


def compress_to(src: str | Path, quality: int, max_side: int | None, target: str) -> Path:
    im = open_image(src)
    resized = bool(max_side and max(im.size) > max_side)
    if resized:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    out = sibling(src, "Compressed", "." + ("jpg" if target == "JPG" else target.lower()))
    if target == "PNG":
        colors = max(16, min(256, int(quality * 2.56)))
        q = im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE,
                                        dither=Image.Dither.FLOYDSTEINBERG)
        atomic_save(lambda dst: q.save(dst, "PNG", optimize=True), out)
    else:
        save_image(im, out, target, quality=quality)
    return ensure_smaller(src, out, resized)


# ---------------------------------------------------------------- resize
def resize_dims(size: tuple[int, int], mode: str, value: int) -> tuple[int, int]:
    """mode: 'pct' (value %), 'long' (longest side px), 'w' (width px), 'h' (height px)."""
    w, h = size
    if mode == "pct":
        k = value / 100
    elif mode == "long":
        k = value / max(w, h)
    elif mode == "w":
        k = value / w
    else:
        k = value / h
    return max(1, round(w * k)), max(1, round(h * k))


def resize_image(src: str | Path, dims: tuple[int, int]) -> Path:
    im = open_image(src)
    im = im.resize(dims, Image.LANCZOS)
    return save_like(im, src, f"{dims[0]}x{dims[1]}")


# ---------------------------------------------------------------- metadata
def read_image_metadata(src: str | Path) -> dict[str, str]:
    info: dict[str, str] = {}
    with Image.open(src) as im:
        info["Dimensions"] = f"{im.width} × {im.height}"
        info["Format"] = str(im.format)
        info["Mode"] = im.mode
        exif = im.getexif()
        for k, v in exif.items():
            info[TAGS.get(k, str(k))] = _fmt(v)
        try:
            for k, v in exif.get_ifd(0x8769).items():  # Exif sub-IFD (camera settings)
                info[TAGS.get(k, str(k))] = _fmt(v)
            gps = exif.get_ifd(0x8825)
            if gps:
                for k, v in gps.items():
                    info["GPS " + GPSTAGS.get(k, str(k))] = _fmt(v)
        except Exception:
            pass
        for k, v in (im.info or {}).items():
            if k in ("exif", "icc_profile", "xmp"):
                info[k.upper()] = f"{len(v)} bytes" if hasattr(v, "__len__") else "yes"
            elif isinstance(v, (str, int, float)):
                info[k] = str(v)
    return info


def _fmt(v) -> str:
    if isinstance(v, bytes):
        return f"<{len(v)} bytes>"
    s = str(v)
    return s if len(s) < 120 else s[:117] + "…"


def metadata_summary(src: str | Path) -> dict[str, str]:
    """The handful of fields people actually care about, human-readable."""
    out: dict[str, str] = {}
    with Image.open(src) as im:
        out["Size"] = f"{im.width} × {im.height}"
        exif = im.getexif()
        sub = {}
        gps = {}
        try:
            sub = exif.get_ifd(0x8769)
            gps = exif.get_ifd(0x8825)
        except Exception:
            pass
        make, model = str(exif.get(0x010F, "")).strip(), str(exif.get(0x0110, "")).strip()
        if make or model:
            out["Camera"] = model if make and model.startswith(make) else f"{make} {model}".strip()
        taken = sub.get(0x9003) or exif.get(0x0132)
        if taken:
            out["Taken"] = str(taken)
        if exif.get(0x0131):
            out["Software"] = str(exif.get(0x0131))
        if sub.get(0x829A):
            t = float(sub[0x829A])
            out["Exposure"] = f"1/{round(1 / t)} s" if 0 < t < 1 else f"{t:g} s"
        if sub.get(0x829D):
            out["Aperture"] = f"f/{float(sub[0x829D]):.1f}"
        if sub.get(0x8827):
            out["ISO"] = str(sub[0x8827])
        loc = gps_decimal(gps)
        if loc:
            out["Location"] = f"{loc[0]:.5f}, {loc[1]:.5f}"
    return out


def gps_decimal(gps) -> tuple[float, float] | None:
    try:
        def conv(v, ref):
            d, m, s_ = (float(x) for x in v)
            val = d + m / 60 + s_ / 3600
            return -val if ref in ("S", "W") else val
        return conv(gps[2], gps[1]), conv(gps[4], gps[3])
    except Exception:
        return None


def count_metadata(src: str | Path) -> tuple[int, bool]:
    """(number of EXIF/XMP/ICC entries, has GPS)."""
    with Image.open(src) as im:
        exif = im.getexif()
        n = len(exif)
        has_gps = False
        try:
            n += len(exif.get_ifd(0x8769))
            g = exif.get_ifd(0x8825)
            has_gps = bool(g)
            n += len(g)
        except Exception:
            pass
        n += sum(1 for k in ("xmp", "XML:com.adobe.xmp", "comment") if k in (im.info or {}))
    return n, has_gps


def strip_location(src: str | Path) -> Path:
    """Remove only GPS tags, keep camera info and everything else."""
    with Image.open(src) as im:
        exif = im.getexif()
        if 0x8825 in exif:
            del exif[0x8825]
        exif_bytes = exif.tobytes()
    im = open_image(src)
    out = sibling(src, "No Location", Path(src).suffix.lower() if Path(src).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff") else ".jpg")
    # orientation already baked in by open_image → reset tag to 1
    ex = Image.Exif()
    ex.load(exif_bytes)
    ex[0x0112] = 1
    save_image(im, out, target_for(out), exif=ex.tobytes())
    return out


def strip_image_metadata(src: str | Path) -> Path:
    im = open_image(src)  # exif_transpose applied, so orientation is baked in
    clean = Image.new(im.mode, im.size)
    clean.paste(im)
    return save_like(clean, src, "Clean")


def read_pdf_metadata(src: str | Path) -> dict[str, str]:
    with open_pdf(src) as doc:
        info = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
        info["Pages"] = str(doc.page_count)
        if doc.get_xml_metadata():
            info["XMP"] = "present"
    return info


def strip_pdf_metadata(src: str | Path) -> Path:
    out = sibling(src, "Clean", ".pdf")
    with open_pdf(src) as doc:
        doc.set_metadata({})
        try:
            doc.del_xml_metadata()
        except Exception:
            pass
        doc.save(out, garbage=3, deflate=True)
    return out


# ---------------------------------------------------------------- pdf extras
def split_pdf(src: str | Path) -> list[Path]:
    outs = []
    with open_pdf(src) as doc:
        for i in range(doc.page_count):
            nd = fitz.open()
            nd.insert_pdf(doc, from_page=i, to_page=i)
            out = sibling(src, f"page {i + 1}", ".pdf")
            nd.save(out)
            nd.close()
            outs.append(out)
    return outs


def merge_pdfs(srcs: list[str | Path]) -> Path:
    out = sibling(srcs[0], "Merged", ".pdf")
    nd = fitz.open()
    for s in srcs:
        with open_pdf(s) as d:
            nd.insert_pdf(d)
    nd.save(out, garbage=3, deflate=True)
    nd.close()
    return out


def protect_pdf(src: str | Path, password: str) -> Path:
    out = sibling(src, "Protected", ".pdf")
    with open_pdf(src) as doc:
        perms = int(fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY)
        doc.save(out, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw=password, user_pw=password,
                 permissions=perms, garbage=3, deflate=True)
    return out


def extract_pdf_images(src: str | Path) -> list[Path]:
    from .util import output_dir, unique_path
    folder = unique_path(output_dir(src) / f"{Path(src).stem} images")
    outs: list[Path] = []
    seen: set[int] = set()
    with open_pdf(src) as doc:
        for pno, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    info = doc.extract_image(xref)
                except Exception:
                    continue
                if not info or info.get("width", 0) < 16:
                    continue
                folder.mkdir(exist_ok=True)
                ext = info.get("ext", "png")
                name = f"page {pno + 1} image {len(outs) + 1}"
                if _raw_image_ok(info, img[1]):
                    p = folder / f"{name}.{'jpg' if ext == 'jpeg' else ext}"
                    p.write_bytes(info["image"])      # untouched original bytes
                else:
                    p = _decode_pdf_image(doc, xref, img[1], folder / name, lossy=ext in ("jpg", "jpeg", "jpx"))
                outs.append(p)
    if not outs:
        raise UserError("No images found in this PDF.")
    return outs


def _raw_image_ok(info: dict, smask: int) -> bool:
    """Can the image's stored bytes be saved as-is and still look right?"""
    if info.get("ext") not in ("jpg", "jpeg", "png") or info.get("colorspace") not in (1, 3) or smask:
        return False
    if "ICC" in str(info.get("cs-name") or ""):
        # the colour profile may live in the PDF rather than in the image file itself
        try:
            with Image.open(io.BytesIO(info["image"])) as im:
                return bool(im.info.get("icc_profile"))
        except Exception:
            return False
    return True


def _decode_pdf_image(doc, xref: int, smask: int, base: Path, lossy: bool) -> Path:
    """Decode exactly as a viewer would (CMYK, inverted decode arrays, colour profiles,
    transparency masks) into sRGB, then save as PNG (or JPEG for photos without alpha)."""
    pix = fitz.Pixmap(doc, xref)
    if smask:
        try:
            pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
        except Exception:
            pass
    cs = pix.colorspace
    if cs is not None and (cs.n not in (1, 3) or "ICC" in str(cs)):
        pix = fitz.Pixmap(fitz.csRGB, pix)   # CMYK / ICC-based -> sRGB, colour-managed
    im = Image.frombytes("RGBA" if pix.alpha else ("L" if pix.n == 1 else "RGB"), (pix.width, pix.height), pix.samples)
    if lossy and not pix.alpha:
        out = base.with_suffix(".jpg")
        im.save(out, "JPEG", quality=95, subsampling=0)
    else:
        out = base.with_suffix(".png")
        im.save(out, "PNG")
    return out


def pdf_page_count(src: str | Path) -> int:
    with fitz.open(src) as d:
        return d.page_count


def rotate_pdf(src: str | Path, degrees: int = 90) -> Path:
    out = sibling(src, "Rotated", ".pdf")
    with open_pdf(src) as doc:
        for p in doc:
            p.set_rotation((p.rotation + degrees) % 360)
        doc.save(out)
    return out


# ---------------------------------------------------------------- redact
def redact(im: Image.Image, rects: list[tuple[int, int, int, int]], mode: str = "black") -> Image.Image:
    im = im.copy()
    for (x0, y0, x1, y1) in rects:
        box = (max(0, min(x0, x1)), max(0, min(y0, y1)),
               min(im.width, max(x0, x1)), min(im.height, max(y0, y1)))
        if box[2] - box[0] < 1 or box[3] - box[1] < 1:
            continue
        if mode == "black":
            ImageDraw.Draw(im).rectangle(box, fill=(0, 0, 0, 255) if im.mode == "RGBA" else 0)
        else:
            region = im.crop(box)
            if mode == "pixelate":
                w, h = region.size
                f = max(8, min(w, h) // 6)
                region = region.resize((max(1, w // f), max(1, h // f)), Image.BILINEAR)
                region = region.resize((w, h), Image.NEAREST)
            else:  # blur – strong enough that text can't be recovered
                region = region.filter(ImageFilter.GaussianBlur(max(12, min(region.size) / 3)))
            im.paste(region, box[:2])
    return im


# ---------------------------------------------------------------- edit
@dataclass
class Adjust:
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 1.0
    warmth: float = 0.0       # -1 … 1
    rotate: int = 0           # multiples of 90
    flip_h: bool = False
    flip_v: bool = False
    grayscale: bool = False
    resize_pct: int = 100


def auto_enhance(im: Image.Image) -> Adjust:
    """Pick gentle adjustments from the histogram (like a phone's 'auto' button)."""
    from PIL import ImageStat
    g = im.convert("L")
    st = ImageStat.Stat(g)
    mean, std = st.mean[0], st.stddev[0]
    a = Adjust()
    a.brightness = max(0.85, min(1.25, 1 + (118 - mean) / 400))
    a.contrast = max(0.95, min(1.3, 1 + (58 - std) / 160))
    sat = ImageStat.Stat(im.convert("HSV").split()[1]).mean[0]
    a.saturation = max(1.0, min(1.3, 1 + (110 - sat) / 400))
    a.sharpness = 1.15
    return a


def apply_adjust(im: Image.Image, a: Adjust) -> Image.Image:
    alpha = im.split()[3] if im.mode == "RGBA" else None
    rgb = im.convert("RGB")
    if a.brightness != 1.0:
        rgb = ImageEnhance.Brightness(rgb).enhance(a.brightness)
    if a.contrast != 1.0:
        rgb = ImageEnhance.Contrast(rgb).enhance(a.contrast)
    if a.saturation != 1.0:
        rgb = ImageEnhance.Color(rgb).enhance(a.saturation)
    if a.sharpness != 1.0:
        rgb = ImageEnhance.Sharpness(rgb).enhance(a.sharpness)
    if a.warmth:
        r, g, b = rgb.split()
        k = a.warmth * 25
        r = r.point(lambda v: max(0, min(255, v + k)))
        b = b.point(lambda v: max(0, min(255, v - k)))
        rgb = Image.merge("RGB", (r, g, b))
    if a.grayscale:
        rgb = ImageOps.grayscale(rgb).convert("RGB")
    out = rgb
    if alpha is not None:
        out = rgb.convert("RGBA")
        out.putalpha(alpha)
    if a.flip_h:
        out = ImageOps.mirror(out)
    if a.flip_v:
        out = ImageOps.flip(out)
    if a.rotate % 360:
        out = out.rotate(-a.rotate, expand=True)
    if a.resize_pct != 100:
        w = max(1, round(out.width * a.resize_pct / 100))
        h = max(1, round(out.height * a.resize_pct / 100))
        out = out.resize((w, h), Image.LANCZOS)
    return out


# ---------------------------------------------------------------- add background
@dataclass
class Background:
    colors: list[str] = field(default_factory=lambda: ["#ff9a5a", "#ff3d6e", "#7b5cff"])
    angle: float = 135.0       # degrees, CSS-style
    padding: float = 0.12      # fraction of the longer image side
    radius: int = 24           # px on the source image scale
    shadow: float = 0.5        # 0 … 1
    aspect: str = "Auto"       # Auto, 1:1, 4:3, 16:9, 9:16, 4:5


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def gradient(size: tuple[int, int], colors: list[str], angle: float) -> Image.Image:
    import math
    w, h = size
    if len(colors) == 1:
        return Image.new("RGB", size, _hex(colors[0]))
    # Build a 1-px ramp, then stretch + rotate a big square and crop the centre.
    stops = [_hex(c) for c in colors]
    n = 512
    ramp = Image.new("RGB", (n, 1))
    px = ramp.load()
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        j = min(int(t), len(stops) - 2)
        f = t - j
        a, b = stops[j], stops[j + 1]
        px[i, 0] = tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))
    diag = int(math.hypot(w, h)) + 2
    big = ramp.resize((diag, diag), Image.BILINEAR)
    big = big.rotate(-(angle - 90), resample=Image.BICUBIC)
    left, top = (diag - w) // 2, (diag - h) // 2
    return big.crop((left, top, left + w, top + h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    scale = 4  # supersample for smooth corners
    m = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1),
                                        radius=radius * scale, fill=255)
    return m.resize(size, Image.LANCZOS)


BG_PRESETS = [
    (N_("Sunset"), ["#ffb36b", "#ff5f6d", "#a24bff"]),
    (N_("Prism"), ["#ff6b9d", "#ffb36b", "#ffe66b", "#7dffb0", "#6bd5ff", "#8a7bff"]),
    (N_("Peach"), ["#ffd6a5", "#ff9a8b"]),
    (N_("Aurora"), ["#00d2ff", "#7a5cff", "#ff5fd2"]),
    (N_("Mint"), ["#a8ffce", "#3ad6c6"]),
    (N_("Ocean"), ["#43cbff", "#2058d6"]),
    (N_("Dusk"), ["#2b1055", "#d53a9d"]),
    (N_("Lemon"), ["#fff59d", "#ffb74d"]),
    (N_("Night"), ["#0f2027", "#2c5364"]),
    (N_("Rose"), ["#ffdde1", "#ee9ca7"]),
]
BG_SOLIDS = ["#ffffff", "#f2f2f7", "#d1d1d6", "#8e8e93", "#1c1c1e", "#000000", "#ff3b30",
          "#ff9500", "#ffcc00", "#34c759", "#00c7be", "#007aff", "#5856d6", "#af52de"]


ASPECTS = {"1:1": 1.0, "4:3": 4 / 3, "16:9": 16 / 9, "9:16": 9 / 16, "4:5": 4 / 5, "3:2": 1.5}


def add_background(im: Image.Image, bg: Background) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    pad = int(max(w, h) * bg.padding)
    cw, ch = w + 2 * pad, h + 2 * pad
    if bg.aspect in ASPECTS:
        r = ASPECTS[bg.aspect]
        if cw / ch < r:
            cw = int(round(ch * r))
        else:
            ch = int(round(cw / r))
    canvas = gradient((cw, ch), bg.colors, bg.angle).convert("RGBA")
    x, y = (cw - w) // 2, (ch - h) // 2
    radius = min(bg.radius, min(w, h) // 2)
    mask = rounded_mask((w, h), radius) if radius > 0 else Image.new("L", (w, h), 255)
    if im.mode == "RGBA":
        mask = ImageChops.multiply(mask, im.split()[3])
    if bg.shadow > 0:
        blur = max(4, int(max(w, h) * 0.035))
        sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        smask = Image.new("L", (cw, ch), 0)
        smask.paste(mask, (x, y + int(blur * 0.6)))
        smask = smask.filter(ImageFilter.GaussianBlur(blur))
        smask = smask.point(lambda v: int(v * 0.65 * bg.shadow))
        sh.putalpha(smask)
        canvas = Image.alpha_composite(canvas, sh)
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    layer.paste(im, (x, y), mask)
    return Image.alpha_composite(canvas, layer)


# ---------------------------------------------------------------- Qt bridge
def pil_to_png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- PDF: page numbers, watermark, unlock
def _visible_point(page, x: float, y: float):
    """A point given in what-you-see coordinates → the page's unrotated coordinates."""
    return fitz.Point(x, y) * page.derotation_matrix


NUMBER_STYLES = {"1": "{n}", "1 / N": "{n} / {total}", "Page 1": "Page {n}",
                 "Page 1 of N": "Page {n} of {total}"}
POSITIONS = ("bottom-center", "bottom-right", "bottom-left", "top-center", "top-right", "top-left")


def pdf_page_numbers(src: str | Path, style: str = "1 / N", position: str = "bottom-center",
                     size: float = 10.0, start: int = 1) -> Path:
    fmt = NUMBER_STYLES.get(style, style)
    if position not in POSITIONS:
        position = "bottom-center"
    out = sibling(src, "Numbered", ".pdf")
    with open_pdf(src) as doc:
        total = doc.page_count + start - 1
        for i, page in enumerate(doc):
            text = fmt.format(n=i + start, total=total)
            w, h = page.rect.width, page.rect.height
            tw = fitz.get_text_length(text, fontname="helv", fontsize=size)
            margin = max(18.0, min(w, h) * 0.045)
            vert, horiz = position.split("-")
            x = {"left": margin, "center": (w - tw) / 2, "right": w - margin - tw}[horiz]
            y = margin + size if vert == "top" else h - margin
            page.insert_text(_visible_point(page, x, y), text, fontsize=size, fontname="helv",
                             color=(0.25, 0.25, 0.25), rotate=page.rotation)
        atomic_save(lambda dst: doc.save(str(dst), garbage=3, deflate=True), out)
    return out


def _hex_rgb01(c: str) -> tuple[float, float, float]:
    r, g, b = _hex(c)
    return r / 255, g / 255, b / 255


def stamp_pdf_page(page, text: str, opacity: float = 0.15, angle: float = 45.0,
                   color: str = "#ff3d6e") -> None:
    """Big centred text across one page (vector, so it stays sharp when zoomed)."""
    import math
    unit = fitz.get_text_length(text, fontname="hebo", fontsize=1) or 1
    w, h = page.rect.width, page.rect.height
    span = math.hypot(w, h) * 0.62 if angle % 180 else w * 0.8
    size = max(8.0, min(span / unit, h * 0.25))
    tw = unit * size
    c = fitz.Point(w / 2, h / 2)
    start = fitz.Point(c.x - tw / 2, c.y + size * 0.35)
    m = fitz.Matrix(angle)   # `rotate=` below already accounts for the page's rotation
    page.insert_text(_visible_point(page, start.x, start.y), text, fontsize=size,
                     fontname="hebo", color=_hex_rgb01(color), fill_opacity=opacity,
                     stroke_opacity=opacity, rotate=page.rotation,
                     morph=(_visible_point(page, c.x, c.y), m), overlay=True)


def watermark_pdf(src: str | Path, text: str, opacity: float = 0.15, angle: float = 45.0,
                  color: str = "#ff3d6e") -> Path:
    text = text.strip()
    if not text:
        raise UserError("Type the watermark text first.")
    out = sibling(src, "Watermarked", ".pdf")
    with open_pdf(src) as doc:
        for page in doc:
            stamp_pdf_page(page, text, opacity, angle, color)
        atomic_save(lambda dst: doc.save(str(dst), garbage=3, deflate=True), out)
    return out


def watermark_pdf_preview(src: str | Path, text: str, opacity: float, angle: float, color: str,
                          width: int = 520) -> Image.Image:
    """Page 1 with the watermark, for the tool window's live preview."""
    with open_pdf(src) as doc:
        one = fitz.open()
        one.insert_pdf(doc, from_page=0, to_page=0)
    page = one[0]
    if text.strip():
        stamp_pdf_page(page, text.strip(), opacity, angle, color)
    zoom = width / max(1.0, page.rect.width)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    one.close()
    return im


def unlock_pdf(src: str | Path, password: str) -> Path:
    out = sibling(src, "Unlocked", ".pdf")
    doc = fitz.open(str(src))
    try:
        if not doc.needs_pass and not doc.is_encrypted:
            raise UserError("This PDF isn't password-protected.")
        if doc.needs_pass and not doc.authenticate(password):
            raise UserError("That password didn't work.")
        atomic_save(lambda dst: doc.save(str(dst), encryption=fitz.PDF_ENCRYPT_NONE, garbage=3,
                                         deflate=True), out)
    finally:
        doc.close()
    return out


def pdf_is_locked(src: str | Path) -> bool:
    try:
        with fitz.open(str(src)) as d:
            return bool(d.needs_pass)
    except Exception:
        return False


# ---------------------------------------------------------------- image watermark
WATERMARK_POSITIONS = ("bottom-right", "bottom-left", "top-right", "top-left", "center", "tile")


def _font(px: int):
    from PIL import ImageFont
    for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "Helvetica.ttc",
                 "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default(size=px)


def watermark_image(im: Image.Image, text: str, position: str = "bottom-right",
                    opacity: float = 0.6, scale: float = 0.045, color: str = "#ffffff") -> Image.Image:
    """Text with a soft shadow so it reads on any photo. `scale` = text height / image height."""
    text = text.strip()
    if not text:
        return im.copy()
    base = im.convert("RGBA")
    w, h = base.size
    px = max(10, int(min(w, h) * scale * (0.6 if position == "tile" else 1)))
    font = _font(px)
    rgb = _hex(color)
    a = int(255 * max(0.0, min(1.0, opacity)))
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    x0, y0, x1, y1 = probe.textbbox((0, 0), text, font=font)
    tw, th = x1 - x0, y1 - y0
    shadow_off = max(1, px // 14)

    def stamp(layer: Image.Image, x: int, y: int):
        d = ImageDraw.Draw(layer)
        d.text((x - x0 + shadow_off, y - y0 + shadow_off), text, font=font, fill=(0, 0, 0, a // 2))
        d.text((x - x0, y - y0), text, font=font, fill=(*rgb, a))

    if position == "tile":
        import math
        diag = int(math.hypot(w, h)) + 2
        layer = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
        step_x, step_y = tw + px * 3, th + px * 3
        for row, y in enumerate(range(0, diag, step_y)):
            offset = (row % 2) * step_x // 2
            for x in range(-step_x + offset, diag, step_x):
                stamp(layer, x, y)
        layer = layer.rotate(30, resample=Image.BICUBIC)
        left, top = (diag - w) // 2, (diag - h) // 2
        layer = layer.crop((left, top, left + w, top + h))
    else:
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        m = max(8, int(min(w, h) * 0.03))
        if position == "center":
            x, y = (w - tw) // 2, (h - th) // 2
        else:
            vert, horiz = position.split("-")
            x = m if horiz == "left" else w - m - tw
            y = m if vert == "top" else h - m - th
        stamp(layer, x, y)
    out = Image.alpha_composite(base, layer)
    return out if im.mode == "RGBA" else out.convert("RGB")


def watermark_image_file(src: str | Path, text: str, **kw) -> Path:
    return save_like(watermark_image(open_image(src), text, **kw), src, "Watermarked")
