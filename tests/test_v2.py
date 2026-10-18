"""Tests for 2.0: video/audio, SVG, e-books, PDF numbers/watermark/unlock, image watermark,
recipes, watch folders, history, the command line and the menu rings."""
import json
import threading
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from dragshift import cli, convert, history, imaging, media, recipes, report, watch
from dragshift.util import (BESIDE, UserError, category, output_dir, output_override, parse_size,
                            progress_hook)

needs_ffmpeg = pytest.mark.skipif(not media.available(), reason="ffmpeg not available")


# ---------------------------------------------------------------- fixtures
def photo(tmp_path, name="Photo.jpg", size=(2400, 1600)) -> Path:
    im = Image.new("RGB", size, (250, 140, 60))
    d = ImageDraw.Draw(im)
    for i in range(0, size[0], 37):
        d.line((i, 0, size[0] - i, size[1]), fill=(i % 255, 90, 200), width=9)
    ex = Image.Exif()
    ex[0x010F] = "Canon"
    ex[0x8825] = {1: "N", 2: (24.0, 33.0, 18.0), 3: "W", 4: (81.0, 47.0, 0.0)}
    p = tmp_path / name
    im.save(p, quality=95, exif=ex)
    return p


def pdf(tmp_path, pages=3, name="Doc.pdf") -> Path:
    doc = convert.fitz.open()
    for i in range(pages):
        pg = doc.new_page()
        pg.insert_text((72, 72), f"Page {i + 1}", fontsize=20)
    doc.set_metadata({"author": "Jimmy"})
    p = tmp_path / name
    doc.save(p)
    return p


def epub(tmp_path) -> Path:
    p = tmp_path / "Book.epub"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>""")
        z.writestr("content.opf", """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Test Book</dc:title><dc:identifier id="id">x</dc:identifier></metadata>
<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>
<spine><itemref idref="c1"/></spine></package>""")
        z.writestr("c1.xhtml", """<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">
