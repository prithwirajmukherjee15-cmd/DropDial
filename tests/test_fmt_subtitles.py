"""Subtitle family: parsers, writers, encodings and tools, checked against independent parsers."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from dropdial import convert, util
from dropdial.formats import subtitles as S
from dropdial.util import UserError

SRT = """1
00:00:01,000 --> 00:00:03,500
Hello, <i>world</i>!
Second line — नमस्ते

2
00:00:04,250 --> 00:00:06,000
日本語のテキスト 🎬

3
00:01:02,003 --> 00:01:05,999
<b>Bold</b> and <u>under</u>
"""
EXPECT = [(1000, 3500, "Hello, world!\nSecond line — नमस्ते"),
          (4250, 6000, "日本語のテキスト 🎬"),
          (62003, 65999, "Bold and under")]


def hand_srt(text):
    """Independent SRT reader: [(start, end, text_without_tags)]."""
    out = []
    for block in re.split(r"\r?\n\r?\n", text.strip()):
        lines = block.splitlines()
        m = re.match(r"(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})$", lines[1])
        assert lines[0].isdigit() and m, block
        g = list(map(int, m.groups()))
        ms = lambda h, mi, s, f: ((h * 60 + mi) * 60 + s) * 1000 + f  # noqa: E731
        out.append((ms(*g[:4]), ms(*g[4:]), re.sub(r"</?[ibu]>", "", "\n".join(lines[2:]))))
    return out


def write(tmp_path, name, text, enc="utf-8"):
    p = tmp_path / name
    p.write_bytes(text.encode(enc))
    return p


def conv(p, target):
    cat = util.category(p)
    assert cat == "subtitle"
    (out,) = convert.convert(p, cat, target)
    assert out != p and out.exists()
    return out


def test_registry_and_targets():
    for ext in ("srt", "vtt", "ass", "ssa", "sbv", "sub", "smi", "sami", "lrc", "ttml", "dfxp"):
        assert util.category(f"x.{ext}") == "subtitle"
        t = convert.targets_for("subtitle", ext)
        assert 0 < len(t) <= 9 and all(x == x.upper() for x in t)
    assert "SRT" not in convert.targets_for("subtitle", "srt")
    assert "TTML" not in convert.targets_for("subtitle", "dfxp")
    assert "SMI" not in convert.targets_for("subtitle", "sami")
    fam = __import__("dropdial.formats", fromlist=["x"]).family("subtitle")
    assert all(len(h) <= 22 for h in fam.hints.values())
    assert len(fam.tools) <= 6


def test_srt_vtt_srt_round_trip(tmp_path):
    src = write(tmp_path, "movie.srt", SRT)
    vtt = conv(src, "VTT")
    vt = vtt.read_text("utf-8")
    assert vt.startswith("WEBVTT\n\n")
    assert "00:00:01.000 --> 00:00:03.500" in vt and "<i>world</i>" in vt
    assert "00:01:02.003 --> 00:01:05.999" in vt
    back = conv(vtt, "SRT")
    raw = back.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" in raw
    assert hand_srt(raw.decode("utf-8")) == EXPECT
    assert "Hello, <i>world</i>!" in raw.decode("utf-8")
    assert src.read_text("utf-8") == SRT          # source untouched


def test_vtt_read_with_pysubs2(tmp_path):
    pysubs2 = pytest.importorskip("pysubs2")
    vtt = conv(write(tmp_path, "a.srt", SRT), "VTT")
    subs = pysubs2.load(str(vtt))
    assert [(e.start, e.end) for e in subs] == [(a, b) for a, b, _ in EXPECT]
    assert subs[1].plaintext == "日本語のテキスト 🎬"


ASS = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,10,1
Style: Thoughts,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,-1,0,0,100,100,0,0,1,2,1,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:05.00,0:00:07.50,Default,,0,0,0,,Second, {\i1}italic{\i0} word
Dialogue: 0,0:00:01.20,0:00:03.45,Default,,0,0,0,,{\an8\pos(960,100)}First line\NSecond, line
Comment: 0,0:00:02.00,0:00:03.00,Default,,0,0,0,,not shown
Dialogue: 0,0:00:08.00,0:00:09.00,Thoughts,,0,0,0,,I'm thinking
Dialogue: 0,0:00:10.00,0:00:11.00,Default,,0,0,0,,{\p1}m 0 0 l 100 0 100 100 0 100{\p0}
Dialogue: 0,0:00:12.00,0:00:13.00,Default,,0,0,0,,{\b1}Bold{\b0} {Translator note}ok
"""


