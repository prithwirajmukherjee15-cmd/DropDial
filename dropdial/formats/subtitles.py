"""Subtitles: SRT, WebVTT, ASS/SSA, YouTube SBV, MicroDVD/SubViewer .sub, SAMI, LRC, TTML/DFXP.

Everything is parsed into a list of `Cue`s (start/end in milliseconds, text as styled runs) and
written back out by a small writer per format. Only italic/bold/underline styling is carried
across formats; positioning, colours and ASS drawings are dropped. Output is always UTF-8.

Tools re-save in the file's own format. "UTF-8" and the fps fixes edit the original text in
place (nothing else changes); "Clean" edits ASS dialogue in place and re-writes other formats.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import util
from . import Family, Tool, register

MAX_BYTES = 50 * 1024 * 1024   # real subtitle files are a few hundred KB
I, B, U = 1, 2, 4              # style flags of a text run
FILM = 24000 / 1001            # "23.976" fps
PAL = 25.0

TARGETS = ["SRT", "VTT", "ASS", "TXT", "SMI", "TTML", "SBV", "LRC"]
HINTS = {
    "SRT": "Plays everywhere", "VTT": "Web & HTML5 video", "ASS": "Styled (mpv, Aegisub)",
    "TXT": "Dialogue only", "SMI": "SAMI (Korean TVs)", "TTML": "Broadcast XML (DFXP)",
    "SBV": "YouTube captions", "LRC": "Synced lyrics",
}
EXT_FMT = {".srt": "srt", ".vtt": "vtt", ".ass": "ass", ".ssa": "ssa", ".sbv": "sbv",
           ".sub": "sub", ".smi": "smi", ".sami": "smi", ".lrc": "lrc", ".ttml": "ttml",
           ".dfxp": "ttml"}
TARGET_EXT = {"SRT": ".srt", "VTT": ".vtt", "ASS": ".ass", "TXT": ".txt", "SMI": ".smi",
              "TTML": ".ttml", "SBV": ".sbv", "LRC": ".lrc"}
BOM_FORMATS = {"ass", "ssa", "smi"}   # their players guess the legacy code page without a BOM


@dataclass
class Cue:
    start: int                       # ms
    end: int                         # ms
    runs: tuple = ()                 # ((text, flags), ...); "\n" separates lines
    settings: str = ""               # WebVTT cue settings, kept for VTT -> VTT

    @property
    def text(self) -> str:
        return "".join(t for t, _ in self.runs)


@dataclass
class Doc:
    fmt: str
    cues: list[Cue]
    fps: float | None = None          # MicroDVD
    header: str = ""                  # VTT STYLE/REGION blocks, SAMI <HEAD>, LRC tags
    tracks: dict[str, list[Cue]] = field(default_factory=dict)   # SAMI languages by class
    wrap2: bool = False               # ASS WrapStyle 2 (\n is a hard break)


# ------------------------------------------------------------------ runs & cues
def _chars(runs):
    return [(c, f) for t, f in runs for c in t]


def _runs(chars) -> tuple:
    out: list[list] = []
    for c, f in chars:
        if out and out[-1][1] == f:
            out[-1][0] += c
        else:
            out.append([c, f])
    return tuple((t, f) for t, f in out)


def _tidy(chars):
    """Spaces collapsed, lines trimmed, empty lines and control characters dropped."""
    lines, cur = [], []
    for c, f in chars:
        if c == "\n":
            lines.append(cur)
            cur = []
        elif c in "\t\xa0 ":
            cur.append((" ", f))
        elif c >= " " and c not in "\ufeff\x7f":
            cur.append((c, f))
    lines.append(cur)
    out = []
    for ln in lines:
        new = []
        for c, f in ln:
            if c == " " and (not new or new[-1][0] == " "):
                continue
            new.append((c, f))
        while new and new[-1][0] == " ":
            new.pop()
        if new:
            if out:
                out.append(("\n", 0))
            out.extend(new)
    return out


def make_cue(start, end, runs, settings="") -> Cue | None:
    chars = _tidy(_chars(runs))
    if not chars:
        return None
    start = max(0, int(start))
    return Cue(start, max(start, int(end)), _runs(chars), settings)


def tidy_cues(cues) -> list[Cue]:
    out, seen = [], set()
    for c in sorted((c for c in cues if c is not None), key=lambda c: (c.start, c.end)):
        key = (c.start, c.end, c.runs)
        if key not in seen:          # e.g. the same ASS line on an outline layer and a text layer
            seen.add(key)
            out.append(c)
    return out


def flatten(cues) -> list[Cue]:
    """Non-overlapping cues for formats/players that show one cue at a time: text that is on
    screen together is stacked into one cue. Overlaps of 100 ms or less are just trimmed."""
    cues = [Cue(c.start, c.end, c.runs, c.settings) for c in cues]
    for a, b in zip(cues, cues[1:]):
        if a.start < b.start < a.end <= b.start + 100:
            a.end = b.start
    if all(a.end <= b.start for a, b in zip(cues, cues[1:])):
        return [c for c in cues if c.end > c.start]
    times = sorted({t for c in cues for t in (c.start, c.end)})
    out: list[Cue] = []
    active: list[Cue] = []
    nxt = 0
    for a, b in zip(times, times[1:]):
        while nxt < len(cues) and cues[nxt].start <= a:
            active.append(cues[nxt])
            nxt += 1
        active = [c for c in active if c.end > a]
        if not active:
            continue
        runs: list = []
        for c in active:
            if runs:
                runs.append(("\n", 0))
            runs.extend(c.runs)
        runs = _runs(_chars(runs))
        if out and out[-1].end == a and out[-1].runs == runs:
            out[-1].end = b
        else:
            out.append(Cue(a, b, runs))
    return out


def plain_lines(cue) -> list[str]:
    return cue.text.split("\n")


# ------------------------------------------------------------------ time helpers
def _ms(h, m, s, frac="") -> int:
    frac = (frac or "")[:3].ljust(3, "0")
    return ((int(h or 0) * 60 + int(m)) * 60 + int(s)) * 1000 + int(frac)


def _hms(ms):
    ms = max(0, int(round(ms)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return h, m, s, ms


def t_srt(ms):
    h, m, s, f = _hms(ms)
    return f"{h:02d}:{m:02d}:{s:02d},{f:03d}"


def t_vtt(ms):
    h, m, s, f = _hms(ms)
    return f"{h:02d}:{m:02d}:{s:02d}.{f:03d}"


def t_sbv(ms):
    h, m, s, f = _hms(ms)
    return f"{h}:{m:02d}:{s:02d}.{f:03d}"


def t_ass(ms):
    cs = int(round(max(0, ms) / 10))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def t_subviewer(ms):
    return t_ass(ms).zfill(11)


def t_lrc(ms):
    cs = int(round(max(0, ms) / 10))
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{m:02d}:{s:02d}.{cs:02d}"


# ------------------------------------------------------------------ decoding
def _score_cjk(text, lo, hi, extra=()) -> float:
    high = [c for c in text if ord(c) > 127]
    if not high:
        return 0.0
    hits = sum(1 for c in high if lo <= ord(c) <= hi or c in extra)
    return hits / len(high)


def _korean_ok(text) -> bool:
    high = [c for c in text if ord(c) > 127]
    if len(high) < 2:
        return False
    good = 0
    for c in high:
        if "\uac00" <= c <= "\ud7a3":
            try:
                c.encode("euc_kr")      # KS X 1001 syllables: what real Korean text uses
                good += 1
            except UnicodeEncodeError:
                pass
    return good / len(high) >= 0.6


def _japanese_ok(text) -> bool:
    high = [c for c in text if ord(c) > 127]
    if len(high) < 2:
        return False
    kana = sum(1 for c in high if "\u3040" <= c <= "\u30ff")
    cjk = sum(1 for c in high if "\u3000" <= c <= "\u9fff" or "\uff00" <= c <= "\uffef")
    return kana / len(high) >= 0.15 and cjk / len(high) >= 0.8


def _cyrillic_ok(text) -> bool:
    words = re.findall(r"\w+", text)
    cyr = [w for w in words if re.search("[\u0400-\u04ff]", w)]
    if len(cyr) < 2:
        return False
    mixed = sum(1 for w in cyr if re.search("[A-Za-z]", w))
    return mixed / len(cyr) < 0.1


def decode(data: bytes) -> tuple[str, str]:
    """(text, encoding). BOMs first, then UTF-8, then the usual legacy code pages."""
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", "replace"), "utf-8-sig"
    for bom, enc in ((b"\xff\xfe\x00\x00", "utf-32-le"), (b"\x00\x00\xfe\xff", "utf-32-be"),
                     (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        if data.startswith(bom):
            return data[len(bom):].decode(enc, "replace"), enc
    if len(data) >= 4 and b"\x00" in data[:400]:
        head = data[:400]
        if head[1::2].count(0) > len(head) // 4:
            return data.decode("utf-16-le", "replace"), "utf-16-le"
        if head[0::2].count(0) > len(head) // 4:
            return data.decode("utf-16-be", "replace"), "utf-16-be"
        raise util.UserError("This doesn't look like a text subtitle file.")
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    m = re.match(rb'\s*<\?xml[^>]*encoding=["\']([\w.-]+)', data)
    if m:
        try:
            return data.decode(m.group(1).decode("ascii")), m.group(1).decode("ascii").lower()
        except (LookupError, UnicodeDecodeError):
            pass
    for enc, ok in (("cp932", _japanese_ok), ("cp949", _korean_ok), ("cp1251", _cyrillic_ok)):
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        if ok(text):
            return text, enc
    try:
        return data.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        return data.decode("latin-1"), "latin-1"


def read_text(src: Path) -> tuple[str, str, bytes]:
    try:
        size = src.stat().st_size
        if size > MAX_BYTES:
            raise util.UserError("This file is too big to be a subtitle file.")
        data = src.read_bytes()
    except OSError:
        raise util.UserError("Can't read this file.") from None
    if data.startswith(b"\x00\x00\x01\xba"):
        raise util.UserError("This .sub is a VobSub picture subtitle; only text subtitles convert.")
    text, enc = decode(data)
    return text.replace("\r\n", "\n").replace("\r", "\n"), enc, data


# ------------------------------------------------------------------ inline markup
_TAG = re.compile(r"<(/?)([a-zA-Z][\w.-]*)([^<>]*)>|\{\\([^{}]*)\}")
_FLAG_TAGS = {"i": I, "em": I, "b": B, "strong": B, "u": U}


def parse_inline(text: str, entities=False, html_ws=False, base=0) -> list:
    """HTML-ish subtitle markup (<i>, <b>, <u>, <br>, {\\i1}) -> runs."""
    if html_ws:
        text = re.sub(r"\s+", " ", text)
    depth = {I: 0, B: 0, U: 0}
    runs, pos = [], 0

    def flags():
        return base | sum(f for f, d in depth.items() if d > 0)

    def add(s):
        if s:
            runs.append((html.unescape(s) if entities else s, flags()))

    for m in _TAG.finditer(text):
        add(text[pos:m.start()])
        pos = m.end()
        if m.group(4) is not None:              # {\i1} style tags inside SRT
            for t in m.group(4).split("\\"):
                mm = re.fullmatch(r"([ibu])(\d)", t.strip())
                if mm:
                    f = {"i": I, "b": B, "u": U}[mm.group(1)]
                    depth[f] = 1 if mm.group(2) != "0" else 0
            continue
        name = m.group(2).lower()
        if name == "br":
            runs.append(("\n", flags()))
        elif name in _FLAG_TAGS:
            f = _FLAG_TAGS[name]
            depth[f] = max(0, depth[f] + (-1 if m.group(1) else 1))
    add(text[pos:])
    return runs


def render_tags(runs, esc=lambda s: s, br="\n") -> str:
    """Runs -> <b><i><u>…</u></i></b>, always well nested."""
    name = {I: "i", B: "b", U: "u"}
    out, stack = [], []
    for t, f in runs:
        want = [x for x in (B, I, U) if f & x]
        k = 0
        while k < len(stack) and k < len(want) and stack[k] == want[k]:
            k += 1
        for x in reversed(stack[k:]):
            out.append(f"</{name[x]}>")
        for x in want[k:]:
            out.append(f"<{name[x]}>")
        stack = want
        out.append(esc(t).replace("\n", br))
    for x in reversed(stack):
        out.append(f"</{name[x]}>")
    return "".join(out)


# ------------------------------------------------------------------ readers
_SRT_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{1,2})[,.:](\d{1,3})"
_SRT_LINE = re.compile(rf"^\s*{_SRT_TIME}\s*-->\s*{_SRT_TIME}")


def read_srt(text: str) -> Doc:
    cues, cur = [], None

    def finish():
        if cur is None:
            return
        lines = cur[2]
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip().isdigit():
            lines.pop()                          # the next cue's number
        body = "\n".join(ln for ln in lines if ln.strip())
        cues.append(make_cue(cur[0], cur[1], parse_inline(body)))

    for line in text.split("\n"):
        m = _SRT_LINE.match(line)
        if m:
            finish()
            g = m.groups()
            cur = (_ms(*g[:4]), _ms(*g[4:]), [])
        elif cur is not None:
            cur[2].append(line)
    finish()
    return Doc("srt", tidy_cues(cues))


_VTT_TIME = r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})"
_VTT_LINE = re.compile(rf"^\s*{_VTT_TIME}\s*-->\s*{_VTT_TIME}(.*)$")


def read_vtt(text: str) -> Doc:
    blocks = re.split(r"\n[ \t]*\n", text.strip("\n"))
    if blocks and blocks[0].lstrip("\ufeff").startswith("WEBVTT"):
        first = blocks[0].split("\n")
        cue_at = next((k for k, ln in enumerate(first) if "-->" in ln), None)
        blocks[0:1] = ["\n".join(first[cue_at:])] if cue_at else []
    cues, header = [], []
    for block in blocks:
        lines = block.strip("\n").split("\n")
        head = lines[0].strip()
        if head.startswith("NOTE") and "-->" not in head:
            continue
        if (head == "STYLE" or head == "REGION") and not cues:
            header.append(block.strip("\n"))
            continue
        for k, ln in enumerate(lines[:2]):
            m = _VTT_LINE.match(ln)
            if m:
                g = m.groups()
                body = "\n".join(lines[k + 1:])
                cues.append(make_cue(_ms(*g[:4]), _ms(*g[4:8]),
                                     _vtt_inline(body), g[8].strip()))
                break
    return Doc("vtt", tidy_cues(cues), header="\n\n".join(header))


def _vtt_inline(body: str) -> list:
    # voice/class/lang/ruby/timestamp tags are dropped; <i>/<b>/<u> kept
    body = re.sub(r"<(?:rt|rp)>.*?</(?:rt|rp)>", "", body, flags=re.S)
    runs, depth, pos = [], {I: 0, B: 0, U: 0}, 0
    for m in re.finditer(r"<(/?)([^\s>./]*)[^>]*>", body):
        if m.start() > pos:
            runs.append((html.unescape(body[pos:m.start()]),
                         sum(f for f, d in depth.items() if d)))
        pos = m.end()
        f = {"i": I, "b": B, "u": U}.get(m.group(2).lower())
        if f:
            depth[f] = max(0, depth[f] + (-1 if m.group(1) else 1))
    if pos < len(body):
        runs.append((html.unescape(body[pos:]), sum(f for f, d in depth.items() if d)))
    return runs


_ASS_DEFAULT_FMT = ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv",
                    "effect", "text"]
_ASS_TIME = re.compile(r"\s*(\d+):(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\s*$")


def _ass_bool(v: str) -> bool:
    try:
        return int(v.strip()) != 0
    except ValueError:
        return False


def _ass_sections(text: str):
    """Yield (section, key, value, line_index) for every 'Key: value' line."""
    section = ""
    for n, line in enumerate(text.split("\n")):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
        elif ":" in s and not s.startswith(";"):
            k, v = s.split(":", 1)
            yield section, k.strip().lower(), v.lstrip(), n


def _ass_layout(text: str):
    styles, fmt, sfmt, wrap2 = {}, _ASS_DEFAULT_FMT, None, False
    for sec, k, v, _ in _ass_sections(text):
        if sec == "script info" and k == "wrapstyle":
            wrap2 = v.strip() == "2"
        elif sec.startswith("v4") and k == "format":
            sfmt = [x.strip().lower() for x in v.split(",")]
        elif sec.startswith("v4") and k == "style" and sfmt:
            vals = [x.strip() for x in v.split(",", len(sfmt) - 1)]
            d = dict(zip(sfmt, vals))
            styles[d.get("name", "").lstrip("*")] = (
                (I if _ass_bool(d.get("italic", "0")) else 0)
                | (B if _ass_bool(d.get("bold", "0")) else 0)
                | (U if _ass_bool(d.get("underline", "0")) else 0))
        elif sec == "events" and k == "format":
            fmt = [x.strip().lower() for x in v.split(",")]
    return styles, fmt, wrap2


def _ass_text_runs(text: str, base: int, styles: dict, wrap2: bool) -> list:
    flags, drawing, runs = base, False, []
    for piece in re.split(r"(\{[^{}]*\})", text):
        if piece.startswith("{") and piece.endswith("}"):
            body = re.sub(r"\\t\((?:[^()]|\([^()]*\))*\)", "", piece[1:-1])
            for t in body.split("\\")[1:]:
                t = t.strip()
                if m := re.fullmatch(r"([iu])(\d*)", t):
                    f = I if m.group(1) == "i" else U
                    on = (base & f) if m.group(2) == "" else m.group(2) != "0"
                    flags = (flags | f) if on else (flags & ~f)
                elif m := re.fullmatch(r"b(\d*)", t):
                    w = m.group(1)
                    on = (base & B) if w == "" else (w == "1" or (len(w) >= 3 and int(w) >= 600))
                    flags = (flags | B) if on else (flags & ~B)
                elif m := re.fullmatch(r"p(\d+)", t):
                    drawing = int(m.group(1)) > 0
                elif t == "r" or (t.startswith("r") and t[1:] in styles):
                    flags = styles.get(t[1:], base) if t != "r" else base
            continue
        if drawing or not piece:
            continue
        piece = piece.replace("\\N", "\n").replace("\\h", " ")
        piece = piece.replace("\\n", "\n" if wrap2 else " ")
        runs.append((piece, flags))
    return runs


def read_ass(text: str) -> Doc:
    styles, fmt, wrap2 = _ass_layout(text)
    cues = []
    for sec, k, v, _ in _ass_sections(text):
        if sec != "events" or k != "dialogue":
            continue
        vals = v.split(",", len(fmt) - 1)
        if len(vals) < len(fmt):
            continue
        d = dict(zip(fmt, vals))
        a, b = _ASS_TIME.match(d.get("start", "")), _ASS_TIME.match(d.get("end", ""))
        if not a or not b:
            continue
        style = d.get("style", "").strip().lstrip("*")
        base = styles.get(style, styles.get("Default", 0))
        cues.append(make_cue(_ms(*a.groups()), _ms(*b.groups()),
                             _ass_text_runs(d.get("text", ""), base, styles, wrap2)))
    return Doc("ass", tidy_cues(cues), wrap2=wrap2)


_SBV_LINE = re.compile(r"^\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})\s*,\s*(\d+):(\d{2}):(\d{2})\.(\d{1,3})\s*$")


def _read_blocks(text, line_re, fmt, br=None) -> Doc:
    cues, cur = [], None
    for line in text.split("\n") + [""]:
        m = line_re.match(line)
        if m:
            g = m.groups()
            cur = (_ms(*g[:4]), _ms(*g[4:]), [])
        elif cur is not None:
            if line.strip():
                cur[2].append(line)
            else:
                body = "\n".join(cur[2])
                if br:
                    body = re.sub(br, "\n", body, flags=re.I)
                cues.append(make_cue(cur[0], cur[1], [(body, 0)]))
                cur = None
    return Doc(fmt, tidy_cues(cues))


def read_sbv(text: str) -> Doc:
    return _read_blocks(text, _SBV_LINE, "sbv")


_SUBVIEWER_LINE = re.compile(r"^\s*(\d+):(\d{2}):(\d{2})\.(\d{2})\s*,\s*(\d+):(\d{2}):(\d{2})\.(\d{2})\s*$")
_MDVD_LINE = re.compile(r"^\s*\{(\d+)\}\{(\d*)\}(.*)$")


def read_subviewer(text: str) -> Doc:
    return _read_blocks(text, _SUBVIEWER_LINE, "subviewer", br=r"\[br\]")


def read_microdvd(text: str, fps: float | None = None) -> Doc:
    rows = [m.groups() for m in map(_MDVD_LINE.match, text.split("\n")) if m]
    if rows and int(rows[0][0]) <= 1 and re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*", rows[0][2]):
        try:
            v = float(rows[0][2].replace(",", "."))
            if 1 <= v <= 240:
                fps = fps or v
        except ValueError:
            pass
        rows = rows[1:]
    fps = fps or FILM
    cues = []
    for n, (a, b, body) in enumerate(rows):
        start = int(a)
        end = int(b) if b else (int(rows[n + 1][0]) if n + 1 < len(rows) else start + round(3 * fps))
        runs, whole = [], 0
        for k, line in enumerate(body.split("|")):
            line_f = whole
            while m := re.match(r"\s*\{([a-zA-Z]):([^}]*)\}", line):
                code, val = m.group(1), m.group(2).lower()
                if code in "yY":
                    f = (I if "i" in val else 0) | (B if "b" in val else 0) | (U if "u" in val else 0)
                    line_f |= f
                    if code == "Y":
                        whole |= f
                line = line[m.end():]
            if line.startswith("/"):               # MPL2-style italics marker
                line_f |= I
                line = line[1:]
            line = re.sub(r"\{[a-zA-Z]:[^}]*\}", "", line)
            if k:
                runs.append(("\n", 0))
            runs.append((line, line_f))
        cues.append(make_cue(start * 1000 / fps + 0.5, end * 1000 / fps + 0.5, runs))
    return Doc("microdvd", tidy_cues(cues), fps=fps)


def _smi_class(attrs: str) -> str:
    m = re.search(r"class\s*=\s*[\"']?([\w-]+)", attrs, re.I)
    return m.group(1) if m else ""


def read_smi(text: str) -> Doc:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    head = re.search(r"<head\b.*?</head>", text, re.I | re.S)
    syncs = list(re.finditer(r"<sync\b([^>]*)>", text, re.I))
    if not syncs:
        return Doc("smi", [])
    events: list[tuple[int, str, str]] = []      # (time, class, html)
    order: list[str] = []
    last_end = None
    for n, m in enumerate(syncs):
        st = re.search(r"start\s*=\s*[\"']?(-?\d+)", m.group(1), re.I)
        if not st:
            continue
        en = re.search(r"end\s*=\s*[\"']?(\d+)", m.group(1), re.I)
        stop = syncs[n + 1].start() if n + 1 < len(syncs) else len(text)
        chunk = text[m.end():stop]
        chunk = re.split(r"</body\s*>", chunk, flags=re.I)[0]
        parts = re.split(r"(<p\b[^>]*>)", chunk, flags=re.I)
        segs = [("", parts[0])] if parts[0].strip() else []
        segs += [(_smi_class(parts[k]), parts[k + 1]) for k in range(1, len(parts) - 1, 2)]
        for cls, body in segs:
            body = re.sub(r"</?(?:p|sync)\b[^>]*>", "", body, flags=re.I)
            events.append((int(st.group(1)), cls, body))
            if cls not in order:
                order.append(cls)
        if en:
            last_end = int(en.group(1))
    tracks: dict[str, list[Cue]] = {}
    for cls in order:
        evs = [e for e in events if e[1] == cls]
        cues = []
        for k, (t, _, body) in enumerate(evs):
            end = evs[k + 1][0] if k + 1 < len(evs) else (last_end or t + 3000)
            cues.append(make_cue(t, end, parse_inline(body, entities=True, html_ws=True)))
        tracks[cls] = tidy_cues(cues)
    main = max(order, key=lambda c: (len(tracks[c]), -order.index(c)))
    return Doc("smi", tracks[main], header=head.group(0) if head else "",
               tracks={c: t for c, t in tracks.items() if t})


_LRC_TAG = re.compile(r"\[([^\]]*)\]")
_LRC_TIME = re.compile(r"^\s*(\d+):(\d{1,2})(?:[.:](\d{1,3}))?\s*$")


def read_lrc(text: str) -> Doc:
    entries, meta, offset = [], [], 0
    for line in text.split("\n"):
        line = line.strip()
        times, pos = [], 0
        while m := _LRC_TAG.match(line, pos):
            tag = m.group(1)
            tm = _LRC_TIME.match(tag)
            if tm:
                times.append(_ms(0, *tm.groups()))
            elif re.match(r"\s*offset\s*:", tag, re.I):
                try:
                    offset = int(tag.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif ":" in tag:
                meta.append(f"[{tag}]")
            pos = m.end()
        lyric = re.sub(r"<\d+:\d{1,2}(?:[.:]\d{1,3})?>", "", line[pos:])   # enhanced word tags
        entries += [(t, lyric) for t in times]
    entries.sort(key=lambda e: e[0])
    cues = []
    for k, (t, lyric) in enumerate(entries):
        if not lyric.strip():
            continue
        nxt = next((e[0] for e in entries[k + 1:] if e[0] > t), t + 5000)
        cues.append(make_cue(t - offset, nxt - offset, [(lyric, 0)]))
    return Doc("lrc", tidy_cues(cues), header="\n".join(meta))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1] if isinstance(tag, str) else ""


def _attr(el, name):
    for k, v in el.attrib.items():
        if _local(k) == name:
            return v
    return None


def read_ttml(text: str) -> Doc:
    import xml.etree.ElementTree as ET
    if re.search(r"<!(?:DOCTYPE|ENTITY)", text, re.I):
        raise util.UserError("This TTML file uses DTD entities, which aren't allowed.")
    body = re.sub(r"^\s*<\?xml[^>]*\?>", "", text.lstrip("\ufeff"))
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise util.UserError("This TTML file is damaged (invalid XML).") from None
    clock = _ttml_clock(root.attrib)
    styles: dict[str, dict] = {}
    for el in root.iter():
        if _local(el.tag) == "style" and _attr(el, "id"):
            styles[_attr(el, "id")] = el.attrib

    def style_flags(attrs, flags, depth=0):
        for ref in (_attr_d(attrs, "style") or "").split():
            if ref in styles and depth < 8:
                flags = style_flags(styles[ref], flags, depth + 1)
        fs, fw, td = (_attr_d(attrs, n) for n in ("fontStyle", "fontWeight", "textDecoration"))
        if fs:
            flags = (flags | I) if fs in ("italic", "oblique") else (flags & ~I)
        if fw:
            flags = (flags | B) if fw == "bold" else (flags & ~B)
        if td:
            flags = (flags | U) if "underline" in td and "noUnderline" not in td else (flags & ~U)
        return flags

    def runs_of(el, flags, out):
        flags = style_flags(el.attrib, flags)
        if el.text:
            out.append((re.sub(r"\s+", " ", el.text), flags))
        for ch in el:
            name = _local(ch.tag)
            if name == "br":
                out.append(("\n", flags))
            elif name in ("span", "a"):
                runs_of(ch, flags, out)
            if ch.tail:
                out.append((re.sub(r"\s+", " ", ch.tail), flags))
        return out

    def timing(el, base, parent_end):
        b, e, d = (_attr(el, n) for n in ("begin", "end", "dur"))
        start = base + clock(b) if b else base
        end = base + clock(e) if e else (start + clock(d) if d else parent_end)
        return start, end

    cues = []

    def walk(el, base, parent_end, flags):
        name = _local(el.tag)
        start, end = timing(el, base, parent_end)
        if name == "p":
            if not _attr(el, "begin") and not _attr(el, "end"):
                spans = [timing(s, start, end) for s in el.iter() if s is not el and _attr(s, "begin")]
                if spans:
                    start, end = min(s for s, _ in spans), max((x for _, x in spans if x is not None),
                                                                default=None)
            cues.append([start, end, runs_of(el, flags, [])])
            return
        flags = style_flags(el.attrib, flags) if name in ("body", "div") else flags
        for ch in el:
            walk(ch, start, end, flags)

    for el in root:
        if _local(el.tag) == "body":
            walk(el, 0, None, 0)
    cues.sort(key=lambda c: c[0])
    out = []
    for k, (s, e, runs) in enumerate(cues):
        if e is None:
            e = next((c[0] for c in cues[k + 1:] if c[0] > s), s + 3000)
        out.append(make_cue(s, e, runs))
    return Doc("ttml", tidy_cues(out))


def _attr_d(attrs: dict, name):
    for k, v in attrs.items():
        if _local(k) == name:
            return v
    return None


def _ttml_clock(root_attrs: dict):
    """TTML time expression -> ms function, using the document's frame and tick rates."""
    def num(name, default):
        try:
            return float((_attr_d(root_attrs, name) or "").split()[0])
        except (ValueError, IndexError):
            return default
    fps = num("frameRate", 30.0)
    mult = (_attr_d(root_attrs, "frameRateMultiplier") or "1 1").split()
    try:
        fps *= float(mult[0]) / float(mult[1])
    except (ValueError, IndexError, ZeroDivisionError):
        pass
    sub = num("subFrameRate", 1.0)
    tick = num("tickRate", fps * sub if _attr_d(root_attrs, "frameRate") else 1.0) or 1.0

    def clock(v: str) -> int:
        v = (v or "").strip()
        if m := re.fullmatch(r"(\d+):(\d{2}):(\d{2})(\.\d+)?", v):
            sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            return round((sec + float(m.group(4) or 0)) * 1000)
        if m := re.fullmatch(r"(\d+):(\d{2}):(\d{2}):(\d+)(?:\.(\d+))?", v):
            sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            frames = int(m.group(4)) + (int(m.group(5)) / sub if m.group(5) else 0)
            return round((sec + frames / fps) * 1000)
        if m := re.fullmatch(r"(\d+(?:\.\d+)?)(h|ms|m|s|f|t)", v):
            x = float(m.group(1))
            scale = {"h": 3_600_000, "m": 60_000, "s": 1000, "ms": 1,
                     "f": 1000 / fps, "t": 1000 / tick}[m.group(2)]
            return round(x * scale)
        raise util.UserError(f"Can't read the TTML time {v[:20]!r}.")
    return clock


