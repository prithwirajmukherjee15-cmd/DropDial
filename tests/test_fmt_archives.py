"""Archives family: safe extraction, faithful re-packing, zip_paths, the List tool.

Every archive is built inside the test. Round trips hash every file and compare file times and
empty folders; malicious archives prove nothing lands outside the output folder."""
import bz2
import gzip
import hashlib
import io
import lzma
import os
import shutil
import sys
import stat
import struct
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

from dropdial import cli, convert, util
from dropdial.formats import archives
from dropdial.util import UserError

py7zr = pytest.importorskip("py7zr")

T0 = 1_600_000_000          # even seconds: ZIP's DOS time only has 2 s resolution


# ---------------------------------------------------------------- helpers
def make_tree(root: Path) -> Path:
    """A realistic folder: Unicode names, nested + empty folders, binary data, fixed times."""
    files = {
        "readme.txt": "Hello archive\n" * 200,
        "नमस्ते दुनिया.txt": "हिन्दी पाठ\n" * 50,
        "日本語/ファイル.md": "# 見出し\n本文です。\n" * 40,
        "日本語/深い/😀 emoji.txt": "smile 😀\n",
        "data/blob.bin": os.urandom(300_000),           # incompressible
        "data/zeros.bin": b"\0" * 200_000,              # very compressible
        "data/run.sh": "#!/bin/sh\necho hi\n",
    }
    for i, (rel, content) in enumerate(files.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        (p.write_bytes if isinstance(content, bytes) else lambda c: p.write_text(c, encoding="utf-8"))(content)
        os.utime(p, (T0 + i * 1000, T0 + i * 1000))
    (root / "data" / "run.sh").chmod(0o755)
    (root / "empty folder").mkdir()
    (root / "data" / "nested empty").mkdir()
    for i, d in enumerate(sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts))):
        os.utime(d, (T0 + 50_000 + i * 2, T0 + 50_000 + i * 2))
    os.utime(root, (T0 + 90_000, T0 + 90_000))
    return root


def snapshot(root: Path, times=True) -> dict:
    """relative path -> ('dir', mtime) or ('file', sha256, mtime)."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        assert not p.is_symlink(), f"symlink created: {rel}"
        m = int(p.stat().st_mtime) if times else None
        out[rel] = ("dir", m) if p.is_dir() else ("file", hashlib.sha256(p.read_bytes()).hexdigest(), m)
    return out


def all_files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")}


def assert_no_leftovers(folder: Path):
    assert not [p for p in folder.iterdir() if p.name.startswith(".~")], "temp files left behind"


def zip_with(path: Path, entries, flag_utf8=None):
    """entries: (name, data, extra kwargs for ZipInfo attributes)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data, *attrs in entries:
            zi = zipfile.ZipInfo(name, date_time=(2021, 5, 6, 7, 8, 10))
            zi.compress_type = zipfile.ZIP_DEFLATED
            for k, v in (attrs[0] if attrs else {}).items():
                setattr(zi, k, v)
            zf.writestr(zi, data)
    return path


def tar_with(path: Path, members, mode="w:gz"):
    """members: TarInfo objects, with bytes payload for regular files."""
    with tarfile.open(path, mode, format=tarfile.PAX_FORMAT) as tf:
        for ti, data in members:
            if data is not None:
                ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
            else:
                tf.addfile(ti)
    return path


def ti(name, kind=tarfile.REGTYPE, linkname="", mtime=T0):
    t = tarfile.TarInfo(name)
    t.type, t.linkname, t.mtime, t.mode = kind, linkname, mtime, 0o644
    return t


