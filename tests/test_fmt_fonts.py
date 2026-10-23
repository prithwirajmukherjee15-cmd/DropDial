"""Font family: TTF / OTF / WOFF / WOFF2 / TTC conversions, specimens and tools.

Fixture fonts are built in the test with fontTools.fontBuilder, so nothing binary is committed.
Every output is re-opened with fontTools *and* rendered with Pillow (FreeType)."""
from __future__ import annotations

import sys
import re
import struct
import zlib
from pathlib import Path

import pytest

pytest.importorskip("fontTools")
from fontTools.fontBuilder import FontBuilder  # noqa: E402
from fontTools.pens.t2CharStringPen import T2CharStringPen  # noqa: E402
from fontTools.pens.ttGlyphPen import TTGlyphPen  # noqa: E402
from fontTools.ttLib import TTCollection, TTFont  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFont  # noqa: E402

from dropdial import convert as conv  # noqa: E402
from dropdial import util  # noqa: E402
from dropdial.formats import fonts  # noqa: E402

CYRILLIC = [chr(c) for c in range(0x410, 0x450)] + ["ё"]
CHARS = (list(fonts.UPPER + fonts.LOWER + "0123456789") + list("!?&@#%*()[]{}.,:;'\"/+-=")
         + CYRILLIC + ["·"])


def _draw(pen, ch: str, style: str, cubic: bool):
    """A distinctive outline per character: 'box' = heavy blocks, 'thin' = hairline bars."""
    k = (ord(ch) * 37) % 200
    if style == "thin":
        pen.moveTo((100 + k, 0)); pen.lineTo((100 + k, 700)); pen.lineTo((130 + k, 700))
        pen.lineTo((130 + k, 0)); pen.closePath()
        return
    pen.moveTo((40, 0)); pen.lineTo((40, 700)); pen.lineTo((520, 700)); pen.lineTo((520, 0))
    pen.closePath()
    # a round counter (curves), different in each glyph
    cx, cy, r = 280, 350, 60 + k // 4
    if cubic:
        c = r * 0.5523
        pen.moveTo((cx - r, cy)); pen.curveTo((cx - r, cy + c), (cx - c, cy + r), (cx, cy + r))
        pen.curveTo((cx + c, cy + r), (cx + r, cy + c), (cx + r, cy))
        pen.curveTo((cx + r, cy - c), (cx + c, cy - r), (cx, cy - r))
        pen.curveTo((cx - c, cy - r), (cx - r, cy - c), (cx - r, cy))
    else:
        pen.moveTo((cx - r, cy)); pen.qCurveTo((cx - r, cy + r), (cx, cy + r))
        pen.qCurveTo((cx + r, cy + r), (cx + r, cy)); pen.qCurveTo((cx + r, cy - r), (cx, cy - r))
        pen.qCurveTo((cx - r, cy - r), (cx - r, cy))
    pen.closePath()


def build_font(path: Path, cff: bool = False, style: str = "box", family: str = "Test Sans",
               sub: str = "Regular", weight: int = 400, chars=CHARS, variable: bool = False) -> Path:
    names = [".notdef", "space"] + [f"uni{ord(c):04X}" for c in chars]
    fb = FontBuilder(1000, isTTF=not cff)
    fb.setupGlyphOrder(names + ([] if cff else ["Aacute", "acutecomb"]))
    cmap = {0x20: "space", **{ord(c): f"uni{ord(c):04X}" for c in chars}}
    if not cff:
        cmap[0xC1] = "Aacute"
    fb.setupCharacterMap(cmap)
    metrics = {n: (600, 40) for n in names}
    metrics["space"] = (300, 0)
    if cff:
        cs = {}
        for n in names:
            pen = T2CharStringPen(metrics[n][0], None)
            if n not in (".notdef", "space"):
                _draw(pen, chr(int(n[3:], 16)), style, True)
            cs[n] = pen.getCharString()
        fb.setupCFF(f"{family.replace(' ', '')}-{sub}", {"FullName": f"{family} {sub}"}, cs, {})
    else:
        glyphs = {}
        for n in names:
            pen = TTGlyphPen(None)
            if n not in (".notdef", "space"):
                _draw(pen, chr(int(n[3:], 16)), style, False)
            glyphs[n] = pen.glyph()
        acute = TTGlyphPen(None)
        acute.moveTo((250, 750)); acute.lineTo((350, 750)); acute.lineTo((300, 850))
        acute.closePath()
        glyphs["acutecomb"] = acute.glyph()
        comp = TTGlyphPen(glyphs)
        comp.addComponent("uni0041", (1, 0, 0, 1, 0, 0))
        comp.addComponent("acutecomb", (1, 0, 0, 1, 0, 0))
        glyphs["Aacute"] = comp.glyph()
        metrics.update(Aacute=(600, 40), acutecomb=(0, 250))
        fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=900, descent=-200)
    fb.setupNameTable({"familyName": family, "styleName": sub,
                       "uniqueFontIdentifier": f"{family} {sub} test",
                       "fullName": f"{family} {sub}", "psName": f"{family.replace(' ', '')}-{sub}",
                       "version": "Version 1.000", "licenseDescription": "Test license"})
    fb.setupOS2(sTypoAscender=900, sTypoDescender=-200, usWinAscent=900, usWinDescent=200,
                usWeightClass=weight)
    fb.setupPost()
    if variable:
        fb.setupFvar([("wght", 100, 400, 900, "Weight")], [])
    fb.save(str(path))
    return path


