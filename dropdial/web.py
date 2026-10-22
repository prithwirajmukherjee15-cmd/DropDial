"""Files dragged out of a web browser: a picture, a link to a file, or a download.

Browsers hand over a URL (and sometimes the picture's pixels) rather than a file on disk. The
dial shows the slices for what the URL points at; when a slice is picked the file is saved to
the Downloads folder first, then converted like any other file.
"""
from __future__ import annotations

import base64
import mimetypes
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .util import UserError, category, report_progress, unique_path

MAX_BYTES = 4 * 1024 ** 3          # refuse anything bigger than 4 GB
TIMEOUT = 30                        # seconds without data before giving up
_TYPE_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
             "image/avif": ".avif", "image/heic": ".heic", "image/svg+xml": ".svg", "image/bmp": ".bmp",
             "image/tiff": ".tiff", "image/x-icon": ".ico", "image/vnd.microsoft.icon": ".ico",
             "application/pdf": ".pdf", "video/mp4": ".mp4", "video/webm": ".webm",
             "video/quicktime": ".mov", "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/wav": ".wav",
             "audio/ogg": ".ogg", "text/plain": ".txt", "text/markdown": ".md", "text/csv": ".csv",
             "application/json": ".json", "application/zip": ".zip",
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
             "application/epub+zip": ".epub"}


@dataclass
class WebItem:
    """Something dragged from a browser: a URL to fetch, or image bytes already in hand."""
    name: str                       # file name we'll save it as (decides the dial's slices)
    url: str = ""
    data: bytes | None = None

    @property
    def category(self) -> str | None:
        return category(self.name)


def downloads_dir() -> Path:
    from PySide6.QtCore import QStandardPaths
    d = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    p = Path(d) if d else Path.home() / "Downloads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _clean_name(name: str) -> str:
    name = urllib.parse.unquote(name).replace("\\", "/").split("/")[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:150] or "download"


def name_from_url(url: str) -> str:
    """'https://x.com/a/photo.jpg?w=200' -> 'photo.jpg' (data: URLs get 'image.<ext>')."""
    if url.startswith("data:"):
        mime = url[5:].split(";", 1)[0].split(",", 1)[0].strip().lower()
        return "image" + (_TYPE_EXT.get(mime) or mimetypes.guess_extension(mime) or ".bin")
    path = urllib.parse.urlsplit(url).path
    return _clean_name(path.rstrip("/").split("/")[-1] or "download")


def from_mime(md) -> list[WebItem]:
    """WebItems for a drag's QMimeData that carries no local files (browser drags)."""
    items: list[WebItem] = []
    urls = [u.toString() for u in md.urls() if not u.isLocalFile()]
    urls = [u for u in urls if u.startswith(("http://", "https://", "data:image/"))]
    if not urls and md.hasHtml():
        # Chrome and Edge put an <img> in the HTML when you drag a picture
        m = re.search(r'<img[^>]+src="([^"]+)"', md.html(), re.I)
        if m and m.group(1).startswith(("http://", "https://", "data:image/")):
            urls = [m.group(1)]
    if not urls and md.hasText():
        t = md.text().strip()
        if re.fullmatch(r"https?://\S+", t):
            urls = [t]
    for u in urls[:20]:
        name = name_from_url(u)
        if category(name) is None and md.hasImage():
            name = Path(name).stem + ".png"          # a picture behind an extension-less URL
        items.append(WebItem(name, url=u))
    if not items and md.hasImage():
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        img = md.imageData()
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        if img is not None and not img.isNull() and img.save(buf, "PNG"):
            items.append(WebItem("image.png", data=bytes(ba)))
    return [i for i in items if i.category is not None]


def fetch(item: WebItem, dest: Path | None = None) -> Path:
    """Save a WebItem into `dest` (Downloads by default) and return the file's path."""
    dest = dest or downloads_dir()
    if item.data is not None:
        out = unique_path(dest / item.name)
        out.write_bytes(item.data)
        return out
    url = item.url
    if url.startswith("data:"):
        head, _, payload = url.partition(",")
        data = base64.b64decode(payload) if ";base64" in head else urllib.parse.unquote_to_bytes(payload)
        out = unique_path(dest / item.name)
        out.write_bytes(data)
        return out
    if not url.startswith(("http://", "https://")):
        raise UserError("Only web links (http/https) can be downloaded.")
    req = urllib.request.Request(url, headers={"User-Agent": f"DropDial/{__version__}"})
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)  # noqa: S310 (scheme checked above)
    except Exception as e:  # noqa: BLE001
        raise UserError("Couldn't download it. The site may need you to be signed in, "
                        "or you're offline.") from e
    with resp:
        name = item.name
        cd = resp.headers.get("Content-Disposition", "")
        m = re.search(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)", cd, re.I)
        if m:
            name = _clean_name(m.group(1) or m.group(2))
        ctype = (resp.headers.get_content_type() or "").lower()
        if Path(name).suffix == "" or category(name) is None:
            ext = _TYPE_EXT.get(ctype)
            if ext:
                name = Path(name).stem + ext
        if ctype == "text/html" and category(item.name) not in (None, "markup", "text"):
            raise UserError("That link opens a web page, not the file itself.")
        total = int(resp.headers.get("Content-Length") or 0)
        if total > MAX_BYTES:
            raise UserError("That file is too big to download here (over 4 GB).")
        out = unique_path(dest / name)
        part = out.with_name(out.name + ".part")
        got = 0
        try:
            with open(part, "wb") as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    got += len(chunk)
                    if got > MAX_BYTES:
                        raise UserError("That file is too big to download here (over 4 GB).")
                    f.write(chunk)
                    if total:
                        report_progress(got / total * 0.5)
            part.replace(out)
        finally:
            part.unlink(missing_ok=True)
    return out
