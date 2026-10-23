"""3D models: STL, OBJ, PLY, glTF/GLB, OFF and 3MF meshes (via trimesh), plus a rendered PNG preview.

Notes
* Geometry is never rotated or rescaled by a conversion: glTF is Y-up and STL/3MF are usually Z-up,
  but every converter keeps the coordinates as they are (like trimesh, MeshLab and most CLI tools).
  Only the preview camera and "Center & ground" care about which way is up (see Y_UP).
* OBJ output that needs an .mtl or texture files is written as a folder "<name> OBJ" holding
  "<name>.obj" plus its .mtl and textures (so the set can be moved or zipped as one); a plain
  OBJ with nothing to reference is written beside the source like any other file.
* trimesh's face-colour code paths need scipy, which the app doesn't bundle, so face colours are
  turned into vertex colours on load (vertices are split only where differently coloured faces meet,
  so colours stay exact).
"""
from __future__ import annotations

import copy
import re
import threading
from importlib.util import find_spec
from pathlib import Path

from .. import util
from ..util import UserError
from . import Family, Tool, register

EXTS = {".stl", ".obj", ".ply", ".glb", ".gltf", ".off", ".3mf"}
ORDER = ["GLB", "STL", "OBJ", "3MF", "PLY", "OFF", "PNG"]
HINTS = {
    "GLB": "Web · AR · Blender", "STL": "For 3D printing", "OBJ": "Mesh + materials",
    "3MF": "Modern 3D printing", "PLY": "Keeps vertex colours", "OFF": "Plain mesh text",
    "PNG": "Rendered preview",
    "Center & ground": "Sit it on the floor", "Repair": "Fix holes & normals",
    "Decimate 50%": "Half the triangles",
}
Y_UP = {"glb", "gltf", "obj", "ply"}          # formats whose files are conventionally Y-up
MAX_BYTES = 1 << 30                           # refuse model files (and referenced files) over 1 GB
MAX_FACES = 30_000_000
DEFAULT_RGB = (184, 192, 206)                 # preview / fill colour for uncoloured meshes
PREVIEW_SIZE = 1600

_HAS_3MF = bool(find_spec("lxml") and find_spec("networkx"))
_HAS_DECIMATE = bool(find_spec("fast_simplification"))
_FS_LOCK = threading.Lock()                   # fast_simplification keeps global state

if not _HAS_3MF:
    EXTS.discard(".3mf")
    ORDER.remove("3MF")


def _available() -> bool:
    return bool(find_spec("trimesh") and find_spec("numpy"))


def _targets(src_ext: str) -> list[str]:
    cur = src_ext.lower().lstrip(".").upper()
    return [t for t in ORDER if t != cur]


# ---------------------------------------------------------------- loading
def _resolver(root: Path):
    """Resolver for files a model references (.bin buffers, .mtl, textures): relative paths inside
    the model's own folder only; never URLs, absolute paths or '..' escapes; never writes."""
    from urllib.parse import unquote

    from trimesh.resolvers import Resolver

    class FolderResolver(Resolver):
        def __init__(self, folder):
            self.root = Path(folder).resolve()

        def get(self, name):
            raw = unquote(str(name)).strip().replace("\\", "/")
            label = raw.rsplit("/", 1)[-1] or "a file"
            if not raw or ":" in raw or raw.startswith("/"):
                raise UserError(f"This model refers to “{label}” outside its folder, which isn't allowed.")
            path = (self.root / raw).resolve()
            if not path.is_relative_to(self.root):
                raise UserError(f"This model refers to “{label}” outside its folder, which isn't allowed.")
            if not path.is_file():
                raise UserError(f"This model needs “{label}”, which isn't in its folder.")
            if path.stat().st_size > MAX_BYTES:
                raise UserError(f"“{label}” is too big to load.")
            return path.read_bytes()

        def write(self, name, data):
            raise PermissionError("read-only")

        def namespaced(self, namespace):
            sub = (self.root / str(namespace)).resolve()
            return FolderResolver(sub if sub.is_relative_to(self.root) else self.root)

        def keys(self):
            return iter(())

    return FolderResolver(root)


