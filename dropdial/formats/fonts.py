"""Fonts: TTF, OTF, WOFF, WOFF2 and collections (TTC / OTC).

* WOFF / WOFF2 <-> TTF / OTF is a container change: the outlines are untouched.
* TTF <-> OTF changes the outline type: cubic CFF curves become quadratic glyf curves
  (cu2qu, within 1/1000 em) and quadratic curves become the identical cubic ones. Hinting is
  dropped by such a change; variable fonts are refused (they'd lose their variations).
* PNG / PDF render a specimen sheet with the font itself; non-Latin samples appear only
  for scripts the font's character map really covers.
* A collection is converted face by face: one output file per face (one PDF for all).
"""
from __future__ import annotations

import html
import importlib.util
import io
import re
import struct
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from . import Family, Tool, register
from ..util import NotSmaller, UserError, output_dir, report_progress, sibling, unique_path

EXTS = {".ttf", ".otf", ".woff", ".woff2", ".ttc", ".otc"}
MAX_FILE = 256 * 1024 * 1024        # plain fonts / collections on disk
MAX_WEB_FILE = 64 * 1024 * 1024     # compressed WOFF / WOFF2
MAX_SFNT = 256 * 1024 * 1024        # decompressed size of a WOFF / WOFF2
MAX_FACES = 64                      # faces in a collection (one output file each)

HINTS = {
    "TTF": "TrueType outlines", "OTF": "PostScript outlines", "WOFF2": "Best for websites",
    "WOFF": "Web font (legacy)", "PNG": "Specimen image", "PDF": "Specimen sheet",
    "Subset Latin": "Smaller web font", "Web Kit": "WOFF2 + @font-face CSS",
    "Font Info": "Glyphs, license, more",
}