def render(path, text="ABCabc", size=48, index=0) -> Image.Image:
    f = ImageFont.truetype(str(path), size, index=index)
    im = Image.new("L", (900, 120), 255)
    ImageDraw.Draw(im).text((10, 10), text, font=f, fill=0)
    return im


def diff(a: Image.Image, b: Image.Image) -> float:
    """Fraction of pixels that differ clearly."""
    d = ImageChops.difference(a, b).point(lambda v: 255 if v > 100 else 0)
    return sum(d.histogram()[255:]) / (a.width * a.height)


def ink(im: Image.Image) -> float:
    g = im.convert("L").point(lambda v: 255 if v < 128 else 0)
    return g.histogram()[255] / (im.width * im.height)


def advances(f: TTFont) -> list[int]:
    return [f["hmtx"][g][0] for g in f.getGlyphOrder()]


@pytest.fixture
def ttf(tmp_path):
    return build_font(tmp_path / "Test Sans.ttf")


@pytest.fixture
def otf(tmp_path):
    return build_font(tmp_path / "Test Sans.otf", cff=True)


# ---------------------------------------------------------------- registry
def test_registry_and_targets():
    for ext in ("ttf", "otf", "woff", "woff2", "ttc", "otc"):
        assert util.category(f"x.{ext}") == "font"
        t = conv.targets_for("font", ext)
        assert ext.upper() not in t and 0 < len(t) <= 9
        assert all(len(fonts.HINTS[x]) <= 22 for x in t)
    assert conv.targets_for("font", "ttf") == ["OTF", "WOFF2", "WOFF", "PNG", "PDF"]
    fam = fonts.register.__globals__["FAMILIES"]["font"]
    assert len(fam.tools) <= 3 and all(len(t.hint) <= 22 for t in fam.tools)


# ---------------------------------------------------------------- web flavours
@pytest.mark.parametrize("web", ["WOFF", "WOFF2"])
@pytest.mark.parametrize("cff", [False, True])
def test_web_round_trip_is_lossless(tmp_path, web, cff):
    src = build_font(tmp_path / ("a.otf" if cff else "a.ttf"), cff=cff)
    [w] = conv.convert(src, "font", web)
    assert w.suffix == "." + web.lower() and w.stat().st_size < src.stat().st_size
    wf = TTFont(str(w))
    assert wf.flavor == web.lower()
    back_target = "OTF" if cff else "TTF"
    [back] = conv.convert(w, "font", back_target)
    a, b = TTFont(str(src)), TTFont(str(back))
    assert b.flavor is None and back != src
    assert a.getGlyphOrder() == b.getGlyphOrder()
    assert a.getBestCmap() == b.getBestCmap()
    assert advances(a) == advances(b)
    for tag in ("head", "hhea", "OS/2"):
        assert a[tag].__dict__.keys() == b[tag].__dict__.keys()
    assert a["hhea"].ascent == b["hhea"].ascent and a["OS/2"].usWeightClass == b["OS/2"].usWeightClass
    gs_a, gs_b = a.getGlyphSet(), b.getGlyphSet()
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    for g in a.getGlyphOrder():
        pa, pb = DecomposingRecordingPen(gs_a), DecomposingRecordingPen(gs_b)
        gs_a[g].draw(pa); gs_b[g].draw(pb)
        assert pa.value == pb.value, g
    assert diff(render(src), render(back)) == 0