def _check_3mf(src: Path) -> None:
    """3MF is a zip of XML: refuse zip bombs and DOCTYPE/ENTITY declarations up front."""
    import zipfile
    try:
        zf = zipfile.ZipFile(src)
    except (zipfile.BadZipFile, OSError):
        raise UserError("This 3MF file is damaged (it isn't a valid 3MF package).") from None
    with zf:
        total = 0
        for info in zf.infolist():
            total += info.file_size
            ratio = info.file_size / max(1, info.compress_size)
            if total > 2 * MAX_BYTES or (ratio > 200 and info.file_size > 64 << 20):
                raise UserError("This 3MF file unpacks to an unreasonable size, so it wasn't opened.")
            if info.filename.lower().endswith((".model", ".rels", ".xml")):
                with zf.open(info) as fh:
                    head = fh.read(1 << 16).replace(b"\x00", b"").upper()
                if b"<!DOCTYPE" in head or b"<!ENTITY" in head:
                    raise UserError("This 3MF file contains unsafe XML, so it wasn't opened.")


def _load(src: Path):
    """Read any supported model into a trimesh.Scene of triangle meshes (or raise UserError)."""
    import numpy as np
    import trimesh

    ext = src.suffix.lower().lstrip(".")
    size = util.file_size(src)
    if size == 0:
        raise UserError("This file is empty.")
    if size > MAX_BYTES:
        raise UserError("This model is too big to convert (over 1 GB).")
    if ext == "3mf":
        _check_3mf(src)
    try:
        with open(src, "rb") as fh:
            scene = trimesh.load_scene(fh, file_type=ext, resolver=_resolver(src.parent))
    except UserError:
        raise
    except MemoryError:
        raise UserError("This model is too big to open.") from None
    except Exception:
        raise UserError(f"Couldn't read this {ext.upper()} file — it may be damaged.") from None

    drop = [k for k, g in scene.geometry.items()
            if not isinstance(g, trimesh.Trimesh) or len(g.faces) == 0]
    if drop:
        scene.delete_geometry(drop)
    if not scene.geometry or not scene.graph.nodes_geometry:
        raise UserError("This file has no 3D surfaces to convert (only points or lines).")
    faces = 0
    for name, g in list(scene.geometry.items()):
        if not np.isfinite(g.vertices).all():
            raise UserError(f"This {ext.upper()} file has broken coordinates — it may be damaged.")
        if len(g.faces) and (g.faces.min() < 0 or g.faces.max() >= len(g.vertices)):
            raise UserError(f"This {ext.upper()} file has broken faces — it may be damaged.")
        faces += len(g.faces)
        if isinstance(g.visual, trimesh.visual.ColorVisuals) and g.visual.kind == "face":
            scene.geometry[name] = _face_to_vertex_colors(g)
    if faces > MAX_FACES:
        raise UserError("This model has too many triangles to convert (over 30 million).")
    return scene


