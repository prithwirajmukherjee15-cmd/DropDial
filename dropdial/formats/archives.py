"""Archives: extract ZIP, 7Z, TAR (.gz/.bz2/.xz) and single-file .gz/.bz2/.xz; re-pack between
ZIP, 7Z and TAR.GZ; and `zip_paths` to zip any files and folders.

Archives are untrusted, so nothing here calls a library's extract-all. Every member goes through
`_Sink`, which only ever creates plain folders and regular files inside a fresh staging folder:
* names are cleaned (`_safe_parts`): '..' members are skipped, leading '/', drive letters and
  backslashes are neutralised, Windows-reserved names (CON, aux.txt, trailing dots) are renamed;
* symlinks, devices and FIFOs are never created; tar hard links become copies of files that were
  already extracted;
* bytes are counted while writing, so a lying header can't get past the size limits.
The staging folder is renamed into place only when everything succeeded.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import struct
import time
from pathlib import Path

from .. import util
from ..util import UserError
from . import Family, Tool, register

MAX_TOTAL = 20 * 1024 ** 3        # refuse archives that expand beyond 20 GB
MAX_ENTRIES = 100_000
MAX_RATIO = 1000                  # expansion ratio considered a bomb...
RATIO_FLOOR = 64 * 1024 ** 2      # ...once more than this much has come out
CHUNK = 1024 * 1024

EXTS = {".zip", ".7z", ".tar", ".tgz", ".gz", ".tbz2", ".tbz", ".bz2", ".txz", ".xz"}
SINGLE = ("gz", "bz2", "xz")      # single-file compressors
_COMPOUND = (".tar.gz", ".tar.bz2", ".tar.xz")

PASSWORD = "This archive is password-protected."
DAMAGED = "This archive is damaged or incomplete."
BOMB = "This archive would expand to an unsafe size (a possible zip bomb), so it wasn't extracted."

# already-compressed data: storing beats deflating it again
_STORED_EXTS = {".zip", ".7z", ".gz", ".bz2", ".xz", ".rar", ".jpg", ".jpeg", ".png", ".gif", ".webp",
                ".heic", ".avif", ".mp4", ".mov", ".mkv", ".webm", ".mp3", ".m4a", ".aac", ".ogg",
                ".opus", ".flac", ".docx", ".xlsx", ".pptx", ".epub", ".zst"}


class _Bomb(Exception):
    pass


# ---------------------------------------------------------------- names
_BAD_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED = ({"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
             | {f"{p}{n}" for p in ("COM", "LPT") for n in (*"123456789", "¹", "²", "³")})


def _win_safe(part: str) -> str:
    """One path component that is a legal file name on Windows, macOS and Linux."""
    part = _BAD_CHARS.sub("_", part).rstrip(" .")
    if not part:
        return "_"
    if part.split(".")[0].rstrip(" ").upper() in _RESERVED:
        part = "_" + part
    while len(part.encode("utf-8")) > 255:          # longest name file systems accept
        stem, dot, ext = part.rpartition(".")
        part = (stem[:-1] + dot + ext) if stem and len(ext) < 16 else part[:-1]
    return part


def _safe_parts(name: str) -> list[str] | None:
    """Archive member name -> safe relative path components, or None to skip the member."""
    if "\x00" in name:
        return None
    name = re.sub(r"^[A-Za-z]:", "", name.replace("\\", "/"))   # 'C:\x' / 'C:x' -> '/x' / 'x'
    parts = []
    for p in name.split("/"):              # leading '/' and '//server' just become relative
        if p in ("", "."):
            continue
        if p == "..":
            return None
        parts.append(_win_safe(p))
    return parts or None


def _norm(name: str) -> str | None:
    parts = _safe_parts(name)
    return "/".join(parts) if parts else None


def _base(src: Path) -> str:
    """'photos.tar.gz' -> 'photos', 'notes.txt.gz' -> 'notes.txt', 'a.zip' -> 'a'."""
    low = src.name.lower()
    for c in _COMPOUND:
        if low.endswith(c) and len(src.name) > len(c):
            return src.name[: -len(c)]
    return src.stem or src.name


def _unique(folder: Path, base: str, ext: str) -> Path:
    """folder/base+ext, or 'base (1)+ext'… (unlike util.unique_path this keeps '.tar.gz' whole)."""
    base = _win_safe(base)
    cand, i = folder / f"{base}{ext}", 1
    while cand.exists() or cand.is_symlink():
        cand, i = folder / f"{base} ({i}){ext}", i + 1
    return cand


# ---------------------------------------------------------------- detection
def _kind(src: Path) -> str:
    """'zip', '7z', 'tar', 'gz', 'bz2' or 'xz', from the content (falls back to the extension)."""
    try:
        with open(src, "rb") as f:
            head = f.read(8)
    except OSError as e:
        raise UserError(f"Can't read this file ({e.strerror or e}).") from None
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    if head[:2] == b"\x1f\x8b" or head[:3] == b"BZh" or head.startswith(b"\xfd7zXZ\x00"):
        return "tar" if _is_tar(src) else {b"\x1f": "gz", b"B": "bz2"}.get(head[:1], "xz")
    if head[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        return "zip"
    import zipfile
    if _is_tar(src):
        return "tar"
    if zipfile.is_zipfile(src):            # e.g. a self-extracting stub in front of the zip
        return "zip"
    ext = src.name.lower()
    if ext.endswith(".zip"):
        return "zip"
    raise UserError("This doesn't look like an archive DropDial can open.")


def _is_tar(src: Path) -> bool:
    import tarfile
    try:
        with tarfile.open(src, "r:*") as tf:
            return tf.next() is not None
    except Exception:  # noqa: BLE001 - any failure just means "not a tar"
        return False


# ---------------------------------------------------------------- the only code that writes members
class _Sink:
    """Writes sanitised members under `root`, enforcing the size limits as bytes arrive."""

    def __init__(self, root: Path, archive_size: int, expected: int = 0, progress=None):
        self.root = root
        self.archive_size = max(archive_size, 1)
        self.expected = expected
        self.progress = progress              # callable -> 0..1, used when `expected` is unknown
        self.written = 0
        self.entries = 0
        self.skipped = 0
        self.files: dict[str, Path] = {}      # normalised name -> written file (for tar hard links)
        self.dir_times: dict[Path, float] = {}

    def count_entry(self):
        self.entries += 1
        if self.entries > MAX_ENTRIES:
            raise _Bomb

    def add(self, n: int):
        self.written += n
        if self.written > MAX_TOTAL or (self.written > RATIO_FLOOR
                                        and self.written > MAX_RATIO * self.archive_size):
            raise _Bomb
        if self.expected:
            util.report_progress(self.written / self.expected)
        elif self.progress:
            util.report_progress(self.progress())

    def _path(self, name: str) -> Path | None:
        parts = _safe_parts(name)
        if not parts:
            self.skipped += 1
            return None
        p = self.root.joinpath(*parts)
        if os.path.commonpath([str(p), str(self.root)]) != str(self.root):  # belt and braces
            self.skipped += 1
            return None
        return p

    def make_dir(self, name: str, mtime: float | None = None) -> None:
        p = self._path(name)
        if p is None:
            return
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:              # a file already has that name
            self.skipped += 1
            return
        if mtime is not None:
            self.dir_times[p] = mtime

    def open_file(self, name: str):
        """A binary file handle for member `name`, or None when the member is skipped."""
        p = self._path(name)
        if p is None:
            return None, None
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            fh = os.fdopen(os.open(p, flags, 0o644), "w+b")
        except OSError:              # a folder already has that name, or a parent is a file
            self.skipped += 1
            return None, None
        self.files[str(p.relative_to(self.root).as_posix())] = p
        return fh, p

    def write_file(self, name: str, stream, mtime: float | None = None, mode: int | None = None) -> Path | None:
        fh, p = self.open_file(name)
        if fh is None:
            return None
        with fh:
            while chunk := stream.read(CHUNK):
                self.add(len(chunk))
                fh.write(chunk)
        self.finish_file(p, mtime, mode)
        return p

    @staticmethod
    def finish_file(p: Path, mtime: float | None, mode: int | None = None) -> None:
        if mode and mode & 0o111 and os.name == "posix":     # keep scripts executable
            try:
                p.chmod(0o755)
            except OSError:
                pass
        _set_mtime(p, mtime)

    def finish(self) -> None:
        for p in sorted(self.dir_times, key=lambda q: len(q.parts), reverse=True):
            _set_mtime(p, self.dir_times[p])     # deepest first: writing a child touches the parent


def _set_mtime(p: Path, mtime: float | None) -> None:
    if mtime is None:
        return
    try:
        os.utime(p, (mtime, mtime))
    except (OSError, OverflowError, ValueError):
        pass


# ---------------------------------------------------------------- readers
def _zip_extra(extra: bytes) -> dict[int, bytes]:
    out, i = {}, 0
    while i + 4 <= len(extra):
        hid, size = struct.unpack_from("<HH", extra, i)
        out.setdefault(hid, extra[i + 4: i + 4 + size])
        i += 4 + size
    return out


def _zip_name(info) -> str:
    """The member name as its author meant it (handles UTF-8 names written without the flag)."""
    import zlib
    if info.flag_bits & 0x800:
        return info.filename
    try:
        raw = info.filename.encode("cp437")
    except UnicodeEncodeError:
        return info.filename
    up = _zip_extra(info.extra).get(0x7075)    # Info-ZIP Unicode Path field
    if up and len(up) > 5 and up[0] == 1 and struct.unpack_from("<I", up, 1)[0] == zlib.crc32(raw):
        try:
            return up[5:].decode("utf-8")
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return info.filename


def _zip_mtime(info) -> float | None:
    ut = _zip_extra(info.extra).get(0x5455)    # extended timestamp: exact UTC seconds
    if ut and len(ut) >= 5 and ut[0] & 1:
        return float(struct.unpack_from("<i", ut, 1)[0])
    try:
        return time.mktime((*info.date_time, 0, 0, -1))   # DOS time is local time
    except (OverflowError, ValueError):
        return None


def _zip_kind(info) -> str:
    mode = info.external_attr >> 16
    fmt = stat.S_IFMT(mode)
    if info.filename.replace("\\", "/").endswith("/") or fmt == stat.S_IFDIR:
        return "dir"
    if fmt in (0, stat.S_IFREG):
        return "file"
    return "other"         # symlink, device, fifo: never created


def _open_zip(src: Path):
    import zipfile
    try:
        return zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise UserError(DAMAGED) from None


def _zip_check(zf, archive_size: int) -> int:
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise _Bomb
    if any(i.flag_bits & 0x1 for i in infos):
        raise UserError(PASSWORD)
    total = 0
    for i in infos:
        total += i.file_size
        if i.file_size > RATIO_FLOOR and i.file_size > MAX_RATIO * max(i.compress_size, 1):
            raise _Bomb
    if total > MAX_TOTAL or (total > RATIO_FLOOR and total > MAX_RATIO * max(archive_size, 1)):
        raise _Bomb
    return total


def _extract_zip(src: Path, sink: _Sink) -> None:
    with _open_zip(src) as zf:
        sink.expected = _zip_check(zf, sink.archive_size)
        for info in zf.infolist():
            sink.count_entry()
            kind, name = _zip_kind(info), _zip_name(info)
            if kind == "dir":
                sink.make_dir(name, _zip_mtime(info))
            elif kind == "file":
                with zf.open(info) as f:
                    sink.write_file(name, f, _zip_mtime(info), info.external_attr >> 16)
            else:
                sink.skipped += 1


def _extract_tar(src: Path, sink: _Sink) -> None:
    import tarfile
    check = getattr(tarfile, "data_filter", None)       # Python's own safety filter, as a 2nd opinion
    declared = 0
    with open(src, "rb") as raw:
        sink.progress = lambda: raw.tell() / sink.archive_size
        with tarfile.open(fileobj=raw, mode="r:*") as tf:
            for m in tf:                                 # streams: one pass, nothing read twice
                sink.count_entry()
                declared += max(m.size, 0) if m.isreg() else 0
                if declared > MAX_TOTAL or (declared > RATIO_FLOOR and declared > MAX_RATIO * sink.archive_size):
                    raise _Bomb                          # header says so: don't even start
                name = _norm(m.name)
                if name is None or not (m.isreg() or m.isdir() or m.islnk()):
                    sink.skipped += 1                    # unsafe name, symlink, device, fifo
                    continue
                if check is not None:
                    try:
                        check(m.replace(name=name, linkname=_norm(m.linkname) or "", deep=False),
                              str(sink.root))
                    except tarfile.FilterError:
                        sink.skipped += 1
                        continue
                if m.isdir():
                    sink.make_dir(name, m.mtime)
                elif m.isreg():
                    sink.write_file(name, tf.extractfile(m), m.mtime, m.mode)
                else:                                    # hard link: copy a file we already wrote
                    target = sink.files.get(_norm(m.linkname) or "")
                    if target is None or not target.is_file():
                        sink.skipped += 1
                        continue
                    with open(target, "rb") as f:
                        sink.write_file(name, f, m.mtime, m.mode)


def _extract_7z(src: Path, sink: _Sink) -> None:
    try:
        import py7zr
    except ImportError:
        raise UserError("Opening 7Z archives needs the py7zr package.") from None
    from py7zr.exceptions import PasswordRequired
    from py7zr.io import Py7zIO, WriterFactory

    times: dict[str, float] = {}

    class Writer(Py7zIO):
        def __init__(self, name: str):
            self.fh, self.path = sink.open_file(name)
            self.name = name

        def write(self, s):
            sink.add(len(s))
            if self.fh is not None:
                self.fh.write(s)
            return len(s)

        def read(self, size=None):
            return self.fh.read(size if size is not None else -1) if self.fh else b""

        def seek(self, offset, whence=0):
            return self.fh.seek(offset, whence) if self.fh else 0

        def flush(self):
            if self.fh is not None:
                self.fh.flush()

        def size(self):
            return self.fh.tell() if self.fh else 0

        def close(self):
            if self.fh is not None and not self.fh.closed:
                self.fh.close()
                sink.finish_file(self.path, times.get(_norm(self.name) or ""))

    class Factory(WriterFactory):
        def create(self, filename: str):
            rel = os.path.relpath(filename, sink.root)    # py7zr hands us root/<its cleaned name>
            if rel.startswith(".."):
                rel = "\x00"                              # -> skipped by _safe_parts
            return Writer(rel)

    # passing a file object keeps py7zr single-threaded, so errors (and _Bomb) surface here
    with open(src, "rb") as fp:
        try:
            z = py7zr.SevenZipFile(fp, "r", max_extract_size=MAX_TOTAL)
        except PasswordRequired:
            raise UserError(PASSWORD) from None
        with z:
            if z.needs_password():
                raise UserError(PASSWORD)
            infos = z.list()
            if len(infos) > MAX_ENTRIES:
                raise _Bomb
            total = sum(i.uncompressed or 0 for i in infos if not i.is_directory)
            if total > MAX_TOTAL or (total > RATIO_FLOOR and total > MAX_RATIO * sink.archive_size):
                raise _Bomb
            sink.expected = total
            targets = []
            for i in infos:
                sink.count_entry()
                name = _norm(i.filename)
                mtime = i.creationtime.timestamp() if i.creationtime else None  # (= last write time)
                if name is None or i.is_symlink or not (i.is_file or i.is_directory):
                    sink.skipped += 1
                elif i.is_directory:
                    sink.make_dir(name, mtime)
                else:
                    targets.append(i.filename)
                    if mtime is not None:
                        times[name] = mtime
            if targets:
                z.extract(path=sink.root, targets=targets, factory=Factory())


def _open_single(kind: str, fileobj):
    import bz2
    import gzip
    import lzma
    if kind == "gz":
        return gzip.GzipFile(fileobj=fileobj, mode="rb")
    return bz2.BZ2File(fileobj) if kind == "bz2" else lzma.LZMAFile(fileobj)


def _extract_single(src: Path, kind: str, sink: _Sink, name: str) -> None:
    with open(src, "rb") as raw:
        sink.progress = lambda: raw.tell() / sink.archive_size
        with _open_single(kind, raw) as f:
            sink.count_entry()
            p = sink.write_file(name, f)
            mtime = getattr(f, "mtime", None)              # gzip remembers the original's time
            if p is not None and mtime:
                _set_mtime(p, float(mtime))


def _read_into(src: Path, kind: str, root: Path) -> _Sink:
    """Extract `src` into the (new, empty) folder `root`. Returns the sink for its counters."""
    import lzma
    import tarfile
    import zipfile
    import zlib
    sink = _Sink(root, util.file_size(src))
    try:
        if kind == "zip":
            _extract_zip(src, sink)
        elif kind == "7z":
            _extract_7z(src, sink)
        elif kind == "tar":
            _extract_tar(src, sink)
        else:
            _extract_single(src, kind, sink, _base(src))
    except _Bomb:
        raise UserError(BOMB) from None
    except UserError:
        raise
    except NotImplementedError:
        raise UserError("This archive uses a compression method DropDial can't read.") from None
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, zlib.error, lzma.LZMAError,
            ValueError, RuntimeError) as e:
        raise UserError(DAMAGED) from e
    except OSError as e:
        if e.errno is None:                          # gzip / bz2 report corrupt data as OSError
            raise UserError(DAMAGED) from e
        raise UserError(f"Couldn't write the extracted files ({e.strerror or e}).") from e
    except Exception as e:  # noqa: BLE001 - py7zr raises its own zoo of exceptions
        if type(e).__module__.startswith("py7zr"):
            raise UserError(DAMAGED) from e
        raise
    sink.finish()
    if not any(root.iterdir()):
        raise UserError("Nothing in this archive could be extracted safely."
                        if sink.skipped else "This archive is empty.")
    return sink


def _staging(folder: Path) -> Path:
    import tempfile
    return Path(tempfile.mkdtemp(prefix=".~dropdial-", dir=folder))


# ---------------------------------------------------------------- extract / re-pack
def extract(src: Path) -> list[Path]:
    """Folder '<name>' next to the archive (a single compressed file comes out as that file)."""
    src = Path(src)
    kind = _kind(src)
    folder = util.output_dir(src)
    stage = _staging(folder)
    try:
        root = stage / "x"          # plain mkdir: normal permissions (mkdtemp's folder is 0700)
        root.mkdir()
        _read_into(src, kind, root)
        base = _base(src)
        items = list(root.iterdir())
        if kind in SINGLE:
            item = items[0]
        elif len(items) == 1 and items[0].is_dir() and items[0].name == _win_safe(base):
            item = items[0]         # 'a.zip' holding 'a/': no 'a/a/'
        else:
            item = root
        final = _unique(folder, base, "")
        os.rename(item, final)
        return [final]
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _walk(root: Path):
    """(path, archive name, is_dir) for everything under root; symlinks and specials skipped."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = sorted(n for n in dirnames if not (d / n).is_symlink())
        for n in dirnames:
            yield d / n, (d / n).relative_to(root).as_posix(), True
        for n in sorted(filenames):
            p = d / n
            if not p.is_symlink() and p.is_file():
                yield p, p.relative_to(root).as_posix(), False