# ---------------------------------------------------------------- registry
def test_registry_and_targets():
    for ext in ("zip", "7z", "tar", "gz", "tgz", "bz2", "tbz2", "xz", "txz"):
        assert util.category(f"x.{ext}") == "archive"
    assert util.category("photos.tar.gz") == "archive"
    assert convert.targets_for("archive", ".zip") == ["EXTRACT", "7Z", "TAR.GZ"]
    assert convert.targets_for("archive", ".7z") == ["EXTRACT", "ZIP", "TAR.GZ"]
    assert convert.targets_for("archive", ".gz") == ["EXTRACT", "ZIP", "7Z"]
    assert convert.targets_for("archive", ".tar") == ["EXTRACT", "ZIP", "7Z", "TAR.GZ"]
    fam = archives.FAMILY if hasattr(archives, "FAMILY") else None
    from dropdial import formats
    fam = fam or formats.family("archive")
    for name in ["EXTRACT", "ZIP", "7Z", "TAR.GZ"] + [t.name for t in fam.tools]:
        assert 0 < len(fam.hints[name]) <= 22


# ---------------------------------------------------------------- round trips
def test_zip_paths_folder_round_trip(tmp_path):
    src = make_tree(tmp_path / "Project")
    before = snapshot(src)
    z = archives.zip_paths([src])
    assert z == tmp_path / "Project.zip"
    with zipfile.ZipFile(z) as zf:
        assert zf.testzip() is None
        names = zf.namelist()
        assert "Project/empty folder/" in names and "Project/日本語/深い/😀 emoji.txt" in names
        assert all(i.flag_bits & 0x800 for i in zf.infolist() if not i.filename.isascii())
    # an independent tool reads it the same way
    if shutil.which("unzip"):
        ind = tmp_path / "unzip-out"
        subprocess.run(["unzip", "-q", str(z), "-d", str(ind)], check=True,
                       env={**os.environ, "LC_ALL": "C.UTF-8"})
        assert snapshot(ind / "Project", times=False) == snapshot(src, times=False)
    out, = archives.extract(z)
    assert out == tmp_path / "Project (1)"         # 'Project/' inside isn't nested twice, never overwrites
    assert snapshot(out) == before
    assert os.access(out / "data" / "run.sh", os.X_OK)
    loose, = archives.extract(archives.zip_paths([src / "readme.txt", src / "data"], tmp_path / "loose.zip"))
    if os.name == "posix":                         # a normal folder, not the 0700 temp folder
        (tmp_path / "ref").mkdir()
        assert stat.S_IMODE(loose.stat().st_mode) == stat.S_IMODE((tmp_path / "ref").stat().st_mode)
    assert_no_leftovers(tmp_path)