def _face_to_vertex_colors(g):
    """Face colours -> vertex colours, splitting a vertex only where faces of different colours meet."""
    import numpy as np
    import trimesh

    fc = np.asarray(g.visual.face_colors, dtype=np.uint8)
    palette, cid = np.unique(fc, axis=0, return_inverse=True)
    cid = cid.reshape(-1)
    key = g.faces.astype(np.int64) * len(palette) + cid[:, None]
    uniq, inv = np.unique(key.reshape(-1), return_inverse=True)
    return trimesh.Trimesh(vertices=g.vertices[uniq // len(palette)], faces=inv.reshape(-1, 3),
                           vertex_colors=palette[uniq % len(palette)], process=False,
                           metadata=dict(g.metadata))


# ---------------------------------------------------------------- colours
def _material_info(mat):
    """(sRGB RGBA factor 0..1 or None, PIL base-colour texture or None) for a trimesh material."""
    import numpy as np
    if mat is None:
        return None, None
    if hasattr(mat, "baseColorFactor") or hasattr(mat, "baseColorTexture"):
        factor, image = getattr(mat, "baseColorFactor", None), getattr(mat, "baseColorTexture", None)
    else:
        factor, image = getattr(mat, "diffuse", None), getattr(mat, "image", None)
    if factor is not None:
        f = np.asarray(factor, dtype=np.float64).reshape(-1)
        f = f / 255.0 if f.max() > 1.0 or f.dtype.kind in "ui" else f
        factor = np.concatenate([f[:4], [1.0] * (4 - len(f[:4]))])
    return factor, image


def _texture_array(image, max_side=1024):
    import numpy as np
    from PIL import Image
    im = image.convert("RGBA")
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
    return np.asarray(im, dtype=np.float32) / 255.0


def _sample(tex, uv):
    """Nearest-texel lookup with wrap-around; uv origin bottom-left (trimesh convention)."""
    import numpy as np
    h, w = tex.shape[:2]
    x = (np.mod(uv[:, 0], 1.0) * w).astype(np.int64).clip(0, w - 1)
    y = ((1.0 - np.mod(uv[:, 1], 1.0)) * h).astype(np.int64).clip(0, h - 1)
    return tex[y, x]


def _vertex_colors(g):
    """(V, 4) float 0..1 sRGB vertex colours for a mesh, or None when it has no colour information."""
    import numpy as np
    import trimesh
    vis = g.visual
    if isinstance(vis, trimesh.visual.ColorVisuals):
        if vis.kind == "vertex":
            return np.asarray(vis.vertex_colors, dtype=np.float64) / 255.0
        return None
    if isinstance(vis, trimesh.visual.TextureVisuals):
        factor, image = _material_info(vis.material)
        base = np.ones(4) if factor is None else factor
        out = np.tile(base, (len(g.vertices), 1))
        uv = vis.uv
        if image is not None and uv is not None and np.shape(uv) == (len(g.vertices), 2):
            out *= _sample(_texture_array(image), np.asarray(uv, dtype=np.float64))
        elif factor is None:
            return None
        return out
    return None


# ---------------------------------------------------------------- writing
def _instances(scene):
    """Yield (geometry, 4x4 world transform) for every placed mesh in the scene."""
    for node in scene.graph.nodes_geometry:
        transform, name = scene.graph[node]
        g = scene.geometry.get(name)
        if g is not None and len(g.faces):
            yield g, transform


def _flatten(scene, colours: bool):
    """One mesh with every instance's transform applied (for single-mesh formats)."""
    import numpy as np
    import trimesh
    verts, faces, cols, offset = [], [], [], 0
    for g, tf in _instances(scene):
        verts.append(trimesh.transformations.transform_points(g.vertices, tf))
        faces.append(g.faces + offset)
        cols.append(_vertex_colors(g) if colours else None)
        offset += len(g.vertices)
    kw = {}
    if any(c is not None for c in cols):
        fill = np.array([*DEFAULT_RGB, 255]) / 255.0
        cols = [np.tile(fill, (len(v), 1)) if c is None else c for c, v in zip(cols, verts)]
        kw["vertex_colors"] = np.round(np.vstack(cols) * 255).clip(0, 255).astype(np.uint8)
    return trimesh.Trimesh(vertices=np.vstack(verts), faces=np.vstack(faces), process=False, **kw)


def _encode(scene, fmt: str) -> bytes:
    from trimesh.exchange import off, ply, stl
    if fmt == "GLB":
        return scene.export(file_type="glb")
    if fmt == "3MF":
        from trimesh.exchange.threemf import export_3MF
        return export_3MF(scene)
    if fmt == "STL":
        return stl.export_stl(_flatten(scene, colours=False))
    if fmt == "PLY":
        return ply.export_ply(_flatten(scene, colours=True), encoding="binary", vertex_normal=False)
    if fmt == "OFF":
        return off.export_off(_flatten(scene, colours=False)).encode("utf-8")
    raise ValueError(fmt)


_SAFE = re.compile(r"[^A-Za-z0-9_\-]+")


def _safe(name, fallback: str) -> str:
    return _SAFE.sub("_", str(name or "")).strip("_")[:48] or fallback


def _write_obj(scene, src: Path, label: str) -> list[Path]:
    """OBJ (+ MTL + textures). Names coming from the file are sanitised: they become file names."""
    import trimesh
    from trimesh.exchange.obj import export_obj

    from ..convert import atomic_save

    clean, used = trimesh.Scene(), set()
    for i, (g, tf) in enumerate(_instances(scene)):
        m = g.copy()
        m.apply_transform(tf)
        if isinstance(m.visual, trimesh.visual.TextureVisuals) and m.visual.material is not None:
            mat = copy.copy(m.visual.material)
            mat.name = _safe(mat.name, f"material_{i}")
            m.visual.material = mat
        gname = _safe(m.metadata.get("name"), f"object_{i}")
        while gname in used:
            gname += "_"
        used.add(gname)
        m.metadata["name"] = gname
        clean.add_geometry(m, geom_name=gname)

    stem = f"{src.stem} {label}".strip() if label else src.stem
    base = _safe(stem, "model")
    text, extra = export_obj(clean, include_color=True, include_texture=True, return_texture=True,
                             mtl_name=f"{base}.mtl", header="DropDial")
    if not extra:
        out = util.sibling(src, label, ".obj")
        atomic_save(lambda dst: Path(dst).write_text(text, encoding="utf-8"), out)
        return [out]

    folder = util.unique_path(util.output_dir(src) / f"{stem} OBJ")
    folder.mkdir(parents=True)
    written = []
    try:
        obj = folder / f"{stem}.obj"
        atomic_save(lambda dst: Path(dst).write_text(text, encoding="utf-8"), obj)
        written.append(obj)
        for name, data in extra.items():
            if Path(name).name != name or name.startswith("."):
                continue               # never write outside the folder
            path = folder / name
            payload = data.encode("utf-8") if isinstance(data, str) else data
            atomic_save(lambda dst, b=payload: Path(dst).write_bytes(b), path)
            written.append(path)
    except BaseException:
        for p in written:
            p.unlink(missing_ok=True)
        try:
            folder.rmdir()
        except OSError:
            pass
        raise
    return written


def _save(scene, src: Path, fmt: str, label: str = "") -> list[Path]:
    from ..convert import atomic_save
    fmt = fmt.upper()
    if fmt == "OBJ":
        return _write_obj(scene, src, label)
    if fmt == "PNG":
        im = render(scene, up=_up_axis(src))
        out = util.sibling(src, label, ".png")
        atomic_save(lambda dst: im.save(dst, "PNG", compress_level=6), out)
        return [out]
    try:
        data = _encode(scene, fmt)
    except MemoryError:
        raise UserError("This model is too big to convert.") from None
    out = util.sibling(src, label, "." + fmt.lower())
    atomic_save(lambda dst: Path(dst).write_bytes(data), out)
    return [out]


def _same_format(src: Path) -> str:
    ext = src.suffix.lower().lstrip(".")
    return "GLB" if ext == "gltf" else ext.upper()   # .gltf + .bin is several files; GLB is one


def _up_axis(src: Path) -> int:
    return 1 if src.suffix.lower().lstrip(".") in Y_UP else 2


def convert(src: Path, target: str) -> list[Path]:
    target = target.upper()
    if target not in ORDER:
        raise UserError(f"Can't turn a 3D model into {target}.")
    return _save(_load(Path(src)), Path(src), target)


# ---------------------------------------------------------------- tools
def _replace_geometry(scene, fn):
    for name, g in list(scene.geometry.items()):
        scene.geometry[name] = fn(g)
    return scene


def center_ground(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        p = Path(p)
        scene = _load(p)
        lo, hi = scene.bounds
        up = _up_axis(p)
        shift = -(lo + hi) / 2.0
        shift[up] = -lo[up]
        scene.apply_translation(shift)
        out += _save(scene, p, _same_format(p), "Centered")
    return out


def _repair_mesh(g):
    import trimesh
    m = g.copy()
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces() & m.unique_faces())
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m, multibody=True)
    trimesh.repair.fill_holes(m)
    return m