READERS = {"srt": read_srt, "vtt": read_vtt, "ass": read_ass, "ssa": read_ass, "sbv": read_sbv,
           "microdvd": read_microdvd, "subviewer": read_subviewer, "smi": read_smi,
           "lrc": read_lrc, "ttml": read_ttml}


def sniff(text: str) -> list[str]:
    """Formats the content looks like, most specific first."""
    head = text[:4000].lstrip("\ufeff \n\t")
    out = []
    if head.startswith("WEBVTT"):
        out.append("vtt")
    if re.search(r"^\s*\[script info\]|^\s*dialogue\s*:", head, re.I | re.M):
        out.append("ass")
    if re.search(r"<sami\b|<sync\b", head, re.I):
        out.append("smi")
    if re.search(r"<tt\b|<tt:tt\b", head):
        out.append("ttml")
    if _SRT_LINE.search(text[:20000]) or re.search(rf"^\s*{_SRT_TIME}\s*-->", text[:20000], re.M):
        out += ["srt", "vtt"]
    if re.search(r"^\s*\{\d+\}\{\d*\}", head, re.M):
        out.append("microdvd")
    if re.search(_SUBVIEWER_LINE.pattern, head, re.M):
        out.append("subviewer")
    if re.search(_SBV_LINE.pattern, head, re.M):
        out.append("sbv")
    if re.search(r"^\s*\[\d+:\d{1,2}(?:[.:]\d{1,3})?\]", head, re.M):
        out.append("lrc")
    return out