def _write_zip(items, out: Path) -> None:
    import zipfile

    def write(dst):
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path, arc, is_dir in items:
                info = zipfile.ZipInfo.from_file(path, arc, strict_timestamps=False)
                mtime = int(os.stat(path).st_mtime)
                if -2 ** 31 <= mtime < 2 ** 31:
                    info.extra = struct.pack("<HHBi", 0x5455, 5, 1, mtime)   # exact UTC time
                if is_dir:
                    zf.writestr(info, b"")
                    continue
                info.compress_type = (zipfile.ZIP_STORED if path.suffix.lower() in _STORED_EXTS
                                      else zipfile.ZIP_DEFLATED)
                with open(path, "rb") as f, zf.open(info, "w") as w:
                    shutil.copyfileobj(f, w, CHUNK)
    _atomic(write, out)


def _write_7z(items, out: Path) -> None:
    import py7zr

    def write(dst):
        with py7zr.SevenZipFile(dst, "w") as z:
            for path, arc, _ in items:
                z.write(path, arc)
    _atomic(write, out)


def _write_targz(items, out: Path, inner: str) -> None:
    import gzip
    import tarfile

    def write(dst):
        with open(dst, "wb") as raw, gzip.GzipFile(filename=inner, mode="wb", fileobj=raw) as gz, \
                tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf:
            for path, arc, is_dir in items:
                ti = tf.gettarinfo(str(path), arc)
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""          # don't leak the local account name
                if is_dir:
                    tf.addfile(ti)
                else:
                    with open(path, "rb") as f:
                        tf.addfile(ti, f)
    _atomic(write, out)


