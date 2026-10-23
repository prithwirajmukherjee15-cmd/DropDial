"""3D model family: conversions are checked by re-reading outputs (trimesh + hand-written parsers)."""
from __future__ import annotations

import sys
import json
import struct
import time
import zipfile
from pathlib import Path

import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")
from PIL import Image  # noqa: E402

from dropdial import convert as conv  # noqa: E402
from dropdial import formats, util  # noqa: E402
from dropdial.formats import models  # noqa: E402

MESH_FORMATS = [t for t in ("GLB", "STL", "OBJ", "3MF", "PLY", "OFF") if t in models.ORDER]


@pytest.fixture(autouse=True)
def _beside(tmp_path):
    with util.output_override(util.BESIDE):
        yield


def _shape():
    """A closed, non-convex test solid: a box with a torus around it (two bodies, one mesh)."""
    box = trimesh.creation.box((2.0, 1.0, 0.6))
    ring = trimesh.creation.torus(1.5, 0.25, major_sections=48, minor_sections=16)
    ring.apply_translation([0.0, 0.0, 0.8])
    return trimesh.util.concatenate([box, ring])


def _write_fixture(mesh_or_scene, path: Path) -> Path:
    data = mesh_or_scene.export(file_type=path.suffix[1:])
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


def _reload(path: Path):
    """Independent re-read: plain trimesh.load into one welded mesh."""
    m = trimesh.load(str(path), force="mesh")
    m.merge_vertices(merge_tex=True, merge_norm=True)
    return m


def _convert(src: Path, target: str) -> list[Path]:
    cat = util.category(src)
    assert cat == "model"
    return conv.convert(src, cat, target)


# ---------------------------------------------------------------- registry
def test_registered_and_targets():
    fam = formats.family_for("thing.STL")
    assert fam is not None and fam.category == "model" and fam.label == "3D model"
    for ext in models.EXTS:
        t = conv.targets_for("model", ext[1:])
        assert ext[1:].upper() not in t and 0 < len(t) <= 9 and "PNG" in t
    assert "GLB" in conv.targets_for("model", "gltf")
    for name, hint in fam.hints.items():
        assert len(hint) <= 22, name
    assert all(t.name in fam.hints for t in fam.tools) and len(fam.tools) <= 6


# ---------------------------------------------------------------- round trips
@pytest.mark.parametrize("src_fmt", MESH_FORMATS)
def test_round_trip_every_pair(tmp_path, src_fmt):
    ref = _shape()
    ref_faces = len(ref.faces)
    welded = ref.copy()
    welded.merge_vertices()
    src = _write_fixture(ref, tmp_path / f"shape.{src_fmt.lower()}")
    for target in MESH_FORMATS:
        if target == src_fmt:
            continue
        outs = _convert(src, target)
        assert outs[0].suffix == "." + target.lower() and outs[0].stat().st_size > 0
        back = _reload(outs[0])
        assert len(back.faces) == ref_faces, (src_fmt, target)
        assert len(back.vertices) == len(welded.vertices), (src_fmt, target)
        assert np.allclose(back.bounds, ref.bounds, atol=1e-5), (src_fmt, target)
        assert back.volume == pytest.approx(ref.volume, rel=1e-4), (src_fmt, target)
        assert back.is_watertight


