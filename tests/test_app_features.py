"""Browser drags, update checks, the dial's rings and wheel, image tracing."""
from __future__ import annotations

import http.server
import threading
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from dropdial import convert, updates, web


# ---------------------------------------------------------------- web downloads
class _Handler(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):  # noqa: N802
        body, headers = self.routes.get(self.path, (None, {}))
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture()
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", _Handler.routes
    srv.shutdown()
    _Handler.routes.clear()


def _png_bytes(color=(200, 30, 40)) -> bytes:
    import io
    b = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(b, "PNG")
    return b.getvalue()


def test_name_from_url():
    assert web.name_from_url("https://x.com/a/My%20Photo.jpg?w=200#k") == "My Photo.jpg"
    assert web.name_from_url("data:image/png;base64,AAAA") == "image.png"
    assert web.name_from_url("https://x.com/") == "download"
    assert "/" not in web.name_from_url("https://x.com/a/..%2F..%2Fevil.jpg")


def test_fetch_downloads_into_folder(server, tmp_path):
    base, routes = server
    png = _png_bytes()
    routes["/img/cat.png"] = (png, {"Content-Type": "image/png"})
    out = web.fetch(web.WebItem("cat.png", url=base + "/img/cat.png"), tmp_path)
    assert out.parent == tmp_path and out.name == "cat.png" and out.read_bytes() == png
    # a second download never overwrites the first
    out2 = web.fetch(web.WebItem("cat.png", url=base + "/img/cat.png"), tmp_path)
    assert out2 != out and out2.exists()


def test_fetch_uses_server_name_and_type(server, tmp_path):
    base, routes = server
    routes["/dl?id=7"] = (b"%PDF-1.4 fake", {"Content-Type": "application/pdf",
                                             "Content-Disposition": 'attachment; filename="../../Report 2026.pdf"'})
    out = web.fetch(web.WebItem("dl", url=base + "/dl?id=7"), tmp_path)
    assert out.name == "Report 2026.pdf" and out.parent == tmp_path       # no path traversal
    routes["/pic"] = (_png_bytes(), {"Content-Type": "image/webp"})
    out = web.fetch(web.WebItem("pic", url=base + "/pic"), tmp_path)
    assert out.suffix == ".webp"


def test_fetch_refuses_html_for_a_file_and_bad_links(server, tmp_path):
    from dropdial.util import UserError
    base, routes = server
    routes["/photo.jpg"] = (b"<html>sign in</html>", {"Content-Type": "text/html"})
    with pytest.raises(UserError):
        web.fetch(web.WebItem("photo.jpg", url=base + "/photo.jpg"), tmp_path)
    with pytest.raises(UserError):
        web.fetch(web.WebItem("x.jpg", url=base + "/missing.jpg"), tmp_path)
    with pytest.raises(UserError):
        web.fetch(web.WebItem("x.jpg", url="file:///etc/passwd"), tmp_path)
    assert not list(tmp_path.glob("*.part"))


def test_fetch_data_url_and_bytes(tmp_path):
    import base64
    png = _png_bytes()
    out = web.fetch(web.WebItem("image.png", url="data:image/png;base64," + base64.b64encode(png).decode()), tmp_path)
    assert out.read_bytes() == png
    out = web.fetch(web.WebItem("image.png", data=png), tmp_path)
    assert out.read_bytes() == png


def test_from_mime_browser_shapes(qapp):
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QImage
    md = QMimeData()
    md.setUrls([QUrl("https://example.com/photos/sunset.jpeg?x=1")])
    items = web.from_mime(md)
    assert [i.name for i in items] == ["sunset.jpeg"] and items[0].category == "image"
    md = QMimeData()
    md.setHtml('<a href="x"><img alt="" src="https://cdn.example.com/p/123.webp"></a>')
    assert [i.name for i in web.from_mime(md)] == ["123.webp"]
    md = QMimeData()
    img = QImage(10, 10, QImage.Format_RGB32)
    img.fill(0xff336699)
    md.setImageData(img)
    items = web.from_mime(md)
    assert items and items[0].data and items[0].name.endswith(".png")
    md = QMimeData()
    md.setText("just some words")
    assert web.from_mime(md) == []