def _atomic(write, out: Path) -> None:
    from ..convert import atomic_save
    try:
        atomic_save(write, out)
    except OSError as e:
        raise UserError(f"Couldn't write {out.name} ({e.strerror or e}).") from e


_WRITERS = {"ZIP": ".zip", "7Z": ".7z", "TAR.GZ": ".tar.gz"}


def repack(src: Path, target: str) -> list[Path]:
    src = Path(src)
    kind = _kind(src)
    folder = util.output_dir(src)
    base = _base(src)
    out = _unique(folder, base, _WRITERS[target])
    stage = _staging(folder)
    try:
        root = stage / "x"
        root.mkdir()
        _read_into(src, kind, root)
        items = list(_walk(root))
        if target == "ZIP":
            _write_zip(items, out)
        elif target == "7Z":
            _write_7z(items, out)
        else:
            _write_targz(items, out, out.name[:-3])
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return [out]


# ---------------------------------------------------------------- zip anything
def zip_paths(paths: list[Path], out: Path | None = None) -> Path:
    """Zip files and folders (folders keep their structure, empty ones too; symlinks are skipped).
    Named after the single item, else '<common parent> (N items).zip' or 'Archive.zip'."""
    paths = [Path(p) for p in paths]
    paths = [p for p in paths if not p.is_symlink() and p.exists()]
    if not paths:
        raise UserError("Nothing to zip.")
    if out is None:
        folder = util.output_dir(paths[0])
        if len(paths) == 1:
            base = paths[0].name if paths[0].is_dir() else (paths[0].stem or paths[0].name)
        else:
            parents = {p.resolve().parent for p in paths}
            parent = parents.pop() if len(parents) == 1 else None
            base = f"{parent.name} ({len(paths)} items)" if parent and parent.name else "Archive"
        out = _unique(folder, base, ".zip")
    out = Path(out)
    skip = {out.resolve(), out.with_name(f".~{out.name}.part").resolve()}

    items, used = [], set()
    for p in paths:
        top = p.name or "item"
        stem, suf = (top, "") if p.is_dir() else (Path(top).stem, Path(top).suffix)
        i = 1
        while top.lower() in used:                    # two dropped 'notes.txt' from different folders
            top, i = f"{stem} ({i}){suf}", i + 1
        used.add(top.lower())
        if p.is_dir():
            items.append((p, top, True))
            items += [(q, f"{top}/{arc}", d) for q, arc, d in _walk(p) if q.resolve() not in skip]
        elif p.is_file() and p.resolve() not in skip:
            items.append((p, top, False))
    _write_zip(items, out)
    return out


