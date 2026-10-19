"""Regression tests for output fidelity: colours, orientation, sizes and streams must match the
original, not just "a file was written". Each test pins a bug that was found and fixed."""
import io
import struct
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageCms, ImageDraw, ImageOps

from dropdial import convert, imaging, media
from dropdial.util import NotSmaller

fitz = convert.fitz
needs_ffmpeg = pytest.mark.skipif(not media.available(), reason="ffmpeg not available")
SRGB = ImageCms.createProfile("sRGB")
INTENT = ImageCms.Intent.RELATIVE_COLORIMETRIC


# ---------------------------------------------------------------- helpers
def wide_gamut_icc() -> bytes:
    """A minimal ICC v2 display profile with Display P3 primaries (D50-adapted), gamma 2.2.
    Generated here so the tests need no third-party profile files."""
    def s15(v):
        return struct.pack(">i", int(round(v * 65536)))

    def xyz(x, y, z):
        return b"XYZ " + b"\0" * 4 + s15(x) + s15(y) + s15(z)

    desc_txt = b"Wide gamut test\0"
    desc = (b"desc" + b"\0" * 4 + struct.pack(">I", len(desc_txt)) + desc_txt
            + struct.pack(">II", 0, 0) + struct.pack(">HB", 0, 0) + b"\0" * 67)
    tags = [(b"desc", desc), (b"cprt", b"text" + b"\0" * 4 + b"none\0"),
            (b"wtpt", xyz(0.9642, 1.0, 0.8249)),
            (b"rXYZ", xyz(0.5151, 0.2412, -0.0011)), (b"gXYZ", xyz(0.2920, 0.6922, 0.0419)),
            (b"bXYZ", xyz(0.1571, 0.0666, 0.7841)),
            (b"rTRC", b"curv" + b"\0" * 4 + struct.pack(">IH", 1, 563))]   # gamma 2.2 (u8Fixed8)
    tags += [(b"gTRC", None), (b"bTRC", None)]                              # share rTRC's data
    table_len = 4 + 12 * len(tags)
    offset = 128 + table_len
    entries, blob, trc_at = [], b"", None
    for sig, data in tags:
        if data is None:
            entries.append((sig, trc_at, 14))
            continue
        while (offset + len(blob)) % 4:
            blob += b"\0"
        at = offset + len(blob)
        if sig == b"rTRC":
            trc_at = at
        entries.append((sig, at, len(data)))
        blob += data
    table = struct.pack(">I", len(tags)) + b"".join(struct.pack(">4sII", s, o, n) for s, o, n in entries)
    size = 128 + len(table) + len(blob)
    header = (struct.pack(">I", size) + b"\0" * 4 + struct.pack(">I", 0x02100000) + b"mntrRGB XYZ "
              + b"\0" * 12 + b"acsp" + b"\0" * 24 + struct.pack(">I", 0) + s15(0.9642) + s15(1.0) + s15(0.8249)
              + b"\0" * 48)
    assert len(header) == 128
    return header + table + blob


ICC = wide_gamut_icc()
WIDE = ImageCms.ImageCmsProfile(io.BytesIO(ICC))
PATCHES = [(20 + i * 70, 20, 60 + i * 70, 100) for i in range(6)]


def scene(w=440, h=300) -> Image.Image:
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    for i, c in enumerate([(230, 20, 30), (20, 170, 60), (25, 60, 220), (250, 200, 20), (220, 40, 180), (20, 190, 230)]):
        d.rectangle((10 + i * 70, 10, 70 + i * 70, 110), fill=c)
    for x in range(w):
        d.line((x, 130, x, h), fill=(int(255 * x / w), 140, 255 - int(255 * x / w)))
    return im


def in_wide(im):
    return ImageCms.profileToProfile(im, SRGB, WIDE, renderingIntent=INTENT, outputMode="RGB")


