"""Camera RAW + Pillow-extra image family (dropdial/formats/rawimages.py).

RAW: rawpy can't write RAW files and binary fixtures aren't allowed, so the tests build a
real (tiny) DNG byte by byte: a Bayer RGGB mosaic with DNG colour tags, an Exif IFD, a GPS IFD
and a maker note. That runs through the real LibRaw develop. The rawpy boundary is also mocked
to check develop parameters, error mapping and that the low-res preview is never used for pixels.
"""
from __future__ import annotations

import io
import os
import struct
import subprocess
import sys
import types
import zlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from dropdial import convert, util
from dropdial.formats import rawimages as ri
from dropdial.util import UserError

HAS_RAWPY = ri._rawpy_ok()
needs_rawpy = pytest.mark.skipif(not HAS_RAWPY, reason="rawpy not installed")


# ---------------------------------------------------------------- tiny TIFF/DNG builder
_FMT = {1: "B", 2: "B", 3: "H", 4: "I", 5: "I", 7: "B", 9: "i", 10: "i"}


def _enc(typ, vals):
    if isinstance(vals, str):
        vals = vals.encode() + b"\0"
    if isinstance(vals, bytes):
        return vals, len(vals)
    b = struct.pack(f"<{len(vals)}{_FMT[typ]}", *vals)
    return b, (len(vals) // 2 if typ in (5, 10) else len(vals))


def _ifd(tags: dict, start: int) -> bytes:
    data_at = start + 2 + 12 * len(tags) + 4
    entries, extra = b"", b""
    for tag in sorted(tags):
        typ, vals = tags[tag]
        b, n = _enc(typ, vals)
        if len(b) <= 4:
            val = b.ljust(4, b"\0")
        else:
            if (data_at + len(extra)) % 2:
                extra += b"\0"
            val = struct.pack("<I", data_at + len(extra))
            extra += b
        entries += struct.pack("<HHI", tag, typ, n) + val
    return struct.pack("<H", len(tags)) + entries + struct.pack("<I", 0) + extra


def _tiff(ifd0: dict, subs: dict[int, dict], strip: bytes) -> bytes:
    """IFD0 + sub-IFDs (Exif 0x8769, GPS 0x8825) + one image strip, little endian."""
    def layout(ptrs, strip_at):
        t0 = {**ifd0, **{k: (4, [v]) for k, v in ptrs.items()}}
        t0[273] = (4, [strip_at])
        t0[279] = (4, [len(strip)])
        blocks, pos = [(8, t0)], 8 + len(_ifd(t0, 8))
        for k, tags in subs.items():
            pos += pos & 1
            blocks.append((pos, tags))
            ptrs[k] = pos
            pos += len(_ifd(tags, pos))
        return blocks, pos + (pos & 1)
    ptrs = {k: 0 for k in subs}
    _, strip_at = layout(ptrs, 0)
    blocks, strip_at = layout(ptrs, strip_at)       # sizes don't depend on offset values
    out = bytearray(b"II*\0" + struct.pack("<I", 8))
    for at, tags in blocks:
        out += b"\0" * (at - len(out))
        out += _ifd(tags, at)
    out += b"\0" * (strip_at - len(out))
    return bytes(out + strip)


def _rat(vals):
    out = []
    for v in vals:
        out += [int(round(v * 10000)), 10000]
    return out


XYZ_TO_SRGB = [3.2406, -1.5372, -0.4986, -0.9689, 1.8758, 0.0415, 0.0557, -0.2040, 1.0570]


def make_dng(path: Path, w=64, h=48, orientation=1) -> Path:
    """Bayer RGGB scene: top quarter grey, below it left half red, right half blue.
    The colour matrix makes camera RGB = linear sRGB, so colours come out as authored."""
    lin = np.zeros((h, w, 3))
    lin[:, : w // 2] = (0.8, 0.1, 0.1)
    lin[:, w // 2:] = (0.1, 0.1, 0.8)
    lin[: h // 4] = (0.5, 0.5, 0.5)
    white = 4095
    cfa = np.zeros((h, w), np.uint16)
    cfa[0::2, 0::2] = lin[0::2, 0::2, 0] * white
    cfa[0::2, 1::2] = lin[0::2, 1::2, 1] * white
    cfa[1::2, 0::2] = lin[1::2, 0::2, 1] * white
    cfa[1::2, 1::2] = lin[1::2, 1::2, 2] * white
    ifd0 = {
        254: (4, [0]), 256: (4, [w]), 257: (4, [h]), 258: (3, [16]), 259: (3, [1]),
        262: (3, [32803]), 271: (2, "DropDialTest"), 272: (2, "Cam 1"), 274: (3, [orientation]),
        277: (3, [1]), 278: (4, [h]), 284: (3, [1]), 306: (2, "2024:05:06 07:08:09"),
        33421: (3, [2, 2]), 33422: (1, [0, 1, 1, 2]),
        50706: (1, [1, 4, 0, 0]), 50708: (2, "DropDial Test Cam"), 50714: (4, [0]),
        50717: (4, [white]), 50721: (10, _rat(XYZ_TO_SRGB)), 50728: (5, _rat([1, 1, 1])),
        50778: (3, [21]),
    }
    exif = {0x829D: (5, [28, 10]), 0x8827: (3, [200]), 0x9003: (2, "2024:05:06 07:08:09"),
            0x927C: (7, b"SECRET-MAKERNOTE" * 4)}
    gps = {0x0001: (2, "N"), 0x0002: (5, [12, 1, 34, 1, 56, 1])}
    path.write_bytes(_tiff(ifd0, {0x8769: exif, 0x8825: gps}, cfa.astype("<u2").tobytes()))
    return path


def rawpy_develop16(path: Path):
    import rawpy
    with rawpy.imread(str(path)) as raw:
        return raw.postprocess(use_camera_wb=True, output_color=rawpy.ColorSpace.sRGB,
                               output_bps=16, gamma=(2.4, 12.92))


def read_tiff16(path: Path) -> tuple[np.ndarray, dict]:
    """Independent reader for our 16-bit TIFF output: parse IFD, inflate strips, undo predictor."""
    b = path.read_bytes()
    assert b[:4] == b"II*\0"
    ifd = struct.unpack_from("<I", b, 4)[0]
    n = struct.unpack_from("<H", b, ifd)[0]
    size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1}
    tags = {}
    for i in range(n):
        tag, typ, cnt = struct.unpack_from("<HHI", b, ifd + 2 + 12 * i)
        nbytes = size[typ] * cnt
        at = ifd + 2 + 12 * i + 8 if nbytes <= 4 else struct.unpack_from("<I", b, ifd + 10 + 12 * i)[0]
        raw = b[at: at + nbytes]
        if typ == 2:
            tags[tag] = raw.rstrip(b"\0").decode()
        elif typ == 7:
            tags[tag] = raw
        else:
            c = {1: "B", 3: "H", 4: "I", 5: "I"}[typ]
            tags[tag] = list(struct.unpack(f"<{len(raw) // struct.calcsize(c)}{c}", raw))
    w, h, spp = tags[256][0], tags[257][0], tags[277][0]
    assert tags[258] == [16] * spp and tags[259] == [8] and tags[317] == [2]
    data = b"".join(zlib.decompress(b[o: o + c]) for o, c in zip(tags[273], tags[279]))
    a = np.frombuffer(data, "<u2").reshape(h, w, spp)
    a = np.cumsum(a, axis=1, dtype=np.uint64).astype(np.uint64) % 65536
    return a.astype(np.uint16), tags


# ---------------------------------------------------------------- RAW: real LibRaw develop
@needs_rawpy
def test_dng_registered_and_targets():
    assert util.category("photo.DNG") == "rawimage"
    for ext in ri.RAW_EXTS:
        assert util.category("x" + ext) == "rawimage", ext
    t = convert.targets_for("rawimage", "dng")
    assert t[:3] == ["JPG", "TIFF", "PNG"] and "PDF" in t and len(t) <= 9
    assert ("HEIC" in t) == convert.HEIF_OK


@needs_rawpy
def test_dng_to_jpg_colour_orientation_and_exif(tmp_path):
    src = make_dng(tmp_path / "shot.dng", orientation=6)     # camera held rotated 90° CW
    before = src.read_bytes()
    [out] = convert.convert(src, "rawimage", "JPG")
    assert out.name == "shot.jpg" and src.read_bytes() == before
    im = Image.open(out)
    assert im.format == "JPEG" and im.size == (48, 64)      # width/height swapped by the flip
    px = np.asarray(im.convert("RGB")).astype(int)
    red, blue, grey = px[4:24, 4:20].mean((0, 1)), px[44:60, 4:20].mean((0, 1)), px[10:50, 40:46].mean((0, 1))
    assert red[0] > 200 and red[1] < 140 and red[2] < 140           # original left half -> top
    assert blue[2] > 200 and blue[0] < 140 and blue[1] < 140        # original right half -> bottom
    assert grey.max() - grey.min() < 12 and grey.mean() > 120       # original top band -> right
    ex = im.getexif()
    assert ex.get(0x010F) == "DropDialTest" and ex.get(0x0110) == "Cam 1"
    assert ex.get(0x0112) == 1                                      # pixels already upright
    sub = ex.get_ifd(0x8769)
    assert sub.get(0x9003) == "2024:05:06 07:08:09" and sub.get(0x8827) == 200
    assert float(sub.get(0x829D)) == pytest.approx(2.8)
    assert 0x927C not in sub and not ex.get_ifd(0x8825)            # no maker note, no GPS
    assert b"SECRET-MAKERNOTE" not in out.read_bytes()


@needs_rawpy
def test_dng_to_png_is_exact_8bit_of_full_develop(tmp_path):
    src = make_dng(tmp_path / "a.dng")
    [out] = convert.convert(src, "rawimage", "PNG")
    got = np.asarray(Image.open(out).convert("RGB")).astype(int)
    ref = np.round(rawpy_develop16(src) / 257.0).astype(int)
    assert got.shape == ref.shape == (48, 64, 3)
    assert np.abs(got - ref).max() <= 1


@needs_rawpy
def test_dng_to_tiff_is_16bit_srgb_full_resolution(tmp_path):
    src = make_dng(tmp_path / "wide.dng", w=1200, h=200)   # several deflate strips
    [out] = convert.convert(src, "rawimage", "TIFF")
    a, tags = read_tiff16(out)
    ref = rawpy_develop16(src)
    assert a.shape == ref.shape == (200, 1200, 3)
    assert np.array_equal(a, ref)
    assert len(tags[273]) > 1 and tags[262] == [2] and tags[274] == [1]
    assert tags[271] == "DropDialTest" and tags[272] == "Cam 1"
    from PIL import ImageCms
    prof = ImageCms.ImageCmsProfile(io.BytesIO(tags[34675]))
    assert "srgb" in ImageCms.getProfileDescription(prof).lower()
    assert (a % 257).any()                         # really 16-bit, not 8-bit scaled up
    im = Image.open(out)                                            # libtiff reads it too
    im.load()
    assert im.size == (1200, 200)
    try:
        import tifffile
    except ImportError:
        return
    assert np.array_equal(tifffile.imread(out), ref)


@needs_rawpy
@pytest.mark.parametrize("target", ["WEBP", "AVIF", "HEIC"])
def test_dng_to_other_photo_formats(tmp_path, target):
    if target == "HEIC" and not convert.HEIF_OK:
        pytest.skip("no HEIF")
    src = make_dng(tmp_path / "p.dng")
    [out] = convert.convert(src, "rawimage", target)
    assert out.suffix == "." + target.lower()
    im = Image.open(out)
    assert im.size == (64, 48)
    px = np.asarray(im.convert("RGB")).astype(int)
    ref = np.round(rawpy_develop16(src) / 257.0).astype(int)
    assert np.abs(px[16:44, 4:28].mean((0, 1)) - ref[16:44, 4:28].mean((0, 1))).max() < 12


@needs_rawpy
def test_dng_to_pdf_one_page_full_resolution_jpeg(tmp_path):
    import pymupdf
    src = make_dng(tmp_path / "doc.dng")
    [out] = convert.convert(src, "rawimage", "PDF")
    with pymupdf.open(out) as doc:
        assert doc.page_count == 1
        page = doc[0]
        assert page.rect.width / page.rect.height == pytest.approx(64 / 48, rel=1e-3)
        [img] = page.get_images()
        info = doc.extract_image(img[0])
        assert info["ext"] == "jpeg" and (info["width"], info["height"]) == (64, 48)
        pix = page.get_pixmap(dpi=150)
        r, g, b = pix.pixel(pix.width // 6, pix.height * 2 // 3)
        assert r > 200 and g < 140 and b < 140


@needs_rawpy
def test_raw_unicode_filename_and_never_overwrites(tmp_path):
    src = make_dng(tmp_path / "फोटो 写真 📷.nef")       # content decides, not the extension
    a = convert.convert(src, "rawimage", "JPG")[0]
    b = convert.convert(src, "rawimage", "JPG")[0]
    assert a.name == "फोटो 写真 📷.jpg" and b.name == "फोटो 写真 📷 (1).jpg"
    assert Image.open(b).size == (64, 48)


@needs_rawpy
@pytest.mark.parametrize("data", [b"", os.urandom(5000), b"II*\0" + os.urandom(3000)])
def test_corrupt_raw_is_friendly(tmp_path, data):
    src = tmp_path / "bad.cr2"
    src.write_bytes(data)
    with pytest.raises(UserError):
        convert.convert(src, "rawimage", "JPG")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.cr2"]


@needs_rawpy
def test_cli_converts_raw(tmp_path):
    src = make_dng(tmp_path / "cli.dng")
    r = subprocess.run([sys.executable, "-m", "dropdial", "convert", str(src), "--to", "JPG"],
                       capture_output=True, text=True, cwd=Path(__file__).parent.parent,
                       env=dict(os.environ, QT_QPA_PLATFORM="offscreen"), timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert Image.open(tmp_path / "cli.jpg").size == (64, 48)


# ---------------------------------------------------------------- RAW: mocked rawpy boundary
def _fake_rawpy(arr=None, thumb=None, error=None):
    m = types.ModuleType("rawpy")

    class LibRawError(Exception):
        pass

    for name in ("LibRawFileUnsupportedError", "LibRawTooBigError", "LibRawUnsufficientMemoryError",
                 "LibRawIOError", "LibRawDataError"):
        setattr(m, name, type(name, (LibRawError,), {}))
    m.LibRawError = LibRawError
    m.ColorSpace = types.SimpleNamespace(sRGB="sRGB")
    m.ThumbFormat = types.SimpleNamespace(JPEG="jpeg", BITMAP="bitmap")
    m.calls = []

    class Raw:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def postprocess(self, **kw):
            m.calls.append(kw)
            if error:
                raise getattr(m, error)("boom")
            return arr

        def extract_thumb(self):
            return types.SimpleNamespace(format=m.ThumbFormat.JPEG, data=thumb)

    def imread(f):
        assert hasattr(f, "read"), "rawpy must get a file object, not a path"
        return Raw()

    m.imread = imread
    return m


def _jpeg_with_exif(make: str) -> bytes:
    ex = Image.Exif()
    ex[0x010F] = make
    ex[0x0110] = "Model X"
    ex.get_ifd(0x8769)[0x9003] = "2023:01:02 03:04:05"
    b = io.BytesIO()
    Image.new("RGB", (16, 12), (0, 255, 0)).save(b, "JPEG", exif=ex.tobytes())
    return b.getvalue()


def test_mock_develop_params_and_full_res_pixels_not_preview(tmp_path, monkeypatch):
    h, w = 30, 40
    yy, xx = np.mgrid[0:h, 0:w]
    arr = np.stack([xx * 1600, yy * 2200, np.full((h, w), 30000)], -1).astype(np.uint16)
    fake = _fake_rawpy(arr, thumb=_jpeg_with_exif("ThumbCam"))
    monkeypatch.setitem(sys.modules, "rawpy", fake)
    src = tmp_path / "x.cr3"
    src.write_bytes(b"\0\0\0\x18ftypcrx " + b"\0" * 100)       # ISO-BMFF style, not TIFF
    [out] = ri._convert(src, "PNG")
    assert fake.calls == [dict(use_camera_wb=True, output_color="sRGB", output_bps=16, gamma=(2.4, 12.92))]
    im = Image.open(out)
    assert im.size == (40, 30)                                      # develop, not the 16×12 preview
    got = np.asarray(im.convert("RGB")).astype(int)
    assert np.abs(got - np.round(arr / 257.0)).max() <= 1
    ex = im.getexif()
    assert ex.get(0x010F) == "ThumbCam" and ex.get_ifd(0x8769).get(0x9003) == "2023:01:02 03:04:05"


def test_mock_monochrome_develop_to_tiff(tmp_path, monkeypatch):
    arr = (np.arange(20 * 10, dtype=np.uint32).reshape(10, 20) * 300).astype(np.uint16)[..., None]
    monkeypatch.setitem(sys.modules, "rawpy", _fake_rawpy(arr))
    src = tmp_path / "mono.dng"
    src.write_bytes(b"MM\0*" + b"\0" * 64)
    [out] = ri._convert(src, "TIFF")
    a, tags = read_tiff16(out)
    assert tags[262] == [1] and a.shape == (10, 20, 1) and np.array_equal(a[..., 0], arr[..., 0])


@pytest.mark.parametrize("error,needle", [("LibRawFileUnsupportedError", "isn't supported"),
                                          ("LibRawTooBigError", "too large"),
                                          ("LibRawDataError", "damaged")])
def test_mock_libraw_errors_become_user_errors(tmp_path, monkeypatch, error, needle):
    monkeypatch.setitem(sys.modules, "rawpy", _fake_rawpy(error=error))
    src = tmp_path / "e.arw"
    src.write_bytes(b"x" * 100)
    with pytest.raises(UserError, match=needle):
        ri._convert(src, "JPG")
    assert [p.name for p in tmp_path.iterdir()] == ["e.arw"]


def test_raw_rejects_unknown_target(tmp_path):
    src = tmp_path / "a.orf"
    src.write_bytes(b"x")
    with pytest.raises(UserError):
        ri._convert(src, "DOCX")


# ---------------------------------------------------------------- PSD (hand-built)
def _packbits(row: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(row):
        j = i
        while j < len(row) and j - i < 128 and row[j] == row[i]:
            j += 1
        if j - i >= 3:
            out += bytes([257 - (j - i), row[i]])
            i = j
            continue
        j = i
        while j < len(row) and j - i < 128 and not (j + 2 < len(row) and row[j] == row[j + 1] == row[j + 2]):
            j += 1
        out += bytes([j - i - 1]) + row[i:j]
        i = j
    return bytes(out)


def make_psd(path: Path, arr: np.ndarray, mode=3, depth=8, rle=False, icc: bytes | None = None) -> Path:
    if arr.ndim == 2:
        arr = arr[..., None]
    h, w, c = arr.shape
    out = b"8BPS" + struct.pack(">H6xHIIHH", 1, c, h, w, depth, mode)
    out += struct.pack(">I", 0)                                  # colour mode data
    res = b""
    if icc:
        res = b"8BIM" + struct.pack(">H", 1039) + b"\0\0" + struct.pack(">I", len(icc)) + icc
        res += b"\0" * (len(icc) & 1)
    out += struct.pack(">I", len(res)) + res
    out += struct.pack(">II", 4, 0)                              # layer/mask info: no layers
    planes = [np.ascontiguousarray(arr[..., i]) for i in range(c)]
    if rle:
        rows = [_packbits(p[y].tobytes()) for p in planes for y in range(h)]
        out += struct.pack(">H", 1) + b"".join(struct.pack(">H", len(r)) for r in rows) + b"".join(rows)
    else:
        out += struct.pack(">H", 0) + b"".join(p.tobytes() for p in planes)
    path.write_bytes(out)
    return path


def _pattern(h=37, w=53, c=3, seed=1):
    rng = np.random.default_rng(seed)
    a = rng.integers(0, 256, (h, w, c), dtype=np.uint8)
    a[:10, :20] = 200                                            # runs for PackBits
    return a


@pytest.mark.parametrize("rle", [False, True])
def test_psd_rgb_composite_exact(tmp_path, rle):
    arr = _pattern()
    src = make_psd(tmp_path / "art.psd", arr, rle=rle)
    assert util.category(src) == "rawimage"
    [out] = convert.convert(src, "rawimage", "PNG")
    got = np.asarray(Image.open(out))
    assert got.shape == arr.shape and np.array_equal(got, arr)


def test_psd_rgba_keeps_alpha_and_grey(tmp_path):
    arr = _pattern(c=4, seed=2)
    [out] = ri._convert(make_psd(tmp_path / "a.psd", arr, rle=True), "PNG")
    im = Image.open(out)
    assert im.mode == "RGBA" and np.array_equal(np.asarray(im), arr)
    g = _pattern(c=1, seed=3)[..., 0]
    [out] = ri._convert(make_psd(tmp_path / "g.psd", g, mode=1), "PNG")
    assert np.array_equal(np.asarray(Image.open(out).convert("L")), g)


def test_psd_icc_profile_is_applied(tmp_path, monkeypatch):
    seen = {}
    real = convert.to_srgb

    def spy(im, icc):
        seen["icc"] = icc
        return real(im, icc)
    monkeypatch.setattr(convert, "to_srgb", spy)
    from PIL import ImageCms
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    arr = _pattern(seed=4)
    [out] = ri._convert(make_psd(tmp_path / "p.psd", arr, icc=icc), "PNG")
    assert seen["icc"] == icc
    assert np.abs(np.asarray(Image.open(out)).astype(int) - arr).max() <= 2   # sRGB -> sRGB


def test_psd_all_targets(tmp_path):
    import pymupdf
    arr = _pattern(seed=5)
    src = make_psd(tmp_path / "all.psd", arr)
    targets = convert.targets_for("rawimage", "psd")
    assert "PSD" not in targets and len(targets) <= 9
    for t in targets:
        [out] = convert.convert(src, "rawimage", t)
        assert out.suffix == "." + t.lower()
        if t == "PDF":
            with pymupdf.open(out) as doc:
                assert doc.page_count == 1
                [img] = doc[0].get_images()
                info = doc.extract_image(img[0])
                assert (info["width"], info["height"]) == (53, 37) and info["ext"] == "png"
                dec = np.asarray(Image.open(io.BytesIO(info["image"])).convert("RGB"))
                assert np.array_equal(dec, arr)                        # lossless page
            continue
        im = Image.open(out)
        assert im.size == (53, 37)
        px = np.asarray(im.convert("RGB")).astype(int)
        if t in ("PNG", "TIFF"):
            assert np.array_equal(px, arr)
        else:   # lossy: compare the flat region and overall mean
            assert np.abs(px[1:9, 1:19].mean((0, 1)) - 200).max() < 8
            assert abs(px.mean() - arr.mean()) < 6


def test_psd_16bit_and_truncated_are_friendly(tmp_path):
    src = make_psd(tmp_path / "deep.psd", _pattern(), depth=16)
    with pytest.raises(UserError, match="16-bit"):
        ri._convert(src, "PNG")
    good = make_psd(tmp_path / "t.psd", _pattern(), rle=True).read_bytes()
    (tmp_path / "t.psd").write_bytes(good[: len(good) // 2])
    with pytest.raises(UserError):
        ri._convert(tmp_path / "t.psd", "PNG")
    (tmp_path / "junk.psd").write_bytes(b"not a psd at all")
    with pytest.raises(UserError, match="Photoshop"):
        ri._convert(tmp_path / "junk.psd", "PNG")


# ---------------------------------------------------------------- other Pillow extras
def _write_pil(path: Path, im: Image.Image, fmt: str, **kw) -> Path:
    im.save(path, fmt, **kw)
    return path


ROUND_TRIPS = [
    ("tga", "TGA", "RGBA"), ("tga", "TGA", "RGB"), ("ppm", "PPM", "RGB"), ("pgm", "PPM", "L"),
    ("pbm", "PPM", "1"), ("pnm", "PPM", "RGB"), ("qoi", "QOI", "RGBA"), ("pcx", "PCX", "RGB"),
    ("dds", "DDS", "RGBA"), ("dds", "DDS", "RGB"), ("sgi", "SGI", "RGB"), ("rgb", "SGI", "RGB"),
    ("xbm", "XBM", "1"), ("jp2", "JPEG2000", "RGB"), ("j2k", "JPEG2000", "RGBA"),
]


@pytest.mark.parametrize("ext,fmt,mode", ROUND_TRIPS)
def test_pillow_extras_round_trip_to_png(tmp_path, ext, fmt, mode):
    arr = _pattern(c=4, seed=hash(ext) % 1000)
    im = Image.fromarray(arr, "RGBA").convert(mode)
    kw = {"no_jp2": ext == "j2k", "irreversible": False} if fmt == "JPEG2000" else {}
    src = _write_pil(tmp_path / f"src.{ext}", im, fmt, **kw)
    assert util.category(src) == "rawimage"
    [out] = convert.convert(src, "rawimage", "PNG")
    got = Image.open(out)
    assert got.size == (53, 37)
    want = im.convert("L" if mode in ("1", "L") else mode)
    have = got.convert(want.mode)
    assert np.array_equal(np.asarray(have), np.asarray(want)), (ext, mode)


def test_icns_source_to_png_and_ico(tmp_path):
    base = Image.fromarray(_pattern(64, 64, 4, seed=9), "RGBA")
    src = _write_pil(tmp_path / "App.icns", base, "ICNS")
    assert "ICO" in convert.targets_for("rawimage", "icns")
    [png] = convert.convert(src, "rawimage", "PNG")
    im = Image.open(png)
    assert im.size == (1024, 1024) and im.mode == "RGBA"         # the largest icon inside
    [ico] = convert.convert(src, "rawimage", "ICO")
    ic = Image.open(ico)
    assert ic.format == "ICO" and (256, 256) in ic.info["sizes"]


def test_unicode_name_for_extras(tmp_path):
    src = _write_pil(tmp_path / "テクスチャ 🎮 बनावट.tga", Image.new("RGB", (9, 7), (1, 2, 3)), "TGA")
    [out] = convert.convert(src, "rawimage", "JPG")
    assert out.name == "テクスチャ 🎮 बनावट.jpg" and Image.open(out).size == (9, 7)


def test_renamed_eps_is_never_handed_to_ghostscript(tmp_path, monkeypatch):
    from PIL import EpsImagePlugin

    def boom(*a, **k):
        raise AssertionError("EPS decoder must not run")
    monkeypatch.setattr(EpsImagePlugin.EpsImageFile, "_open", boom)
    src = tmp_path / "evil.tga"
    src.write_bytes(b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n")
    with pytest.raises(UserError, match="TGA"):
        ri._convert(src, "PNG")


def test_decompression_bomb_header_is_refused(tmp_path):
    # TGA header claiming 60000 x 60000 truecolour pixels, no data
    hdr = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, 60000, 60000, 24, 0x20)
    src = tmp_path / "bomb.tga"
    src.write_bytes(hdr + b"\0" * 64)
    with pytest.raises(UserError, match="too large"):
        ri._convert(src, "PNG")
    assert [p.name for p in tmp_path.iterdir()] == ["bomb.tga"]


def test_family_claims_no_main_image_formats():
    fam = ri.register.__globals__["FAMILIES"]["rawimage"]
    assert not fam.exts & util.IMAGE_EXTS
    assert util.category("x.png") == "image" and util.category("x.tif") == "image"
    for ext in ri.PIL_EXTS:
        t = convert.targets_for("rawimage", ext)
        assert 0 < len(t) <= 9 and ext.lstrip(".").upper() not in t
        for name in t:
            assert len(fam.hints[name]) <= 22


# ---------------------------------------------------------------- save_extra (ICNS/TGA/QOI/PPM/JP2)
def test_save_extra_icns_square_padded_1024(tmp_path):
    im = Image.new("RGBA", (64, 32), (220, 30, 40, 255))
    out = tmp_path / "icon.icns"
    ri.save_extra(im, out, "ICNS")
    b = out.read_bytes()
    assert b[:4] == b"icns" and struct.unpack(">I", b[4:8])[0] == len(b)
    types_, pos = [], 8
    while pos < len(b):                                    # walk the element list by hand
        typ, ln = b[pos:pos + 4], struct.unpack(">I", b[pos + 4:pos + 8])[0]
        assert ln >= 8
        types_.append(typ)
        pos += ln
    assert pos == len(b) and b"ic10" in types_ and b"ic09" in types_
    r = Image.open(out)
    assert r.size == (1024, 1024)
    r.load()
    a = np.asarray(r.convert("RGBA")).astype(int)
    assert a[5, 512, 3] == 0 and a[1018, 512, 3] == 0        # transparent padding top/bottom
    assert np.abs(a[512, 512] - [220, 30, 40, 255]).max() <= 2
    assert np.abs(a[300, 5] - [220, 30, 40, 255]).max() <= 2 # image spans the full width


def test_save_extra_icns_downscales_big_images(tmp_path):
    out = tmp_path / "big.icns"
    ri.save_extra(Image.new("RGB", (2000, 1500), (0, 128, 255)), out, "ICNS")
    assert Image.open(out).size == (1024, 1024)


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L"])
def test_save_extra_tga_qoi_ppm_jp2_round_trip(tmp_path, mode):
    im = Image.fromarray(_pattern(c=4, seed=7), "RGBA").convert(mode)
    for target, magic in (("TGA", None), ("QOI", b"qoif"), ("PPM", b"P6"), ("JP2", b"\0\0\0\x0cjP  ")):
        out = tmp_path / f"o-{mode}.{target.lower()}"
        ri.save_extra(im, out, target)
        b = out.read_bytes()
        if magic:
            assert b.startswith(magic), target
        r = Image.open(out)
        assert r.size == (53, 37)
        if target == "TGA":
            assert struct.unpack("<HH", b[12:16]) == (53, 37)
        if target == "QOI":
            assert struct.unpack(">II", b[4:12]) == (53, 37)
        want = im
        if target == "PPM":
            want = convert.flatten(im)
        elif target == "QOI" and mode == "L":
            want = im.convert("RGB")
        assert np.array_equal(np.asarray(r.convert(want.mode)), np.asarray(want)), (target, mode)


def test_extra_targets_via_convert_and_bad_target(tmp_path):
    src = make_psd(tmp_path / "s.psd", _pattern(seed=11))
    for t in ("TGA", "QOI", "PPM", "JP2", "ICNS"):
        [out] = ri._convert(src, t)
        assert out.suffix == "." + t.lower() and Image.open(out).size in ((53, 37), (1024, 1024))
    with pytest.raises(UserError):
        ri._convert(src, "MP3")
    with pytest.raises(ValueError):
        ri.save_extra(Image.new("RGB", (2, 2)), tmp_path / "x.bin", "XYZ")


# ---------------------------------------------------------------- 16-bit TIFF writer
def test_tiff16_writer_unit(tmp_path):
    rng = np.random.default_rng(0)
    for shape in ((3, 5, 3), (257, 300, 3), (40, 7)):
        a = rng.integers(0, 65536, shape, dtype=np.uint16)
        out = tmp_path / f"t{len(shape)}-{shape[0]}.tiff"
        out.write_bytes(ri._tiff16_bytes(a, {271: "Ünïcode Make", 272: "M"}))
        got, tags = read_tiff16(out)
        assert np.array_equal(got.reshape(a.shape), a)
        assert tags[272] == "M" and tags[271].startswith("?n")      # non-ASCII made safe
        Image.open(out).load()