# ---------------------------------------------------------------- outline conversion
def test_ttf_to_otf_makes_cff_with_same_shapes(ttf):
    [out] = conv.convert(ttf, "font", "OTF")
    a, b = TTFont(str(ttf)), TTFont(str(out))
    assert "CFF " in b and "glyf" not in b and b.sfntVersion == "OTTO"
    assert b["maxp"].tableVersion == 0x5000
    assert a.getGlyphOrder() == b.getGlyphOrder() and a.getBestCmap() == b.getBestCmap()
    assert advances(a) == advances(b)
    # the composite Á is decomposed into real outlines
    from fontTools.pens.boundsPen import BoundsPen
    ga, gb = a.getGlyphSet(), b.getGlyphSet()
    for g in a.getGlyphOrder():
        pa, pb = BoundsPen(ga), BoundsPen(gb)
        ga[g].draw(pa); gb[g].draw(pb)
        if pa.bounds:
            assert all(abs(x - y) <= 1 for x, y in zip(pa.bounds, pb.bounds)), g
            assert b["hmtx"][g][1] == round(pb.bounds[0])
    assert diff(render(ttf, "ABCÁxyzДж"), render(out, "ABCÁxyzДж")) < 0.03   # cubic vs quadratic rasterise a hair differently per FreeType build


def test_otf_to_ttf_makes_quadratic_glyf(otf):
    [out] = conv.convert(otf, "font", "TTF")
    a, b = TTFont(str(otf)), TTFont(str(out))
    assert "glyf" in b and "CFF " not in b and b.sfntVersion == "\x00\x01\x00\x00"
    assert a.getGlyphOrder() == b.getGlyphOrder() and a.getBestCmap() == b.getBestCmap()
    assert advances(a) == advances(b)
    g = b["glyf"]["uni0041"]
    assert g.numberOfContours == 2 and any(not (f & 1) for f in g.flags)   # off-curve points
    from fontTools.pens.boundsPen import BoundsPen
    ga, gb = a.getGlyphSet(), b.getGlyphSet()
    for name in a.getGlyphOrder():
        pa, pb = BoundsPen(ga), BoundsPen(gb)
        ga[name].draw(pa); gb[name].draw(pb)
        if pa.bounds:
            assert all(abs(x - y) <= 1.5 for x, y in zip(pa.bounds, pb.bounds)), name
    assert diff(render(otf, "ABCxyzДж"), render(out, "ABCxyzДж")) < 0.03


def test_variable_font_cannot_change_outlines(tmp_path):
    src = build_font(tmp_path / "v.ttf", variable=True)
    with pytest.raises(util.UserError, match="Variable"):
        conv.convert(src, "font", "OTF")
    [w] = conv.convert(src, "font", "WOFF2")      # a container change is still fine
    assert "fvar" in TTFont(str(w))


def test_collection_gives_one_file_per_face(tmp_path):
    a = TTFont(str(build_font(tmp_path / "r.ttf", sub="Regular")))
    b = TTFont(str(build_font(tmp_path / "b.ttf", sub="Bold", weight=700, style="thin")))
    coll = TTCollection()
    coll.fonts = [a, b]
    src = tmp_path / "Family.ttc"
    coll.save(str(src))
    outs = conv.convert(src, "font", "OTF")
    assert [o.name for o in outs] == ["Family Test Sans Regular.otf", "Family Test Sans Bold.otf"]
    weights = [TTFont(str(o))["OS/2"].usWeightClass for o in outs]
    assert weights == [400, 700]
    assert diff(render(outs[0]), render(src, index=0)) < 0.03
    assert diff(render(outs[1]), render(src, index=1)) < 0.03
    pdf = conv.convert(src, "font", "PDF")[0]
    import pymupdf
    [one] = conv.convert(tmp_path / "r.ttf", "font", "PDF")
    with pymupdf.open(str(pdf)) as d, pymupdf.open(str(one)) as d1:
        assert d.page_count == 2 * d1.page_count       # each face starts its own page
        assert d[0].get_text().startswith("Test Sans Regular")
        assert d[d1.page_count].get_text().startswith("Test Sans Bold")
    assert len(conv.convert(src, "font", "PNG")) == 2