<head><title>One</title></head><body><h1>Chapter One</h1><p>It was a dark and stormy night.</p></body></html>""")
    return p


def svg(tmp_path) -> Path:
    p = tmp_path / "Logo.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
                 '<rect width="40" height="20" rx="4" fill="#ff3366"/></svg>')
    return p


@pytest.fixture(scope="module")
def clip(tmp_path_factory) -> Path:
    if not media.available():
        pytest.skip("ffmpeg not available")
    d = tmp_path_factory.mktemp("media")
    out = d / "Clip.mov"
    media.run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=320x240:rate=15", "-f", "lavfi", "-i",
                      "sine=frequency=440", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                      "-c:a", "aac", "-shortest"], out)
    return out


# ---------------------------------------------------------------- util
def test_categories_and_sizes():
    assert category("a.MP4") == "video" and category("a.flac") == "audio"
    assert category("a.svg") == "vector" and category("a.epub") == "ebook"
    assert parse_size("500KB") == 512_000 and parse_size("1.5 mb") == int(1.5 * 1024 ** 2)
    assert parse_size("2000") == 2000
    with pytest.raises(UserError):
        parse_size("lots")


def test_output_override_is_per_thread(tmp_path):
    src = tmp_path / "a.png"
    other = tmp_path / "elsewhere"
    seen = {}

    def worker():
        seen["thread"] = output_dir(src)

    with output_override(other):
        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert output_dir(src) == other
    assert seen["thread"] == tmp_path          # the other thread was unaffected
    with output_override(BESIDE):
        assert output_dir(src) == tmp_path


# ---------------------------------------------------------------- new formats
def test_svg_conversions(tmp_path):
    s = svg(tmp_path)
    png = convert.convert(s, "vector", "PNG")[0]
    im = Image.open(png)
    assert im.size == (2048, 1024) and im.mode == "RGBA"   # small icons are rendered crisp
    out_pdf = convert.convert(s, "vector", "PDF")[0]
    with convert.fitz.open(out_pdf) as d:
        assert d.page_count == 1
    for t in ("JPG", "WEBP", "ICO"):
        assert convert.convert(s, "vector", t)[0].exists()


def test_ebook_conversions(tmp_path):
    b = epub(tmp_path)
    out_pdf = convert.convert(b, "ebook", "PDF")[0]
    with convert.fitz.open(out_pdf) as d:
        assert "stormy night" in d[0].get_text()
    assert "Chapter One" in convert.convert(b, "ebook", "TXT")[0].read_text()
    from docx import Document
    docx = convert.convert(b, "ebook", "DOCX")[0]
    assert any("stormy" in p.text for p in Document(docx).paragraphs)


# ---------------------------------------------------------------- PDF + image tools
def test_pdf_numbers_watermark_unlock(tmp_path):
    p = pdf(tmp_path)
    n = imaging.pdf_page_numbers(p, "Page 1 of N")
    with convert.fitz.open(n) as d:
        assert "Page 3 of 3" in d[2].get_text()
    w = imaging.watermark_pdf(p, "DRAFT")
    with convert.fitz.open(w) as d:
        assert all("DRAFT" in pg.get_text() for pg in d)
    with pytest.raises(UserError):
        imaging.watermark_pdf(p, "   ")
    prot = imaging.protect_pdf(p, "s3cret")
    assert imaging.pdf_is_locked(prot) and not imaging.pdf_is_locked(p)
    with pytest.raises(UserError):
        imaging.unlock_pdf(prot, "wrong")
    with pytest.raises(UserError):
        imaging.unlock_pdf(p, "x")                    # not protected
    un = imaging.unlock_pdf(prot, "s3cret")
    with convert.fitz.open(un) as d:
        assert not d.needs_pass and "Page 1" in d[0].get_text()
    assert imaging.watermark_pdf_preview(p, "DRAFT", 0.2, 45, "#ff0000", width=300).width == 300


def test_rotated_page_numbers_land_on_page(tmp_path):
    doc = convert.fitz.open()
    pg = doc.new_page()
    pg.set_rotation(90)
    p = tmp_path / "rot.pdf"
    doc.save(p)
    out = imaging.pdf_page_numbers(p, "1")
    with convert.fitz.open(out) as d:
        assert d[0].get_text().strip() == "1"


def test_image_watermark(tmp_path):
    src = photo(tmp_path, size=(800, 500))
    im = convert.open_image(src)
    for pos in imaging.WATERMARK_POSITIONS:
        out = imaging.watermark_image(im, "© Test", position=pos)
        assert out.size == im.size and out.mode == im.mode
        assert out.tobytes() != im.tobytes()
    assert imaging.watermark_image(im, "  ").tobytes() == im.tobytes()
    saved = imaging.watermark_image_file(src, "© Test", position="center")
    assert saved.name == "Photo Watermarked.jpg"


# ---------------------------------------------------------------- media
def test_probe_parser_without_ffmpeg():
    banner = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'a.mov':
  Duration: 00:01:02.50, start: 0.000000, bitrate: 1200 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p, 1920x1080 [SAR 1:1 DAR 16:9], 29.97 fps
      Side data:
        displaymatrix: rotation of -90.00 degrees
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s"""
    i = media.parse_probe(banner)
    assert (i.duration, i.width, i.height, i.vcodec, i.acodec) == (62.5, 1920, 1080, "h264", "aac")
    assert i.fps == 29.97 and i.rotation == 270 and i.has_video and i.has_audio
    cover = media.parse_probe("Duration: 00:03:00.00\n Stream #0:0: Audio: mp3, 44100 Hz\n"
                              " Stream #0:1: Video: mjpeg (Baseline), yuvj420p, 600x600")
    assert cover.has_audio and not cover.has_video       # album art isn't a video