def load(src: Path) -> tuple[Doc, str, str]:
    """(document, decoded text, encoding) of a subtitle file."""
    text, enc, _ = read_text(src)
    want = EXT_FMT.get(src.suffix.lower(), "")
    if want == "sub":
        want = next((f for f in sniff(text) if f in ("microdvd", "subviewer")), "microdvd")
    tried = []
    found = sniff(text)
    # a header-signed format (WEBVTT, [Script Info], <SAMI>, <tt>) wins over a wrong extension
    first = found[:1] if found[:1] in (["vtt"], ["ass"], ["smi"], ["ttml"]) else []
    if want == "ssa" and first == ["ass"]:
        first = []
    for fmt in first + [want] + found:
        if fmt in tried or fmt not in READERS:
            continue
        tried.append(fmt)
        try:
            doc = READERS[fmt](text)
        except util.UserError:
            if fmt == want:
                raise
            continue
        if doc.cues:
            if fmt == "ssa" or (fmt == "ass" and want == "ssa"):
                doc.fmt = "ssa"
            return doc, text, enc
    raise util.UserError("No subtitles found in this file.")


# ------------------------------------------------------------------ writers
def _plain_join(cue, sep=" "):
    return sep.join(ln for ln in plain_lines(cue))


def write_srt(doc: Doc) -> str:
    out = []
    for n, c in enumerate(flatten(doc.cues), 1):
        out.append(f"{n}\n{t_srt(c.start)} --> {t_srt(c.end)}\n{render_tags(c.runs)}\n")
    return "\n".join(out)


