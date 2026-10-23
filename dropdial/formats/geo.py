"""Map data: GPX tracks, KML/KMZ, GeoJSON and (with pyshp) Shapefiles.

Everything is read into one small model (`GeoDoc` of `Feature`s: waypoints, tracks, routes,
polygons) and written back out, so every format converts to every other. Coordinates are kept
as full Python floats (written with `repr`, so they round-trip exactly), elevations and
per-point timestamps survive wherever the target format can hold them:

* GPX  — waypoints, routes, tracks with segments, <ele>, <time>;
* KML  — Placemarks; timed lines are written as gx:Track / gx:MultiTrack so times survive;
* GeoJSON — RFC 7946 with the de-facto `coordTimes` / `time` properties (togeojson,
  geojson.io) and `_gpxType` to tell routes from tracks;
* Shapefile — a zip of one layer per geometry type (no per-point times: the format can't).

Inputs are untrusted: XML is parsed with defusedxml (DOCTYPE/entities refused), sizes are
capped and KMZ entries are read in memory with zip-bomb guards — nothing is extracted.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..util import UserError, report_progress, sibling
from . import Family, Tool, register

MAX_BYTES = 200 * 1024 * 1024       # largest XML/JSON we parse (a 24 h 1 Hz GPX is ~15 MB)
EARTH_R = 6371008.8                 # mean Earth radius, metres (IUGG)
SIMPLIFY_M = 5.0                    # Ramer–Douglas–Peucker tolerance
MOVING_MPS = 0.3                    # slower than this between two fixes counts as stopped
ELE_NOISE_M = 3.0                   # elevation changes smaller than this are GPS noise

GPX_NS = "http://www.topografix.com/GPX/1/1"
KML_NS = "http://www.opengis.net/kml/2.2"
GX_NS = "http://www.google.com/kml/ext/2.2"


def _has(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


SHP_OK = _has("shapefile")          # pyshp


# ---------------------------------------------------------------- model
@dataclass
class Pt:
    lat: float
    lon: float
    ele: float | None = None
    time: datetime | None = None    # always timezone-aware UTC


@dataclass
class Feature:
    kind: str                       # "wpt" | "trk" | "rte" | "poly"
    name: str = ""
    desc: str = ""
    props: dict = field(default_factory=dict)
    point: Pt | None = None                                  # wpt
    segments: list[list[Pt]] = field(default_factory=list)   # trk / rte
    polygons: list[list[list[Pt]]] = field(default_factory=list)  # poly: [[outer, hole…], …]

    def all_points(self) -> list[Pt]:
        if self.point is not None:
            return [self.point]
        if self.segments:
            return [p for s in self.segments for p in s]
        return [p for poly in self.polygons for ring in poly for p in ring]


@dataclass
class GeoDoc:
    name: str = ""
    desc: str = ""
    features: list[Feature] = field(default_factory=list)

    def of(self, *kinds: str) -> list[Feature]:
        return [f for f in self.features if f.kind in kinds]

    def all_points(self) -> list[Pt]:
        return [p for f in self.features for p in f.all_points()]


# ---------------------------------------------------------------- small helpers
def _num(x: float) -> str:
    """Shortest exact decimal for a float, never in exponent form (GPX uses xsd:decimal)."""
    s = repr(float(x))
    if "e" in s or "E" in s:
        s = f"{x:.12f}".rstrip("0").rstrip(".")
    return s


def _ptime(s) -> datetime | None:
    if not isinstance(s, str) or not s.strip():
        return None
    t = s.strip()
    if t[-1] in "zZ":
        t = t[:-1] + "+00:00"
    t = re.sub(r"(\.\d{6})\d+", r"\1", t)      # Python 3.11 wants ≤ 6 fraction digits
    try:
        dt = datetime.fromisoformat(t)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ftime(dt: datetime) -> str:
    s = dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat()
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s + "Z"


def _coord(lat, lon, ele=None) -> Pt:
    try:
        lat, lon = float(lat), float(lon)
        ele = None if ele is None or ele == "" else float(ele)
    except (TypeError, ValueError):
        raise UserError("This file has a coordinate that isn't a number.") from None
    if not (math.isfinite(lat) and math.isfinite(lon)) or abs(lat) > 90 or abs(lon) > 180:
        raise UserError("This file has coordinates that aren't latitude/longitude "
                        "(it may use a projected coordinate system).")
    if ele is not None and not math.isfinite(ele):
        ele = None
    return Pt(lat, lon, ele)


def _closed(ring: list[Pt]) -> list[Pt]:
    if ring and (ring[0].lat, ring[0].lon) != (ring[-1].lat, ring[-1].lon):
        return ring + [ring[0]]
    return ring


_BAD_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")


def _esc(s) -> str:
    s = _BAD_XML.sub("", str(s))
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _read_capped(path: Path) -> bytes:
    try:
        size = path.stat().st_size
        if size > MAX_BYTES:
            raise UserError("This map file is too large to open (over 200 MB).")
        return path.read_bytes()
    except OSError as e:
        raise UserError(f"Couldn't read the file ({e.strerror or e}).") from None


def _xml(data: bytes):
    """Parse untrusted XML: no DOCTYPE, no entities, no external references."""
    from xml.etree.ElementTree import ParseError
    try:
        import defusedxml.ElementTree as safe_et
        from defusedxml import DefusedXmlException
    except ImportError:                     # fallback: refuse anything with a DTD
        safe_et, DefusedXmlException = None, ValueError
        probe = data
        if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
            probe = data.decode("utf-16", "ignore").encode()
        if re.search(rb"<!(DOCTYPE|ENTITY)", probe, re.I):
            raise UserError("This file uses XML DOCTYPE/entities, which DropDial won't open "
                            "for safety.")
    try:
        if safe_et is not None:
            return safe_et.fromstring(data, forbid_dtd=True)
        import xml.etree.ElementTree as et
        return et.fromstring(data)
    except DefusedXmlException:
        raise UserError("This file uses XML DOCTYPE/entities, which DropDial won't open "
                        "for safety.") from None
    except (ParseError, ValueError, UnicodeError):
        raise UserError("This file isn't valid XML — it may be damaged or incomplete.") from None


def _ln(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _kids(el, name: str):
    return [c for c in el if _ln(c.tag) == name]


def _kid(el, name: str):
    for c in el:
        if _ln(c.tag) == name:
            return c
    return None


def _text(el, name: str) -> str:
    c = _kid(el, name) if el is not None else None
    return (c.text or "").strip() if c is not None else ""


# ---------------------------------------------------------------- GPX
def _gpx_pt(el) -> Pt:
    p = _coord(el.get("lat"), el.get("lon"), _text(el, "ele") or None)
    p.time = _ptime(_text(el, "time"))
    return p


def read_gpx_bytes(data: bytes) -> GeoDoc:
    root = _xml(data)
    if _ln(root.tag) != "gpx":
        raise UserError("This doesn't look like a GPX file.")
    meta = _kid(root, "metadata")
    doc = GeoDoc(name=_text(meta, "name") or _text(root, "name"),     # GPX 1.1 / 1.0
                 desc=_text(meta, "desc") or _text(root, "desc"))

    def head(el, kind):
        props = {k: _text(el, k) for k in ("cmt", "sym", "type") if _text(el, k)}
        return Feature(kind, name=_text(el, "name"), desc=_text(el, "desc"), props=props)

    for el in root:
        ln = _ln(el.tag)
        if ln == "wpt":
            f = head(el, "wpt")
            f.point = _gpx_pt(el)
            doc.features.append(f)
        elif ln == "rte":
            f = head(el, "rte")
            pts = [_gpx_pt(p) for p in _kids(el, "rtept")]
            if pts:
                f.segments = [pts]
                doc.features.append(f)
        elif ln == "trk":
            f = head(el, "trk")
            f.segments = [s for s in ([_gpx_pt(p) for p in _kids(seg, "trkpt")]
                                      for seg in _kids(el, "trkseg")) if s]
            if f.segments:
                doc.features.append(f)
    return doc


def _gpx_pt_xml(tag: str, p: Pt, extra: str = "", ind: str = "") -> str:
    inner = ""
    if p.ele is not None:
        inner += f"<ele>{_num(p.ele)}</ele>"
    if p.time is not None:
        inner += f"<time>{_ftime(p.time)}</time>"
    inner += extra
    return f'{ind}<{tag} lat="{_num(p.lat)}" lon="{_num(p.lon)}">{inner}</{tag}>'


def gpx_text(doc: GeoDoc) -> str:
    def head(f: Feature, keys: tuple) -> str:
        out = f"<name>{_esc(f.name)}</name>" if f.name else ""
        for k in keys:
            if k == "desc":
                out += f"<desc>{_esc(f.desc)}</desc>" if f.desc else ""
            elif f.props.get(k) not in (None, ""):
                out += f"<{k}>{_esc(f.props[k])}</{k}>"
        return out

    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<gpx version="1.1" creator="DropDial" xmlns="{GPX_NS}" '
         'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
         f'xsi:schemaLocation="{GPX_NS} http://www.topografix.com/GPX/1/1/gpx.xsd">']
    if doc.name or doc.desc:
        o.append("  <metadata>" + (f"<name>{_esc(doc.name)}</name>" if doc.name else "")
                 + (f"<desc>{_esc(doc.desc)}</desc>" if doc.desc else "") + "</metadata>")
    for f in doc.of("wpt"):                               # GPX 1.1 order: wpt*, rte*, trk*
        o.append(_gpx_pt_xml("wpt", f.point, head(f, ("cmt", "desc", "sym", "type")), "  "))
    for f in doc.of("rte"):
        o.append("  <rte>" + head(f, ("cmt", "desc", "type")))
        o += [_gpx_pt_xml("rtept", p, ind="    ") for s in f.segments for p in s]
        o.append("  </rte>")
    for f in doc.of("trk", "poly"):
        segs = f.segments if f.kind == "trk" else [_closed(r) for poly in f.polygons for r in poly]
        if f.kind == "poly" and not f.props.get("type"):
            f = Feature("poly", f.name, f.desc, {**f.props, "type": "polygon"})
        o.append("  <trk>" + head(f, ("cmt", "desc", "type")))
        for s in segs:
            o.append("    <trkseg>")
            o += [_gpx_pt_xml("trkpt", p, ind="      ") for p in s]
            o.append("    </trkseg>")
        o.append("  </trk>")
    o.append("</gpx>")
    return "\n".join(o) + "\n"


# ---------------------------------------------------------------- KML / KMZ
def _kml_coords(text: str | None) -> list[Pt]:
    text = re.sub(r"\s*,\s*", ",", (text or "").strip())
    pts = []
    for tup in text.split():
        v = tup.split(",")
        if len(v) < 2:
            continue
        pts.append(_coord(v[1], v[0], v[2] if len(v) > 2 else None))
    return pts


def _kml_track(el) -> list[Pt]:
    whens = [_ptime((w.text or "").strip()) for w in _kids(el, "when")]
    pts = []
    for c in _kids(el, "coord"):
        v = (c.text or "").split()
        if len(v) >= 2:
            pts.append(_coord(v[1], v[0], v[2] if len(v) > 2 else None))
    if len(whens) == len(pts):
        for p, t in zip(pts, whens):
            p.time = t
    return pts


def _kml_geoms(el, out: list) -> None:
    """Flatten one geometry element into ("pt"|"line"|"poly", data) items."""
    ln = _ln(el.tag)
    if ln == "Point":
        out += [("pt", p) for p in _kml_coords(_text(el, "coordinates"))[:1]]
    elif ln in ("LineString", "LinearRing"):
        pts = _kml_coords(_text(el, "coordinates"))
        if pts:
            out.append(("line", pts))
    elif ln == "Track":
        pts = _kml_track(el)
        if pts:
            out.append(("line", pts))
    elif ln == "Polygon":
        rings = []
        for bname in ("outerBoundaryIs", "innerBoundaryIs"):
            for b in _kids(el, bname):
                for lr in _kids(b, "LinearRing"):
                    ring = _kml_coords(_text(lr, "coordinates"))
                    if ring:
                        rings.append(ring)
        if rings:
            out.append(("poly", rings))
    elif ln in ("MultiGeometry", "MultiTrack"):
        for c in el:
            _kml_geoms(c, out)


_KML_GEOMS = {"Point", "LineString", "LinearRing", "Polygon", "MultiGeometry", "Track", "MultiTrack"}


def _kml_placemark(pm, doc: GeoDoc) -> None:
    name, desc = _text(pm, "name"), _text(pm, "description")
    props = {}
    ext = _kid(pm, "ExtendedData")
    if ext is not None:
        for d in ext.iter():
            if _ln(d.tag) == "Data" and d.get("name"):
                props[d.get("name")] = _text(d, "value")
            elif _ln(d.tag) == "SimpleData" and d.get("name"):
                props[d.get("name")] = (d.text or "").strip()
    stamp = _ptime(_text(_kid(pm, "TimeStamp"), "when")) if _kid(pm, "TimeStamp") is not None else None
    geoms: list = []
    for c in pm:
        if _ln(c.tag) in _KML_GEOMS:
            _kml_geoms(c, geoms)
    for kind, data in geoms:
        if kind == "pt":
            if data.time is None:
                data.time = stamp
            doc.features.append(Feature("wpt", name, desc, dict(props), point=data))
    lines = [d for k, d in geoms if k == "line"]
    if lines:
        doc.features.append(Feature("trk", name, desc, dict(props), segments=lines))
    polys = [d for k, d in geoms if k == "poly"]
    if polys:
        doc.features.append(Feature("poly", name, desc, dict(props), polygons=polys))


def read_kml_bytes(data: bytes) -> GeoDoc:
    root = _xml(data)
    if _ln(root.tag) != "kml":
        raise UserError("This doesn't look like a KML file.")
    doc = GeoDoc()
    top = next((e for e in root if _ln(e.tag) in ("Document", "Folder")), None)
    if top is not None:
        doc.name, doc.desc = _text(top, "name"), _text(top, "description")
    for el in root.iter():                 # document order, through any Folder nesting
        if _ln(el.tag) == "Placemark":
            _kml_placemark(el, doc)
    return doc


def _kml_coord_text(pts: list[Pt]) -> str:
    return " ".join(f"{_num(p.lon)},{_num(p.lat)}" + (f",{_num(p.ele)}" if p.ele is not None else "")
                    for p in pts)


def kml_text(doc: GeoDoc) -> str:
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<kml xmlns="{KML_NS}" xmlns:gx="{GX_NS}">', "<Document>"]
    if doc.name:
        o.append(f"  <name>{_esc(doc.name)}</name>")
    if doc.desc:
        o.append(f"  <description>{_esc(doc.desc)}</description>")
    o.append('  <Style id="line"><LineStyle><color>ff0f48d9</color><width>4</width></LineStyle></Style>')
    o.append('  <Style id="area"><LineStyle><color>ffc27119</color><width>2</width></LineStyle>'
             '<PolyStyle><color>401971c2</color></PolyStyle></Style>')
    for f in doc.features:
        parts = ["  <Placemark>"]
        if f.name:
            parts.append(f"<name>{_esc(f.name)}</name>")
        if f.desc:
            parts.append(f"<description>{_esc(f.desc)}</description>")
        if f.kind == "wpt" and f.point.time is not None:
            parts.append(f"<TimeStamp><when>{_ftime(f.point.time)}</when></TimeStamp>")
        if f.kind != "wpt":
            parts.append("<styleUrl>#area</styleUrl>" if f.kind == "poly" else "<styleUrl>#line</styleUrl>")
        if f.props:
            parts.append("<ExtendedData>" + "".join(
                f'<Data name="{_esc(k)}"><value>{_esc(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))}</value></Data>'
                for k, v in f.props.items()) + "</ExtendedData>")
        if f.kind == "wpt":
            parts.append(f"<Point><coordinates>{_kml_coord_text([f.point])}</coordinates></Point>")
        elif f.kind in ("trk", "rte"):
            timed = all(p.time is not None for s in f.segments for p in s)
            if timed:     # gx:Track keeps a timestamp per point (Google Earth time slider)
                tracks = ["<gx:Track>" + "".join(f"<when>{_ftime(p.time)}</when>" for p in s)
                          + "".join(f"<gx:coord>{_num(p.lon)} {_num(p.lat)}"
                                    + (f" {_num(p.ele)}" if p.ele is not None else "") + "</gx:coord>"
                                    for p in s) + "</gx:Track>" for s in f.segments]
                parts.append(tracks[0] if len(tracks) == 1 else
                             "<gx:MultiTrack>" + "".join(tracks) + "</gx:MultiTrack>")
            else:
                lines = [f"<LineString><tessellate>1</tessellate><coordinates>{_kml_coord_text(s)}"
                         "</coordinates></LineString>" for s in f.segments]
                parts.append(lines[0] if len(lines) == 1 else
                             "<MultiGeometry>" + "".join(lines) + "</MultiGeometry>")
        else:
            polys = []
            for poly in f.polygons:
                x = "<Polygon><outerBoundaryIs><LinearRing><coordinates>" \
                    f"{_kml_coord_text(_closed(poly[0]))}</coordinates></LinearRing></outerBoundaryIs>"
                for hole in poly[1:]:
                    x += "<innerBoundaryIs><LinearRing><coordinates>" \
                         f"{_kml_coord_text(_closed(hole))}</coordinates></LinearRing></innerBoundaryIs>"
                polys.append(x + "</Polygon>")
            parts.append(polys[0] if len(polys) == 1 else
                         "<MultiGeometry>" + "".join(polys) + "</MultiGeometry>")
        parts.append("</Placemark>")
        o.append("".join(parts))
    o += ["</Document>", "</kml>"]
    return "\n".join(o) + "\n"


def read_kmz(path: Path) -> GeoDoc:
    import zipfile
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise UserError("This KMZ file is damaged (it isn't a valid zip).") from None
    with zf:
        kmls = [i for i in zf.infolist() if i.filename.lower().endswith(".kml") and not i.is_dir()]
        if not kmls:
            raise UserError("This KMZ has no KML document inside.")
        info = next((i for i in kmls if i.filename.lower() == "doc.kml"), kmls[0])
        if info.file_size > MAX_BYTES or (info.file_size > 10 * 1024 * 1024
                                          and info.file_size > 100 * max(info.compress_size, 1)):
            raise UserError("The KML inside this KMZ is too large to open safely.")
        try:
            with zf.open(info) as fh:
                data = fh.read(MAX_BYTES + 1)
        except (zipfile.BadZipFile, RuntimeError, OSError, EOFError, NotImplementedError):
            raise UserError("Couldn't read the KML inside this KMZ (damaged or encrypted).") from None
        if len(data) > MAX_BYTES:
            raise UserError("The KML inside this KMZ is too large to open safely.")
    return read_kml_bytes(data)


def _write_kmz(doc: GeoDoc, out: Path) -> None:
    import zipfile
    from ..convert import atomic_save

    def write(dst):
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("doc.kml", kml_text(doc).encode("utf-8", "replace"))
    atomic_save(write, out)


# ---------------------------------------------------------------- GeoJSON
def _gj_pos(c) -> Pt:
    if not isinstance(c, (list, tuple)) or len(c) < 2 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) for v in c[:3]):
        raise UserError("This GeoJSON has a malformed coordinate.")
    return _coord(c[1], c[0], c[2] if len(c) > 2 else None)


def _gj_times(seq, n: int) -> list:
    if isinstance(seq, list) and len(seq) == n:
        return [_ptime(t) for t in seq]
    return [None] * n


def _gj_feature(geom, props: dict, doc: GeoDoc) -> None:
    if not isinstance(geom, dict):
        return                                  # null geometry: nothing to place on a map
    props = dict(props)
    name = props.pop("name", "")
    desc = props.pop("description", None) or props.pop("desc", "")
    props.pop("description", None)
    name = "" if name is None else str(name)
    desc = "" if desc is None else str(desc)
    times = props.pop("coordTimes", None)
    ptime = _ptime(props.pop("time", None)) if isinstance(props.get("time"), str) else None
    kind = "rte" if props.pop("_gpxType", None) == "rte" else "trk"
    t, c = geom.get("type"), geom.get("coordinates")
    try:
        if t == "Point":
            p = _gj_pos(c)
            p.time = ptime
            doc.features.append(Feature("wpt", name, desc, props, point=p))
        elif t == "MultiPoint":
            for p in map(_gj_pos, c):
                doc.features.append(Feature("wpt", name, desc, dict(props), point=p))
        elif t in ("LineString", "MultiLineString"):
            lines = [c] if t == "LineString" else list(c)
            tlist = [times] if t == "LineString" else (times if isinstance(times, list) else [])
            segs = []
            for i, line in enumerate(lines):
                pts = [_gj_pos(x) for x in line]
                for p, tm in zip(pts, _gj_times(tlist[i] if i < len(tlist) else None, len(pts))):
                    p.time = tm
                if pts:
                    segs.append(pts)
            if segs:
                doc.features.append(Feature(kind, name, desc, props, segments=segs))
        elif t in ("Polygon", "MultiPolygon"):
            polys = [c] if t == "Polygon" else list(c)
            out = [[[_gj_pos(x) for x in ring] for ring in poly] for poly in polys]
            out = [[r for r in poly if r] for poly in out]
            out = [poly for poly in out if poly]
            if out:
                doc.features.append(Feature("poly", name, desc, props, polygons=out))
        elif t == "GeometryCollection":
            for g in geom.get("geometries") or []:
                _gj_feature(g, {**props, "name": name, "description": desc}, doc)
        else:
            raise UserError(f"This GeoJSON has an unknown geometry type ({str(t)[:30]}).")
    except TypeError:
        raise UserError("This GeoJSON has malformed coordinates.") from None


def read_geojson_bytes(data: bytes) -> GeoDoc:
    try:
        obj = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise UserError("This isn't valid GeoJSON — it may be damaged or incomplete.") from None
    if not isinstance(obj, dict) or "type" not in obj:
        raise UserError("This doesn't look like a GeoJSON file.")
    crs = obj.get("crs")
    if isinstance(crs, dict):
        cname = str((crs.get("properties") or {}).get("name", ""))
        if cname and not re.search(r"CRS84|4326|WGS ?84", cname, re.I):
            raise UserError("This GeoJSON uses a projected coordinate system; only "
                            "latitude/longitude (WGS 84) is supported.")
    doc = GeoDoc(name=str(obj.get("name") or ""))
    t = obj["type"]
    feats = obj.get("features") if t == "FeatureCollection" else [obj] if t == "Feature" else \
        [{"type": "Feature", "geometry": obj, "properties": {}}]
    if not isinstance(feats, list):
        raise UserError("This GeoJSON's feature list is malformed.")
    for f in feats:
        if isinstance(f, dict):
            props = f.get("properties")
            _gj_feature(f.get("geometry"), props if isinstance(props, dict) else {}, doc)
    return doc


def geojson_text(doc: GeoDoc) -> str:
    def pos(p: Pt) -> list:
        return [p.lon, p.lat] if p.ele is None else [p.lon, p.lat, p.ele]

    def t(p: Pt):
        return _ftime(p.time) if p.time is not None else None

    feats = []
    for f in doc.features:
        props = {"name": f.name} if f.name else {}
        if f.desc:
            props["description"] = f.desc
        props.update(f.props)
        if f.kind == "wpt":
            geom = {"type": "Point", "coordinates": pos(f.point)}
            if f.point.time is not None:
                props["time"] = t(f.point)
        elif f.kind in ("trk", "rte"):
            props["_gpxType"] = f.kind
            coords = [[pos(p) for p in s] for s in f.segments]
            times = [[t(p) for p in s] for s in f.segments]
            single = len(coords) == 1
            geom = {"type": "LineString" if single else "MultiLineString",
                    "coordinates": coords[0] if single else coords}
            if any(x is not None for s in times for x in s):
                props["coordTimes"] = times[0] if single else times
        else:
            coords = [[[pos(p) for p in _closed(r)] for r in poly] for poly in f.polygons]
            single = len(coords) == 1
            geom = {"type": "Polygon" if single else "MultiPolygon",
                    "coordinates": coords[0] if single else coords}
        feats.append({"type": "Feature", "properties": props, "geometry": geom})
    fc = {"type": "FeatureCollection"}
    if doc.name:
        fc["name"] = doc.name
    fc["features"] = feats
    return json.dumps(fc, ensure_ascii=False, indent=1) + "\n"


# ---------------------------------------------------------------- Shapefile (pyshp)
WGS84_PRJ = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
             'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')


def _signed_area(ring: list[tuple[float, float]]) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1])) / 2


def _inside(pt: tuple[float, float], ring: list[tuple[float, float]]) -> bool:
    x, y, hit = pt[0], pt[1], False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def read_shp(path: Path) -> GeoDoc:
    if not SHP_OK:
        raise UserError("Shapefile support needs the pyshp package.")
    import shapefile
    prj = path.with_suffix(".prj")
    if not prj.exists():
        prj = path.with_suffix(".PRJ")
    if prj.exists():
        try:
            wkt = prj.read_text("utf-8", "ignore")[:20000]
        except OSError:
            wkt = ""
        if re.search(r"PROJCS|PROJCRS", wkt, re.I):
            raise UserError("This shapefile uses a projected coordinate system; only "
                            "latitude/longitude (WGS 84) shapefiles are supported.")
    if path.stat().st_size > MAX_BYTES:
        raise UserError("This shapefile is too large to open (over 200 MB).")
    try:
        r = shapefile.Reader(str(path), encodingErrors="replace")
    except Exception:
        raise UserError("Couldn't open this shapefile — its .shx/.dbf companions may be missing "
                        "or damaged.") from None
    doc = GeoDoc(name=path.stem)
    try:
        with r:
            fields = [f[0] for f in r.fields[1:]] if r.dbf else []
            for i, shape in enumerate(r.iterShapes()):
                rec = r.record(i) if r.dbf else []
                props = {k: v for k, v in zip(fields, rec) if v not in (None, "")}
                props = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in props.items()}
                name = str(next((props.pop(k) for k in ("name", "NAME", "Name") if k in props), ""))
                desc = str(next((props.pop(k) for k in ("desc", "DESC", "descriptio", "DESCRIPTIO")
                                 if k in props), ""))
                tstr = props.pop("time", None) if isinstance(props.get("time"), str) else None
                kind_tag = props.pop("kind", None) if props.get("kind") in ("track", "route") else None
                st = shape.shapeType
                pts = shape.points
                zs = list(getattr(shape, "z", None) or []) if st in (11, 13, 15, 18) else []

                def mk(j):
                    return _coord(pts[j][1], pts[j][0], zs[j] if j < len(zs) else None)

                if st == 0 or not pts:
                    continue
                if st in (1, 11, 21, 8, 18, 28):          # point / multipoint
                    for j in range(len(pts)):
                        p = mk(j)
                        p.time = _ptime(tstr)
                        doc.features.append(Feature("wpt", name, desc, dict(props), point=p))
                    continue
                bounds = list(shape.parts) + [len(pts)]
                rings = [[mk(j) for j in range(a, b)] for a, b in zip(bounds, bounds[1:]) if b > a]
                if st in (3, 13, 23):                     # polyline
                    kind = "rte" if kind_tag == "route" else "trk"
                    doc.features.append(Feature(kind, name, desc, props, segments=rings))
                elif st in (5, 15, 25):                   # polygon: clockwise rings are outers
                    polys: list[list[list[Pt]]] = []
                    holes = []
                    for ring in rings:
                        xy = [(p.lon, p.lat) for p in ring]
                        (polys.append([ring]) if _signed_area(xy) <= 0 else holes.append(ring))
                    for h in holes:
                        home = next((poly for poly in polys if _inside((h[0].lon, h[0].lat),
                                     [(p.lon, p.lat) for p in poly[0]])), None)
                        (home.append(h) if home is not None else polys.append([h]))
                    doc.features.append(Feature("poly", name, desc, props, polygons=polys))
    except UserError:
        raise
    except Exception:
        raise UserError("This shapefile is damaged and couldn't be read.") from None
    return doc


def _dbf_str(v, limit: int = 254) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return s.encode("utf-8")[:limit].decode("utf-8", "ignore")


def _write_shp_zip(doc: GeoDoc, out: Path, stem: str) -> None:
    import shapefile
    import tempfile
    import zipfile
    from ..convert import atomic_save

    safe = re.sub(r"[^\w-]+", "_", stem).strip("_") or "map"
    layers = [("points", doc.of("wpt")), ("lines", doc.of("trk", "rte")), ("polygons", doc.of("poly"))]
    with tempfile.TemporaryDirectory() as td:
        written = []
        for lname, feats in layers:
            if not feats:
                continue
            has_z = all(p.ele is not None for f in feats for p in f.all_points())
            types = {"points": (shapefile.POINT, shapefile.POINTZ),
                     "lines": (shapefile.POLYLINE, shapefile.POLYLINEZ),
                     "polygons": (shapefile.POLYGON, shapefile.POLYGONZ)}[lname]
            base = Path(td) / f"{safe}_{lname}"
            # dbf field names are ≤ 10 ASCII chars: map each property key to a unique one
            cols: dict[str, str] = {}
            fixed = ["name", "desc"] + (["time"] if lname == "points" else []) + \
                    (["kind"] if lname == "lines" else [])
            used = set(fixed)
            for f in feats:
                for k in f.props:
                    if k in cols or k in fixed:
                        continue
                    c = re.sub(r"[^A-Za-z0-9_]", "_", k)[:10] or "field"
                    n = 1
                    while c.lower() in {u.lower() for u in used}:
                        c = f"{c[:8]}{n}"
                        n += 1
                    cols[k] = c
                    used.add(c)
            w = shapefile.Writer(str(base), shapeType=types[has_z], encoding="utf-8")
            try:
                for fname in fixed + list(cols.values()):
                    w.field(fname, "C", 254)
                for f in feats:
                    def xy(p: Pt):
                        return [p.lon, p.lat, p.ele] if has_z else [p.lon, p.lat]
                    if lname == "points":
                        (w.pointz(f.point.lon, f.point.lat, f.point.ele) if has_z
                         else w.point(f.point.lon, f.point.lat))
                        extra = [_ftime(f.point.time) if f.point.time else ""]
                    elif lname == "lines":
                        (w.linez if has_z else w.line)([[xy(p) for p in s] for s in f.segments])
                        extra = ["route" if f.kind == "rte" else "track"]
                    else:
                        rings = []
                        for poly in f.polygons:
                            for k, ring in enumerate(poly):
                                ring = _closed(ring)
                                cw = _signed_area([(p.lon, p.lat) for p in ring]) < 0
                                if cw != (k == 0):          # outer clockwise, holes counter-clockwise
                                    ring = ring[::-1]
                                rings.append([xy(p) for p in ring])
                        (w.polyz if has_z else w.poly)(rings)
                        extra = []
                    w.record(*([_dbf_str(f.name), _dbf_str(f.desc)] + extra
                               + [_dbf_str(f.props[k]) if k in f.props else "" for k in cols]))
            finally:
                w.close()
            base.with_suffix(".prj").write_text(WGS84_PRJ, encoding="ascii")
            base.with_suffix(".cpg").write_text("UTF-8", encoding="ascii")
            written += [base.with_suffix(e) for e in (".shp", ".shx", ".dbf", ".prj", ".cpg")]

        def write(dst):
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
                for p in written:
                    z.write(p, p.name)
        atomic_save(write, out)


# ---------------------------------------------------------------- read / write dispatch
def read(path: str | Path) -> GeoDoc:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".kmz":
        doc = read_kmz(path)
    elif ext == ".shp":
        doc = read_shp(path)
    else:
        data = _read_capped(path)
        doc = {".gpx": read_gpx_bytes, ".kml": read_kml_bytes,
               ".geojson": read_geojson_bytes}[ext](data)
    if not doc.features:
        raise UserError("No points, tracks or shapes were found in this file.")
    return doc


def _save_text(text: str, out: Path) -> None:
    from ..convert import atomic_save
    atomic_save(lambda dst: Path(dst).write_text(text, encoding="utf-8", errors="replace"), out)


def write(doc: GeoDoc, src: Path, fmt: str, label: str = "") -> Path:
    """Write `doc` beside `src` as GPX/KML/KMZ/GEOJSON/SHP/CSV/PNG; returns the file."""
    fmt = fmt.upper()
    if fmt == "SHP":
        out = sibling(src, f"{label} shapefile".strip(), ".zip")
        _write_shp_zip(doc, out, f"{src.stem} {label}".strip())
        return out
    out = sibling(src, label, "." + fmt.lower())
    if fmt == "GPX":
        _save_text(gpx_text(doc), out)
    elif fmt == "KML":
        _save_text(kml_text(doc), out)
    elif fmt == "KMZ":
        _write_kmz(doc, out)
    elif fmt == "GEOJSON":
        _save_text(geojson_text(doc), out)
    elif fmt == "CSV":
        _write_csv(doc, out)
    elif fmt == "PNG":
        render_png(doc, out, src.stem)
    else:
        raise UserError(f"Can't save map data as {fmt}.")
    return out


def _write_csv(doc: GeoDoc, out: Path) -> None:
    import csv
    from ..convert import atomic_save
    kinds = {"wpt": "waypoint", "trk": "track", "rte": "route", "poly": "polygon"}
    counters: dict[str, int] = {}
    rows = []
    for f in doc.features:
        counters[f.kind] = n = counters.get(f.kind, 0) + 1
        if f.kind == "wpt":
            segs = [[f.point]]
        elif f.kind == "poly":
            segs = [r for poly in f.polygons for r in poly]
        else:
            segs = f.segments
        for si, seg in enumerate(segs, 1):
            for p in seg:
                rows.append([kinds[f.kind], n, si, _num(p.lat), _num(p.lon),
                             "" if p.ele is None else _num(p.ele),
                             _ftime(p.time) if p.time else "", f.name, f.desc])

    def w(dst):
        with open(dst, "w", newline="", encoding="utf-8-sig", errors="replace") as fh:   # BOM: Excel
            cw = csv.writer(fh)
            cw.writerow(["type", "feature", "segment", "lat", "lon", "ele", "time", "name", "desc"])
            cw.writerows(rows)
    atomic_save(w, out)


# ---------------------------------------------------------------- geometry
def haversine(a: Pt, b: Pt) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(h)))


def rdp(pts: list[Pt], tol: float = SIMPLIFY_M) -> list[Pt]:
    """Ramer–Douglas–Peucker on a local metric projection (iterative: no recursion limit)."""
    n = len(pts)
    if n < 3:
        return list(pts)
    lat0 = math.radians(sum(p.lat for p in pts) / n)
    k = math.pi / 180 * EARTH_R
    xy = [(p.lon * k * math.cos(lat0), p.lat * k) for p in pts]
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = xy[a], xy[b]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            px, py = xy[i]
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
            d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k_ in zip(pts, keep) if k_]


# ---------------------------------------------------------------- tools
def _fmt_dur(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def stats(doc: GeoDoc) -> dict:
    lines = doc.of("trk") or doc.of("rte")
    segs = [s for f in lines for s in f.segments]
    dist = gain = loss = moving = 0.0
    moving_dist = 0.0
    for s in segs:
        ref = None
        for a, b in zip(s, s[1:]):
            d = haversine(a, b)
            dist += d
            if a.time and b.time:
                dt = (b.time - a.time).total_seconds()
                if dt > 0 and d / dt >= MOVING_MPS:
                    moving += dt
                    moving_dist += d
        for p in s:                    # hysteresis filter against GPS elevation jitter
            if p.ele is None:
                continue
            if ref is None:
                ref = p.ele
            elif p.ele - ref >= ELE_NOISE_M:
                gain, ref = gain + p.ele - ref, p.ele
            elif ref - p.ele >= ELE_NOISE_M:
                loss, ref = loss + ref - p.ele, p.ele
    times = [p.time for s in segs for p in s if p.time]
    eles = [p.ele for s in segs for p in s if p.ele is not None]
    allp = doc.all_points()
    return {"distance_m": dist, "gain_m": gain, "loss_m": loss,
            "duration_s": (max(times) - min(times)).total_seconds() if len(times) > 1 else None,
            "moving_s": moving if len(times) > 1 else None, "moving_m": moving_dist,
            "start": min(times) if times else None,
            "ele_min": min(eles) if eles else None, "ele_max": max(eles) if eles else None,
            "points": sum(len(s) for s in segs), "segments": len(segs), "lines": len(lines),
            "line_kind": "route" if lines and lines[0].kind == "rte" else "track",
            "waypoints": len(doc.of("wpt")), "polygons": len(doc.of("poly")),
            "bbox": (min(p.lat for p in allp), min(p.lon for p in allp),
                     max(p.lat for p in allp), max(p.lon for p in allp))}


def stats_text(doc: GeoDoc, title: str) -> str:
    st = stats(doc)
    rows = [("Distance", f"{st['distance_m'] / 1000:.2f} km")]
    if st["ele_max"] is not None:
        rows.append(("Elevation gain", f"+{st['gain_m']:.0f} m"))
        rows.append(("Elevation loss", f"-{st['loss_m']:.0f} m"))
        rows.append(("Highest / lowest", f"{st['ele_max']:.0f} m / {st['ele_min']:.0f} m"))
    if st["start"] is not None:
        rows.append(("Start", st["start"].strftime("%Y-%m-%d %H:%M:%S UTC")))
    if st["duration_s"]:
        rows.append(("Duration", _fmt_dur(st["duration_s"])))
        rows.append(("Moving time", _fmt_dur(st["moving_s"])))
        rows.append(("Average speed", f"{st['distance_m'] / st['duration_s'] * 3.6:.1f} km/h"))
        if st["moving_s"]:
            mv = st["moving_m"] / st["moving_s"]
            rows.append(("Moving speed", f"{mv * 3.6:.1f} km/h"))
            if mv > 0:
                pace = 1000 / mv
                rows.append(("Moving pace", f"{int(pace // 60)}:{int(pace % 60):02d} /km"))
    s, w, n, e = st["bbox"]
    plural = "s" if st["lines"] != 1 else ""
    rows += [("Points", f"{st['points']} in {st['lines']} {st['line_kind']}{plural}, "
                        f"{st['segments']} segment{'s' if st['segments'] != 1 else ''}"),
             ("Waypoints", str(st["waypoints"]))]
    if st["polygons"]:
        rows.append(("Polygons", str(st["polygons"])))
    rows.append(("Bounding box", f"S {_num(round(s, 6))}, W {_num(round(w, 6))}, "
                                 f"N {_num(round(n, 6))}, E {_num(round(e, 6))}"))
    out = [title, "=" * max(len(title), 8)] + [f"{k + ':':<18}{v}" for k, v in rows]
    out += ["", f"Distance is great-circle (haversine); elevation changes under {ELE_NOISE_M:.0f} m are "
                f"ignored as GPS noise; moving = faster than {MOVING_MPS * 3.6:.1f} km/h."]
    return "\n".join(out) + "\n"


def _src_fmt(src: Path) -> str:
    ext = src.suffix.lower().lstrip(".")
    return "SHP" if ext == "shp" else ext.upper()


def tool_stats(paths: list[Path]) -> list[Path]:
    outs = []
    for src in paths:
        doc = read(src)
        if not (doc.of("trk", "rte")):
            raise UserError("There's no track or route in this file to measure.")
        out = sibling(src, "stats", ".txt")
        title = doc.name or doc.of("trk", "rte")[0].name or src.stem
        _save_text(stats_text(doc, title), out)
        outs.append(out)
    return outs


def tool_reverse(paths: list[Path]) -> list[Path]:
    outs = []
    for src in paths:
        doc = read(src)
        lines = doc.of("trk", "rte")
        if not lines:
            raise UserError("There's no track or route in this file to reverse.")
        for f in lines:
            # timestamps would run backwards, so a reversed route carries none
            f.segments = [[Pt(p.lat, p.lon, p.ele) for p in reversed(s)] for s in reversed(f.segments)]
        outs.append(write(doc, src, _src_fmt(src), "reversed"))
    return outs


def tool_simplify(paths: list[Path]) -> list[Path]:
    outs = []
    for src in paths:
        doc = read(src)
        shapes = doc.of("trk", "rte", "poly")
        if not shapes:
            raise UserError("There's no track or shape in this file to simplify.")
        before = after = 0
        for f in shapes:
            if f.kind == "poly":
                new = []
                for poly in f.polygons:
                    rings = []
                    for r in poly:
                        s = rdp(_closed(r))
                        rings.append(s if len(s) >= 4 else r)
                    new.append(rings)
                before += sum(len(r) for poly in f.polygons for r in poly)
                f.polygons = new
            else:
                before += sum(len(s) for s in f.segments)
                f.segments = [rdp(s) for s in f.segments]
            after += len(f.all_points())
        outs.append(write(doc, src, _src_fmt(src), f"simplified {before}→{after} pts"))
    return outs


# ---------------------------------------------------------------- PNG preview
PALETTE = [(217, 72, 15), (25, 113, 194), (47, 158, 68), (174, 62, 201), (230, 119, 0),
           (12, 133, 153), (194, 37, 92)]


def _font(px: int, bold: bool = False):
    from PIL import ImageFont
    names = (("DejaVuSans-Bold.ttf", "segoeuib.ttf", "Arial Bold.ttf", "arialbd.ttf",
              "LiberationSans-Bold.ttf") if bold else
             ("DejaVuSans.ttf", "segoeui.ttf", "Arial Unicode.ttf", "Arial.ttf", "arial.ttf",
              "Helvetica.ttc", "LiberationSans-Regular.ttf"))
    for n in names:
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            continue
    return ImageFont.load_default(size=px)


def _nice(x: float) -> float:
    """1, 2 or 5 × 10^n at or below x."""
    if x <= 0:
        return 1.0
    e = math.floor(math.log10(x))
    for m in (5, 2, 1):
        if m * 10 ** e <= x:
            return m * 10 ** e
    return 10 ** e


def render_png(doc: GeoDoc, out: Path, fallback_title: str = "") -> None:
    from PIL import Image, ImageDraw
    from ..convert import atomic_save

    pts = doc.all_points()
    s_lat, w_lon = min(p.lat for p in pts), min(p.lon for p in pts)
    n_lat, e_lon = max(p.lat for p in pts), max(p.lon for p in pts)
    lat0 = (s_lat + n_lat) / 2
    kx = math.cos(math.radians(lat0))
    # minimum extent ~ 400 m so a single point still gets a sensible frame
    min_deg = 400 / (math.pi / 180 * EARTH_R)
    if (n_lat - s_lat) < min_deg:
        s_lat, n_lat = lat0 - min_deg / 2, lat0 + min_deg / 2
    lonc = (w_lon + e_lon) / 2
    if (e_lon - w_lon) * kx < min_deg:
        w_lon, e_lon = lonc - min_deg / 2 / kx, lonc + min_deg / 2 / kx
    span_x, span_y = (e_lon - w_lon) * kx, n_lat - s_lat

    SS = 2                                   # draw at 2× and downsample: smooth lines
    W = 1600
    aspect = max(0.6, min(1.25, span_y / span_x))
    H = int(W * aspect) + 110
    top, pad = 96, 56
    mw, mh = W - 2 * pad, H - top - pad
    scale = min(mw / span_x, mh / span_y) * 0.92
    cx, cy = pad + mw / 2, top + mh / 2
    lonm, latm = (w_lon + e_lon) / 2, (s_lat + n_lat) / 2

    def P(lat, lon):
        return ((cx + (lon - lonm) * kx * scale) * SS, (cy - (lat - latm) * scale) * SS)

    img = Image.new("RGB", (W * SS, H * SS), (244, 241, 234))
    d = ImageDraw.Draw(img, "RGBA")
    box = (pad * SS, top * SS, (W - pad) * SS, (H - pad) * SS)
    d.rectangle(box, fill=(252, 251, 248), outline=(214, 208, 196), width=SS)

    # lat/lon grid with labels (degrees of the visible frame)
    f_small, f_mid = _font(13 * SS), _font(15 * SS)
    vis_lat = mh / scale
    vis_lon = mw / scale / kx
    step = _nice(max(vis_lat, vis_lon) / 6)
    dec = max(0, -math.floor(math.log10(step)))

    def lab(v, pos, neg):
        return f"{abs(v):.{dec}f}°{pos if v >= 0 else neg}"
    lat_lo, lat_hi = latm - vis_lat / 2, latm + vis_lat / 2
    lon_lo, lon_hi = lonm - vis_lon / 2, lonm + vis_lon / 2
    v = math.ceil(lat_lo / step) * step
    while v <= lat_hi:
        y = P(v, lonm)[1]
        d.line([(box[0], y), (box[2], y)], fill=(226, 221, 210), width=SS)
        d.text((box[0] + 6 * SS, y - 4 * SS), lab(v, "N", "S"), font=f_small, fill=(138, 133, 119),
               anchor="ls")
        v += step
    v = math.ceil(lon_lo / step) * step
    while v <= lon_hi:
        x = P(latm, v)[0]
        d.line([(x, box[1]), (x, box[3])], fill=(226, 221, 210), width=SS)
        if x < box[2] - 70 * SS:
            d.text((x + 4 * SS, box[3] - 6 * SS), lab(v, "E", "W"), font=f_small, fill=(138, 133, 119),
                   anchor="ls")
        v += step

    # polygons, then lines (with a white halo), then waypoints on top
    ci = 0
    for f in doc.of("poly"):
        col = PALETTE[ci % len(PALETTE)]
        ci += 1
        for poly in f.polygons:
            for k, ring in enumerate(poly):
                xy = [P(p.lat, p.lon) for p in ring]
                if len(xy) >= 3:
                    d.polygon(xy, fill=(*col, 50) if k == 0 else (252, 251, 248, 255))
                    d.line(xy + xy[:1], fill=(*col, 230), width=2 * SS, joint="curve")
    for f in doc.of("trk", "rte"):
        col = PALETTE[ci % len(PALETTE)]
        ci += 1
        for s in f.segments:
            xy = [P(p.lat, p.lon) for p in s]
            if len(xy) > 1:
                d.line(xy, fill=(255, 255, 255, 230), width=7 * SS, joint="curve")
                d.line(xy, fill=(*col, 255), width=4 * SS, joint="curve")
        first, last = f.segments[0][0], f.segments[-1][-1]
        for p, c in ((last, (33, 37, 41)), (first, (47, 158, 68))):
            x, y = P(p.lat, p.lon)
            r = 7 * SS
            d.ellipse((x - r, y - r, x + r, y + r), fill=c, outline=(255, 255, 255), width=2 * SS)
    for f in doc.of("wpt"):
        x, y = P(f.point.lat, f.point.lon)
        r = 6 * SS
        d.ellipse((x - r, y - r, x + r, y + r), fill=(201, 42, 42), outline=(255, 255, 255), width=2 * SS)
        if f.name:
            d.text((x + 10 * SS, y), f.name[:40], font=f_mid, fill=(52, 50, 45), anchor="lm",
                   stroke_width=3 * SS, stroke_fill=(255, 255, 255))

    # scale bar (bottom-left) — metres per pixel at the centre latitude
    m_per_px = (math.pi / 180 * EARTH_R) / scale
    length_m = _nice(m_per_px * mw / 5)
    bar = length_m / m_per_px * SS
    bx, by = box[0] + 18 * SS, box[3] - 34 * SS
    for i in range(4):
        x0 = bx + bar * i / 4
        d.rectangle((x0, by, x0 + bar / 4, by + 7 * SS), fill=(52, 50, 45) if i % 2 == 0 else (255, 255, 255),
                    outline=(52, 50, 45), width=SS)
    lbl = f"{length_m / 1000:g} km" if length_m >= 1000 else f"{length_m:g} m"
    d.text((bx + bar + 8 * SS, by + 4 * SS), lbl, font=f_mid, fill=(52, 50, 45), anchor="lm",
           stroke_width=2 * SS, stroke_fill=(252, 251, 248))

    # north arrow (top-right)
    nx, ny = box[2] - 34 * SS, box[1] + 26 * SS
    a = 14 * SS
    d.polygon([(nx, ny), (nx - a * 0.6, ny + a * 2), (nx, ny + a * 1.5)], fill=(52, 50, 45))
    d.polygon([(nx, ny), (nx + a * 0.6, ny + a * 2), (nx, ny + a * 1.5)], fill=(160, 155, 145))
    d.text((nx, ny + a * 2 + 4 * SS), "N", font=_font(15 * SS, True), fill=(52, 50, 45), anchor="mt")

    # header: title + summary
    st = stats(doc) if doc.of("trk", "rte") else None
    title = (doc.name or fallback_title or "Map")[:80]
    d.text((pad * SS, 34 * SS), title, font=_font(26 * SS, True), fill=(33, 37, 41), anchor="ls")
    bits = []
    if st:
        bits.append(f"{st['distance_m'] / 1000:.2f} km")
        if st["ele_max"] is not None:
            bits.append(f"+{st['gain_m']:.0f} m / -{st['loss_m']:.0f} m")
        if st["duration_s"]:
            bits.append(_fmt_dur(st["duration_s"]))
    for kind, word in (("trk", "track"), ("rte", "route"), ("wpt", "waypoint"), ("poly", "area")):
        n = len(doc.of(kind))
        if n:
            bits.append(f"{n} {word}{'s' if n != 1 else ''}")
    d.text((pad * SS, 62 * SS), "  ·  ".join(bits), font=f_mid, fill=(110, 106, 96), anchor="ls")
    d.text(((W - pad) * SS, (H - pad + 22) * SS), "WGS 84 · equirectangular, no basemap",
           font=f_small, fill=(160, 155, 145), anchor="rs")

    final = img.resize((W, H), Image.LANCZOS)
    atomic_save(lambda dst: final.save(dst, "PNG", optimize=True), out)


# ---------------------------------------------------------------- family
EXTS = {".gpx", ".kml", ".kmz", ".geojson"} | ({".shp"} if SHP_OK else set())
ALL_TARGETS = ["GPX", "KML", "KMZ", "GEOJSON", "SHP", "CSV", "PNG"]


def targets(src_ext: str) -> list[str]:
    cur = src_ext.lower().lstrip(".").upper()
    return [t for t in ALL_TARGETS if t != cur and (t != "SHP" or SHP_OK)]


def convert(src: Path, target: str) -> list[Path]:
    target = target.upper()
    if target not in ALL_TARGETS:
        raise UserError(f"Can't convert map data to {target}.")
    if target == "SHP" and not SHP_OK:
        raise UserError("Saving a Shapefile needs the pyshp package.")
    doc = read(src)
    report_progress(0.5)
    return [write(doc, Path(src), target)]


register(Family(
    category="geo",
    label="Map data",
    exts=EXTS,
    targets=targets,
    convert=convert,
    hints={"GPX": "GPS devices · Strava", "KML": "Google Earth", "KMZ": "Zipped KML",
           "GEOJSON": "Web maps · QGIS", "SHP": "Shapefile (zipped)", "CSV": "One row per point",
           "PNG": "Map preview image", "Stats": "Km · climb · time",
           "Reverse": "Ride it the other way", "Simplify": "Fewer points (5 m)"},
    tools=[Tool("Stats", "Σ", "Km · climb · time", tool_stats, working="Measuring…"),
           Tool("Reverse", "⇄", "Ride it the other way", tool_reverse, working="Reversing…"),
           Tool("Simplify", "≈", "Fewer points (5 m)", tool_simplify, working="Simplifying…")],
))