@needs_ffmpeg
def test_video_conversions_and_tools(clip):
    info = media.probe(clip)
    assert info.has_video and info.has_audio and 1.5 < info.duration < 2.5
    for t in media.targets_for("video", ".mov"):
        out = convert.convert(clip, "video", t)[0]
        assert out.exists() and out.stat().st_size > 0
    gif = clip.with_suffix(".gif")
    assert Image.open(gif).is_animated
    assert media.probe(clip.with_suffix(".mp3")).has_audio
    assert media.probe(media.compress_video(clip)).vcodec == "h264"
    assert not media.probe(media.mute_video(clip)).has_audio
    assert Image.open(media.video_frame(clip)).size == (320, 240)
    rot = media.probe(media.rotate_video(clip))
    assert (rot.width, rot.height) == (240, 320)
    assert media.extract_audio(clip).suffix == ".mp3"
    r = report.summarize("tool:Mute", [clip], [clip.with_name("Clip Muted.mov")])
    assert r.title == "Sound removed"


@needs_ffmpeg
def test_audio_conversions_and_tools(clip):
    mp3 = media.extract_audio(clip)
    for t in media.targets_for("audio", ".mp3"):
        assert media.probe(convert.convert(mp3, "audio", t)[0]).has_audio
    for fn in (media.normalize_audio, media.trim_silence, media.compress_audio):
        assert media.probe(fn(mp3)).has_audio
    seen = []
    with progress_hook(seen.append):
        media.compress_audio(mp3, kbps=64)
    assert seen and seen[-1] > 0.5


def test_missing_ffmpeg_is_a_friendly_error(monkeypatch, tmp_path):
    media.ffmpeg_path.cache_clear()
    monkeypatch.setattr(media.shutil, "which", lambda *_: None)
    monkeypatch.setenv("DRAGSHIFT_FFMPEG", "")
    import builtins
    real_import = builtins.__import__

    def no_imageio(name, *a, **k):
        if name == "imageio_ffmpeg":
            raise ImportError
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_imageio)
    try:
        assert not media.available()
        with pytest.raises(UserError, match="ffmpeg"):
            media.probe(tmp_path / "x.mp4")
    finally:
        monkeypatch.undo()
        media.ffmpeg_path.cache_clear()


# ---------------------------------------------------------------- recipes
def test_recipe_applicability():
    names = lambda cat: [r.name for r in recipes.menu_recipes(cat)]
    assert names("image")[:3] == ["Web-ready", "Email size", "Private"]
    assert "Web-ready" not in names("video") and "Share video" in names("video")
    assert names("docx") == [] and names("audio") == ["Podcast"]
    r = recipes.find("web-ready")                         # by slug
    assert r.summary("image") == "resize long 2048 px → remove metadata → save as WEBP"
    with pytest.raises(UserError):
        recipes.find("nope")


def test_recipe_run_web_ready(tmp_path):
    src = photo(tmp_path)
    res = recipes.run(recipes.find("Web-ready"), [src])
    out = res.outputs[0]
    assert out.name == "Photo Web-ready.webp" and out.parent == tmp_path
    im = Image.open(out)
    assert max(im.size) == 2048
    assert imaging.count_metadata(out)[0] == 0
    left = sorted(p.name for p in tmp_path.iterdir() if p.name != "dragshift-home")
    assert left == ["Photo Web-ready.webp", "Photo.jpg"]  # no temp files left behind
    assert res.steps_run == ["resize long 2048 px", "remove metadata", "save as WEBP"]


def test_recipe_combine_and_skips(tmp_path):
    a, b = photo(tmp_path, "p1.jpg", (600, 800)), photo(tmp_path, "p2.jpg", (600, 800))
    res = recipes.run(recipes.find("Scan → PDF"), [a, b])
    assert [o.name for o in res.outputs] == ["p1 Scan to PDF.pdf"]
    with convert.fitz.open(res.outputs[0]) as d:
        assert d.page_count == 2
    # mixed drop: the PDF gets watermark + numbers, the photo only the watermark
    doc = pdf(tmp_path)
    outs = recipes.run(recipes.find("Confidential"), [doc, a]).outputs
    assert {o.suffix for o in outs} == {".pdf", ".jpg"}
    # nothing to do -> friendly error, nothing written
    small = photo(tmp_path, "tiny.jpg", (300, 200))
    r = recipes.Recipe("Shrink", [{"step": "resize", "mode": "long", "value": 1000}])
    with pytest.raises(UserError, match="Nothing to change"):
        recipes.run(r, [small])
    with pytest.raises(UserError):
        recipes.run(recipes.find("Podcast"), [small])     # doesn't apply to images