# ---------------------------------------------------------------- specimens
def test_png_specimen_really_uses_the_font(tmp_path):
    box = build_font(tmp_path / "Box.ttf", family="Box Face")
    thin = build_font(tmp_path / "Thin.otf", cff=True, family="Thin Face", style="thin")
    [pb] = conv.convert(box, "font", "PNG")
    [pt] = conv.convert(thin, "font", "PNG")
    ib, it = Image.open(pb), Image.open(pt)
    ib.load()
    assert ib.format == "PNG" and ib.width == 1600 and ib.height > 1000
    # heavy block glyphs vs hairlines: same layout, very different ink
    assert ink(ib) > 3 * ink(it)
    # the glyph rows are our font, not a fallback: identical to rendering with the font directly
    assert diff(render(box, "ABC", 52), _default_render("ABC", 52)) > 0.02
    # the uppercase row in the sheet is pixel-identical to drawing it with the font itself
    f = ImageFont.truetype(str(box), 52)
    row = Image.new("RGB", (1600, 80), "white")
    ImageDraw.Draw(row).text((72, 0), fonts.UPPER, font=f, fill="#111111")
    x0, y0, x1, y1 = ImageChops.difference(row, Image.new("RGB", row.size, "white")).getbbox()
    patch = row.crop((x0, y0, x1, y1)).convert("L")
    w, h = patch.size
    found = any(diff(ib.crop((x0, y, x0 + w, y + h)).convert("L"), patch) == 0
                for y in range(0, 600))
    assert found


def _default_render(text, size):
    f = ImageFont.load_default(size)
    im = Image.new("L", (900, 120), 255)
    ImageDraw.Draw(im).text((10, 10), text, font=f, fill=0)
    return im


def test_specimen_only_shows_covered_scripts(ttf):
    plan = fonts._plan(TTFont(str(ttf)))
    labels = [s[0] for s in plan["scripts"]]
    assert "Cyrillic" in labels
    assert not {"Devanagari", "Japanese", "Greek", "Arabic"} & set(labels)
    assert plan["pangram"] == fonts.PANGRAM and plan["name"] == "Test Sans Regular"


def test_pdf_specimen_embeds_the_font(ttf):
    import pymupdf
    [pdf] = conv.convert(ttf, "font", "PDF")
    with pymupdf.open(str(pdf)) as d:
        text = "".join(p.get_text() for p in d)
        used = {f[3].split("+")[-1] for p in d for f in p.get_fonts()}
    assert "TestSans-Regular" in used or "Test Sans Regular" in used
    for s in (fonts.UPPER, fonts.LOWER, fonts.PANGRAM, "Cyrillic", "Съешь же ещё"):
        assert s in text
    assert "Devanagari" not in text and "Greek" not in text


def test_system_font_specimen_covers_its_scripts():
    path = Path("/usr/share/fonts/truetype/freefont/FreeSerif.ttf")
    if not path.exists():
        pytest.skip("FreeSerif not installed")
    labels = {s[0] for s in fonts._plan(TTFont(str(path)))["scripts"]}
    assert {"Greek", "Cyrillic", "Hebrew", "Devanagari"} <= labels
    assert "Korean" not in labels


# ---------------------------------------------------------------- tools
def test_subset_latin(tmp_path, ttf):
    [out] = fonts.subset_latin(ttf)
    assert out.name == "Test Sans Latin.ttf" and out.stat().st_size < ttf.stat().st_size
    f = TTFont(str(out))
    cmap = f.getBestCmap()
    assert set(cmap) <= set(fonts.LATIN)
    assert all(ord(c) in cmap for c in fonts.UPPER + fonts.LOWER + "0123456789" + "Á")
    assert not any(ord(c) in cmap for c in CYRILLIC)
    assert diff(render(ttf, "Hello Á"), render(out, "Hello Á")) == 0
    # already Latin-only: nothing to gain, nothing left behind
    small = build_font(tmp_path / "Latin only.ttf", chars=list(fonts.UPPER))
    with pytest.raises(util.NotSmaller):
        fonts.subset_latin(small)
    assert not (tmp_path / "Latin only Latin.ttf").exists()
    cyr = build_font(tmp_path / "Cyr.ttf", chars=CYRILLIC)
    with pytest.raises(util.UserError, match="no Latin"):
        fonts.subset_latin(cyr)