# ---------------------------------------------------------------- listing tool
def _listing(src: Path) -> list[tuple[str, int, float | None, str]]:
    """(name, size, mtime, note) per member, without extracting anything."""
    kind = _kind(src)
    rows = []
    if kind == "zip":
        with _open_zip(src) as zf:
            for i in zf.infolist()[:MAX_ENTRIES]:
                k = _zip_kind(i)
                note = "folder" if k == "dir" else ("" if k == "file" else "link/special, not extracted")
                if i.flag_bits & 1:
                    note = "encrypted"
                rows.append((_zip_name(i), i.file_size, _zip_mtime(i), note))
    elif kind == "7z":
        import py7zr
        from py7zr.exceptions import PasswordRequired
        try:
            with py7zr.SevenZipFile(src) as z:
                for i in z.list()[:MAX_ENTRIES]:
                    note = "folder" if i.is_directory else ("link, not extracted" if i.is_symlink else "")
                    t = i.creationtime.timestamp() if i.creationtime else None
                    rows.append((i.filename, i.uncompressed or 0, t, note))
        except PasswordRequired:
            raise UserError(PASSWORD) from None
    elif kind == "tar":
        import tarfile
        with tarfile.open(src, "r:*") as tf:
            for m in tf:
                if len(rows) >= MAX_ENTRIES:
                    break
                note = ("folder" if m.isdir() else "" if m.isreg() else
                        f"link to {m.linkname}" if m.islnk() else "link/special, not extracted")
                rows.append((m.name, m.size if m.isreg() else 0, float(m.mtime), note))
    else:
        size = 0
        with open(src, "rb") as raw, _open_single(kind, raw) as f:
            while chunk := f.read(CHUNK):
                size += len(chunk)
                if size > MAX_TOTAL:
                    raise _Bomb
        rows.append((_base(src), size, None, ""))
    return rows