def write_vtt(doc: Doc) -> str:
    out = ["WEBVTT\n"]
    if doc.fmt == "vtt" and doc.header:
        out.append(doc.header + "\n")
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    for c in doc.cues:
        settings = f" {c.settings}" if doc.fmt == "vtt" and c.settings else ""
        out.append(f"{t_vtt(c.start)} --> {t_vtt(c.end)}{settings}\n{render_tags(c.runs, esc)}\n")
    return "\n".join(out)


ASS_HEADER = """[Script Info]
; Script generated by DropDial
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, \
Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, \
Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3.5,1.5,\
2,100,100,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ass_text(runs) -> str:
    out, cur = [], 0
    for t, f in runs:
        if f != cur:
            out.append("{" + "".join(f"\\{n}{int(bool(f & x))}" for n, x in
                                     (("i", I), ("b", B), ("u", U)) if (f ^ cur) & x) + "}")
            cur = f
        t = t.replace("\\", "\u29f5").replace("{", "(").replace("}", ")")
        out.append(t.replace("\n", "\\N"))
    return "".join(out)


def write_ass(doc: Doc, title="") -> str:
    lines = [ASS_HEADER.format(title=title or "Untitled")]
    for c in doc.cues:
        lines.append(f"Dialogue: 0,{t_ass(c.start)},{t_ass(c.end)},Default,,0,0,0,,{ass_text(c.runs)}\n")
    return "".join(lines)


def write_sbv(doc: Doc) -> str:
    return "\n".join(f"{t_sbv(c.start)},{t_sbv(c.end)}\n{c.text}\n" for c in flatten(doc.cues))


def write_subviewer(doc: Doc) -> str:
    t = t_subviewer
    head = ("[INFORMATION]\n[TITLE]\n[AUTHOR]\n[SOURCE]\n[PRG]\n[FILEPATH]\n[DELAY]0\n[CD TRACK]0\n"
            "[COMMENT]\n[END INFORMATION]\n[SUBTITLE]\n[COLF]&HFFFFFF,[STYLE]bd,[SIZE]18,[FONT]Arial\n")
    return head + "".join(f"{t(c.start)},{t(c.end)}\n{c.text.replace(chr(10), '[br]')}\n\n"
                          for c in flatten(doc.cues))


def write_microdvd(doc: Doc) -> str:
    fps = doc.fps or FILM
    out = [f"{{1}}{{1}}{fps:.3f}".rstrip("0").rstrip(".") + "\n"]
    for c in flatten(doc.cues):
        lines = []
        for ln in _split_lines(c.runs):
            text = "".join(t for t, _ in ln).replace("|", "/")
            common = I | B | U
            for _, f in ln:
                common &= f
            codes = "".join(f"{{y:{n}}}" for n, x in (("i", I), ("b", B), ("u", U)) if common & x)
            lines.append(codes + text)
        a, b = round(c.start * fps / 1000), round(c.end * fps / 1000)
        out.append(f"{{{a}}}{{{max(a, b)}}}{'|'.join(lines)}\n")
    return "".join(out)


def _split_lines(runs):
    lines, cur = [], []
    for c, f in _chars(runs):
        if c == "\n":
            lines.append(cur)
            cur = []
        else:
            cur.append((c, f))
    return [_runs(ln) for ln in lines + [cur]]


def _lang_of(cues) -> str:
    text = "".join(c.text for c in cues[:400])
    for lang, pat in (("ja", "[\u3040-\u30ff]"), ("ko", "[\uac00-\ud7a3]"), ("zh", "[\u4e00-\u9fff]"),
                      ("hi", "[\u0900-\u097f]"), ("ru", "[\u0400-\u04ff]"), ("ar", "[\u0600-\u06ff]"),
                      ("he", "[\u0590-\u05ff]"), ("th", "[\u0e00-\u0e7f]"), ("el", "[\u0370-\u03ff]")):
        if len(re.findall(pat, text)) > 5:
            return lang
    return ""


_SMI_CLASSES = {"ko": ("KRCC", "ko-KR"), "ja": ("JPCC", "ja-JP"), "zh": ("ZHCC", "zh-CN")}


def write_smi(doc: Doc, title="") -> str:
    def body(runs):
        return render_tags(runs, lambda s: html.escape(s, quote=False), "<br>")
    if doc.fmt == "smi" and doc.tracks:
        tracks = doc.tracks
        head = re.sub(r"charset\s*=\s*[\"']?[\w-]+", "charset=utf-8", doc.header, flags=re.I)
    else:
        cls, lang = _SMI_CLASSES.get(_lang_of(doc.cues), ("ENCC", "en-US"))
        tracks = {cls: doc.cues}
        head = (f"<HEAD>\n<TITLE>{html.escape(title)}</TITLE>\n<STYLE TYPE=\"text/css\">\n<!--\n"
                "P { margin-left:8pt; margin-right:8pt; margin-bottom:2pt; margin-top:2pt;\n"
                "    text-align:center; font-size:20pt; font-family:Arial, sans-serif;\n"
                "    font-weight:normal; color:white; }\n"
                f".{cls} {{ Name:{cls}; lang:{lang}; SAMIType:CC; }}\n-->\n</STYLE>\n</HEAD>")
    events = []
    for k, (cls, cues) in enumerate(tracks.items()):
        p = f"<P Class={cls}>" if cls else "<P>"
        cues = flatten(cues)
        for n, c in enumerate(cues):
            events.append((c.start, k, f"<SYNC Start={c.start}>{p}{body(c.runs)}"))
            if n + 1 == len(cues) or cues[n + 1].start > c.end:
                events.append((c.end, k, f"<SYNC Start={c.end}>{p}&nbsp;"))
    events.sort(key=lambda e: (e[0], e[1]))
    return "<SAMI>\n" + head + "\n<BODY>\n" + "\n".join(e[2] for e in events) + "\n</BODY>\n</SAMI>\n"


def write_lrc(doc: Doc) -> str:
    out = [doc.header + "\n"] if doc.fmt == "lrc" and doc.header else []
    cues = flatten(doc.cues)
    for n, c in enumerate(cues):
        out.append(f"[{t_lrc(c.start)}]{_plain_join(c)}\n")
        if n + 1 == len(cues) or round(cues[n + 1].start / 10) > round(c.end / 10):
            out.append(f"[{t_lrc(c.end)}]\n")
    return "".join(out)


def write_ttml(doc: Doc) -> str:
    from xml.sax.saxutils import escape, quoteattr

    def p_body(runs):
        out = []
        for t, f in runs:
            parts = escape(t).split("\n")
            text = "<br/>".join(parts)
            attrs = "".join(a for a, x in ((' tts:fontStyle="italic"', I), (' tts:fontWeight="bold"', B),
                                            (' tts:textDecoration="underline"', U)) if f & x)
            out.append(f"<span{attrs}>{text}</span>" if attrs and t.strip("\n") else text)
        return "".join(out)
    lang = _lang_of(doc.cues)
    ps = "\n".join(f'      <p begin="{t_vtt(c.start)}" end="{t_vtt(c.end)}">{p_body(c.runs)}</p>'
                   for c in doc.cues)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<tt xmlns="http://www.w3.org/ns/ttml" xmlns:tts="http://www.w3.org/ns/ttml#styling"'
            f' xmlns:ttp="http://www.w3.org/ns/ttml#parameter" ttp:timeBase="media" xml:lang={quoteattr(lang)}>\n'
            '  <head>\n    <styling>\n'
            '      <style xml:id="base" tts:fontFamily="proportionalSansSerif" tts:textAlign="center"'
            ' tts:color="white"/>\n    </styling>\n    <layout>\n'
            '      <region xml:id="bottom" tts:origin="10% 75%" tts:extent="80% 20%"'
            ' tts:displayAlign="after" tts:textAlign="center"/>\n    </layout>\n  </head>\n'
            f'  <body style="base" region="bottom">\n    <div>\n{ps}\n    </div>\n  </body>\n</tt>\n')


def write_txt(doc: Doc) -> str:
    out, prev = [], None
    for c in doc.cues:
        lines = plain_lines(c)
        if sum(ln.lstrip().startswith(("-", "–", "—")) for ln in lines) >= 2:
            block = lines                         # "- Hi!\n- Hello." stays two speakers
        else:
            block = [" ".join(lines)]
        for ln in block:
            if ln != prev:                        # rolling captions repeat lines
                out.append(ln)
            prev = ln
    return "\n".join(out) + "\n"


WRITERS = {"srt": write_srt, "vtt": write_vtt, "ass": write_ass, "ssa": write_ass,
           "sbv": write_sbv, "subviewer": write_subviewer, "microdvd": write_microdvd,
           "smi": write_smi, "lrc": write_lrc, "ttml": write_ttml, "txt": write_txt}


def render(doc: Doc, fmt: str, title="") -> str:
    fn = WRITERS[fmt]
    return fn(doc, title) if fmt in ("ass", "ssa", "smi") else fn(doc)


def save_text(text: str, out: Path, fmt: str = "") -> None:
    """UTF-8; a BOM for ASS/SAMI, Windows line ends for SRT (what hardware players expect)."""
    from ..convert import atomic_save
    if fmt == "srt":
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    data = ("\ufeff" if fmt in BOM_FORMATS else "") + text
    atomic_save(lambda dst: Path(dst).write_bytes(data.encode("utf-8")), out)


# ------------------------------------------------------------------ conversion
def targets(src_ext: str) -> list[str]:
    own = EXT_FMT.get("." + src_ext.lower().lstrip("."), "")
    return [t for t in TARGETS if t.lower() != own]


def convert(src: Path, target: str) -> list[Path]:
    target = target.upper()
    if target not in TARGET_EXT:
        raise util.UserError(f"Subtitles can't be converted to {target}.")
    doc, _, _ = load(src)
    fmt = target.lower()
    text = render(doc, fmt, src.stem)
    out = util.sibling(src, ext=TARGET_EXT[target])
    save_text(text, out, fmt)
    return [out]


def _own_format(src: Path, doc: Doc) -> str:
    want = EXT_FMT.get(src.suffix.lower(), "srt")
    if want == "sub":
        return doc.fmt if doc.fmt in ("microdvd", "subviewer") else "subviewer"
    if want in ("ass", "ssa") and doc.fmt not in ("ass", "ssa"):
        return "ass"
    return want


# ------------------------------------------------------------------ Clean (hearing-impaired notes)
_BRACKETS = re.compile(r"\[[^\[\]]*\]|\([^()]*\)|（[^（）]*）|［[^［］]*］|【[^【】]*】")
_MUSIC = re.compile(r"[♪♫♬♩🎵🎶]+")
_SPEAKER = re.compile(r"^([ \t]*(?:[-–—][ \t]*)?)([^\n:]{1,32}?)[ \t]*:(?=[ \t]|$)[ \t]*", re.M)
_DASH = re.compile(r"^[ \t]*[-–—][ \t]*", re.M)


def clean_mask(s: str) -> list[bool]:
    """Which characters of a cue's text to keep after removing SDH annotations."""
    idx = list(range(len(s)))
    cur = s

    def drop(spans):
        nonlocal idx, cur
        dead = set()
        for a, b in spans:
            dead.update(range(a, b))
        if dead:
            idx = [i for k, i in enumerate(idx) if k not in dead]
            cur = "".join(s[i] for i in idx)
        return bool(dead)

    dashes_before = len(_DASH.findall(s))
    touched = False
    while drop(m.span() for m in _BRACKETS.finditer(cur)):   # repeat for nested brackets
        touched = True
    touched |= drop(m.span() for m in _MUSIC.finditer(cur))
    touched |= drop((m.start(2), m.end()) for m in _SPEAKER.finditer(cur)
                    if m.group(2).isupper() and not m.group(2)[0].isdigit())
    # tidy: spaces, then lines left without any words, then a lone dialogue dash
    for pat in (r"(?<= ) +", r"^ +", r" +$"):
        drop(m.span() for m in re.finditer(pat, cur, re.M))
    if touched:
        spans, pos = [], 0
        for line in cur.split("\n"):
            if not re.search(r"\w", line):
                spans.append((pos, pos + len(line) + 1))
            pos += len(line) + 1
        drop(spans)
        drop([(m.start(), m.end()) for m in re.finditer(r"\n+$|^\n+", cur)])
        if dashes_before >= 2 and "\n" not in cur:
            drop(m.span() for m in _DASH.finditer(cur))
    keep = [False] * len(s)
    for i in idx:
        keep[i] = True
    return keep