def test_binary_stl_layout(tmp_path):
    src = _write_fixture(_shape(), tmp_path / "shape.glb")
    out = _convert(src, "STL")[0]
    raw = out.read_bytes()
    (n,) = struct.unpack("<I", raw[80:84])
    assert n == len(_shape().faces) and len(raw) == 84 + 50 * n
    tri = np.frombuffer(raw[84:], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    v = tri["v"].reshape(-1, 3)
    assert np.allclose(v.min(0), _shape().bounds[0], atol=1e-5)


def test_off_and_ply_parse_by_hand(tmp_path):
    src = _write_fixture(_shape(), tmp_path / "shape.stl")
    off = _convert(src, "OFF")[0].read_text().split()
    assert off[0] == "OFF"
    nv, nf = int(off[1]), int(off[2])
    assert nf == len(_shape().faces)
    ply = _convert(src, "PLY")[0].read_bytes()
    head = ply[: ply.index(b"end_header")].decode()
    assert "binary_little_endian" in head and f"element face {nf}" in head and f"element vertex {nv}" in head


def test_glb_and_3mf_containers(tmp_path):
    src = _write_fixture(_shape(), tmp_path / "shape.off")
    glb = _convert(src, "GLB")[0].read_bytes()
    magic, version, length = struct.unpack("<4sII", glb[:12])
    assert magic == b"glTF" and version == 2 and length == len(glb)
    clen, ctype = struct.unpack("<I4s", glb[12:20])
    doc = json.loads(glb[20:20 + clen])
    assert ctype == b"JSON" and doc["asset"]["version"] == "2.0"
    idx = doc["meshes"][0]["primitives"][0]["indices"]
    assert doc["accessors"][idx]["count"] == 3 * len(_shape().faces)
    if "3MF" in MESH_FORMATS:
        from defusedxml import ElementTree
        out = _convert(src, "3MF")[0]
        with zipfile.ZipFile(out) as z:
            root = ElementTree.fromstring(z.read("3D/3dmodel.model"))
        tris = [e for e in root.iter() if e.tag.endswith("}triangle")]
        assert len(tris) == len(_shape().faces)


def test_multi_object_scene(tmp_path):
    scene = trimesh.Scene()
    scene.add_geometry(trimesh.creation.box((1, 1, 1)), node_name="Würfel 箱",
                       transform=trimesh.transformations.translation_matrix([5, 0, 0]))
    scene.add_geometry(trimesh.creation.icosphere(2), node_name="Kugel हिंदी 🎲")
    src = _write_fixture(scene, tmp_path / "two parts.glb")
    glb = trimesh.load_scene(str(_convert(src, "3MF" if "3MF" in MESH_FORMATS else "GLB")[0]))
    assert len(glb.geometry) == 2
    assert np.allclose(glb.bounds, scene.bounds, atol=1e-5)
    stl = _reload(_convert(src, "STL")[0])        # flattened with transforms applied
    assert np.allclose(stl.bounds, scene.bounds, atol=1e-5)
    assert len(stl.faces) == sum(len(g.faces) for g in scene.geometry.values())
    # GLB -> GLB (via a tool) keeps the scene and the Unicode node names
    out = models.center_ground([src])[0]
    again = trimesh.load_scene(str(out))
    assert {"Würfel 箱", "Kugel हिंदी 🎲"} <= set(again.graph.nodes)


def _textured_sphere():
    sphere = trimesh.creation.uv_sphere(radius=1.0, count=[24, 24])
    uv = np.c_[(sphere.vertices[:, 0] + 1) / 2, (sphere.vertices[:, 2] + 1) / 2]
    img = Image.new("RGB", (64, 64), (220, 30, 30))
    img.paste((30, 40, 220), (32, 0, 64, 64))      # right half (u > 0.5) blue
    mat = trimesh.visual.material.PBRMaterial(name="paint ../evil name", baseColorTexture=img)
    sphere.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
    return sphere


def test_textured_glb_to_obj_folder_and_back(tmp_path):
    src = _write_fixture(_textured_sphere(), tmp_path / "ball.glb")
    outs = _convert(src, "OBJ")
    folder = tmp_path / "ball OBJ"
    assert outs[0] == folder / "ball.obj"
    names = sorted(p.name for p in folder.iterdir())
    assert all(p.parent == folder for p in outs)
    mtl = next(p for p in outs if p.suffix == ".mtl")
    tex = [p for p in outs if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    assert len(tex) == 1 and ".." not in tex[0].name and "/" not in tex[0].name
    assert f"map_Kd {tex[0].name}" in mtl.read_text()
    assert f"mtllib {mtl.name}" in outs[0].read_text()
    assert not list(tmp_path.glob("evil*")) and len(names) == 3
    back = trimesh.load(str(outs[0]), force="mesh")
    assert isinstance(back.visual, trimesh.visual.TextureVisuals) and back.visual.material.image is not None
    # the texture really maps: vertices with x > 0.5 sample blue
    cols = back.visual.to_color().vertex_colors
    right = back.vertices[:, 0] > 0.5
    assert cols[right, 2].mean() > 150 and cols[back.vertices[:, 0] < -0.5, 0].mean() > 150
    # ...and OBJ (+MTL+PNG) -> GLB keeps the texture
    glb = trimesh.load(str(_convert(outs[0], "GLB")[0]), force="mesh")
    assert glb.visual.material.baseColorTexture is not None
    assert len(glb.faces) == len(_textured_sphere().faces)


def test_vertex_and_face_colours(tmp_path):
    m = trimesh.creation.icosphere(2)
    vc = np.zeros((len(m.vertices), 4), dtype=np.uint8)
    vc[:, 3] = 255
    vc[m.vertices[:, 2] > 0, 0] = 255
    vc[m.vertices[:, 2] <= 0, 2] = 255
    m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=vc)
    src = _write_fixture(m, tmp_path / "paint.ply")
    glb = trimesh.load(str(_convert(src, "GLB")[0]), force="mesh", process=False)
    ply = trimesh.load(str(_convert(tmp_path / "paint.glb", "PLY")[0]), force="mesh", process=False)
    for back in (glb, ply):
        top = back.vertices[:, 2] > 0
        assert (back.visual.vertex_colors[top, 0] == 255).all()
        assert (back.visual.vertex_colors[~top, 2] == 255).all()
    # face colours become exact vertex colours (vertices split only on colour borders)
    b = trimesh.creation.box()
    b.visual.face_colors = [[255, 0, 0, 255]] * 6 + [[0, 255, 0, 255]] * 6
    src = _write_fixture(b, tmp_path / "faces.ply")
    back = trimesh.load(str(_convert(src, "GLB")[0]), force="mesh", process=False)
    fc = back.visual.vertex_colors[back.faces]
    assert (fc == fc[:, :1]).all()                                  # each face one colour
    assert len(back.faces) == 12 and np.allclose(back.bounds, b.bounds)


def test_gltf_external_bin_and_escape(tmp_path):
    files = trimesh.Scene(_shape()).export(file_type="gltf")
    (tmp_path / "ok").mkdir()
    for name, data in files.items():
        (tmp_path / "ok" / name).write_bytes(data)
    gltf = tmp_path / "ok" / "model.gltf"
    back = _reload(_convert(gltf, "STL")[0])
    assert len(back.faces) == len(_shape().faces)
    # a buffer outside the folder (or a URL) is refused with a friendly error
    doc = json.loads(gltf.read_bytes())
    (tmp_path / "secret.bin").write_bytes((tmp_path / "ok" / doc["buffers"][0]["uri"]).read_bytes())
    for uri in ("../secret.bin", "https://example.com/x.bin", str(tmp_path / "secret.bin")):
        doc["buffers"][0]["uri"] = uri
        bad = tmp_path / "ok" / "bad.gltf"
        bad.write_text(json.dumps(doc))
        with pytest.raises(util.UserError):
            _convert(bad, "STL")
    # missing .bin
    doc["buffers"][0]["uri"] = "gone.bin"
    bad.write_text(json.dumps(doc))
    with pytest.raises(util.UserError, match="gone.bin"):
        _convert(bad, "GLB")


def test_bad_inputs(tmp_path):
    for name, data in {"empty.stl": b"", "junk.glb": b"glTF\x02\x00\x00\x00garbage",
                       "junk.3mf": b"not a zip", "junk.ply": b"ply\nformat nonsense\n",
                       "points.ply": b"ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\n"
                                     b"property float y\nproperty float z\nend_header\n0 0 0\n"}.items():
        if name.endswith(".3mf") and "3MF" not in MESH_FORMATS:
            continue
        p = tmp_path / name
        p.write_bytes(data)
        with pytest.raises(util.UserError):
            _convert(p, "STL" if not name.endswith(".stl") else "GLB")
    if "3MF" in MESH_FORMATS:
        good = _write_fixture(_shape(), tmp_path / "x.3mf")
        bomb = tmp_path / "entity.3mf"
        with zipfile.ZipFile(good) as zin, zipfile.ZipFile(bomb, "w") as zout:
            for info in zin.infolist():
                data = zin.read(info)
                if info.filename.endswith(".model"):
                    data = data.replace(b"?>", b'?><!DOCTYPE m [<!ENTITY a "aaaa">]>', 1)
                zout.writestr(info, data)
        with pytest.raises(util.UserError, match="unsafe"):
            _convert(bomb, "STL")


def test_never_overwrites_and_unicode_names(tmp_path):
    src = _write_fixture(_shape(), tmp_path / "模型 हिंदी 🎲.stl")
    a = _convert(src, "OBJ")[0]
    b = _convert(src, "OBJ")[0]
    assert a != b and a.exists() and b.exists() and b.name == "模型 हिंदी 🎲 (1).obj"
    assert src.read_bytes() == _shape().export(file_type="stl")


# ---------------------------------------------------------------- preview
def test_preview_box_three_faces(tmp_path):
    src = _write_fixture(trimesh.creation.box((2, 1.5, 1)), tmp_path / "box.stl")
    out = _convert(src, "PNG")[0]
    im = Image.open(out)
    assert im.mode == "RGBA" and max(im.size) == 1600
    a = np.asarray(im)
    for y, x in ((0, 0), (0, -1), (-1, 0), (-1, -1)):
        assert a[y, x, 3] == 0                                      # transparent background
    solid = a[a[..., 3] == 255][:, :3]
    frac = len(solid) / (a.shape[0] * a.shape[1])
    assert 0.25 < frac < 0.85
    colours, counts = np.unique(solid, axis=0, return_counts=True)
    top3 = colours[np.argsort(counts)[-3:]].astype(int)
    assert counts[np.argsort(counts)[-3:]].sum() > 0.9 * len(solid)   # flat faces: 3 solid colours
    lum = sorted(top3.mean(axis=1))
    assert lum[1] - lum[0] > 12 and lum[2] - lum[1] > 12


def test_preview_no_holes_and_occlusion(tmp_path):
    # smooth sphere: its silhouette is a filled disc (no holes), lit side brighter than shadow side
    src = _write_fixture(trimesh.creation.icosphere(4), tmp_path / "ball.ply")
    a = np.asarray(Image.open(_convert(src, "PNG")[0]))
    alpha = a[..., 3]
    ys, xs = np.nonzero(alpha == 255)
    cy, cx = ys.mean(), xs.mean()
    r = (xs.max() - xs.min()) / 2
    yy, xx = np.mgrid[: a.shape[0], : a.shape[1]]
    inside = (yy - cy) ** 2 + (xx - cx) ** 2 < (0.97 * r) ** 2
    assert (alpha[inside] == 255).all()
    lum = a[..., :3].mean(axis=2)
    left_top = lum[int(cy - r / 2), int(cx - r / 2)]
    right_bottom = lum[int(cy + r / 2), int(cx + r / 2)]
    assert left_top > right_bottom + 20
    # a red box in front of a blue box: the near (red) one wins where they overlap
    scene = trimesh.Scene()
    near = trimesh.creation.box((1, 1, 1))
    near.visual = trimesh.visual.ColorVisuals(near, vertex_colors=[255, 0, 0, 255])
    far = trimesh.creation.box((1, 1, 1))
    far.visual = trimesh.visual.ColorVisuals(far, vertex_colors=[0, 0, 255, 255])
    scene.add_geometry(near, node_name="near")
    scene.add_geometry(far, node_name="far",       # behind along the view direction
                       transform=trimesh.transformations.translation_matrix([-0.8, 1.2, 0.0]))
    im = np.asarray(models.render(scene, up=2, size=400))
    solid = im[im[..., 3] == 255][:, :3].astype(int)
    red = (solid[:, 0] > solid[:, 2] + 40).sum()
    blue = (solid[:, 2] > solid[:, 0] + 40).sum()
    assert red > 0 and blue > 0 and red > blue
    cy, cx = np.argwhere(im[..., 3] == 255).mean(axis=0).astype(int)
    assert im[cy, cx, 0] > im[cy, cx, 2]                         # centre of the overlap is red


def test_preview_texture_and_speed(tmp_path):
    src = _write_fixture(_textured_sphere(), tmp_path / "tex.glb")
    a = np.asarray(Image.open(_convert(src, "PNG")[0]))
    solid = a[a[..., 3] == 255][:, :3].astype(int)
    assert (solid[:, 0] > solid[:, 2] + 40).sum() > 1000 and (solid[:, 2] > solid[:, 0] + 40).sum() > 1000
    big = trimesh.creation.icosphere(6)                          # 81920 faces
    big = trimesh.util.concatenate([big, big.copy().apply_translation([2.2, 0, 0]),
                                    trimesh.creation.torus(1.2, 0.3, major_sections=256,
                                                           minor_sections=64)])
    assert len(big.faces) >= 190_000
    src = _write_fixture(big, tmp_path / "big.stl")
    scene = models._load(src)
    t = time.perf_counter()
    im = models.render(scene)
    assert time.perf_counter() - t < 8.0     # ~2 s on an idle 4-core machine
    assert np.asarray(im)[..., 3].mean() > 20


# ---------------------------------------------------------------- tools
def test_center_and_ground(tmp_path):
    m = _shape()
    m.apply_translation([10, -4, 7])
    stl = _write_fixture(m, tmp_path / "off center.stl")
    back = _reload(models.center_ground([stl])[0])
    assert back.bounds[0][2] == pytest.approx(0, abs=1e-6)
    assert np.allclose(back.bounds[:, :2].mean(axis=0), 0, atol=1e-6)
    assert np.allclose(np.ptp(back.bounds, axis=0), np.ptp(m.bounds, axis=0))
    glb = _write_fixture(m, tmp_path / "off center.glb")           # glTF is Y-up
    out = models.center_ground([glb])[0]
    assert out.name == "off center Centered.glb"
    b = trimesh.load_scene(str(out)).bounds
    assert b[0][1] == pytest.approx(0, abs=1e-6) and np.allclose(b[:, [0, 2]].mean(axis=0), 0, atol=1e-6)


def test_repair(tmp_path):
    m = trimesh.creation.icosphere(3)
    faces = m.faces.copy()
    faces[::5] = faces[::5, ::-1]                                  # broken winding
    keep = np.ones(len(faces), bool)
    keep[7] = False                                                # one-triangle hole
    lines = [f"v {x} {y} {z}" for x, y, z in m.vertices]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in faces[keep]]
    lines += [f"v {x} {y} {z}" for x, y, z in m.vertices[:3]]       # duplicate vertices
    src = tmp_path / "broken.obj"
    src.write_text("\n".join(lines))
    before = trimesh.load(str(src), force="mesh", process=False)
    assert not before.is_watertight and not before.is_winding_consistent
    out = models.repair([src])[0]
    assert out.name == "broken Repaired.obj"
    after = trimesh.load(str(out), force="mesh", process=False)
    assert after.is_watertight and after.is_winding_consistent and after.volume > 0
    assert len(after.faces) == len(m.faces) and len(after.vertices) == len(m.vertices)
    assert after.volume == pytest.approx(m.volume, rel=1e-6)