def looks(path, size=None, page=0) -> np.ndarray:
    """sRGB pixels a colour-managed viewer would show (independent of DropDial's code)."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        with fitz.open(path) as d:
            pg = d[page]
            z = size[0] / pg.rect.width if size else 1
            pix = pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        im = Image.open(path)
        icc = im.info.get("icc_profile")
        im = ImageOps.exif_transpose(im)
        if im.mode in ("I;16", "I"):
            im = Image.fromarray((np.asarray(im, float) / 257).astype(np.uint8), "L")
        im = im.convert("RGBA").convert("RGB") if im.mode in ("P", "LA", "RGBA") else im
        if icc:
            im = ImageCms.profileToProfile(im, ImageCms.ImageCmsProfile(io.BytesIO(icc)), SRGB,
                                           renderingIntent=INTENT, outputMode="RGB")
        im = im.convert("RGB")
    if size and im.size != tuple(size):
        im = im.resize(size, Image.LANCZOS)
    return np.asarray(im, float)


def patch_err(a, b) -> float:
    return max(float(np.abs(a[y0:y1, x0:x1].reshape(-1, 3).mean(0) - b[y0:y1, x0:x1].reshape(-1, 3).mean(0)).max())
               for x0, y0, x1, y1 in PATCHES)


# ---------------------------------------------------------------- images: colour profiles
def test_generated_profile_is_valid_and_wide():
    im = in_wide(Image.new("RGB", (4, 4), (230, 20, 30)))
    assert im.getpixel((0, 0)) != (230, 20, 30)           # it really is a different colour space


@pytest.mark.parametrize("target", ["PDF", "JPG", "WEBP", "PNG", "TIFF", "AVIF", "HEIC", "BMP"])
def test_wide_gamut_photo_keeps_its_colours(tmp_path, target):
    """iPhone photos and Mac screenshots carry a Display P3 profile; dropping it (as image→PDF,
    JPG and WebP used to) shifts colours by up to ~70/255."""
    src = tmp_path / "shot.png"
    ref = scene()
    in_wide(ref).save(src, icc_profile=ICC)
    if target not in convert.targets_for("image", ".png"):
        pytest.skip(f"{target} not available")
    out = convert.convert(src, "image", target)[0]
    assert patch_err(np.asarray(ref, float), looks(out, ref.size)) < 6


def test_rotated_wide_gamut_jpeg_to_pdf_upright_and_right(tmp_path):
    ref = scene()
    src = tmp_path / "IMG.jpg"
    ex = Image.Exif()
    ex[0x0112] = 6
    in_wide(ref).rotate(90, expand=True).save(src, quality=95, icc_profile=ICC, exif=ex)
    out = convert.convert(src, "image", "PDF")[0]
    with fitz.open(out) as d:
        assert d[0].rect.width > d[0].rect.height                    # upright = landscape
    assert patch_err(np.asarray(ref, float), looks(out, ref.size)) < 6


def test_16bit_png_is_not_white(tmp_path):
    ref = scene().convert("L")
    src = tmp_path / "g16.png"
    Image.fromarray(np.asarray(ref, np.uint16) * 257).save(src)
    assert Image.open(src).mode == "I;16"
    for target in ("JPG", "PDF", "WEBP"):
        got = looks(convert.convert(src, "image", target)[0], ref.size).mean(2)
        assert np.abs(got - np.asarray(ref, float)).mean() < 4, target


def test_cmyk_jpeg_outputs_are_valid_rgb(tmp_path):
    src = tmp_path / "print.jpg"
    scene().convert("CMYK").save(src, quality=95)
    for target in ("PNG", "WEBP", "PDF"):
        out = convert.convert(src, "image", target)[0]
        im = Image.open(out) if target != "PDF" else None
        assert im is None or (im.mode in ("RGB", "RGBA") and not im.info.get("icc_profile"))
        assert patch_err(looks(src), looks(out, (440, 300))) < 6


def test_image_pdf_embeds_jpeg_losslessly_and_sizes_pages_sensibly(tmp_path):
    jpg = tmp_path / "photo.jpg"
    scene().save(jpg, quality=90, dpi=(72, 72))
    out = convert.convert(jpg, "image", "PDF")[0]
    with fitz.open(out) as d:
        xref = d[0].get_images()[0][0]
        assert d.extract_image(xref)["image"] == jpg.read_bytes()      # original bytes, no re-encode
        assert round(d[0].rect.width) == round(440 * 72 / 150)          # 72 dpi claim ignored -> 150
    scan = tmp_path / "scan.png"
    Image.new("RGB", (2480, 3508), "white").save(scan, dpi=(300, 300))
    with fitz.open(convert.convert(scan, "image", "PDF")[0]) as d:
        assert abs(d[0].rect.width / 72 - 8.27) < 0.02                 # A4 scan stays A4


def test_compress_never_keeps_a_bigger_file(tmp_path):
    src = tmp_path / "tiny.jpg"
    scene().resize((200, 136)).save(src, quality=20)
    with pytest.raises(NotSmaller):
        imaging.compress_to(src, 95, None, "JPG")
    assert [p.name for p in tmp_path.iterdir()] == ["tiny.jpg"]
    good = tmp_path / "big.png"                                   # photo-like: compresses for real
    noisy = np.asarray(scene(), float) + np.random.default_rng(0).normal(0, 12, (300, 440, 3))
    Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8)).save(good)
    outs = imaging.compress_each([src, good], lambda p: imaging.compress_to(p, 95, None, imaging.lossy_target(p)))
    assert len(outs) == 1 and outs[0].stem == "big Compressed"


# ---------------------------------------------------------------- PDFs
def _pdf_with_tricky_images(tmp_path) -> Path:
    cmyk = tmp_path / "cmyk.jpg"
    scene().convert("CMYK").save(cmyk, quality=95)
    rgba = in_wide(scene()).convert("RGBA")
    a = np.asarray(rgba).copy()
    a[:, 300:, 3] = 0                                                   # right part transparent
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, "PNG", icc_profile=ICC)
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_image(fitz.Rect(0, 0, 440, 300), filename=str(cmyk))
    p2 = doc.new_page()
    p2.insert_image(fitz.Rect(0, 0, 440, 300), stream=buf.getvalue())
    out = tmp_path / "tricky.pdf"
    doc.save(out)
    return out


def _region(path, page) -> np.ndarray:
    with fitz.open(path) as d:
        pix = d[page].get_pixmap(clip=fitz.Rect(0, 0, 440, 300), alpha=False)
        return np.asarray(Image.frombytes("RGB", (pix.width, pix.height), pix.samples), float)


def test_pdf_compress_keeps_cmyk_wide_gamut_and_transparency(tmp_path):
    """PyMuPDF's re-encoder left CMYK/ICC images mislabelled (CMYK error ~166/255)."""
    src = _pdf_with_tricky_images(tmp_path)
    out = imaging.compress_pdf(src)
    for page in (0, 1):
        assert patch_err(_region(src, page), _region(out, page)) < 6, page
    assert _region(out, 1)[150, 400].tolist() == [255.0, 255.0, 255.0]    # transparent stays see-through