def clean_cues(cues) -> list[Cue]:
    out = []
    for c in cues:
        chars = _chars(c.runs)
        keep = clean_mask("".join(ch for ch, _ in chars))
        if all(keep):
            out.append(c)
            continue
        new = make_cue(c.start, c.end, _runs([x for x, k in zip(chars, keep) if k]), c.settings)
        if new is not None and re.search(r"\w", new.text):
            out.append(new)
    return out


def clean_doc(doc: Doc) -> Doc:
    return Doc(doc.fmt, clean_cues(doc.cues), doc.fps, doc.header,
               {k: clean_cues(v) for k, v in doc.tracks.items()}, doc.wrap2)


def _ass_clean_text(text: str, wrap2: bool) -> str | None:
    """Clean one ASS Text field in place, keeping every override tag. None = nothing left."""
    items, prefix, drawing = [], "", False     # items: [prefix, char, raw]
    for piece in re.split(r"(\{[^{}]*\})", text):
        if piece.startswith("{") and piece.endswith("}"):
            prefix += piece
            for m in re.finditer(r"\\p(\d+)", piece):
                drawing = int(m.group(1)) > 0
            continue
        if drawing:
            prefix += piece
            continue
        for m in re.finditer(r"\\[Nnh]|.", piece, re.S):
            raw = m.group(0)
            ch = {"\\N": "\n", "\\h": " ", "\\n": "\n" if wrap2 else " "}.get(raw, raw)
            items.append([prefix, ch, raw])
            prefix = ""
    keep = clean_mask("".join(it[1] for it in items))
    out, carry = [], ""
    for it, k in zip(items, keep):
        if k:
            out.append(carry + it[0] + it[2])
            carry = ""
        else:
            carry += it[0]
    plain = "".join(it[1] for it, k in zip(items, keep) if k)
    if not re.search(r"\w", plain):
        return None
    return "".join(out) + carry + prefix