# Google Fonts' "latin" range: Basic Latin, Latin-1, common punctuation and symbols
LATIN = sorted(set(range(0x20, 0x7F)) | set(range(0xA0, 0x100)) | set(range(0x2000, 0x2070)) | {
    0x131, 0x152, 0x153, 0x2BB, 0x2BC, 0x2C6, 0x2DA, 0x2DC, 0x304, 0x308, 0x329, 0x20AC,
    0x2122, 0x2191, 0x2193, 0x2212, 0x2215, 0xFEFF, 0xFFFD})

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"
FIGURES = "0123456789 !?&@#%*()[]{}.,:;'\"/+-="
PANGRAM = "The quick brown fox jumps over the lazy dog."
# (label, sample, needs shaping, right-to-left)
SCRIPTS = [
    ("Latin Extended", "Zażółć gęślą jaźń · Ångström · Øresund", False, False),
    ("Vietnamese", "Tiếng Việt có dấu", False, False),
    ("Greek", "Θέλει αρετή και τόλμη η ελευθερία", False, False),
    ("Cyrillic", "Съешь же ещё этих мягких французских булок", False, False),
    ("Armenian", "Բարեւ աշխարհ", False, False),
    ("Georgian", "გამარჯობა მსოფლიო", False, False),
    ("Hebrew", "שלום עולם", False, True),
    ("Arabic", "مرحبا بالعالم", True, True),
    ("Devanagari", "नमस्ते दुनिया", True, False),
    ("Bengali", "নমস্কার বিশ্ব", True, False),
    ("Tamil", "வணக்கம் உலகம்", True, False),
    ("Thai", "สวัสดีชาวโลก", True, False),
    ("Japanese", "いろはにほへと ちりぬるを 日本語", False, False),
    ("Chinese", "我能吞下玻璃而不伤身体", False, False),
    ("Korean", "다람쥐 헌 쳇바퀴에 타고파", False, False),
]
# Unicode blocks reported by Font Info (start, end, name)
BLOCKS = [
    (0x0020, 0x007E, "Basic Latin"), (0x00A0, 0x00FF, "Latin-1 Supplement"),
    (0x0100, 0x017F, "Latin Extended-A"), (0x0180, 0x024F, "Latin Extended-B"),
    (0x0250, 0x02AF, "IPA Extensions"), (0x0300, 0x036F, "Combining Diacritics"),
    (0x0370, 0x03FF, "Greek and Coptic"), (0x0400, 0x04FF, "Cyrillic"),
    (0x0530, 0x058F, "Armenian"), (0x0590, 0x05FF, "Hebrew"), (0x0600, 0x06FF, "Arabic"),
    (0x0900, 0x097F, "Devanagari"), (0x0980, 0x09FF, "Bengali"), (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"), (0x0B80, 0x0BFF, "Tamil"), (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"), (0x0D00, 0x0D7F, "Malayalam"), (0x0E00, 0x0E7F, "Thai"),
    (0x10A0, 0x10FF, "Georgian"), (0x1E00, 0x1EFF, "Latin Extended Additional"),
    (0x1F00, 0x1FFF, "Greek Extended"), (0x2000, 0x206F, "General Punctuation"),
    (0x20A0, 0x20CF, "Currency Symbols"), (0x2100, 0x214F, "Letterlike Symbols"),
    (0x2190, 0x21FF, "Arrows"), (0x2200, 0x22FF, "Mathematical Operators"),
    (0x2500, 0x257F, "Box Drawing"), (0x25A0, 0x25FF, "Geometric Shapes"),
    (0x2600, 0x26FF, "Miscellaneous Symbols"), (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"), (0x4E00, 0x9FFF, "CJK Unified Ideographs"),
    (0xAC00, 0xD7A3, "Hangul Syllables"), (0xE000, 0xF8FF, "Private Use Area"),
    (0x1F300, 0x1FAFF, "Emoji & Pictographs"),
]
FEATURES = {
    "kern": "kerning", "liga": "standard ligatures", "dlig": "discretionary ligatures",
    "calt": "contextual alternates", "smcp": "small capitals", "c2sc": "caps to small caps",
    "onum": "old-style figures", "lnum": "lining figures", "tnum": "tabular figures",
    "pnum": "proportional figures", "frac": "fractions", "sups": "superscript",
    "subs": "subscript", "ordn": "ordinals", "case": "case-sensitive forms", "zero": "slashed zero",
    "swsh": "swashes", "salt": "stylistic alternates", "locl": "localized forms",
    "mark": "mark positioning", "mkmk": "mark-to-mark positioning", "ccmp": "glyph composition",
}


def _have(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def _targets(src_ext: str) -> list[str]:
    ext = src_ext.lower().lstrip(".")
    out = ["TTF", "OTF", "WOFF2", "WOFF", "PNG", "PDF"]
    if not _have("brotli"):
        out.remove("WOFF2")
    return [t for t in out if t.lower() != ext]


# ---------------------------------------------------------------- reading (untrusted input)
@contextmanager
def _friendly(msg: str = "This font file is damaged or uses something DropDial can't read."):
    try:
        yield
    except UserError:
        raise
    except MemoryError:
        raise UserError("This font is too big to process.") from None
    except Exception as e:
        import traceback
        traceback.print_exc()           # the real cause goes to the log; the user gets a sentence
        raise UserError(msg) from e


def _sniff(data: bytes) -> str:
    tag = data[:4]
    if tag in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return "sfnt"
    return {b"ttcf": "collection", b"wOFF": "woff", b"wOF2": "woff2"}.get(tag) or ""


def _guard_woff(data: bytes) -> None:
    """Refuse WOFF files whose tables would inflate past MAX_SFNT (zip bombs)."""
    import zlib
    if len(data) < 44:
        raise UserError("This WOFF file is damaged.")
    num, = struct.unpack(">H", data[12:14])
    total, = struct.unpack(">I", data[16:20])
    if total > MAX_SFNT or len(data) < 44 + 20 * num:
        raise UserError("This WOFF file is damaged or too big.")
    for i in range(num):
        _tag, off, comp, orig, _ = struct.unpack(">4sIIII", data[44 + 20 * i: 64 + 20 * i])
        if orig > MAX_SFNT or off + comp > len(data):
            raise UserError("This WOFF file is damaged or too big.")
        if comp < orig:
            try:
                out = zlib.decompressobj().decompress(data[off: off + comp], orig + 1)
            except zlib.error:
                raise UserError("This WOFF file is damaged.") from None
            if len(out) > orig:
                raise UserError("This WOFF file is damaged.")


def _guard_woff2(data: bytes) -> None:
    """Refuse WOFF2 files whose Brotli stream would inflate past its declared size."""
    if not _have("brotli"):
        raise UserError("Reading WOFF2 needs the 'brotli' package.")
    import brotli
    from fontTools.ttLib import woff2
    f = io.BytesIO(data)
    with _friendly("This WOFF2 file is damaged."):
        hdr = woff2.sstruct.unpack(woff2.woff2DirectoryFormat, f.read(woff2.woff2DirectorySize))
        if hdr["sfntVersion"] in (b"ttcf", "ttcf"):
            raise UserError("WOFF2 font collections aren't supported.")
        total = 0
        for _ in range(hdr["numTables"]):
            entry = woff2.WOFF2DirectoryEntry()
            entry.fromFile(f)
            total += entry.length
        if total > MAX_SFNT or hdr["totalSfntSize"] > MAX_SFNT:
            raise UserError("This WOFF2 file is too big.")
        d = brotli.Decompressor()
        try:
            out = d.process(f.read(hdr["totalCompressedSize"]), output_buffer_limit=total + 1)
            if len(out) != total or not d.is_finished():
                raise UserError("This WOFF2 file is damaged.")
        except TypeError:   # brotli < 1.2 can't bound its output; the declared sizes were checked
            pass
        except brotli.error:
            raise UserError("This WOFF2 file is damaged.") from None


def _open(path: Path) -> tuple[str, list]:
    """('sfnt' | 'collection' | 'woff' | 'woff2', [TTFont, …]) for a font file."""
    from fontTools.ttLib import TTCollection, TTFont
    path = Path(path)
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            head = fh.read(4)
    except OSError:
        raise UserError("Can't open this font file.") from None
    kind = _sniff(head)
    if not kind:
        raise UserError("This isn't a font file DropDial can read (TTF, OTF, WOFF, WOFF2, TTC).")
    if size > (MAX_WEB_FILE if kind.startswith("woff") else MAX_FILE):
        raise UserError("This font file is too big.")
    data = path.read_bytes()
    if kind == "woff":
        _guard_woff(data)
    elif kind == "woff2":
        _guard_woff2(data)
    with _friendly():
        if kind == "collection":
            faces = TTCollection(io.BytesIO(data), recalcTimestamp=False).fonts
            if not 0 < len(faces) <= MAX_FACES:
                raise UserError("This font collection has too many faces.")
        else:
            faces = [TTFont(io.BytesIO(data), recalcTimestamp=False)]
        for f in faces:
            order = f.getGlyphOrder()
            if f["maxp"].numGlyphs != len(order) or not order:
                raise UserError("This font file is damaged.")
            f["head"], f["hmtx"], f["cmap"], f["name"]
    return kind, faces


def _standalone(face):
    """A collection member as its own font (safe to modify and save)."""
    from fontTools.ttLib import TTFont
    buf = io.BytesIO()
    face.save(buf)
    buf.seek(0)
    return TTFont(buf, recalcTimestamp=False)


def _outlines(font) -> str:
    for tag, kind in (("glyf", "TrueType"), ("CFF ", "CFF"), ("CFF2", "CFF2")):
        if tag in font:
            return kind
    return "bitmap"


def _name(font, *ids: int) -> str:
    table = font["name"]
    for i in ids:
        try:
            s = table.getDebugName(i)
        except Exception:
            s = None
        if s and s.strip():
            return s.strip()
    return ""


def _display_name(font) -> str:
    full = _name(font, 4)
    if full:
        return full
    fam, style = _name(font, 16, 1), _name(font, 17, 2)
    return f"{fam} {style}".strip() or "Untitled font"


def _file_label(font) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", _display_name(font)).strip()[:80] or "face"


def _cmap(font) -> dict[int, str]:
    best = font.getBestCmap() or {}
    if not best:     # symbol fonts: (3, 0) maps U+F020…U+F0FF
        sym = font["cmap"].getcmap(3, 0)
        best = dict(sym.cmap) if sym else {}
    return best


def _save(font, out: Path) -> Path:
    """Save, then reload the result to prove it's a valid font with every glyph."""
    from fontTools.ttLib import TTFont
    from ..convert import atomic_save
    n = len(font.getGlyphOrder())
    atomic_save(lambda dst: font.save(str(dst)), out)
    try:
        check = TTFont(str(out))
        ok = check["maxp"].numGlyphs == n and check["cmap"] is not None
        check.close()
        if ok and font.flavor is None and _outlines(font) != "bitmap":
            from PIL import ImageFont      # and that FreeType (what apps use) opens it
            ImageFont.truetype(str(out), 24).getbbox("A")
    except Exception:
        ok = False
    if not ok:
        out.unlink(missing_ok=True)
        raise UserError("The converted font didn't come out right, so it was removed.")
    return out


# ---------------------------------------------------------------- outline conversion
TT_ONLY = ("fpgm", "prep", "cvt ", "hdmx", "LTSH", "VDMX", "DSIG")


def _no_variations(font) -> None:
    if "fvar" in font:
        raise UserError("Variable fonts can't change outline type; convert to WOFF2 instead.")


def _to_cff(font) -> None:
    """Quadratic TrueType outlines -> cubic CFF (in place)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.filterPen import DecomposingFilterPen
    from fontTools.pens.reverseContourPen import ReverseContourPen
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    _no_variations(font)
    order, gs, hmtx = font.getGlyphOrder(), font.getGlyphSet(), font["hmtx"]
    charstrings = {}
    for i, name in enumerate(order):
        pen = T2CharStringPen(hmtx[name][0], None)
        # each quadratic becomes the identical cubic (degree elevation, exact); TrueType
        # contours run clockwise, PostScript ones counter-clockwise
        gs[name].draw(DecomposingFilterPen(ReverseContourPen(pen), gs))
        charstrings[name] = pen.getCharString()
        if i % 256 == 0:
            report_progress(0.8 * i / len(order))
    for tag in TT_ONLY + ("glyf", "loca", "gasp"):
        if tag in font:
            del font[tag]
    fb = FontBuilder(font=font)
    ps = re.sub(r"[^!-~]|[\[\](){}<>/%]", "", _name(font, 6) or _display_name(font))[:63]
    info = {"FullName": _display_name(font), "FamilyName": _name(font, 16, 1),
            "Weight": _name(font, 17, 2), "Notice": _name(font, 0)[:1000],
            "isFixedPitch": int(bool(font["post"].isFixedPitch)),
            "ItalicAngle": font["post"].italicAngle,
            "UnderlinePosition": font["post"].underlinePosition,
            "UnderlineThickness": font["post"].underlineThickness}
    fb.setupCFF(ps or "Untitled", info, charstrings, {})
    fb.setupMaxp()
    font["post"].formatType = 3.0
    cs = font["CFF "].cff.topDictIndex[0].CharStrings
    for name in order:     # left side bearing = left edge of the outline
        bounds = cs[name].calcBounds(cs)
        adv = hmtx[name][0]
        hmtx[name] = (adv, int(round(bounds[0])) if bounds else 0)


def _to_glyf(font) -> None:
    """Cubic CFF outlines -> quadratic TrueType (in place), within 1/1000 em."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    _no_variations(font)
    order, gs, hmtx = font.getGlyphOrder(), font.getGlyphSet(), font["hmtx"]
    max_err = font["head"].unitsPerEm / 1000
    glyphs = {}
    for i, name in enumerate(order):
        pen = TTGlyphPen(None)
        gs[name].draw(Cu2QuPen(pen, max_err, reverse_direction=True))
        glyphs[name] = pen.glyph()
        if i % 256 == 0:
            report_progress(0.8 * i / len(order))
    for tag in ("CFF ", "CFF2", "VORG", "DSIG"):
        if tag in font:
            del font[tag]
    fb = FontBuilder(font=font)
    fb.isTTF = True
    font.sfntVersion = "\x00\x01\x00\x00"
    font["head"].glyphDataFormat = 0
    fb.setupGlyf(glyphs)
    fb.setupMaxp()
    post = font["post"]
    post.formatType, post.extraNames, post.mapping = 2.0, [], {}
    for name in order:
        g = glyphs[name]
        hmtx[name] = (hmtx[name][0], getattr(g, "xMin", 0) if g.numberOfContours else 0)


def _convert_face(font, target: str) -> str:
    """Change `font` in place for target; returns the output extension."""
    outl = _outlines(font)
    if "DSIG" in font:        # a signature is invalid once anything changes
        del font["DSIG"]
    if target in ("WOFF", "WOFF2"):
        font.flavor = target.lower()
        return "." + target.lower()
    font.flavor = None
    if target == "TTF" and outl in ("CFF", "CFF2"):
        _to_glyf(font)
    elif target == "OTF" and outl == "TrueType":
        _to_cff(font)
    return "." + target.lower()


def convert(src: Path, target: str) -> list[Path]:
    target = target.upper()
    if target == "WOFF2" and not _have("brotli"):
        raise UserError("Writing WOFF2 needs the 'brotli' package.")
    kind, faces = _open(src)
    if target in ("PNG", "PDF"):
        return _specimen(src, faces, target)
    outs = []
    multi = len(faces) > 1
    for i, face in enumerate(faces):
        with _friendly("This font couldn't be converted (it may be damaged)."):
            font = _standalone(face) if kind == "collection" else face
            ext = _convert_face(font, target)
            out = sibling(src, _file_label(font) if multi else "", ext)
            outs.append(_save(font, out))
        report_progress((i + 1) / len(faces))
    return outs


# ---------------------------------------------------------------- specimens
def _shaping() -> tuple[bool, bool]:
    """(Pillow can shape complex scripts, Pillow can lay out right-to-left text)"""
    from PIL import features
    raqm = bool(features.check_feature("raqm"))
    return raqm, raqm and bool(features.check_feature("fribidi"))


def _plan(font) -> dict:
    """What a specimen shows: only characters the font maps (no fallback-font boxes)."""
    cmap = _cmap(font)

    def covered(s: str) -> bool:
        return all(c.isspace() or ord(c) in cmap for c in s)

    def keep(s: str) -> str:
        return "".join(c for c in s if c.isspace() or ord(c) in cmap).strip()

    name = _display_name(font)
    lines = [(lbl, keep(s)) for lbl, s in (("Uppercase", UPPER), ("Lowercase", LOWER),
                                           ("Figures & punctuation", FIGURES))]
    lines = [(lbl, s) for lbl, s in lines if s]
    scripts = [(lbl, s, shape, rtl) for lbl, s, shape, rtl in SCRIPTS if covered(s)]
    sample = ""
    if not lines:      # no Latin at all (symbols, CJK-only…): show what the font does have
        chars = [chr(c) for c in sorted(cmap) if c > 0x20
                 and unicodedata.category(chr(c))[0] not in "CZM"][:96]
        sample = "".join(chars)
    outl = _outlines(font)
    meta = [_name(font, 5).replace("Version ", "v"),
            f"{len(font.getGlyphOrder()):,} glyphs", f"{len(cmap):,} characters",
            {"TrueType": "TrueType outlines", "CFF": "PostScript (CFF) outlines",
             "CFF2": "CFF2 outlines", "bitmap": "bitmap glyphs"}[outl]]
    if "fvar" in font:
        meta.append("variable: " + ", ".join(a.axisTag for a in font["fvar"].axes))
    return {"name": name, "name_in_font": covered(name), "meta": " · ".join(m for m in meta if m),
            "lines": lines, "pangram": PANGRAM if covered(PANGRAM) else "",
            "scripts": scripts, "sample": sample, "outlines": outl, "cmap": cmap}


def _sfnt_bytes(font) -> bytes:
    font.flavor = None
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def _specimen_png(font, out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    from ..convert import atomic_save
    plan = _plan(font)
    data = _sfnt_bytes(font)
    shape_ok, rtl_ok = _shaping()
    cache: dict[int, object] = {}

    def face(size: int):
        if size not in cache:
            try:
                cache[size] = ImageFont.truetype(io.BytesIO(data), size)
            except OSError:
                raise UserError("This font can't be rendered (bitmap-only fonts such as colour "
                                "emoji aren't supported).") from None
        return cache[size]

    W, M = 1600, 72
    label = ImageFont.load_default(20)
    rows: list[tuple] = []   # (text, font, colour, gap after)

    def fit(text: str, f) -> str:
        """Cut a line that is wider than the page (with an ellipsis if the font has one)."""
        if f.getlength(text) <= W - 2 * M:
            return text
        ell = "…" if f is label or 0x2026 in plan["cmap"] else ""
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if f.getlength(text[:mid] + ell) <= W - 2 * M:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo].rstrip() + ell

    title_font = face(64) if plan["name_in_font"] else ImageFont.load_default(56)
    rows.append((plan["name"], title_font, "#111111", 8))
    rows.append((plan["meta"], label, "#666666", 36))
    for lbl, text in plan["lines"]:
        rows.append((lbl, label, "#888888", 4))
        rows.append((text, face(52), "#111111", 22))
    if plan["sample"]:
        rows.append(("Characters", label, "#888888", 4))
        f = face(44)
        chunk = ""
        for c in plan["sample"]:
            if f.getlength(chunk + c) > W - 2 * M:
                rows.append((chunk, f, "#111111", 6))
                chunk = ""
            chunk += c
        if chunk:
            rows.append((chunk, f, "#111111", 22))
    if plan["pangram"]:
        for size in (12, 18, 24, 36, 48, 72):
            rows.append((f"{size} px", label, "#888888", 2))
            rows.append((plan["pangram"], face(size), "#111111", 14))
    for lbl, text, shape, rtl in plan["scripts"]:
        if (shape and not shape_ok) or (rtl and not rtl_ok):
            continue      # Pillow can't lay this script out correctly here
        rows.append((lbl, label, "#888888", 4))
        rows.append((text, face(40), "#111111", 18))

    def height(f) -> int:
        asc, desc = f.getmetrics()
        return asc + desc

    rows = [(fit(t, f), f, col, gap) for t, f, col, gap in rows]
    H = M * 2 + sum(height(f) + gap for _, f, _, gap in rows)
    im = Image.new("RGB", (W, min(H, 20000)), "white")
    d = ImageDraw.Draw(im)
    y = M
    for text, f, col, gap in rows:
        d.text((M, y), text, font=f, fill=col)
        y += height(f) + gap
    atomic_save(lambda dst: im.save(dst, "PNG", optimize=True), out)
    return out


def _specimen_html(plan: dict, family: str) -> str:
    e = html.escape
    sf = f'font-family:"{family}"'
    parts = [f'<h1 style=\'{sf};font-size:30pt\'>{e(plan["name"])}</h1>' if plan["name_in_font"]
             else f'<h1 class="lbl" style="font-size:26pt">{e(plan["name"])}</h1>',
             f'<p class="lbl meta">{e(plan["meta"])}</p>']
    for lbl, text in plan["lines"]:
        parts += [f'<p class="lbl">{e(lbl)}</p>', f"<p style='{sf};font-size:26pt'>{e(text)}</p>"]
    if plan["sample"]:
        parts += ['<p class="lbl">Characters</p>',
                  f"<p style='{sf};font-size:22pt'>{e(' '.join(plan['sample']))}</p>"]
    if plan["pangram"]:
        for size in (9, 12, 18, 24, 36, 48):
            parts += [f'<p class="lbl">{size} pt</p>',
                      f"<p style='{sf};font-size:{size}pt'>{e(plan['pangram'])}</p>"]
    for lbl, text, _shape, rtl in plan["scripts"]:
        d = ' dir="rtl"' if rtl else ""
        parts += [f'<p class="lbl">{e(lbl)}</p>', f"<p{d} style='{sf};font-size:20pt'>{e(text)}</p>"]
    return "\n".join(parts)


def _specimen_pdf(src: Path, faces: list, out: Path) -> Path:
    from ..convert import atomic_save, fitz
    css = ("body{margin:0} p{margin:0 0 6pt 0} h1{margin:0 0 4pt 0;font-weight:normal}"
           ".lbl{font-family:sans-serif;font-size:8pt;color:#888;margin:8pt 0 1pt 0}"
           ".meta{font-size:9pt;color:#555;margin-bottom:14pt}")

    def write(dst):
        writer = fitz.DocumentWriter(str(dst))
        page = fitz.paper_rect("a4")
        where = page + (48, 48, -48, -48)
        for i, font in enumerate(faces):
            plan = _plan(font)
            if plan["outlines"] == "bitmap":
                raise UserError("Bitmap-only fonts (such as colour emoji) can't be made into "
                                "a PDF specimen.")
            arch = fitz.Archive()
            fname = f"face{i}.{'otf' if plan['outlines'] != 'TrueType' else 'ttf'}"
            arch.add(_sfnt_bytes(font), fname)
            fam = f"DropDialSpecimen{i}"
            story = fitz.Story(html=_specimen_html(plan, fam), archive=arch,
                               user_css=f'@font-face{{font-family:"{fam}";src:url("{fname}")}}' + css)
            more = True
            while more:
                dev = writer.begin_page(page)
                more, _ = story.place(where)
                story.draw(dev)
                writer.end_page()
            report_progress((i + 1) / len(faces))
        writer.close()
        doc = fitz.open(str(dst))      # embed only the glyphs the sheet uses
        try:
            doc.subset_fonts()
            doc.save(str(dst) + ".tmp", garbage=3, deflate=True)
        finally:
            doc.close()
        Path(str(dst) + ".tmp").replace(dst)

    atomic_save(write, out)
    return out


def _specimen(src: Path, faces: list, target: str) -> list[Path]:
    with _friendly("Couldn't render this font (it may be damaged)."):
        if target == "PDF":
            return [_specimen_pdf(src, faces, sibling(src, "Specimen", ".pdf"))]
        outs = []
        for i, font in enumerate(faces):
            lbl = f"Specimen {_file_label(font)}" if len(faces) > 1 else "Specimen"
            outs.append(_specimen_png(font, sibling(src, lbl, ".png")))
            report_progress((i + 1) / len(faces))
        return outs


# ---------------------------------------------------------------- tools
def subset_latin(src: Path) -> list[Path]:
    import logging
    from fontTools import subset
    logging.getLogger("fontTools.subset").setLevel(logging.ERROR)   # "table dropped" chatter
    kind, faces = _open(src)
    outs = []
    for face in faces:
        with _friendly("This font couldn't be subset (it may be damaged)."):
            font = _standalone(face) if kind == "collection" else face
            cmap = _cmap(font)
            if not any(c in cmap for c in range(0x41, 0x7B)):
                raise UserError("This font has no Latin letters to keep.")
            opts = subset.Options()
            opts.layout_features = ["*"]
            opts.name_IDs = ["*"]
            opts.name_languages = ["*"]
            opts.name_legacy = True
            opts.notdef_outline = True
            opts.glyph_names = True
            opts.legacy_kern = True
            opts.recalc_timestamp = False
            sub = subset.Subsetter(opts)
            sub.populate(unicodes=LATIN)
            sub.subset(font)
            if "DSIG" in font:
                del font["DSIG"]
            if kind == "collection":
                ext = ".otf" if _outlines(font) != "TrueType" else ".ttf"
                out = sibling(src, f"{_file_label(font)} Latin", ext)
            else:
                out = sibling(src, "Latin")
            outs.append(_save(font, out))
    if kind != "collection" and outs[0].stat().st_size >= Path(src).stat().st_size:
        outs[0].unlink(missing_ok=True)
        raise NotSmaller("This font already holds only Latin characters.")
    return outs


def _css_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def web_kit(srcs: list[Path]) -> list[Path]:
    """WOFF2 of every dropped font plus one stylesheet with an @font-face rule for each."""
    from urllib.parse import quote
    if not _have("brotli"):
        raise UserError("Making WOFF2 needs the 'brotli' package.")
    folder = output_dir(srcs[0])
    rules, outs, families = [], [], []
    for src in srcs:
        kind, faces = _open(src)
        for face in faces:
            with _friendly("This font couldn't be converted (it may be damaged)."):
                font = _standalone(face) if kind == "collection" else face
                fam = _name(font, 16, 1) or _display_name(font)
                os2 = font["OS/2"] if "OS/2" in font else None
                weight = str(getattr(os2, "usWeightClass", 400) or 400)
                stretch = ""
                style = "normal"
                if os2 is not None:
                    style = "italic" if os2.fsSelection & 1 else (
                        "oblique" if os2.fsSelection & 0x200 else "normal")
                    widths = {1: "50%", 2: "62.5%", 3: "75%", 4: "87.5%", 6: "112.5%",
                              7: "125%", 8: "150%", 9: "200%"}
                    stretch = widths.get(os2.usWidthClass, "")
                if "fvar" in font:
                    for a in font["fvar"].axes:
                        if a.axisTag == "wght":
                            weight = f"{a.minValue:g} {a.maxValue:g}"
                        elif a.axisTag == "wdth":
                            stretch = f"{a.minValue:g}% {a.maxValue:g}%"
                stem = Path(src).stem if len(faces) == 1 else f"{Path(src).stem} {_file_label(font)}"
                out = unique_path(folder / f"{stem}.woff2")
                _convert_face(font, "WOFF2")
                outs.append(_save(font, out))
                rule = [f"  font-family: {_css_string(fam)};",
                        f'  src: url("{quote(out.name)}") format("woff2");',
                        f"  font-weight: {weight};", f"  font-style: {style};"]
                if stretch:
                    rule.append(f"  font-stretch: {stretch};")
                rule.append("  font-display: swap;")
                rules.append("@font-face {\n" + "\n".join(rule) + "\n}")
                if fam not in families:
                    families.append(fam)
    name = families[0] if len(families) == 1 else "fonts"
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", name).strip() or "fonts"
    css = unique_path(folder / f"{name}.css")
    usage = "\n".join(f"/* font-family: {_css_string(f)}, sans-serif; */" for f in families)
    css.write_text("/* Web fonts made by DropDial. Use them with: */\n" + usage + "\n\n"
                   + "\n\n".join(rules) + "\n", encoding="utf-8")
    return outs + [css]


def _info_text(src: Path, kind: str, font) -> str:
    cmap = _cmap(font)
    outl = _outlines(font)
    os2 = font["OS/2"] if "OS/2" in font else None
    lines = [_display_name(font), "=" * len(_display_name(font))]

    def row(label: str, value) -> None:
        if value not in (None, ""):
            lines.append(f"{label + ':':<20}{value}")

    row("Family", _name(font, 16, 1))
    row("Style", _name(font, 17, 2))
    row("PostScript name", _name(font, 6))
    row("Version", _name(font, 5))
    row("File format", {"sfnt": "OpenType" if outl != "TrueType" else "TrueType",
                        "collection": "Font collection", "woff": "WOFF", "woff2": "WOFF2"}[kind])
    row("Outlines", {"TrueType": "TrueType (quadratic)", "CFF": "PostScript / CFF (cubic)",
                     "CFF2": "CFF2 (cubic)", "bitmap": "none (bitmap glyphs)"}[outl])
    row("Glyphs", f"{len(font.getGlyphOrder()):,}")
    row("Characters mapped", f"{len(cmap):,}")
    row("Units per em", font["head"].unitsPerEm)
    if os2 is not None:
        row("Weight class", os2.usWeightClass)
        row("Width class", os2.usWidthClass)
        fs = os2.fsType
        emb = ("Restricted (no embedding)" if fs & 0x2 else "Preview & print" if fs & 0x4
               else "Editable" if fs & 0x8 else "Installable")
        row("Embedding", emb + (", no subsetting" if fs & 0x100 else "")
            + (", bitmap only" if fs & 0x200 else ""))
    row("Italic", "yes" if font["post"].italicAngle or (os2 and os2.fsSelection & 1) else "no")
    row("Monospaced", "yes" if font["post"].isFixedPitch else "no")
    hinted = ("fpgm" in font or "prep" in font) if outl == "TrueType" else None
    if hinted is not None:
        row("Hinting", "TrueType instructions" if hinted else "none")
    colour = [t for t in ("COLR", "CBDT", "sbix", "SVG ") if t in font]
    row("Colour glyphs", ", ".join(t.strip() for t in colour))
    if "fvar" in font:
        lines += ["", "Variable axes"]
        for a in font["fvar"].axes:
            lines.append(f"  {a.axisTag}  {a.minValue:g} … {a.maxValue:g} (default {a.defaultValue:g})")
        inst = [_name(font, i.subfamilyNameID) for i in font["fvar"].instances]
        if inst:
            lines.append("  Named instances: " + ", ".join(i for i in inst if i))
    feats = set()
    for tag in ("GSUB", "GPOS"):
        if tag in font and font[tag].table.FeatureList:
            feats |= {r.FeatureTag for r in font[tag].table.FeatureList.FeatureRecord}
    if "kern" in font:
        feats.add("kern")
    if feats:
        lines += ["", "OpenType features"]
        for f in sorted(feats):
            desc = FEATURES.get(f, "")
            if re.fullmatch(r"(ss|cv)\d\d", f):
                desc = ("stylistic set " if f[:2] == "ss" else "character variant ") + str(int(f[2:]))
            lines.append(f"  {f}  {desc}".rstrip())
    lines += ["", "Unicode coverage"]
    for lo, hi, name in BLOCKS:
        n = sum(1 for c in range(lo, hi + 1) if c in cmap)
        if n:
            lines.append(f"  {name:<28}{n:>6} of {hi - lo + 1}")
    lines += ["", "Legal"]
    for label, ids in (("Copyright", (0,)), ("Trademark", (7,)), ("Manufacturer", (8,)),
                       ("Designer", (9,)), ("Vendor URL", (11,)), ("License", (13,)),
                       ("License URL", (14,))):
        v = _name(font, *ids)
        if v:
            lines.append(f"  {label}: {v}")
    return "\n".join(lines)


def font_info(src: Path) -> list[Path]:
    kind, faces = _open(src)
    with _friendly("This font's details couldn't be read (it may be damaged)."):
        text = "\n\n\n".join(_info_text(src, kind, f) for f in faces)
    out = sibling(src, "Info", ".txt")
    from ..convert import atomic_save
    atomic_save(lambda dst: Path(dst).write_text(text + "\n", encoding="utf-8"), out)
    return [out]


register(Family(
    category="font",
    label="Font",
    exts=EXTS,
    targets=_targets,
    convert=convert,
    hints=HINTS,
    tools=[
        Tool("Subset Latin", "✂", HINTS["Subset Latin"], lambda fs: [o for f in fs for o in subset_latin(f)],
             working="Subsetting…"),
        Tool("Web Kit", "⟨⟩", HINTS["Web Kit"], web_kit, multi=True, working="Making web fonts…"),
        Tool("Font Info", "ⓘ", HINTS["Font Info"], lambda fs: [o for f in fs for o in font_info(f)],
             working="Reading…"),
    ],
    available=lambda: _have("fontTools"),
))