def test_ass_to_srt(tmp_path):
    out = conv(write(tmp_path, "show.ass", ASS), "SRT")
    text = out.read_text("utf-8")
    assert hand_srt(text) == [(1200, 3450, "First line\nSecond, line"),
                              (5000, 7500, "Second, italic word"),
                              (8000, 9000, "I'm thinking"),
                              (12000, 13000, "Bold ok")]
    assert "<i>italic</i>" in text and "<i>I'm thinking</i>" in text and "<b>Bold</b>" in text
    assert "not shown" not in text and "m 0 0" not in text and "pos" not in text


def test_srt_to_ass_read_back(tmp_path):
    pysubs2 = pytest.importorskip("pysubs2")
    out = conv(write(tmp_path, "m.srt", SRT), "ASS")
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")
    subs = pysubs2.load(str(out))
    # ASS stores centiseconds
    assert [(e.start, e.end) for e in subs] == [(1000, 3500), (4250, 6000), (62000, 66000)]
    assert subs[0].plaintext == "Hello, world!\nSecond line — नमस्ते"
    assert r"{\i1}world{\i0}" in subs[0].text


def test_microdvd_frames(tmp_path):
    p = write(tmp_path, "film.sub", "{1}{1}25\n{25}{75}Hello|{y:i}world\n{100}{150}Bye\n")
    text = conv(p, "SRT").read_text("utf-8")
    assert hand_srt(text) == [(1000, 3000, "Hello\nworld"), (4000, 6000, "Bye")]
    assert "<i>world</i>" in text
    # no fps line: assume 23.976
    p2 = write(tmp_path, "film2.sub", "{240}{480}Hi\n")
    assert hand_srt(conv(p2, "SRT").read_text("utf-8")) == [(10010, 20020, "Hi")]


def test_subviewer_sub(tmp_path):
    p = write(tmp_path, "sv.sub", "[INFORMATION]\n[END INFORMATION]\n[SUBTITLE]\n"
              "00:00:01.50,00:00:02.75\nOne[br]Two\n\n")
    assert hand_srt(conv(p, "SRT").read_text("utf-8")) == [(1500, 2750, "One\nTwo")]


KOREAN_SAMI = """<SAMI>
<HEAD><TITLE>테스트</TITLE>
<STYLE TYPE="text/css"><!--
P { font-size:20pt; }
.KRCC { Name:Korean; lang:ko-KR; SAMIType:CC; }
.ENCC { Name:English; lang:en-US; SAMIType:CC; }
--></STYLE></HEAD>
<BODY>
<SYNC Start=1000><P Class=KRCC>안녕하세요<br>반갑습니다
<SYNC Start=1000><P Class=ENCC>Hello
<SYNC Start=3500><P Class=KRCC>&nbsp;
<SYNC Start=3500><P Class=ENCC>&nbsp;
<SYNC Start=4000><P Class=KRCC><i>감사합니다</i>
<SYNC Start=6000><P Class=KRCC>&nbsp;
</BODY>
</SAMI>
"""


def test_korean_sami_cp949(tmp_path):
    p = write(tmp_path, "drama.smi", KOREAN_SAMI, "cp949")
    with pytest.raises(UnicodeDecodeError):
        p.read_bytes().decode("utf-8")
    text = conv(p, "SRT").read_text("utf-8")
    assert hand_srt(text) == [(1000, 3500, "안녕하세요\n반갑습니다"), (4000, 6000, "감사합니다")]
    # UTF-8 tool keeps the SAMI as-is, both languages, now readable as UTF-8 (with a BOM)
    (u,) = S.tool_utf8([p])
    raw = u.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw[3:].decode("utf-8") == KOREAN_SAMI
    with pytest.raises(UserError):
        S.tool_utf8([u])