def _ass_edit(text: str, fn) -> str:
    """Apply fn(fields: dict) -> dict | None to every Dialogue line, keeping everything else."""
    _, fmt, _ = _ass_layout(text)
    lines = text.split("\n")
    out = []
    section = ""
    for line in lines:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
        m = re.match(r"(\s*)(Dialogue|Comment)(\s*:\s*)(.*)$", line, re.I)
        if section == "events" and m:
            vals = m.group(4).split(",", len(fmt) - 1)
            if len(vals) == len(fmt):
                d = fn(dict(zip(fmt, vals)), m.group(2).lower())
                if d is None:
                    continue
                line = m.group(1) + m.group(2) + m.group(3) + ",".join(d[k] for k in fmt)
        out.append(line)
    return "\n".join(out)


def tool_clean(paths: list[Path]) -> list[Path]:
    outs = []
    for src in paths:
        doc, text, _ = load(src)
        fmt = _own_format(src, doc)
        if doc.fmt in ("ass", "ssa") and fmt in ("ass", "ssa"):
            removed = 0

            def fix(d, kind):
                nonlocal removed
                if kind != "dialogue":
                    return d
                new = _ass_clean_text(d["text"], doc.wrap2)
                if new is None:
                    removed += 1
                    return None
                return {**d, "text": new}
            result = _ass_edit(text, fix)
            if result == text:
                raise util.UserError("Nothing to clean: no [notes], (sounds) or NAMES: found.")
            out = util.sibling(src, "Clean")
            save_text(result, out, fmt)
        else:
            cleaned = clean_doc(doc)
            if cleaned.cues == doc.cues and cleaned.tracks == doc.tracks:
                raise util.UserError("Nothing to clean: no [notes], (sounds) or NAMES: found.")
            if not cleaned.cues:
                raise util.UserError("Cleaning would leave no subtitles at all.")
            out = util.sibling(src, "Clean")
            save_text(render(cleaned, fmt, src.stem), out, fmt)
        outs.append(out)
    return outs