def test_pdf_extract_images_decodes_cmyk_correctly(tmp_path):
    src = _pdf_with_tricky_images(tmp_path)
    outs = imaging.extract_pdf_images(src)
    first = looks(outs[0], (440, 300))
    assert patch_err(_region(src, 0), first) < 6


def test_pdf_to_images_are_colour_managed(tmp_path):
    src = _pdf_with_tricky_images(tmp_path)
    page2 = convert.convert(src, "pdf", "PNG")[1]
    got = looks(page2)
    k = got.shape[1] / 595
    crop = Image.fromarray(got[:int(300 * k), :int(440 * k)].astype(np.uint8)).resize((440, 300))
    want = np.asarray(scene(), float).copy()
    want[:, 300:] = 255                                                 # that part of the image is transparent
    assert patch_err(want, np.asarray(crop, float)) < 6


# ---------------------------------------------------------------- SVG
def test_svg_gradients_percent_sizes_and_vector_pdf(tmp_path):
    grad = tmp_path / "g.svg"
    grad.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="80"><defs><linearGradient id="g">'
                    '<stop offset="0" stop-color="#f00"/><stop offset="1" stop-color="#00f"/></linearGradient></defs>'
                    '<rect width="300" height="80" fill="url(#g)"/></svg>')
    a = np.asarray(Image.open(convert.convert(grad, "vector", "PNG")[0]).convert("RGB"), float)
    assert a[10, 10, 0] > 200 and a[10, -10, 2] > 200                    # red to blue, not black
    pdf = convert.convert(grad, "vector", "PDF")[0]
    with fitz.open(pdf) as d:
        assert not d[0].get_images() and round(d[0].rect.width) == 300  # vector
        pix = d[0].get_pixmap(alpha=False)
        assert pix.pixel(5, 40)[0] > 200
    pct = tmp_path / "p.svg"
    pct.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 120 60">'
                   '<rect width="120" height="60" fill="#1e60dc"/></svg>')
    im = Image.open(convert.convert(pct, "vector", "PNG")[0])
    assert abs(im.width / im.height - 2) < 0.01