@pytest.mark.skipif(not models._HAS_DECIMATE, reason="fast_simplification not installed")
def test_decimate(tmp_path):
    src = _write_fixture(trimesh.creation.icosphere(4), tmp_path / "ball.stl")
    out = models.decimate([src])[0]
    assert out.name == "ball Decimated.stl"
    back = _reload(out)
    ref = trimesh.creation.icosphere(4)
    assert 0.4 < len(back.faces) / len(ref.faces) < 0.6
    assert np.allclose(back.bounds, ref.bounds, atol=0.03)
    assert back.volume == pytest.approx(ref.volume, rel=0.02)
    # a textured model keeps its texture and UVs
    tex = _write_fixture(_textured_sphere(), tmp_path / "tex.glb")
    g = trimesh.load(str(models.decimate([tex])[0]), force="mesh")
    assert g.visual.material.baseColorTexture is not None and g.visual.uv is not None
    assert len(g.faces) < len(_textured_sphere().faces)
    cols = g.visual.to_color().vertex_colors
    assert cols[g.vertices[:, 0] > 0.5, 2].mean() > 150


def test_cli_converts(tmp_path):
    import subprocess
    import sys
    src = _write_fixture(_shape(), tmp_path / "cli.stl")
    r = subprocess.run([sys.executable, "-m", "dropdial", "convert", str(src), "--to", "GLB"],
                       capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1],
                       env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=120)
    assert r.returncode == 0, r.stderr
    back = trimesh.load(str(tmp_path / "cli.glb"), force="mesh")
    assert len(back.faces) == len(_shape().faces)