# ---------------------------------------------------------------- updates
def test_update_picks_newest_real_release():
    rel = [{"tag_name": "latest", "name": "DropDial (latest build)"},
           {"tag_name": "v1.2.0", "html_url": "u120"},
           {"tag_name": "v1.10.0", "html_url": "u1100", "prerelease": True},
           {"tag_name": "v1.3.1", "html_url": "u131"},
           {"tag_name": "v9.0.0", "draft": True}]
    u = updates.newest(rel, "1.0.0")
    assert u.version == "1.3.1" and u.url == "u131"
    assert updates.newest(rel, "1.3.1") is None
    assert updates.newest(rel, "2.0") is None
    assert updates.parse_version("v1.10") > updates.parse_version("v1.9.9")


# ---------------------------------------------------------------- the dial
@pytest.fixture()
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _rings(paths):
    from dropdial.app import DropDialApp
    return DropDialApp.build_rings(None, [str(p) for p in paths])


def test_rings_split_long_lists(tmp_path):
    src = tmp_path / "a.png"
    Image.new("RGB", (8, 8)).save(src)
    rings = _rings([src])
    conv = [i.label for i in rings["Convert"]]
    more = [i.label for i in rings.get("More formats", [])]
    assert len(conv) <= 8 and conv[:3] == ["JPG", "WEBP", "PDF"]
    assert set(conv + more) == set(convert.targets_for("image", "png"))
    assert not more or len(more) >= 3


def test_zip_offered_for_folders_and_mixed_files(tmp_path):
    from dropdial.app import can_zip
    if not can_zip():
        pytest.skip("archives module not available")
    d = tmp_path / "Holiday"
    d.mkdir()
    (d / "a.txt").write_text("x")
    assert [i.key for i in _rings([d])["Convert"]] == ["zip:ZIP"]
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    for p in (a, b):
        Image.new("RGB", (8, 8)).save(p)
    keys = [i.key for ring in _rings([a, b]).values() for i in ring]
    assert "zip:ZIP" in keys


def test_wheel_flips_rings(qapp, tmp_path):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from dropdial.radial import RadialMenu
    src = tmp_path / "a.png"
    Image.new("RGB", (8, 8)).save(src)
    m = RadialMenu(lambda p: _rings(p), lambda p: "1 KB")
    m._load([str(src)])
    assert len(m.ring_names) >= 3

    def wheel(dy):
        ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, dy), Qt.NoButton,
                         Qt.NoModifier, Qt.NoScrollPhase, False)
        m.wheelEvent(ev)
    wheel(-120)
    assert m.ring_idx == 1
    wheel(-60)
    assert m.ring_idx == 1          # half a notch (touchpads) doesn't flip yet
    wheel(-60)
    assert m.ring_idx == 2
    wheel(120)
    assert m.ring_idx == 1


def test_web_drag_fills_the_dial(qapp):
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
    from PySide6.QtGui import QDragEnterEvent
    from dropdial.radial import RadialMenu
    m = RadialMenu(lambda p: _rings(p), lambda p: "?")
    md = QMimeData()
    md.setUrls([QUrl("https://example.com/files/report.pdf")])
    ev = QDragEnterEvent(QPointF(200, 200), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    m.dragEnterEvent(ev)
    assert ev.isAccepted() and m.hub_text == "From the web"
    assert "DOCX" in [i.label for i in m.rings["Convert"]]
    assert all(p in m.web_items for p in m.paths)


# ---------------------------------------------------------------- image → SVG
@pytest.mark.skipif(not convert.can_trace(), reason="vtracer not installed")
def test_trace_svg_matches_the_picture(tmp_path):
    im = Image.new("RGB", (900, 600), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((80, 80, 420, 420), fill=(220, 30, 40))
    d.rectangle((480, 150, 840, 520), fill=(20, 90, 200))
    src = tmp_path / "logo.png"
    im.save(src)
    out = convert.convert(src, "image", "SVG")[0]
    text = out.read_text()
    assert text.lstrip().startswith("<?xml") and "<path" in text and "<!--" not in text
    back = convert.svg_to_image(out).convert("RGB").resize(im.size)
    err = np.abs(np.asarray(back, float) - np.asarray(im, float)).mean()
    assert err < 3, err
    # big pictures are traced smaller but keep their size on screen
    big = tmp_path / "big.png"
    im.resize((4000, 2667)).save(big)
    out = convert.convert(big, "image", "SVG")[0]
    assert 'width="4000" height="2667" viewBox=' in out.read_text()