def list_contents(paths: list[Path]) -> list[Path]:
    src = Path(paths[0])
    try:
        rows = _listing(src)
    except _Bomb:
        raise UserError(BOMB) from None
    except UserError:
        raise
    except Exception as e:  # noqa: BLE001
        raise UserError(DAMAGED) from e
    files = [r for r in rows if r[3] != "folder"]
    total = sum(r[1] for r in files)
    lines = [src.name, f"{len(files)} files, {len(rows) - len(files)} folders, "
                       f"{util.human_size(total)} unpacked ({util.human_size(util.file_size(src))} packed)", ""]
    for name, size, mtime, note in rows:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)) if mtime else " " * 16
        flag = "" if _norm(name) else "  [unsafe path, skipped on extract]"
        size_s = "" if note == "folder" else util.human_size(size)
        lines.append(f"{size_s:>10}  {when}  {name}{'/' if note == 'folder' and not name.endswith('/') else ''}"
                     f"{f'  ({note})' if note and note != 'folder' else ''}{flag}")
    out = util.sibling(src, "contents", ext=".txt")
    from ..convert import atomic_save
    atomic_save(lambda dst: Path(dst).write_text("\n".join(lines) + "\n", encoding="utf-8"), out)
    return [out]


# ---------------------------------------------------------------- registry
def _targets(src_ext: str) -> list[str]:
    own = {"zip": "ZIP", "7z": "7Z", "gz": "TAR.GZ", "tgz": "TAR.GZ"}.get(src_ext.lower().lstrip("."))
    return ["EXTRACT"] + [t for t in _WRITERS if t != own]


def _convert(src: Path, target: str) -> list[Path]:
    target = target.upper()
    if target == "EXTRACT":
        return extract(src)
    if target in _WRITERS:
        return repack(src, target)
    raise UserError(f"Can't convert an archive to {target}.")


def _has_7z() -> bool:
    import importlib.util
    return importlib.util.find_spec("py7zr") is not None


register(Family(
    category="archive",
    label="Archive",
    exts=EXTS,
    targets=lambda ext: [t for t in _targets(ext) if t != "7Z" or _has_7z()],
    convert=_convert,
    hints={"EXTRACT": "Unpack to a folder", "ZIP": "Opens everywhere", "7Z": "Smallest archive",
           "TAR.GZ": "Linux & macOS standard", "List": "Contents as a .txt"},
    tools=[Tool("List", "☰", "Contents as a .txt", list_contents, working="Listing…")],
))