def test_recipe_progress_and_output_folder(tmp_path):
    src = photo(tmp_path, size=(500, 400))
    seen = []
    dest = tmp_path / "out"
    with progress_hook(seen.append), output_override(dest):
        out = recipes.run(recipes.find("Private"), [src]).outputs[0]
    assert out.parent == dest
    assert seen == sorted(seen) and seen[-1] < 1.01


def test_custom_recipes_store(isolated_home, tmp_path):
    r = recipes.Recipe("Thumbs", [{"step": "resize", "mode": "long", "value": 200},
                                  {"step": "convert", "to": "JPG", "quality": 80}], "▦")
    recipes.save_recipe(r)
    assert recipes.find("thumbs").glyph == "▦"
    assert "Thumbs" in [x.name for x in recipes.menu_recipes("image")]
    recipes.set_hidden("Thumbs", True)
    assert "Thumbs" not in [x.name for x in recipes.menu_recipes("image")]
    # a custom recipe with a built-in's name replaces it
    recipes.save_recipe(recipes.Recipe("Private", [{"step": "strip_metadata", "location_only": True}]))
    assert recipes.find("Private").steps[0]["location_only"] is True
    assert len([x for x in recipes.all_recipes() if x.name == "Private"]) == 1
    recipes.delete_recipe("Private")
    assert recipes.find("Private").builtin
    with pytest.raises(UserError):
        recipes.save_recipe(recipes.Recipe("Bad", [{"step": "explode"}]))
    # JSON files work directly
    f = tmp_path / "r.json"
    f.write_text(json.dumps(r.to_json()))
    assert recipes.find(str(f)).name == "Thumbs"
    # a corrupt store never breaks things
    recipes.store_path().write_text("{not json")
    assert recipes.find("Web-ready").builtin


