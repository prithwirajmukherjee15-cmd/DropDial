"""Camera RAW photos (developed with LibRaw via rawpy) and image formats the main image
module doesn't open: Photoshop composites, TGA, QOI, DDS, PCX, Netpbm, ICNS, XBM, SGI and
JPEG 2000. Writing reuses dropdial.convert, so colour handling (ICC -> sRGB), JPEG settings
and PDF embedding match the main image module exactly. `save_extra` writes ICNS, TGA, QOI,
PPM and JP2 for any image and is meant to be shared with the main image module."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from ..util import UserError, report_progress, sibling
from . import Family, register

RAW_EXTS = {".dng", ".cr2", ".cr3", ".nef", ".nrw", ".arw", ".srf", ".sr2", ".orf", ".rw2",
            ".raf", ".pef", ".srw", ".x3f", ".3fr", ".iiq", ".rwl", ".erf", ".mrw", ".kdc",
            ".dcr", ".mos"}

# extension -> (Pillow decoders allowed, name for messages). Restricting the decoder means a
# renamed file is never handed to an unexpected plug-in (e.g. EPS, which runs Ghostscript).
PIL_EXTS = {
    ".psd": (("PSD",), "Photoshop"),
    ".tga": (("TGA",), "TGA"),
    ".ppm": (("PPM",), "PPM"), ".pgm": (("PPM",), "PGM"), ".pbm": (("PPM",), "PBM"),
    ".pnm": (("PPM",), "PNM"),
    ".qoi": (("QOI",), "QOI"),
    ".dds": (("DDS",), "DDS"),
    ".pcx": (("PCX",), "PCX"),
    ".icns": (("ICNS",), "macOS icon"),
    ".xbm": (("XBM",), "XBM"),
    ".sgi": (("SGI",), "SGI"), ".rgb": (("SGI",), "SGI"), ".rgba": (("SGI",), "SGI"),
    ".bw": (("SGI",), "SGI"),
    ".jp2": (("JPEG2000",), "JPEG 2000"), ".j2k": (("JPEG2000",), "JPEG 2000"),
    ".jpx": (("JPEG2000",), "JPEG 2000"),
}

RAW_TARGETS = ["JPG", "TIFF", "PNG", "WEBP", "HEIC", "AVIF", "PDF"]
PIL_TARGETS = ["PNG", "JPG", "WEBP", "TIFF", "HEIC", "AVIF", "PDF"]
EXTRA_TARGETS = {"ICNS": "ICNS", "TGA": "TGA", "QOI": "QOI", "PPM": "PPM", "JP2": "JPEG2000"}
MAIN_TARGETS = {"PNG", "JPG", "WEBP", "TIFF", "HEIC", "AVIF", "PDF", "ICO", "BMP", "GIF"}

HINTS = {
    "JPG": "Opens everywhere", "TIFF": "16-bit, for editing", "PNG": "Lossless",
    "WEBP": "Small, for the web", "HEIC": "Small, Apple photos", "AVIF": "Smallest file",
    "PDF": "One page per image", "ICO": "Windows icon", "ICNS": "macOS app icon",
    "TGA": "Game textures", "QOI": "Fast lossless", "PPM": "Plain pixel map",
    "JP2": "Lossless JPEG 2000",
}

MAX_RAW_BYTES = 1024 ** 3     # the largest real RAW files (150 MP backs) are ~300 MB

# camera information kept from the RAW file's EXIF (no maker notes, serial numbers or GPS)
KEEP_IFD0 = {0x010F, 0x0110, 0x0131, 0x0132, 0x013B, 0x8298}
KEEP_EXIF = {0x829A, 0x829D, 0x8822, 0x8827, 0x8832, 0x9003, 0x9004, 0x9010, 0x9011, 0x9012,
             0x9201, 0x9202, 0x9204, 0x9205, 0x9207, 0x9208, 0x9209, 0x920A, 0x9290, 0x9291,
             0x9292, 0xA402, 0xA403, 0xA405, 0xA406, 0xA433, 0xA434}


def _rawpy_ok() -> bool:
    return importlib.util.find_spec("rawpy") is not None


def _targets(src_ext: str) -> list[str]:
    from ..convert import HEIF_OK
    ext = "." + src_ext.lower().lstrip(".")
    t = list(RAW_TARGETS if ext in RAW_EXTS else PIL_TARGETS)
    if ext == ".icns":
        t.append("ICO")            # Mac icon -> Windows icon
    return [x for x in t if HEIF_OK or x != "HEIC"]


# ---------------------------------------------------------------- reading
def _open_pil(src: Path):
    """Decode a Pillow-readable extra format upright and in sRGB (RGB, RGBA or L)."""
    from PIL import Image, ImageOps
    from ..convert import to_srgb
    formats, name = PIL_EXTS[src.suffix.lower()]
    try:
        with Image.open(src, formats=list(formats)) as im:
            icc = im.info.get("icc_profile")
            im.load()
            im = ImageOps.exif_transpose(im)
            im = to_srgb(im, icc)
            if im.mode not in ("RGB", "RGBA", "L"):
                raise ValueError(im.mode)
            return im
    except Image.DecompressionBombError:
        raise UserError("This image is too large to convert safely.") from None
    except MemoryError:
        raise UserError("This image is too large for the memory available.") from None
    except Exception:
        if src.suffix.lower() == ".psd":
            raise UserError("Can't read this Photoshop file. It may be damaged, or use 16-bit, "
                            "32-bit or Lab colour (save it as 8-bit RGB).") from None
        raise UserError(f"Can't read this {name} file. It may be damaged or not really {name}.") from None


def _develop(src: Path):
    """Full RAW develop: camera white balance, sRGB primaries and tone curve, orientation
    applied. Returns (uint16 H×W×3 or H×W array, embedded JPEG preview bytes or None)."""
    import numpy as np
    import rawpy
    try:
        size = src.stat().st_size
    except OSError:
        raise UserError("Can't open this file.") from None
    if size > MAX_RAW_BYTES:
        raise UserError("This file is far too large to be a camera RAW photo.")
    report_progress(0.05)
    thumb = None
    try:
        # pass the file object: LibRaw then never sees the path (non-ASCII names on Windows)
        with open(src, "rb") as f, rawpy.imread(f) as raw:
            report_progress(0.2)
            rgb = raw.postprocess(use_camera_wb=True, output_color=rawpy.ColorSpace.sRGB,
                                  output_bps=16, gamma=(2.4, 12.92))
            report_progress(0.75)
            try:
                t = raw.extract_thumb()
                if t.format == rawpy.ThumbFormat.JPEG:
                    thumb = bytes(t.data)
            except Exception:
                pass
    except rawpy.LibRawFileUnsupportedError:
        raise UserError("This RAW file isn't supported. It may be damaged, or the camera is "
                        "newer than the RAW decoder.") from None
    except (rawpy.LibRawTooBigError, rawpy.LibRawUnsufficientMemoryError, MemoryError):
        raise UserError("This RAW photo is too large for the memory available.") from None
    except (rawpy.LibRawError, OSError, ValueError):
        raise UserError("Can't read this RAW file. It may be damaged or incomplete.") from None
    rgb = np.asarray(rgb)
    if rgb.ndim == 3 and rgb.shape[2] == 1:
        rgb = rgb[:, :, 0]
    if rgb.dtype != np.uint16 or rgb.ndim not in (2, 3) or min(rgb.shape[:2]) < 1:
        raise UserError("Can't read this RAW file. It may be damaged or incomplete.")
    return rgb, thumb


def _camera_exif(src: Path, thumb: bytes | None):
    """Camera, lens, exposure and capture date from the RAW (or its embedded preview) as a
    fresh, minimal Exif with orientation 1 (the develop already rotated the pixels)."""
    import io
    import warnings
    from PIL import Image
    warnings.filterwarnings("ignore", "Corrupt EXIF", UserWarning)   # odd maker headers
    found = None
    try:
        with open(src, "rb") as f:
            head = f.read(4 << 20)   # TIFF-based RAWs keep IFD0 and the Exif IFD up front
        if head[:4] in (b"II*\0", b"MM\0*"):
            ex = Image.Exif()
            ex.load(head)
            if ex.get(0x010F) or ex.get(0x0110):
                found = ex
    except Exception:
        pass
    if found is None and thumb:
        try:
            with Image.open(io.BytesIO(thumb), formats=["JPEG"]) as t:
                ex = t.getexif()
                if ex.get(0x010F) or ex.get(0x0110):
                    found = ex
        except Exception:
            pass
    if found is None:
        return None
    out = Image.Exif()
    for k in KEEP_IFD0:
        v = found.get(k)
        if isinstance(v, str) and v.strip("\0 "):
            out[k] = v.strip("\0 ")
    out[0x0112] = 1
    try:
        sub = found.get_ifd(0x8769)
        kept = {k: v for k, v in sub.items() if k in KEEP_EXIF and not isinstance(v, bytes)}
        if kept:
            out.get_ifd(0x8769).update(kept)
    except Exception:
        pass
    return out


def _to_8bit(a):
    import numpy as np
    from PIL import Image
    a8 = ((a.astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
    return Image.fromarray(a8, "L" if a8.ndim == 2 else "RGB")


# ---------------------------------------------------------------- writing
def _tiff16_bytes(a, text: dict[int, str]) -> bytes:
    """Baseline 16-bit TIFF (Adobe Deflate + horizontal predictor) tagged with sRGB: Pillow
    can't write 16-bit colour TIFFs. `text` adds ASCII tags (Make, Model, DateTime…)."""
    import struct
    import zlib
    import numpy as np
    from ..convert import _srgb_profile
    h, w = a.shape[:2]
    spp = 1 if a.ndim == 2 else a.shape[2]
    a = np.ascontiguousarray(a.reshape(h, w, spp), dtype="<u2")
    d = a.copy()
    d[:, 1:] -= a[:, :-1]                         # predictor 2; uint16 arithmetic wraps
    rows = max(1, (256 << 10) // (w * spp * 2))
    strips = [zlib.compress(d[y:y + rows].tobytes(), 6) for y in range(0, h, rows)]
    icc = _srgb_profile().tobytes()

    SHORT, LONG, RATIONAL, ASCII, UNDEF = 3, 4, 5, 2, 7
    fmt = {SHORT: "H", LONG: "I", RATIONAL: "I", ASCII: "B", UNDEF: "B"}
    tags: dict[int, tuple[int, list | bytes]] = {
        256: (LONG, [w]), 257: (LONG, [h]), 258: (SHORT, [16] * spp), 259: (SHORT, [8]),
        262: (SHORT, [2 if spp == 3 else 1]), 273: (LONG, [0] * len(strips)), 274: (SHORT, [1]),
        277: (SHORT, [spp]), 278: (LONG, [rows]), 279: (LONG, [len(s) for s in strips]),
        282: (RATIONAL, [300, 1]), 283: (RATIONAL, [300, 1]), 284: (SHORT, [1]),
        296: (SHORT, [2]), 317: (SHORT, [2]), 339: (SHORT, [1] * spp), 34675: (UNDEF, icc),
    }
    for k, v in text.items():
        tags[k] = (ASCII, v.encode("ascii", "replace") + b"\0")

    def payload(typ, vals) -> bytes:
        return bytes(vals) if isinstance(vals, bytes) else struct.pack(f"<{len(vals)}{fmt[typ]}", *vals)

    def count(typ, vals) -> int:
        return len(vals) // 2 if typ == RATIONAL else len(vals)

    order = sorted(tags)
    ifd_size = 2 + 12 * len(order) + 4
    extra_at = 8 + ifd_size
    # pass 1: place out-of-line values; strip offsets need the final data position
    blobs: dict[int, int] = {}
    pos = extra_at
    for k in order:
        n = len(payload(*tags[k]))
        if n > 4:
            pos += pos & 1
            blobs[k] = pos
            pos += n
    pos += pos & 1
    offsets, p = [], pos
    for s in strips:
        offsets.append(p)
        p += len(s)
    tags[273] = (LONG, offsets)

    out = bytearray(b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", len(order)))
    extra = bytearray()
    for k in order:
        typ, vals = tags[k]
        data = payload(typ, vals)
        if len(data) > 4:
            value = struct.pack("<I", blobs[k])
            pad = blobs[k] - extra_at - len(extra)
            extra += b"\0" * pad + data
        else:
            value = data.ljust(4, b"\0")
        out += struct.pack("<HHI", k, typ, count(typ, vals)) + value
    out += struct.pack("<I", 0) + extra
    out += b"\0" * (pos - len(out))
    for s in strips:
        out += s
    return bytes(out)


def save_extra(im, out, target: str) -> None:
    """Write `im` (any Pillow image, ideally already sRGB) as ICNS, TGA, QOI, PPM or JP2."""
    from PIL import Image, features
    from ..convert import atomic_save, flatten, to_srgb
    t = target.upper()
    if t not in EXTRA_TARGETS:
        raise ValueError(f"save_extra can't write {target}")
    if im.mode not in ("RGB", "RGBA", "L"):
        im = to_srgb(im, im.info.get("icc_profile"))
    kw: dict = {}
    if t == "ICNS":
        # square canvas (transparent padding), 1024 px master: Pillow derives 16…512 from it
        src = im.convert("RGBA")
        side = max(src.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
        im = canvas if side == 1024 else canvas.resize((1024, 1024), Image.LANCZOS)
    elif t == "PPM":
        im = flatten(im)                      # P6: RGB only
    elif t == "QOI":
        im = im if im.mode in ("RGB", "RGBA") else im.convert("RGB")
    elif t == "JP2":
        if not features.check_codec("jpg_2000"):
            raise UserError("JPEG 2000 isn't available in this build.")
        kw.update(no_jp2=False, irreversible=False)    # lossless, .jp2 container
    atomic_save(lambda dst: im.save(dst, EXTRA_TARGETS[t], **kw), out)


def _write(im, src: Path, t: str, exif=None) -> Path:
    from ..convert import save_image, write_images_pdf
    out = sibling(src, ext="." + t.lower())
    if t in EXTRA_TARGETS:
        save_extra(im, out, t)
    elif t == "PDF":
        write_images_pdf([im], out)
    else:
        save_image(im, out, t, exif=exif.tobytes() if exif is not None else None)
    return out


def _raw_to(src: Path, t: str) -> list[Path]:
    from ..convert import atomic_save, save_image, write_images_pdf
    a16, thumb = _develop(src)
    exif = _camera_exif(src, thumb)
    if t == "TIFF":
        text = {}
        if exif is not None:
            text = {k: exif[k] for k in (0x010F, 0x0110, 0x0131, 0x0132, 0x013B, 0x8298) if k in exif}
            text = {k: v for k, v in text.items() if isinstance(v, str) and v.isascii()}
        data = _tiff16_bytes(a16, text)
        out = sibling(src, ext=".tiff")
        atomic_save(lambda dst: Path(dst).write_bytes(data), out)
        report_progress(1.0)
        return [out]
    im = _to_8bit(a16)
    del a16
    if t == "PDF":
        # a developed photo: embed a visually lossless 4:4:4 JPEG, as the main module does
        # for lossy sources (a lossless PNG page would be ~5x larger)
        out = sibling(src, ext=".pdf")
        with tempfile.TemporaryDirectory() as tmp:
            jpg = Path(tmp) / "page.jpg"
            save_image(im, jpg, "JPG", quality=95)
            write_images_pdf([jpg], out)
        report_progress(1.0)
        return [out]
    out = _write(im, src, t, exif)
    report_progress(1.0)
    return [out]


def _convert(src: Path, target: str) -> list[Path]:
    from ..convert import HEIF_OK
    src = Path(src)
    t = target.upper()
    ext = src.suffix.lower()
    if t == "HEIC" and not HEIF_OK:
        raise UserError("HEIC isn't available on this computer.")
    if ext in RAW_EXTS:
        if t not in RAW_TARGETS and t not in EXTRA_TARGETS:
            raise UserError(f"Can't turn a RAW photo into {t}.")
        return _raw_to(src, t)
    if ext not in PIL_EXTS:
        raise UserError("This file type isn't supported here.")
    if t not in MAIN_TARGETS and t not in EXTRA_TARGETS:
        raise UserError(f"Can't convert this image to {t}.")
    return [_write(_open_pil(src), src, t)]


register(Family(
    category="rawimage",
    label="Pro image",
    exts=(RAW_EXTS if _rawpy_ok() else set()) | set(PIL_EXTS),
    targets=_targets,
    convert=_convert,
    hints=HINTS,
))