def test_repack_chain_preserves_everything(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    src = make_tree(tmp_path / "Album")
    before = snapshot(src)
    z = archives.zip_paths([src], work / "Album.zip")
    sz, = convert.convert(z, "archive", "7Z")
    assert sz == work / "Album.7z"
    with py7zr.SevenZipFile(sz) as a:               # verify with py7zr directly (CRCs included)
        assert a.test() is not False
        assert "Album/empty folder" in a.getnames()
    tgz, = convert.convert(sz, "archive", "TAR.GZ")
    assert tgz == work / "Album.tar.gz"
    with tarfile.open(tgz) as tf:
        members = {m.name: m for m in tf.getmembers()}
        assert members["Album/data/nested empty"].isdir()
        assert all(m.uname == "" and m.uid == 0 for m in members.values())
        assert tf.extractfile(members["Album/नमस्ते दुनिया.txt"]).read() == (src / "नमस्ते दुनिया.txt").read_bytes()
    if shutil.which("tar") and sys.platform != "win32":   # Windows tar reads "C:" as a host name
        ind = tmp_path / "tar-out"
        ind.mkdir()
        subprocess.run(["tar", "-xzf", str(tgz), "-C", str(ind)], check=True)
        files_only = {k: v for k, v in before.items() if v[0] == "file"}   # GNU tar re-dates folders
        assert {k: v for k, v in snapshot(ind / "Album").items() if v[0] == "file"} == files_only
        assert snapshot(ind / "Album", times=False) == snapshot(src, times=False)
    z2, = convert.convert(tgz, "archive", "ZIP")
    assert z2.name == "Album (1).zip"              # Album.zip exists already
    for arc in (z, sz, tgz, z2):
        d, = archives.extract(arc)
        if arc is z2:                                  # 'Album (1).zip' holds 'Album/': kept as is
            assert all_files(d) == {"Album"} | {f"Album/{n}" for n in before}
            d = d / "Album"
        assert snapshot(d) == before, arc.name
    assert_no_leftovers(work)


@pytest.mark.parametrize("mode,ext", [("w", ".tar"), ("w:gz", ".tar.gz"), ("w:gz", ".tgz"),
                                      ("w:bz2", ".tar.bz2"), ("w:xz", ".tar.xz"), ("w:xz", ".txz")])
def test_tar_variants_extract(tmp_path, mode, ext):
    src = make_tree(tmp_path / "src")
    arc = tmp_path / f"backup{ext}"
    with tarfile.open(arc, mode) as tf:
        tf.add(src, arcname=".")                      # members named './…', a common style
    out, = archives.extract(arc)
    assert out == tmp_path / "backup"
    assert snapshot(out) == snapshot(src)


def test_7z_made_by_py7zr_with_top_level_files(tmp_path):
    src = make_tree(tmp_path / "src")
    arc = tmp_path / "loose.7z"
    with py7zr.SevenZipFile(arc, "w") as a:
        for p in sorted(src.iterdir()):
            a.writeall(p, p.name)
    out, = archives.extract(arc)
    assert out == tmp_path / "loose"                 # top level files -> a folder named after it
    assert snapshot(out, times=False) == snapshot(src, times=False)
    assert (out / "readme.txt").stat().st_mtime == pytest.approx((src / "readme.txt").stat().st_mtime, abs=1)


@pytest.mark.parametrize("ext,opener", [(".gz", gzip.open), (".bz2", bz2.open), (".xz", lzma.open)])
def test_single_file_compressed(tmp_path, ext, opener):
    data = ("line नमस्ते 😀 %d\n" * 1).encode() * 1 + b"".join(b"row %d,value\n" % i for i in range(20000))
    arc = tmp_path / f"notes.csv{ext}"
    with opener(arc, "wb") as f:
        f.write(data)
    out, = archives.extract(arc)
    assert out == tmp_path / "notes.csv" and out.read_bytes() == data
    out2, = archives.extract(arc)
    assert out2 == tmp_path / "notes.csv (1)" or out2.name.startswith("notes.csv (1)")
    z, = convert.convert(arc, "archive", "ZIP")
    assert z.name == "notes.csv.zip"
    with zipfile.ZipFile(z) as zf:
        assert zf.namelist() == ["notes.csv"] and zf.read("notes.csv") == data


def test_gzip_keeps_original_time(tmp_path):
    arc = tmp_path / "log.txt.gz"
    with open(arc, "wb") as raw, gzip.GzipFile("log.txt", "wb", fileobj=raw, mtime=T0) as g:
        g.write(b"x" * 1000)
    out, = archives.extract(arc)
    assert int(out.stat().st_mtime) == T0


def test_tar_hardlink_inside_archive_is_copied(tmp_path):
    arc = tar_with(tmp_path / "links.tar.gz", [
        (ti("a.txt"), b"original"),
        (ti("b.txt", tarfile.LNKTYPE, "a.txt"), None),
    ])
    out, = archives.extract(arc)
    assert (out / "b.txt").read_bytes() == b"original"
    assert os.stat(out / "a.txt").st_ino != os.stat(out / "b.txt").st_ino


# ---------------------------------------------------------------- malicious archives
def _escape_check(tmp_path: Path, arc_name: str, build):
    """Build an archive deep in tmp_path, extract it, and return the output folder after
    proving nothing new appeared anywhere else under tmp_path."""
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    (tmp_path / "secret.txt").write_text("keep me")
    arc = build(deep / arc_name)
    before = all_files(tmp_path)
    out, = archives.extract(arc)
    new = all_files(tmp_path) - before
    rel_out = out.relative_to(tmp_path).as_posix()
    assert all(n == rel_out or n.startswith(rel_out + "/") for n in new), new
    assert (tmp_path / "secret.txt").read_text() == "keep me"
    assert not any(p.is_symlink() for p in out.rglob("*"))
    assert_no_leftovers(deep)
    return out


def test_zip_slip_traversal_and_absolute_paths(tmp_path):
    out = _escape_check(tmp_path, "evil.zip", lambda p: zip_with(p, [
        ("../evil1.txt", b"x"), ("../../evil2.txt", b"x"), ("a/../../../evil3.txt", b"x"),
        ("..\\..\\evil4.txt", b"x"), ("/etc/evil5.txt", b"abs"), ("C:\\Windows\\evil6.txt", b"drive"),
        ("C:evil7.txt", b"drive-rel"), ("//server/share/evil8.txt", b"unc"), ("good.txt", b"fine"),
    ]))
    assert all_files(out) == {"good.txt", "etc", "etc/evil5.txt", "Windows", "Windows/evil6.txt",
                              "evil7.txt", "server", "server/share", "server/share/evil8.txt"}
    assert (out / "good.txt").read_bytes() == b"fine"


def test_zip_symlink_member_is_not_created(tmp_path):
    link_attrs = {"external_attr": (stat.S_IFLNK | 0o777) << 16, "create_system": 3}
    out = _escape_check(tmp_path, "link.zip", lambda p: zip_with(p, [
        ("escape", b"../../../secret.txt", link_attrs), ("ok.txt", b"ok"),
    ]))
    assert all_files(out) == {"ok.txt"}


def test_tar_symlink_hardlink_and_device_escapes(tmp_path):
    def build(p):
        return tar_with(p, [
            (ti("dir/link", tarfile.SYMTYPE, "../../../.."), None),
            (ti("dir/link/secret.txt"), b"pwned through symlink"),
            (ti("abs-link", tarfile.SYMTYPE, "/etc"), None),
            (ti("abs-link/passwd"), b"pwned"),
            (ti("hard", tarfile.LNKTYPE, "../../../secret.txt"), None),
            (ti("hard2", tarfile.LNKTYPE, "/etc/passwd"), None),
            (ti("dev", tarfile.CHRTYPE), None),
            (ti("fifo", tarfile.FIFOTYPE), None),
            (ti("../../evil.txt"), b"x"),
            (ti("/abs/evil.txt"), b"abs"),
            (ti("fine.txt"), b"fine"),
        ])
    out = _escape_check(tmp_path, "evil.tar.gz", build)
    # the link members are gone; files 'under' them land in ordinary folders inside
    assert all_files(out) == {"dir", "dir/link", "dir/link/secret.txt", "abs-link", "abs-link/passwd",
                              "abs", "abs/evil.txt", "fine.txt"}
    assert (out / "dir" / "link").is_dir() and not (out / "dir" / "link").is_symlink()


def evil_7z(path: Path, names: dict[str, str]) -> Path:
    """py7zr refuses to write '..' names, so write same-length placeholders into a plain
    (unencoded) header, swap the UTF-16 names in, and fix the header CRCs."""
    import zlib
    with py7zr.SevenZipFile(path, "w") as a:
        a.set_encoded_header_mode(False)
        for i, ph in enumerate(names):
            a.writestr(f"payload {i}".encode(), ph)
    raw = bytearray(path.read_bytes())
    for ph, real in names.items():
        assert len(ph) == len(real)
        i = raw.index(ph.encode("utf-16-le"))
        raw[i:i + 2 * len(ph)] = real.encode("utf-16-le")
    off, size = struct.unpack_from("<QQ", raw, 12)
    struct.pack_into("<I", raw, 28, zlib.crc32(raw[32 + off: 32 + off + size]))
    struct.pack_into("<I", raw, 8, zlib.crc32(raw[12:32]))
    path.write_bytes(bytes(raw))
    return path


def test_7z_traversal_names_are_skipped(tmp_path):
    def build(p):
        return evil_7z(p, {"AA/AA/evil.txt": "../../evil.txt", "AAAAAAevil2.txt": "..\\..\\evil2.txt",
                           "AAAAAevil3.txt": "/tmp/evil3.txt", "good.txt": "good.txt"})
    with py7zr.SevenZipFile(build(tmp_path / "check.7z")) as a:     # the patch really worked
        assert "../../evil.txt" in a.getnames()
    out = _escape_check(tmp_path, "evil.7z", build)
    assert all_files(out) == {"good.txt", "tmp", "tmp/evil3.txt"}
    assert (out / "good.txt").read_bytes() == b"payload 3"


@pytest.mark.skipif(sys.platform == "win32", reason="making symlinks needs admin rights on Windows")
def test_7z_symlink_member_is_not_created(tmp_path):
    def build(p):
        src = tmp_path / "linky"
        src.mkdir()
        (src / "real.txt").write_text("real")
        (src / "to-secret").symlink_to(tmp_path / "secret.txt")
        (src / "to-root").symlink_to("/", target_is_directory=True)
        with py7zr.SevenZipFile(p, "w") as a:
            a.writeall(src, "linky")
        with py7zr.SevenZipFile(p) as a:
            assert sum(f.is_symlink for f in a.list()) == 2
        shutil.rmtree(src)
        return p
    out = _escape_check(tmp_path, "links.7z", build)
    assert all_files(out) == {"linky", "linky/real.txt"}


def test_zip_bomb_ratio_refused(tmp_path):
    arc = tmp_path / "bomb.zip"
    with zipfile.ZipFile(arc, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        with zf.open("zeros.bin", "w") as w:            # 100 MB of zeros -> ~100 KB, > 1000:1
            for _ in range(100):
                w.write(b"\0" * 1024 * 1024)
    info = zipfile.ZipFile(arc).infolist()[0]
    assert info.file_size / info.compress_size > 1000
    with pytest.raises(UserError, match="unsafe size"):
        archives.extract(arc)
    with pytest.raises(UserError, match="unsafe size"):
        convert.convert(arc, "archive", "7Z")
    assert sorted(p.name for p in tmp_path.iterdir() if p.name != "dropdial-home") == ["bomb.zip"]


@pytest.mark.parametrize("fmt", ["7z", "tar.xz", "bz2", "xz"])
def test_ratio_bomb_other_formats(tmp_path, monkeypatch, fmt):
    monkeypatch.setattr(archives, "RATIO_FLOOR", 1_000_000)   # same rule, smaller fixture
    data = b"\0" * 5_000_000
    arc = tmp_path / f"zeros.{fmt}"
    if fmt == "7z":
        with py7zr.SevenZipFile(arc, "w") as a:
            a.writestr(data, "zeros.bin")
    elif fmt == "tar.xz":
        tar_with(arc, [(ti("zeros.bin"), data)], "w:xz")
    else:
        arc.write_bytes(bz2.compress(data) if fmt == "bz2" else lzma.compress(data))
    assert arc.stat().st_size * 1000 < len(data)
    with pytest.raises(UserError, match="unsafe size"):
        archives.extract(arc)
    assert sorted(p.name for p in tmp_path.iterdir() if p.name != "dropdial-home") == [arc.name]


def test_tar_bomb_refused_from_header(tmp_path):
    arc = tmp_path / "bomb.tar.bz2"
    t = ti("zeros.bin")
    t.size = 200 * 1024 * 1024
    with tarfile.open(arc, "w:bz2") as tf:              # bz2 squeezes 200 MB of zeros to ~ bytes
        class Zeros(io.RawIOBase):
            left = t.size

            def readable(self):
                return True

            def readinto(self, b):
                n = min(len(b), self.left)
                b[:n] = b"\0" * n
                self.left -= n
                return n
        tf.addfile(t, io.BufferedReader(Zeros(), 1 << 20))
    assert arc.stat().st_size * 1000 < t.size
    with pytest.raises(UserError, match="unsafe size"):
        archives.extract(arc)
    assert_no_leftovers(tmp_path)
    assert not (tmp_path / "bomb").exists()


@pytest.mark.parametrize("fmt", ["zip", "7z", "tar.gz", "gz"])
def test_total_size_limit_enforced_while_streaming(tmp_path, monkeypatch, fmt):
    monkeypatch.setattr(archives, "MAX_TOTAL", 1_000_000)
    data = os.urandom(1_500_000)                       # ratio ~1, only the total is too big
    arc = tmp_path / f"big.{fmt}"
    if fmt == "zip":
        zip_with(arc, [("big.bin", data)])
    elif fmt == "7z":
        with py7zr.SevenZipFile(arc, "w") as a:
            a.writestr(data, "big.bin")
    elif fmt == "tar.gz":
        tar_with(arc, [(ti("big.bin"), data)])
    else:
        arc.write_bytes(gzip.compress(data))
    with pytest.raises(UserError, match="unsafe size"):
        archives.extract(arc)
    assert_no_leftovers(tmp_path)
    assert not (tmp_path / "big").exists()


def test_too_many_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(archives, "MAX_ENTRIES", 50)
    arc = zip_with(tmp_path / "many.zip", [(f"f{i}.txt", b"") for i in range(60)])
    with pytest.raises(UserError, match="unsafe size"):
        archives.extract(arc)
    tgz = tar_with(tmp_path / "many.tar.gz", [(ti(f"f{i}.txt"), b"") for i in range(60)])
    with pytest.raises(UserError, match="unsafe size"):
        archives.extract(tgz)


# ---------------------------------------------------------------- passwords, damage, names
def test_encrypted_zip(tmp_path):
    arc = zip_with(tmp_path / "secret.zip", [("a.txt", b"hello")])
    raw = bytearray(arc.read_bytes())
    for sig, off in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):   # set the 'encrypted' flag bit
        i = raw.index(sig)
        raw[i + off] |= 1
    arc.write_bytes(bytes(raw))
    assert zipfile.ZipFile(arc).infolist()[0].flag_bits & 1
    with pytest.raises(UserError, match="password-protected"):
        archives.extract(arc)
    with pytest.raises(UserError, match="password-protected"):
        convert.convert(arc, "archive", "TAR.GZ")


@pytest.mark.parametrize("header_encryption", [False, True])
def test_encrypted_7z(tmp_path, header_encryption):
    arc = tmp_path / "secret.7z"
    with py7zr.SevenZipFile(arc, "w", password="hunter2", header_encryption=header_encryption) as a:
        a.writestr(b"top secret", "a.txt")
    with pytest.raises(UserError, match="password-protected"):
        archives.extract(arc)
    assert not (tmp_path / "secret").exists()
    assert_no_leftovers(tmp_path)


@pytest.mark.parametrize("name,content", [
    ("junk.zip", b"PK\x03\x04 this is not really a zip" * 3),
    ("noise.7z", os.urandom(4000)),
    ("cut.tar.gz", None), ("cut.zip", None), ("cut.7z", None), ("bad.gz", b"\x1f\x8b\x08\x00garbage!" * 10),
])
def test_damaged_archives_give_friendly_errors(tmp_path, name, content):
    arc = tmp_path / name
    if content is None:                                # a real archive cut in half
        src = make_tree(tmp_path / "src")
        whole = tmp_path / ("whole." + name.split(".", 1)[1])
        if name.endswith(".zip"):
            archives.zip_paths([src], whole)
        elif name.endswith(".7z"):
            with py7zr.SevenZipFile(whole, "w") as a:
                a.writeall(src, "src")
        else:
            with tarfile.open(whole, "w:gz") as tf:
                tf.add(src, "src")
        content = whole.read_bytes()[: whole.stat().st_size // 2]
    arc.write_bytes(content)
    before = arc.read_bytes()
    with pytest.raises(UserError):
        archives.extract(arc)
    assert arc.read_bytes() == before
    assert_no_leftovers(tmp_path)


def test_empty_archive(tmp_path):
    arc = zip_with(tmp_path / "nothing.zip", [])
    with pytest.raises(UserError, match="empty"):
        archives.extract(arc)


def test_unicode_names_without_utf8_flag(tmp_path):
    names = {"日本語のファイル.txt": "XXXXXXXXXXXXXXXXXXXXXXXXXX.txt",   # UTF-8 bytes, flag not set
             "café.txt": "YYYYYYYY"}                                       # genuine CP437 bytes
    raw_names = {"日本語のファイル.txt": "日本語のファイル".encode(), "café.txt": b"caf\x82.txt"}
    placeholders = {"日本語のファイル.txt": b"X" * len(raw_names["日本語のファイル.txt"]),
                    "café.txt": b"Y" * len(raw_names["café.txt"])}
    arc = tmp_path / "legacy.zip"
    zip_with(arc, [(placeholders[k].decode() + (".txt" if k.startswith("日") else ""), k.encode())
                   for k in names])
    raw = arc.read_bytes()
    for k in names:
        raw = raw.replace(placeholders[k], raw_names[k])
    arc.write_bytes(raw)
    assert not any(i.flag_bits & 0x800 for i in zipfile.ZipFile(arc).infolist())
    out, = archives.extract(arc)
    assert all_files(out) == {"日本語のファイル.txt", "café.txt"}
    assert (out / "café.txt").read_bytes() == "café.txt".encode()


def test_windows_reserved_and_illegal_names_sanitized(tmp_path):
    arc = zip_with(tmp_path / "win.zip", [
        ("CON", b"1"), ("aux.txt", b"2"), ("dots...", b"3"), ("trail ", b"4"), ("ab:c?.txt", b"5"),
        ("LPT1/x.txt", b"6"), ("nul .log", b"7"), ("ok.txt", b"8"),
    ])
    out, = archives.extract(arc)
    assert all_files(out) == {"_CON", "_aux.txt", "dots", "trail", "ab_c_.txt", "_LPT1", "_LPT1/x.txt",
                              "_nul .log", "ok.txt"}
    assert (out / "_LPT1" / "x.txt").read_bytes() == b"6"


@pytest.mark.filterwarnings("ignore:Duplicate name")
def test_conflicting_and_duplicate_members_dont_crash(tmp_path):
    arc = zip_with(tmp_path / "dup.zip", [("a", b"file a"), ("a/b.txt", b"under a"), ("c.txt", b"one"),
                                          ("c.txt", b"two")])
    out, = archives.extract(arc)
    assert (out / "a").read_bytes() == b"file a"
    assert (out / "c.txt").read_bytes() == b"two"


def test_source_never_modified_and_never_overwrites(tmp_path):
    src = make_tree(tmp_path / "src")
    arc = archives.zip_paths([src / "readme.txt", src / "data"], tmp_path / "pack.zip")
    h = hashlib.sha256(arc.read_bytes()).hexdigest()
    (tmp_path / "pack").mkdir()
    (tmp_path / "pack" / "mine.txt").write_text("user file")
    o1, = archives.extract(arc)
    o2, = archives.extract(arc)
    assert (o1.name, o2.name) == ("pack (1)", "pack (2)")
    assert (tmp_path / "pack" / "mine.txt").read_text() == "user file"
    assert hashlib.sha256(arc.read_bytes()).hexdigest() == h


# ---------------------------------------------------------------- zip_paths naming & safety
def test_zip_paths_names_and_symlinks(tmp_path):
    a = tmp_path / "Holiday"
    a.mkdir()
    (a / "one.jpg").write_bytes(b"\xff\xd8 jpeg-ish")
    (a / "two.txt").write_text("two")
    (tmp_path / "secret.txt").write_text("private")
    sub = a / "folder"
    sub.mkdir()
    (sub / "inside.txt").write_text("inside")
    try:
        (sub / "escape.txt").symlink_to(tmp_path / "secret.txt")
        (sub / "loop").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported here")

    single = archives.zip_paths([a / "two.txt"])
    assert single.name == "two.zip"
    with zipfile.ZipFile(single) as zf:
        assert zf.namelist() == ["two.txt"] and zf.read("two.txt") == b"two"

    many = archives.zip_paths([a / "one.jpg", a / "two.txt", sub])
    assert many.name == "Holiday (3 items).zip"
    with zipfile.ZipFile(many) as zf:
        assert sorted(zf.namelist()) == ["folder/", "folder/inside.txt", "one.jpg", "two.txt"]
        assert zf.getinfo("one.jpg").compress_type == zipfile.ZIP_STORED
        assert zf.read("folder/inside.txt") == b"inside"
        assert b"private" not in many.read_bytes()

    other = tmp_path / "Other"
    other.mkdir()
    (other / "two.txt").write_text("other two")
    mixed = archives.zip_paths([a / "two.txt", other / "two.txt"])
    assert mixed.name == "Archive.zip"
    with zipfile.ZipFile(mixed) as zf:
        assert sorted(zf.namelist()) == ["two (1).txt", "two.txt"]
        assert zf.read("two (1).txt") == b"other two"

    with pytest.raises(UserError):
        archives.zip_paths([sub / "escape.txt"])        # only a symlink: nothing to zip


def test_zip_paths_stores_exact_times(tmp_path):
    f = tmp_path / "odd.txt"
    f.write_text("x")
    os.utime(f, (T0 + 1, T0 + 1))                          # odd second: DOS time can't hold it
    z = archives.zip_paths([f])
    info = zipfile.ZipFile(z).getinfo("odd.txt")
    i = info.extra.index(b"UT")
    assert struct.unpack_from("<i", info.extra, i + 5)[0] == T0 + 1
    f.unlink()
    out, = archives.extract(z)
    assert int((out / "odd.txt").stat().st_mtime) == T0 + 1


# ---------------------------------------------------------------- tool + command line
def test_list_tool(tmp_path):
    src = make_tree(tmp_path / "src")
    arc = archives.zip_paths([src], tmp_path / "src.zip")
    fam = __import__("dropdial.formats", fromlist=["family"]).family("archive")
    tool = next(t for t in fam.tools if t.name == "List")
    out, = tool.run([arc])
    assert out.name == "src contents.txt"
    text = out.read_text(encoding="utf-8")
    assert "7 files, 6 folders" in text
    assert "src/日本語/深い/😀 emoji.txt" in text and "src/empty folder/" in text
    assert "292.969 KB" not in text and util.human_size(300_000) in text
    tgz = tmp_path / "evil.tar.gz"
    tar_with(tgz, [(ti("../x.txt"), b"x"), (ti("l", tarfile.SYMTYPE, "/etc"), None)])
    text = tool.run([tgz])[0].read_text(encoding="utf-8")
    assert "unsafe path" in text and "not extracted" in text


def test_command_line(tmp_path, capsys):
    src = make_tree(tmp_path / "Docs")
    arc = archives.zip_paths([src])
    assert cli.main(["convert", str(arc), "--to", "7z"]) == 0
    with py7zr.SevenZipFile(tmp_path / "Docs.7z") as a:
        assert "Docs/readme.txt" in a.getnames()
    assert cli.main(["convert", str(tmp_path / "Docs.7z"), "--to", "extract"]) == 0
    assert snapshot(tmp_path / "Docs (1)") == snapshot(src)
    assert cli.main(["convert", str(arc), "--to", "tar.gz"]) == 0
    assert (tmp_path / "Docs.tar.gz").exists()