# ------------------------------------------------------------------ UTF-8
def tool_utf8(paths: list[Path]) -> list[Path]:
    outs = []
    for src in paths:
        doc, _, enc = load(src)
        raw = src.read_bytes()
        text, _ = decode(raw)                      # original line endings kept
        fmt = _own_format(src, doc)
        bom = fmt in BOM_FORMATS
        if fmt == "ttml":
            text = re.sub(r"^(\s*<\?xml[^>]*encoding=)([\"'])[\w.-]+\2", r"\1\2UTF-8\2", text)
        elif fmt == "smi":
            text = re.sub(r"(charset\s*=\s*[\"']?)[\w-]+", r"\1utf-8", text, flags=re.I)
        data = (("\ufeff" if bom else "") + text).encode("utf-8")
        if data == raw:
            raise util.UserError("This file is already UTF-8.")
        out = util.sibling(src, "UTF-8")
        from ..convert import atomic_save
        atomic_save(lambda dst: Path(dst).write_bytes(data), out)
        outs.append(out)
    return outs


# ------------------------------------------------------------------ frame-rate sync
def retime(text: str, fmt: str, k: float) -> str:
    """Scale every time in the file's own text by k, leaving everything else untouched."""
    def sc(ms):
        return int(round(ms * k))

    if fmt == "srt":
        def srt(m):
            g = m.groups()
            return f"{t_srt(sc(_ms(*g[:4])))} --> {t_srt(sc(_ms(*g[4:])))}"
        return re.sub(rf"(?m)^[ \t]*{_SRT_TIME}[ \t]*-->[ \t]*{_SRT_TIME}", srt, text)
    if fmt == "vtt":
        text = re.sub(rf"(?m)^[ \t]*{_VTT_TIME}[ \t]*-->[ \t]*{_VTT_TIME}",
                      lambda m: f"{t_vtt(sc(_ms(*m.groups()[:4])))} --> {t_vtt(sc(_ms(*m.groups()[4:])))}",
                      text)
        return re.sub(rf"<{_VTT_TIME}>", lambda m: f"<{t_vtt(sc(_ms(*m.groups())))}>", text)
    if fmt in ("ass", "ssa"):
        def fix(d, _kind):
            for key in ("start", "end"):
                m = _ASS_TIME.match(d.get(key, ""))
                if m:
                    d[key] = t_ass(sc(_ms(*m.groups())))
            return d
        return _ass_edit(text, fix)
    if fmt in ("sbv", "subviewer"):
        line, tf = (_SBV_LINE, t_sbv) if fmt == "sbv" else (_SUBVIEWER_LINE, t_subviewer)

        def blk(m):
            g = m.groups()
            return f"{tf(sc(_ms(*g[:4])))},{tf(sc(_ms(*g[4:])))}"
        return re.sub(line.pattern.replace(r"\s*$", "[ \t]*$").replace(r"^\s*", "^[ \t]*"),
                      blk, text, flags=re.M)
    if fmt == "microdvd":
        def mdvd(m):
            if m.group(2) == "1" and m.group(1) in ("0", "1") and \
                    re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*", m.group(3)):
                return m.group(0)                 # the {1}{1}fps line
            b = str(sc(int(m.group(2)))) if m.group(2) else ""
            return f"{{{sc(int(m.group(1)))}}}{{{b}}}{m.group(3)}"
        return re.sub(r"(?m)^\{(\d+)\}\{(\d*)\}(.*)$", mdvd, text)
    if fmt == "smi":
        def sync(m):
            return re.sub(r"(?i)(\b(?:start|end)\s*=\s*[\"']?)(\d+)",
                          lambda a: a.group(1) + str(sc(int(a.group(2)))), m.group(0))
        return re.sub(r"(?i)<sync\b[^>]*>", sync, text)
    if fmt == "lrc":
        def lrc_tag(m):
            return f"{m.group(1)}{t_lrc(sc(_ms(0, m.group(2), m.group(3), m.group(4))))}{m.group(5)}"
        text = re.sub(r"([\[<])(\d+):(\d{1,2})(?:[.:](\d{1,3}))?([\]>])", lrc_tag, text)
        return re.sub(r"(?i)(\[\s*offset\s*:\s*)([+-]?\d+)",
                      lambda m: m.group(1) + ("+" if m.group(2).startswith("+") else "")
                      + str(sc(int(m.group(2)))), text)
    if fmt == "ttml":
        rm = re.search(r"<(?:\w+:)?tt\b[^>]*>", text)
        attrs = dict(re.findall(r"([\w:]+)\s*=\s*\"([^\"]*)\"", rm.group(0))) if rm else {}
        clock = _ttml_clock(attrs)
        return re.sub(r"(\s(?:begin|end|dur)\s*=\s*)([\"'])([^\"']*)\2",
                      lambda m: f"{m.group(1)}{m.group(2)}{t_vtt(sc(clock(m.group(3))))}{m.group(2)}",
                      text)
    raise util.UserError("This subtitle format can't be re-timed.")