def test_smi_output_read_by_pysubs2(tmp_path):
    pysubs2 = pytest.importorskip("pysubs2")
    out = conv(write(tmp_path, "k.srt", "1\n00:00:01,000 --> 00:00:02,000\n안녕하세요 세계\n"), "SMI")
    raw = out.read_text("utf-8-sig")
    assert "Class=KRCC" in raw and "<SYNC Start=2000><P Class=KRCC>&nbsp;" in raw
    subs = pysubs2.SSAFile.from_string(raw, format_="sami")
    got = [(e.start, e.end, e.plaintext) for e in subs if e.plaintext.strip()]
    assert got == [(1000, 2000, "안녕하세요 세계")]


def test_encodings(tmp_path):
    body = "1\n00:00:01,000 --> 00:00:02,000\nCafé crème, déjà vu\n"
    for enc, name in (("cp1252", "a.srt"), ("utf-16", "b.srt"), ("utf-8-sig", "c.srt")):
        out = conv(write(tmp_path, name, body, enc), "SRT" if name != "a.srt" else "VTT")
        assert "Café crème, déjà vu" in out.read_text("utf-8")
    jp = "1\n00:00:01,000 --> 00:00:02,000\nこんにちは、世界。ありがとう\n"
    out = conv(write(tmp_path, "j.srt", jp, "shift_jis"), "TXT")
    assert out.read_text("utf-8") == "こんにちは、世界。ありがとう\n"
    ru = "1\n00:00:01,000 --> 00:00:02,000\nПривет, как дела? Хорошо\n"
    assert "Привет, как дела?" in conv(write(tmp_path, "r.srt", ru, "cp1251"), "TXT").read_text("utf-8")


def test_utf8_tool_srt_bom_and_cp1252(tmp_path):
    body = "1\r\n00:00:01,000 --> 00:00:02,000\r\nÀ bientôt\r\n"
    (o,) = S.tool_utf8([write(tmp_path, "x.srt", body, "cp1252")])
    assert o.read_bytes() == body.encode("utf-8")
    (o2,) = S.tool_utf8([write(tmp_path, "y.srt", body, "utf-8-sig")])
    assert o2.read_bytes() == body.encode("utf-8")
    with pytest.raises(UserError):
        S.tool_utf8([o2])


def test_clean_tool(tmp_path):
    src = """1
00:00:01,000 --> 00:00:02,000
[MUSIC PLAYING]

2
00:00:02,500 --> 00:00:04,000
JOHN: Where are you going?

3
00:00:05,000 --> 00:00:06,000
- (laughs) Nowhere.
- MARY: Really?

4
00:00:07,000 --> 00:00:08,000
♪ La la la ♪

5
00:00:09,000 --> 00:00:10,000
- [door slams]
- <i>Who's there?</i>

6
00:00:11,000 --> 00:00:12,000
Meet me at 10:30, Dr. Smith.

7
00:00:13,000 --> 00:00:14,000
...
"""
    (out,) = S.tool_clean([write(tmp_path, "c.srt", src)])
    assert out.name == "c Clean.srt"
    text = out.read_bytes().decode("utf-8")
    assert hand_srt(text) == [(2500, 4000, "Where are you going?"),
                              (5000, 6000, "- Nowhere.\n- Really?"),
                              (7000, 8000, "La la la"),
                              (9000, 10000, "Who's there?"),
                              (11000, 12000, "Meet me at 10:30, Dr. Smith."),
                              (13000, 14000, "...")]
    assert text.startswith("1\r\n00:00:02,500") and "<i>Who's there?</i>" in text
    clean = write(tmp_path, "ok.srt", "1\n00:00:01,000 --> 00:00:02,000\nNothing here\n")
    with pytest.raises(UserError):
        S.tool_clean([clean])