# ---------------------------------------------------------------- watch folders
class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_folder_scanner(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    photo(inbox, "old.jpg", (300, 200))                    # already there: never processed
    rule = watch.WatchRule(str(inbox), "recipe:Private")
    clock = Clock()
    sc = watch.FolderScanner(rule, settle=1.0, clock=clock)
    assert sc.poll() == []
    new = photo(inbox, "new.jpg", (300, 200))
    (inbox / "notes.zip").write_bytes(b"x")               # unsupported
    (inbox / ".~partial.jpg.part").write_bytes(b"x")       # being written
    assert sc.poll() == []                                 # first sight: wait for it to settle
    clock.t = 0.5
    assert sc.poll() == []
    clock.t = 1.6
    assert sc.poll() == [new]
    clock.t = 5
    assert sc.poll() == []                                 # only once
    outs = rule.process(new)
    assert outs[0].parent == inbox / "DragShift" and outs[0].name == "new Private.jpg"
    assert imaging.count_metadata(outs[0])[0] == 0


def test_watch_rule_filters_and_store(tmp_path):
    conv = watch.WatchRule(str(tmp_path), "convert:PDF", output="beside")
    assert conv.accepts(tmp_path / "a.png") and not conv.accepts(tmp_path / "a.pdf")
    rec = watch.WatchRule(str(tmp_path), "recipe:Web-ready", output="beside")
    assert rec.accepts(tmp_path / "a.png")
    assert not rec.accepts(tmp_path / "a Web-ready.webp")   # our own result
    assert not rec.accepts(tmp_path / "a.mp3")
    assert not watch.WatchRule(str(tmp_path), "recipe:Missing").accepts(tmp_path / "a.png")
    watch.save_rules([conv, rec])
    loaded = watch.load_rules()
    assert [r.action for r in loaded] == ["convert:PDF", "recipe:Web-ready"] and loaded[0].output == "beside"


# ---------------------------------------------------------------- history
def test_history(tmp_path, monkeypatch):
    src = photo(tmp_path, size=(400, 300))
    out = imaging.compress_image(src, 40)
    r = report.summarize("tool:Compress", [src], [out])
    assert history.add(r, "tool:Compress") is not None
    assert history.add(report.Result("x", "y", []), "x") is None       # nothing written: not logged
    e = history.entries()[0]
    assert e.title == "Compressed" and e.existing_outs == [out] and e.when() == "just now"
    assert history.stats()["saved"] > 0
    monkeypatch.setattr(history, "MAX_ENTRIES", 5)
    for _ in range(10):
        history.add(r, "tool:Compress")
    assert len(history.entries()) == 5
    history.clear()
    assert history.entries() == []


# ---------------------------------------------------------------- command line
def run_cli(*args) -> int:
    return cli.main([str(a) for a in args])


def test_cli_detection():
    assert cli.is_cli(["x", "convert", "a.png", "--to", "jpg"])
    assert cli.is_cli(["x", "--out", "dir", "recipe", "list"])
    assert cli.is_cli(["x", "--version"])
    assert not cli.is_cli(["x", "photo.jpg"]) and not cli.is_cli(["x", "--quiet"]) and not cli.is_cli(["x"])


def test_cli_commands(tmp_path, capsys):
    src = photo(tmp_path)
    assert run_cli("convert", src, "--to", "webp", "-q") == 0
    assert (tmp_path / "Photo.webp").exists()
    assert run_cli("compress", src, "--target", "150KB", "-q") == 0
    assert (tmp_path / "Photo Compressed.jpg").stat().st_size <= 150 * 1024
    assert run_cli("resize", src, "--long", "800", "-q") == 0
    assert run_cli("--out", tmp_path / "web", "recipe", "run", "web-ready", src, "-q") == 0
    assert (tmp_path / "web" / "Photo Web-ready.webp").exists()
    capsys.readouterr()
    assert run_cli("strip", src, "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["ok"] and data[0]["outputs"][0].endswith("Photo Clean.jpg")
    doc = pdf(tmp_path)
    assert run_cli("pdf", "protect", doc, "--password", "abcd", "-q") == 0
    assert run_cli("pdf", "unlock", tmp_path / "Doc Protected.pdf", "--password", "nope", "-q") == 1
    assert run_cli("pdf", "merge", doc, doc, "-q") == 0
    assert run_cli("convert", tmp_path / "missing.png", src, "--to", "xyz") == 1
    err = capsys.readouterr().err
    assert "file not found" in err and "can't convert" in err
    assert run_cli("recipe", "list") == 0 and "Web-ready" in capsys.readouterr().out
    assert run_cli("formats", "--json") == 0
    assert any(r["type"] == "ebook" for r in json.loads(capsys.readouterr().out))
    assert len(history.entries()) >= 5                          # command-line results are logged too


# ---------------------------------------------------------------- menu rings
def test_menu_rings(tmp_path):
    from dragshift.app import DragShiftApp
    rings = lambda p: {k: [i.label for i in v] for k, v in DragShiftApp.build_rings(None, [str(p)]).items()}
    img = rings(photo(tmp_path, size=(100, 80)))
    assert list(img) == ["Convert", "Tools", "Recipes"] and "Watermark" in img["Tools"]
    doc = pdf(tmp_path)
    assert {"Numbers", "Watermark"} <= set(rings(doc)["Tools"])
    assert rings(imaging.protect_pdf(doc, "pw12")) == {"Tools": ["Unlock"]}
    assert list(rings(svg(tmp_path))) == ["Convert"]
    assert rings(epub(tmp_path))["Convert"] == ["PDF", "DOCX", "TXT"]
    vid = rings(tmp_path / "x.mp4")
    assert vid["Tools"] == media.VIDEO_TOOLS and "GIF" in vid["Convert"] and "Share video" in vid["Recipes"]
    assert rings(tmp_path / "x.zip") == {"Unsupported": []}