def test_web_kit_writes_woff2_and_css(tmp_path):
    r = build_font(tmp_path / "Test-Regular.otf", cff=True)
    b = build_font(tmp_path / "Test-Bold.ttf", sub="Bold", weight=700)
    outs = fonts.web_kit([r, b])
    css = [o for o in outs if o.suffix == ".css"]
    woffs = [o for o in outs if o.suffix == ".woff2"]
    assert len(css) == 1 and len(woffs) == 2 and css[0].name == "Test Sans.css"
    text = css[0].read_text(encoding="utf-8")
    assert text.count("@font-face") == 2 and 'font-family: "Test Sans";' in text
    for url in re.findall(r'url\("([^"]+)"\)', text):
        assert (tmp_path / url.replace("%20", " ")).exists()
    assert re.findall(r"font-weight: (\d+);", text) == ["400", "700"]
    assert all(TTFont(str(w)).flavor == "woff2" for w in woffs)


def test_font_info(ttf):
    [out] = fonts.font_info(ttf)
    t = out.read_text(encoding="utf-8")
    assert "Test Sans Regular" in t and "Version 1.000" in t and "Test license" in t
    assert re.search(r"Glyphs:\s+%d" % len(TTFont(str(ttf)).getGlyphOrder()), t)
    assert re.search(r"Cyrillic\s+65 of 256", t) and "Embedding:" in t


# ---------------------------------------------------------------- untrusted input
def test_bad_input_is_a_friendly_error(tmp_path, ttf):
    junk = tmp_path / "junk.ttf"
    junk.write_bytes(b"this is not a font at all" * 10)
    with pytest.raises(util.UserError):
        conv.convert(junk, "font", "WOFF2")
    cut = tmp_path / "cut.ttf"
    cut.write_bytes(ttf.read_bytes()[:600])
    for t in ("OTF", "WOFF", "PNG"):
        with pytest.raises(util.UserError):
            conv.convert(cut, "font", t)
    bad2 = tmp_path / "bad.woff2"
    [w2] = conv.convert(ttf, "font", "WOFF2")
    data = bytearray(w2.read_bytes())
    data[-40:] = b"\xff" * 40
    bad2.write_bytes(bytes(data))
    with pytest.raises(util.UserError):
        conv.convert(bad2, "font", "TTF")
    assert ttf.read_bytes()[:4] == b"\x00\x01\x00\x00"   # source untouched


def test_woff_zip_bomb_is_refused(tmp_path):
    payload = zlib.compress(b"\0" * 20_000_000, 9)
    head = struct.pack(">4sIIHHIHHIIIII", b"wOFF", 0x00010000, 44 + 20 + len(payload), 1, 0,
                       12 + 16 + 1000, 1, 0, 0, 0, 0, 0, 0)
    entry = struct.pack(">4sIIII", b"glyf", 64, len(payload), 1000, 0)
    bomb = tmp_path / "bomb.woff"
    bomb.write_bytes(head + entry + payload)
    with pytest.raises(util.UserError):
        conv.convert(bomb, "font", "TTF")


def test_cli_goes_through_registry(tmp_path, ttf):
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-W", "ignore", "-m", "dropdial", "convert", str(ttf),
                        "--to", "WOFF2"], capture_output=True, text=True, timeout=120,
                       cwd=Path(__file__).resolve().parents[1])
    assert r.returncode == 0, r.stderr + r.stdout
    assert TTFont(str(tmp_path / "Test Sans.woff2")).flavor == "woff2"


def test_unicode_names_survive(tmp_path):
    src = build_font(tmp_path / "फ़ॉन्ट 日本.ttf", family="Tëst 日本 हिन्दी")
    [w] = conv.convert(src, "font", "WOFF2")
    assert w.name == "फ़ॉन्ट 日本.woff2"
    assert TTFont(str(w))["name"].getDebugName(1) == "Tëst 日本 हिन्दी"
    [png] = conv.convert(src, "font", "PNG")     # title falls back to a font that has it
    assert Image.open(png).width == 1600
    [info] = fonts.font_info(src)
    assert "Tëst 日本 हिन्दी" in info.read_text(encoding="utf-8")