def test_clean_ass_keeps_styling(tmp_path):
    src = ASS.replace("Second, {\\i1}italic{\\i0} word", "{\\i1}[thunder]{\\i0} BOB: Run!")
    (out,) = S.tool_clean([write(tmp_path, "s.ass", src)])
    text = out.read_text("utf-8-sig")
    assert "[V4+ Styles]" in text and "Style: Thoughts" in text and "Comment:" in text
    line = [ln for ln in text.splitlines() if ln.startswith("Dialogue: 0,0:00:05.00")][0]
    assert line.endswith(",,{\\i1}{\\i0}Run!")
    assert "{\\an8\\pos(960,100)}First line\\NSecond, line" in text


def test_fps_sync(tmp_path):
    k = S.FILM / 25
    src = write(tmp_path, "m.srt", SRT)
    (out,) = S._sync_tool(k, "25fps")([src])
    got = hand_srt(out.read_text("utf-8"))
    assert [(a, b) for a, b, _ in got] == [(round(a * k), round(b * k)) for a, b, _ in EXPECT]
    assert got[0][0] == 959 and got[2][1] == round(65999 * 24000 / 1001 / 25)
    # and back again lands within a millisecond
    (back,) = S._sync_tool(1 / k, "23.976fps")([out])
    for (a, b, _), (x, y, _) in zip(EXPECT, hand_srt(back.read_text("utf-8"))):
        assert abs(a - x) <= 1 and abs(b - y) <= 1


def test_fps_sync_ass_and_others_keep_content(tmp_path):
    tool = next(t for t in S.TOOLS if t.name == "25 fps")
    (out,) = tool.run([write(tmp_path, "s.ass", ASS)])
    text = out.read_text("utf-8-sig")
    assert "Dialogue: 0,0:00:01.15,0:00:03.31,Default" in text      # 1.20*0.959=1.151, 3.45→3.309
    assert "{\\an8\\pos(960,100)}First line" in text and "Style: Thoughts" in text
    sami = write(tmp_path, "k.smi", KOREAN_SAMI, "cp949")
    (o2,) = tool.run([sami])
    t2 = o2.read_text("utf-8-sig")
    assert "<SYNC Start=959><P Class=KRCC>" in t2 and "<SYNC Start=3357>" in t2 and "Class=ENCC" in t2
    (o3,) = tool.run([write(tmp_path, "f.sub", "{1}{1}25\n{1000}{2000}Hi\n")])
    assert o3.read_text("utf-8") == "{1}{1}25\n{959}{1918}Hi\n"


TTML = """<?xml version="1.0" encoding="utf-8"?>
<tt xmlns="http://www.w3.org/ns/ttml" xmlns:tts="http://www.w3.org/ns/ttml#styling"
    xmlns:ttp="http://www.w3.org/ns/ttml#parameter" ttp:tickRate="10000000" ttp:frameRate="25">
  <head><styling><style xml:id="it" tts:fontStyle="italic"/></styling></head>
  <body><div>
    <p begin="10000000t" end="25000000t">First
       line<br/>second</p>
    <p begin="00:00:03:05" dur="2s" style="it">Framed</p>
    <p begin="5.5s" end="00:00:07.250"><span tts:fontWeight="bold">Bold</span> text</p>
  </div></body>
</tt>"""


def test_ttml_in_and_out(tmp_path):
    p = write(tmp_path, "n.dfxp", TTML)
    text = conv(p, "SRT").read_text("utf-8")
    assert hand_srt(text) == [(1000, 2500, "First line\nsecond"), (3200, 5200, "Framed"),
                              (5500, 7250, "Bold text")]
    assert "<i>Framed</i>" in text and "<b>Bold</b>" in text
    out = conv(write(tmp_path, "m.srt", SRT), "TTML")
    root = ET.parse(out).getroot()
    ns = {"t": "http://www.w3.org/ns/ttml"}
    ps = root.findall(".//t:p", ns)
    assert [(p.get("begin"), p.get("end")) for p in ps][0] == ("00:00:01.000", "00:00:03.500")
    assert "".join(ps[1].itertext()) == "日本語のテキスト 🎬"
    assert ps[0].find("t:br", ns) is not None