# ---------------------------------------------------------------- video
def _ff(*args):
    subprocess.run([media.ffmpeg_path(), "-v", "error", "-y", *map(str, args)], check=True)


def _streams(path) -> dict:
    info = media.probe(path)
    w, h = info.width, info.height
    return {"w": h if info.rotation % 180 else w, "h": w if info.rotation % 180 else h,
            "a": info.acodec, "hdr": info.hdr, "dur": info.duration}


@needs_ffmpeg
def test_rotate_handles_odd_sizes_and_unplayable_audio(tmp_path):
    src = tmp_path / "odd.mov"
    _ff("-f", "lavfi", "-i", "testsrc2=size=321x181:rate=10", "-f", "lavfi", "-i", "sine=sample_rate=48000",
        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv444p", "-c:a", "pcm_s16le", "-shortest", src)
    s = _streams(media.rotate_video(src))
    assert (s["w"], s["h"]) == (180, 320) and s["a"] == "aac"


@needs_ffmpeg
def test_compress_limits_the_short_side_for_portrait_video(tmp_path):
    src = tmp_path / "land.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=10", "-t", "1", "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", src)
    portrait = tmp_path / "portrait.mov"
    try:
        _ff("-display_rotation:v:0", "90", "-i", src, "-c", "copy", portrait)     # ffmpeg 6.1+
    except subprocess.CalledProcessError:
        _ff("-i", src, "-c", "copy", "-metadata:s:v:0", "rotate=90", portrait)    # older ffmpeg (Debian 12)
    if _streams(portrait)["h"] <= _streams(portrait)["w"]:
        pytest.skip("this ffmpeg can't write a rotated test clip")
    s = _streams(media.compress_video(portrait, max_height=360))
    assert (s["w"], s["h"]) == (360, 640)                     # not 202x360
    gif = media.gif_from_video(portrait, width=320)
    assert Image.open(gif).size == (180, 320)                 # long side capped, not 320x568


@needs_ffmpeg
def test_video_compress_never_bigger(tmp_path):
    src = tmp_path / "small.webm"
    _ff("-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10", "-t", "1", "-c:v", "libvpx-vp9", "-b:v", "60k",
        "-deadline", "realtime", src)
    with pytest.raises(NotSmaller):
        media.compress_video(src, crf=18)
    assert not list(tmp_path.glob("*Compressed*"))


@needs_ffmpeg
def test_hdr_video_is_tone_mapped_to_sdr(tmp_path):
    src = tmp_path / "hdr.mov"
    try:
        _ff("-f", "lavfi", "-i", "testsrc2=size=320x180:rate=10", "-t", "1", "-vf", "format=yuv420p10le",
            "-c:v", "libx265", "-preset", "ultrafast", "-x265-params",
            "colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc:log-level=error",
            "-color_primaries", "bt2020", "-color_trc", "arib-std-b67", "-colorspace", "bt2020nc", src)
    except subprocess.CalledProcessError:
        pytest.skip("no HEVC encoder")
    assert media.probe(src).hdr
    out = convert.convert(src, "video", "MP4")[0]
    if media._can_tonemap():
        assert not media.probe(out).hdr
        assert "bt709" in subprocess.run([media.ffmpeg_path(), "-hide_banner", "-i", str(out)],
                                         capture_output=True, text=True).stderr