def repair(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        p = Path(p)
        scene = _replace_geometry(_load(p), _repair_mesh)
        out += _save(scene, p, _same_format(p), "Repaired")
    return out


def _decimate_mesh(g):
    """Quadric decimation to ~50 % of the triangles, keeping UVs/vertex colours and the material."""
    import fast_simplification as fs
    import numpy as np
    import trimesh

    if len(g.faces) < 16:
        return g.copy()
    vis = g.visual
    textured = (isinstance(vis, trimesh.visual.TextureVisuals) and vis.uv is not None
                and np.shape(vis.uv) == (len(g.vertices), 2))
    m = g.copy()
    if not textured:
        m.merge_vertices(merge_tex=True, merge_norm=True)
    colors = (np.asarray(m.visual.vertex_colors) if isinstance(m.visual, trimesh.visual.ColorVisuals)
              and m.visual.kind == "vertex" else None)
    with _FS_LOCK:
        pts, tris, collapses = fs.simplify(m.vertices, m.faces, target_reduction=0.5,
                                           return_collapses=True, preserve_border=textured)
        _, _, mapping = fs.replay_simplification(m.vertices, m.faces, collapses)
    # each new vertex takes the attributes of one original vertex that collapsed into it
    src = np.zeros(len(pts), dtype=np.int64)
    ok = (mapping >= 0) & (mapping < len(pts))
    src[mapping[ok]] = np.flatnonzero(ok)
    kw = {}
    if textured:
        kw["visual"] = trimesh.visual.TextureVisuals(uv=np.asarray(m.visual.uv)[src],
                                                     material=m.visual.material)
    elif colors is not None:
        kw["vertex_colors"] = colors[src]
    elif isinstance(m.visual, trimesh.visual.TextureVisuals):
        kw["visual"] = trimesh.visual.TextureVisuals(material=m.visual.material)
    return trimesh.Trimesh(vertices=pts, faces=tris, process=False, metadata=dict(g.metadata), **kw)


def decimate(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        p = Path(p)
        scene = _replace_geometry(_load(p), _decimate_mesh)
        out += _save(scene, p, _same_format(p), "Decimated")
    return out


# ---------------------------------------------------------------- preview renderer
# Orthographic 3/4 view, z-buffered triangle rasterisation in numpy (2x supersampled),
# crease-aware smooth normals, two-sided Lambert key + fill light with hemispheric ambient,
# soft contact shadow, transparent background.
AZIMUTH, ELEVATION = 38.0, 28.0
CREASE_DEG = 40.0


def _gather(scene, up: int):
    """World-space triangles (rotated to Z-up) plus per-corner colours/UVs for rendering."""
    import numpy as np
    import trimesh
    tris, cols, uvs, tex_ids, cull, textures = [], [], [], [], [], []
    tex_index: dict[int, int] = {}
    default = np.array([*DEFAULT_RGB, 255], dtype=np.float32) / 255.0
    for g, tf in _instances(scene):
        v = trimesh.transformations.transform_points(g.vertices, tf)
        t = v[g.faces]
        if up == 1:                      # Y-up -> Z-up: (x, y, z) -> (x, -z, y), a proper rotation
            t = np.stack([t[..., 0], -t[..., 2], t[..., 1]], axis=-1)
        n = len(g.faces)
        vis = g.visual
        corner = np.broadcast_to(default, (n, 3, 4))
        uv = np.zeros((n, 3, 2), dtype=np.float32)
        tid = -1
        if isinstance(vis, trimesh.visual.ColorVisuals) and vis.kind == "vertex":
            corner = (np.asarray(vis.vertex_colors, dtype=np.float32) / 255.0)[g.faces]
        elif isinstance(vis, trimesh.visual.TextureVisuals):
            factor, image = _material_info(vis.material)
            if factor is not None:
                corner = np.broadcast_to(factor.astype(np.float32), (n, 3, 4))
            elif image is not None:
                corner = np.ones((n, 3, 4), dtype=np.float32)
            if image is not None and vis.uv is not None and np.shape(vis.uv) == (len(g.vertices), 2):
                key = id(image)
                if key not in tex_index:
                    tex_index[key] = len(textures)
                    textures.append(_texture_array(image))
                tid = tex_index[key]
                uv = np.asarray(vis.uv, dtype=np.float32)[g.faces]
        # closed, consistently wound meshes can skip faces pointing away from the camera
        closed = bool(g.is_watertight and g.is_winding_consistent)
        sign = 1.0
        if closed:
            vol = g.volume * np.linalg.det(tf[:3, :3])
            sign = 1.0 if vol >= 0 else -1.0
        tris.append(t)
        cols.append(np.asarray(corner, dtype=np.float32))
        uvs.append(uv)
        tex_ids.append(np.full(n, tid, dtype=np.int32))
        cull.append(np.full(n, sign if closed else 0.0, dtype=np.float32))
    return (np.concatenate(tris).astype(np.float64), np.concatenate(cols), np.concatenate(uvs),
            np.concatenate(tex_ids), np.concatenate(cull), textures)


def _corner_normals(tris, fn, fw):
    """Smooth normals per triangle corner, averaging only neighbours within CREASE_DEG
    (box edges stay sharp, spheres come out smooth). Corners are matched by position, so
    unwelded files (STL, UV seams) shade smoothly too."""
    import numpy as np
    n = len(tris)
    flat = np.repeat(fn[:, None, :], 3, axis=1).astype(np.float32)
    if n > 3_000_000:
        return flat
    pts = tris.reshape(-1, 3)
    lo = pts.min(axis=0)
    tol = max(float((pts.max(axis=0) - lo).max()), 1e-30) * 1e-7
    q = np.round((pts - lo) / tol).astype(np.int64)
    order = np.lexsort((q[:, 2], q[:, 1], q[:, 0]))
    qs = q[order]
    first = np.ones(len(order), dtype=bool)
    first[1:] = (qs[1:] != qs[:-1]).any(axis=1)
    gid = np.cumsum(first) - 1
    starts = np.flatnonzero(first)
    counts = np.diff(np.append(starts, len(order)))
    k = counts[gid]
    total = int(k.sum())
    if total > 40_000_000:              # pathological fans: flat shading is fine
        return flat
    a = np.repeat(order, k)
    off = np.arange(total) - np.repeat(np.cumsum(k) - k, k)
    b = order[np.repeat(starts[gid], k) + off]
    fa, fb = a // 3, b // 3
    fn32 = fn.astype(np.float32)
    dot = fn32[fa, 0] * fn32[fb, 0] + fn32[fa, 1] * fn32[fb, 1] + fn32[fa, 2] * fn32[fb, 2]
    keep = dot >= np.cos(np.radians(CREASE_DEG))
    a, fb = a[keep], fb[keep]
    acc = np.stack([np.bincount(a, weights=fw[fb, j], minlength=3 * n) for j in range(3)], axis=1)
    length = np.linalg.norm(acc, axis=1, keepdims=True)
    out = np.where(length > 0, acc / np.maximum(length, 1e-30), flat.reshape(-1, 3))
    return out.reshape(n, 3, 3).astype(np.float32)


def render(scene, up: int = 2, size: int = PREVIEW_SIZE, ss: int = 2):
    """Render a scene to an RGBA PIL image (long side `size`, transparent background)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    tris, ccol, cuv, tex_id, cull, textures = _gather(scene, up)
    az, el = np.radians(AZIMUTH), np.radians(ELEVATION)
    to_cam = np.array([np.sin(az) * np.cos(el), -np.cos(az) * np.cos(el), np.sin(el)])
    right = np.array([np.cos(az), np.sin(az), 0.0])
    upv = np.cross(right, -to_cam)

    # contact shadow footprint: triangles in the lowest fifth of the model, dropped onto the ground
    zmin, zmax = tris[..., 2].min(), tris[..., 2].max()
    low = tris[tris[..., 2].min(axis=1) <= zmin + 0.2 * (zmax - zmin) + 1e-12].copy()
    low[..., 2] = zmin
    gx, gy = (low @ right).reshape(-1), (low @ upv).reshape(-1)

    X, Y, D = tris @ right, tris @ upv, tris @ -to_cam
    xs = np.concatenate([X.reshape(-1), gx])
    ys = np.concatenate([Y.reshape(-1), gy])
    ex, ey = xs.max() - xs.min(), ys.max() - ys.min()
    if max(ex, ey) <= 0 or not np.isfinite([ex, ey]).all():
        raise UserError("This model has no visible size to draw.")
    margin = 0.07
    if ex >= ey:
        W = size
        H = int(round(min(size, max(size * 0.55, size * ey / ex + 2 * margin * size))))
    else:
        H = size
        W = int(round(min(size, max(size * 0.55, size * ex / ey + 2 * margin * size))))
    scale = min((W * (1 - 2 * margin)) / max(ex, 1e-30), (H * (1 - 2 * margin)) / max(ey, 1e-30))
    cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2
    Ws, Hs, s = W * ss, H * ss, scale * ss

    sx = (X - cx) * s + Ws / 2
    sy = Hs / 2 - (Y - cy) * s
    dmin, dmax = D.min(), D.max()
    dz = (D - dmin) / max(dmax - dmin, 1e-30)

    # face normals (world), facing test, culling
    e1, e2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    fw = np.cross(e1, e2)
    fl = np.linalg.norm(fw, axis=1)
    fn = fw / np.maximum(fl, 1e-300)[:, None]
    facing = fn @ to_cam
    x0, x1, x2 = sx[:, 0], sx[:, 1], sx[:, 2]
    y0, y1, y2 = sy[:, 0], sy[:, 1], sy[:, 2]
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    live = (np.abs(area) > 1e-9) & (fl > 0) & ~((cull != 0) & (facing * cull <= 0))

    # bounding boxes in pixel-centre space
    ix0 = np.ceil(np.minimum(np.minimum(x0, x1), x2) - 0.5).clip(0, Ws - 1).astype(np.int64)
    ix1 = np.floor(np.maximum(np.maximum(x0, x1), x2) - 0.5).clip(-1, Ws - 1).astype(np.int64)
    iy0 = np.ceil(np.minimum(np.minimum(y0, y1), y2) - 0.5).clip(0, Hs - 1).astype(np.int64)
    iy1 = np.floor(np.maximum(np.maximum(y0, y1), y2) - 0.5).clip(-1, Hs - 1).astype(np.int64)
    bw, bh = ix1 - ix0 + 1, iy1 - iy0 + 1
    live &= (bw > 0) & (bh > 0)
    idx = np.flatnonzero(live)

    # barycentric + depth planes: w_i(px, py) = a_i px + b_i py + c_i
    A = np.where(live, area, 1.0)
    a0, b0, c0 = (y1 - y2) / A, (x2 - x1) / A, (x1 * y2 - x2 * y1) / A
    a1, b1, c1 = (y2 - y0) / A, (x0 - x2) / A, (x2 * y0 - x0 * y2) / A
    a2, b2, c2 = (y0 - y1) / A, (x1 - x0) / A, (x0 * y1 - x1 * y0) / A
    az_ = a0 * dz[:, 0] + a1 * dz[:, 1] + a2 * dz[:, 2]
    bz_ = b0 * dz[:, 0] + b1 * dz[:, 1] + b2 * dz[:, 2]
    cz_ = c0 * dz[:, 0] + c1 * dz[:, 1] + c2 * dz[:, 2]

    # scanline spans: for every (triangle, pixel row) solve the three edge inequalities for the
    # covered x range, so only pixels inside the triangle are ever generated
    eps = -1e-7
    rows_t = np.repeat(idx, bh[idx])
    ry = np.repeat(iy0[idx], bh[idx]) + (np.arange(len(rows_t))
                                         - np.repeat(np.cumsum(bh[idx]) - bh[idx], bh[idx]))
    fy = ry + 0.5
    lo = ix0[rows_t].astype(np.float64)
    hi = ix1[rows_t].astype(np.float64)
    for a, b, c in ((a0, b0, c0), (a1, b1, c1), (a2, b2, c2)):
        at = a[rows_t]
        v = b[rows_t] * fy + c[rows_t]
        with np.errstate(divide="ignore", invalid="ignore"):
            bound = (eps - v) / at - 0.5          # pixel index where a*(px+0.5) + v == eps
        lo = np.where(at > 0, np.maximum(lo, np.ceil(bound)), lo)
        hi = np.where(at < 0, np.minimum(hi, np.floor(bound)), hi)
        hi = np.where((at == 0) & (v < eps), -1, hi)
    span = np.maximum(0, hi - lo + 1).astype(np.int64)
    keep = span > 0
    rows_t, ry, span, lo = rows_t[keep], ry[keep], span[keep], lo[keep].astype(np.int64)

    EMPTY = np.iinfo(np.int64).max
    zbuf = np.full(Ws * Hs, EMPTY, dtype=np.int64)
    ZQ = (1 << 30) - 1
    budget = 1 << 21
    cum = np.cumsum(span)
    cuts = np.searchsorted(cum, np.arange(budget, cum[-1] if len(cum) else 0, budget), side="right")
    edges = [0, *np.unique(cuts).tolist(), len(span)]
    for i, (s0, s1) in enumerate(zip(edges[:-1], edges[1:])):
        if s1 <= s0:
            continue
        n_ = span[s0:s1]
        rep = np.repeat(np.arange(s1 - s0), n_)
        px = lo[s0:s1][rep] + (np.arange(len(rep)) - np.repeat(np.cumsum(n_) - n_, n_))
        py = ry[s0:s1][rep]
        t = rows_t[s0:s1][rep]
        z = (az_[t] * (px + 0.5) + bz_[t] * (py + 0.5) + cz_[t]).clip(0, 1)
        np.minimum.at(zbuf, py * Ws + px, ((z * ZQ).astype(np.int64) << 32) | t)
        util.report_progress(0.85 * (i + 1) / (len(edges) - 1))

    covered = np.flatnonzero(zbuf != EMPTY)
    t = (zbuf[covered] & 0xFFFFFFFF).astype(np.int64)
    del zbuf
    fx, fy = covered % Ws + 0.5, covered // Ws + 0.5
    w1 = (a1[t] * fx + b1[t] * fy + c1[t]).clip(0, 1).astype(np.float32)[:, None]
    w2 = (a2[t] * fx + b2[t] * fy + c2[t]).clip(0, 1).astype(np.float32)[:, None]
    del fx, fy

    def interp(q):
        """Per-pixel value of a per-corner attribute q (n, 3, k): q0 + (q1-q0) w1 + (q2-q0) w2."""
        q = np.asarray(q, dtype=np.float32)
        out = np.take(np.ascontiguousarray(q[:, 1] - q[:, 0]), t, axis=0)
        out *= w1
        out += np.take(np.ascontiguousarray(q[:, 2] - q[:, 0]), t, axis=0) * w2
        out += np.take(np.ascontiguousarray(q[:, 0]), t, axis=0)
        return out

    # normals: crease-aware smooth, flipped toward the camera for faces seen from behind
    used = np.unique(t)
    cn = np.zeros((len(tris), 3, 3), dtype=np.float32)
    cn[used] = _corner_normals(tris[used], fn[used], fw[used])
    cn *= np.where(facing < 0, -1.0, 1.0).astype(np.float32)[:, None, None]
    nrm = interp(cn)
    nrm /= np.maximum(np.sqrt((nrm * nrm).sum(axis=1, keepdims=True)), 1e-12)

    lin = np.power(ccol[:, :, :3].clip(0, 1), 2.2)                # linear-light colour
    if (lin == lin[0, 0]).all():
        base = np.broadcast_to(lin[0, 0], (len(t), 3)).copy() if textures else lin[0, 0]
    else:
        base = interp(lin)
    tid = tex_id[t]
    for k, tex in enumerate(textures):
        sel = np.flatnonzero(tid == k)
        if len(sel):
            ts, q = t[sel], cuv
            uv = (np.take(q[:, 0], ts, axis=0) + np.take(q[:, 1] - q[:, 0], ts, axis=0) * w1[sel]
                  + np.take(q[:, 2] - q[:, 0], ts, axis=0) * w2[sel])
            base[sel] *= np.power(_sample(tex, uv)[:, :3], 2.2)

    key_l = np.array([-0.45, -0.75, 1.0], dtype=np.float32)
    key_l /= np.linalg.norm(key_l)
    fill_l = np.array([0.9, -0.35, 0.25], dtype=np.float32)
    fill_l /= np.linalg.norm(fill_l)
    light = (0.21 + 0.09 * nrm[:, 2]
             + 0.85 * np.maximum(nrm @ key_l, 0) + 0.25 * np.maximum(nrm @ fill_l, 0))
    lut = np.round(np.power(np.linspace(0, 1, 4096), 1 / 2.2) * 255).astype(np.uint8)
    rgb = lut[(base * light[:, None] * 4095).clip(0, 4095).astype(np.int32)]   # linear -> sRGB

    buf = np.zeros((Ws * Hs, 4), dtype=np.uint8)
    buf[covered, :3] = rgb
    buf[covered, 3] = 255
    model = Image.frombuffer("RGBa", (Ws, Hs), buf.tobytes(), "raw", "RGBa", 0, 1)
    model = model.reduce(ss).convert("RGBA")
    util.report_progress(0.95)

    # soft contact shadow under the model, drawn at quarter resolution then blurred
    q = 4
    small = Image.new("L", (max(1, W // q), max(1, H // q)), 0)
    sxg = ((gx - cx) * scale + W / 2) / q
    syg = (H / 2 - (gy - cy) * scale) / q
    if len(low) <= 20000:
        draw = ImageDraw.Draw(small)
        for tri in np.stack([sxg, syg], axis=1).reshape(-1, 3, 2).tolist():
            draw.polygon([tuple(p) for p in tri], fill=255)
    else:                                   # dense mesh: splat the vertices, then close the gaps
        ok = (sxg >= 0) & (sxg < small.width) & (syg >= 0) & (syg < small.height)
        grid = np.zeros((small.height, small.width), dtype=np.uint8)
        grid[syg[ok].astype(np.int64), sxg[ok].astype(np.int64)] = 255
        small = Image.fromarray(grid).filter(ImageFilter.MaxFilter(3))
    shadow = small.resize((W, H), Image.Resampling.BILINEAR)
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(2.0, 0.015 * max(W, H))))
    shadow = shadow.point(lambda v: v * 60 // 255)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.putalpha(shadow)
    return Image.alpha_composite(out, model)


register(Family(
    category="model",
    label="3D model",
    exts=EXTS,
    targets=_targets,
    convert=convert,
    hints=HINTS,
    tools=[
        Tool("Center & ground", "⊥", HINTS["Center & ground"], center_ground, working="Centering…"),
        Tool("Repair", "✚", HINTS["Repair"], repair, working="Repairing…"),
        *([Tool("Decimate 50%", "◭", HINTS["Decimate 50%"], decimate, working="Simplifying…")]
          if _HAS_DECIMATE else []),
    ],
    available=_available,
))