def test_ttml_rejects_entities(tmp_path):
    bomb = '<?xml version="1.0"?><!DOCTYPE tt [<!ENTITY a "aaaa">]><tt><body><p begin="1s" end="2s">&a;</p></body></tt>'
    with pytest.raises(UserError):
        conv(write(tmp_path, "b.ttml", bomb), "SRT")


def test_lrc_sbv_txt(tmp_path):
    lrc = "[ar:Someone]\n[ti:Song]\n[offset:+500]\n[00:12.00][01:00.50]Chorus line\n[00:15.30]Verse\n[00:20.00]\n"
    text = conv(write(tmp_path, "song.lrc", lrc), "SRT").read_text("utf-8")
    assert hand_srt(text) == [(11500, 14800, "Chorus line"), (14800, 19500, "Verse"),
                              (60000, 65000, "Chorus line")]
    out = conv(write(tmp_path, "m.srt", SRT), "LRC").read_text("utf-8")
    assert out.splitlines()[:3] == ["[00:01.00]Hello, world! Second line — नमस्ते",
                                    "[00:03.50]", "[00:04.25]日本語のテキスト 🎬"]
    sbv = conv(write(tmp_path, "m2.srt", SRT), "SBV").read_text("utf-8")
    assert sbv.startswith("0:00:01.000,0:00:03.500\nHello, world!\nSecond line — नमस्ते\n\n")
    back = conv(write(tmp_path, "y.sbv", sbv), "SRT").read_text("utf-8")
    assert [(a, b) for a, b, _ in hand_srt(back)] == [(a, b) for a, b, _ in EXPECT]
    txt = conv(write(tmp_path, "m3.srt", SRT), "TXT").read_text("utf-8")
    assert txt == "Hello, world! Second line — नमस्ते\n日本語のテキスト 🎬\nBold and under\n"


def test_overlaps_sorted_and_stacked(tmp_path):
    src = ("2\n00:00:05,000 --> 00:00:06,000\nLater\n\n"
           "1\n00:00:01,000 --> 00:00:04,000\nTop\n\n"
           "3\n00:00:02,000 --> 00:00:03,000\nBottom\n")
    vtt = conv(write(tmp_path, "o.srt", src), "VTT").read_text("utf-8")
    assert vtt.index("Top") < vtt.index("Bottom") < vtt.index("Later")   # VTT keeps overlaps
    srt = conv(write(tmp_path, "o.vtt", vtt), "SRT").read_text("utf-8")
    assert hand_srt(srt) == [(1000, 2000, "Top"), (2000, 3000, "Top\nBottom"),
                             (3000, 4000, "Top"), (5000, 6000, "Later")]


def test_bad_input(tmp_path):
    with pytest.raises(UserError):
        conv(write(tmp_path, "e.srt", "just some words\n"), "VTT")
    p = tmp_path / "v.sub"
    p.write_bytes(b"\x00\x00\x01\xba" + bytes(200))
    with pytest.raises(UserError):
        conv(p, "SRT")


def test_mislabelled_vtt_as_srt(tmp_path):
    vt = "WEBVTT\n\n00:01.000 --> 00:02.000 align:start\n<v Bob>Hi &amp; bye\n"
    assert conv(write(tmp_path, "w.srt", vt), "TXT").read_text("utf-8") == "Hi & bye\n"
    assert hand_srt(conv(write(tmp_path, "w2.vtt", vt), "SRT").read_text("utf-8")) == \
        [(1000, 2000, "Hi & bye")]


def test_cli(tmp_path):
    import subprocess
    import sys
    p = write(tmp_path, "cli.srt", SRT)
    r = subprocess.run([sys.executable, "-m", "dropdial", "convert", str(p), "--to", "VTT"],
                       capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "cli.vtt").read_text("utf-8").startswith("WEBVTT")