def _sync_tool(k: float, label: str):
    def run(paths: list[Path]) -> list[Path]:
        outs = []
        for src in paths:
            doc, _, _ = load(src)
            text, _ = decode(src.read_bytes())
            fmt = _own_format(src, doc)
            if fmt != doc.fmt and not (fmt in ("ass", "ssa") and doc.fmt in ("ass", "ssa")):
                # content doesn't match the extension: re-write it properly
                doc.cues = [Cue(int(round(c.start * k)), int(round(c.end * k)), c.runs, c.settings)
                            for c in doc.cues]
                result = render(doc, fmt, src.stem)
            else:
                result = retime(text, fmt, k)
            out = util.sibling(src, label)
            save_text(result.lstrip("\ufeff"), out, "" if fmt == "srt" else fmt)
            outs.append(out)
        return outs
    return run


TOOLS = [
    Tool("Clean", "✂", "Remove [SDH] notes", tool_clean, working="Cleaning…"),
    Tool("UTF-8", "ü", "Fix garbled accents", tool_utf8, working="Re-encoding…"),
    Tool("25 fps", "»", "23.976 → 25 fps (PAL)", _sync_tool(FILM / PAL, "25fps"),
         working="Re-timing…"),
    Tool("23.976 fps", "«", "25 → 23.976 fps", _sync_tool(PAL / FILM, "23.976fps"),
         working="Re-timing…"),
]

register(Family(
    category="subtitle",
    label="Subtitles",
    exts=set(EXT_FMT),
    targets=targets,
    convert=convert,
    hints={**HINTS, **{t.name: t.hint for t in TOOLS}},
    tools=TOOLS,
))
