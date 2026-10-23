"""Map data family: GPX / KML / KMZ / GeoJSON / Shapefile / CSV / PNG and the tools.

Outputs are checked with independent parsers (stdlib ElementTree, json, csv, zipfile, struct,
Pillow, pyshp) against the values the fixtures were built from."""
from __future__ import annotations

import csv
import json
import math
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from dropdial import convert as conv
from dropdial import formats, util
from dropdial.formats import geo
from dropdial.util import UserError

GPX = "{http://www.topografix.com/GPX/1/1}"
KML = "{http://www.opengis.net/kml/2.2}"
GX = "{http://www.google.com/kml/ext/2.2}"
T0 = datetime(2024, 5, 1, 6, 30, 0, tzinfo=timezone.utc)

# two segments of a hand-built track with awkward precision, negative longitudes and a
# fractional-second timestamp; waypoints with Hindi, Japanese and emoji names
SEG1 = [(51.50735091234567, -0.12775829812345, 11.25, T0),
        (51.5080123456789, -0.12601234567891, 12.5, T0 + timedelta(seconds=20)),
        (51.50912345678912, -0.12432109876543, 15.75, T0 + timedelta(seconds=41, microseconds=250000))]
SEG2 = [(51.51002468013579, -0.12301357924680, 18.0, T0 + timedelta(minutes=5)),
        (51.51111111111111, -0.12222222222222, 21.125, T0 + timedelta(minutes=5, seconds=30)),
        (51.51234567890123, -0.12123456789012, 19.5, T0 + timedelta(minutes=6))]
WPTS = [(51.5007292, -0.1246254, 5.5, "बिग बेन", "घड़ी"),
        (51.5033635, -0.1195629, 7.0, "ロンドン・アイ 🎡", "観覧車")]


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S") + (f".{t.microsecond:06d}".rstrip("0") if t.microsecond else "") + "Z"


def make_gpx(path: Path, with_route: bool = False) -> Path:
    def pt(tag, lat, lon, ele, t, extra=""):
        return (f'<{tag} lat="{lat!r}" lon="{lon!r}"><ele>{ele!r}</ele>'
                + (f"<time>{iso(t)}</time>" if t else "") + f"{extra}</{tag}>")
    wpts = "".join(pt("wpt", la, lo, e, None, f"<name>{n}</name><desc>{d}</desc><sym>Flag</sym>")
                   for la, lo, e, n, d in WPTS)
    rte = ""
    if with_route:
        rte = ("<rte><name>Plan</name>" + "".join(pt("rtept", la, lo, e, None) for la, lo, e, _ in SEG1)
               + "</rte>")
    trk = ("<trk><name>Morning walk 朝</name><desc>Two parts</desc>"
           + "".join("<trkseg>" + "".join(pt("trkpt", *p) for p in seg) + "</trkseg>" for seg in (SEG1, SEG2))
           + "</trk>")
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                    f'<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">'
                    f"<metadata><name>London 🚶</name></metadata>{wpts}{rte}{trk}</gpx>", encoding="utf-8")
    return path


def gpx_parse(path: Path) -> dict:
    """Independent GPX reader (stdlib ElementTree on our own trusted output)."""
    root = ET.parse(path).getroot()
    assert root.tag == f"{GPX}gpx" and root.get("version") == "1.1"

    def p(el):
        e, t = el.find(f"{GPX}ele"), el.find(f"{GPX}time")
        return (float(el.get("lat")), float(el.get("lon")), float(e.text) if e is not None else None,
                datetime.fromisoformat(t.text.replace("Z", "+00:00")) if t is not None else None)
    return {"wpts": [(p(w), w.findtext(f"{GPX}name"), w.findtext(f"{GPX}desc")) for w in root.findall(f"{GPX}wpt")],
            "trks": [(t.findtext(f"{GPX}name"), [[p(x) for x in s.findall(f"{GPX}trkpt")]
                                                 for s in t.findall(f"{GPX}trkseg")]) for t in root.findall(f"{GPX}trk")],
            "rtes": [(r.findtext(f"{GPX}name"), [p(x) for x in r.findall(f"{GPX}rtept")]) for r in root.findall(f"{GPX}rte")],
            "name": root.findtext(f"{GPX}metadata/{GPX}name")}


def same_pts(got, want):
    assert len(got) == len(want)
    for g, w in zip(got, want):
        assert g[0] == pytest.approx(w[0], abs=1e-9) and g[1] == pytest.approx(w[1], abs=1e-9)
        if w[2] is None:
            assert g[2] is None
        else:
            assert g[2] == pytest.approx(w[2], abs=1e-9)
        if len(w) > 3:
            assert g[3] == w[3]


def one(paths):
    assert len(paths) == 1 and paths[0].exists() and paths[0].stat().st_size > 0
    return paths[0]


# ---------------------------------------------------------------- registry
def test_registered_and_targets():
    assert util.category("route.gpx") == "geo" and util.category("a.KMZ") == "geo"
    assert util.category("x.geojson") == "geo"
    assert util.category("x.json") != "geo"          # .json belongs to the data family
    fam = formats.family("geo")
    assert fam.label == "Map data"
    for ext in ("gpx", "kml", "kmz", "geojson", "shp"):
        t = conv.targets_for("geo", ext)
        assert ext.upper() not in t and 0 < len(t) <= 9
        assert all(x in fam.hints and len(fam.hints[x]) <= 22 for x in t)
    assert conv.targets_for("geo", "gpx") == ["KML", "KMZ", "GEOJSON", "SHP", "CSV", "PNG"]
    assert len(fam.tools) <= 6 and all(len(t.hint) <= 22 for t in fam.tools)


# ---------------------------------------------------------------- the main round trip
def test_gpx_kml_geojson_gpx_keeps_everything(tmp_path):
    src = make_gpx(tmp_path / "walk.gpx")
    kml = one(conv.convert(src, "geo", "KML"))

    # KML checked with a plain parser: gx:MultiTrack carries both segments and every timestamp
    root = ET.parse(kml).getroot()
    pms = root.findall(f".//{KML}Placemark")
    names = [pm.findtext(f"{KML}name") for pm in pms]
    assert names == ["बिग बेन", "ロンドン・アイ 🎡", "Morning walk 朝"]
    assert root.findtext(f"{KML}Document/{KML}name") == "London 🚶"
    pt = pms[0].findtext(f"{KML}Point/{KML}coordinates").split(",")
    assert (float(pt[1]), float(pt[0]), float(pt[2])) == WPTS[0][:3]       # lon,lat order in KML
    tracks = pms[2].findall(f"{GX}MultiTrack/{GX}Track")
    assert len(tracks) == 2
    for trk, seg in zip(tracks, (SEG1, SEG2)):
        whens = [datetime.fromisoformat(w.text.replace("Z", "+00:00")) for w in trk.findall(f"{KML}when")]
        coords = [tuple(map(float, c.text.split())) for c in trk.findall(f"{GX}coord")]
        same_pts([(c[1], c[0], c[2], w) for c, w in zip(coords, whens)], seg)

    gj = one(conv.convert(kml, "geo", "GEOJSON"))
    data = json.loads(gj.read_text("utf-8"))
    assert data["type"] == "FeatureCollection" and data["name"] == "London 🚶"
    f_line = data["features"][2]
    assert f_line["geometry"]["type"] == "MultiLineString"
    assert f_line["properties"]["name"] == "Morning walk 朝"
    for line, times, seg in zip(f_line["geometry"]["coordinates"], f_line["properties"]["coordTimes"], (SEG1, SEG2)):
        same_pts([(c[1], c[0], c[2], datetime.fromisoformat(t.replace("Z", "+00:00")))
                  for c, t in zip(line, times)], seg)
    w0 = data["features"][0]
    assert w0["geometry"] == {"type": "Point", "coordinates": [WPTS[0][1], WPTS[0][0], WPTS[0][2]]}
    assert w0["properties"]["description"] == "घड़ी" and w0["properties"]["sym"] == "Flag"

    back = one(conv.convert(gj, "geo", "GPX"))
    g = gpx_parse(back)
    assert g["name"] == "London 🚶"
    assert [(w[1], w[2]) for w in g["wpts"]] == [(n, d) for *_, n, d in WPTS]
    same_pts([w[0] for w in g["wpts"]], [(la, lo, e, None) for la, lo, e, *_ in WPTS])
    assert len(g["trks"]) == 1 and g["trks"][0][0] == "Morning walk 朝"
    segs = g["trks"][0][1]
    assert len(segs) == 2
    same_pts(segs[0], SEG1)
    same_pts(segs[1], SEG2)
    assert "<sym>Flag</sym>" in back.read_text("utf-8")
    assert src.read_text("utf-8").startswith("<?xml")     # source untouched


def test_route_survives_geojson_round_trip(tmp_path):
    src = make_gpx(tmp_path / "plan.gpx", with_route=True)
    gj = one(conv.convert(src, "geo", "GEOJSON"))
    feats = json.loads(gj.read_text("utf-8"))["features"]
    rte = [f for f in feats if f["properties"].get("_gpxType") == "rte"]
    assert len(rte) == 1 and "coordTimes" not in rte[0]["properties"]
    g = gpx_parse(one(conv.convert(gj, "geo", "GPX")))
    assert len(g["rtes"]) == 1 and g["rtes"][0][0] == "Plan"
    same_pts(g["rtes"][0][1], [(la, lo, e, None) for la, lo, e, _ in SEG1])
    same_pts(g["trks"][0][1][1], SEG2)


def test_kmz_round_trip(tmp_path):
    src = make_gpx(tmp_path / "walk.gpx")
    kmz = one(conv.convert(src, "geo", "KMZ"))
    with zipfile.ZipFile(kmz) as z:
        assert z.namelist() == ["doc.kml"]
        assert z.testzip() is None
        root = ET.fromstring(z.read("doc.kml"))
    assert len(root.findall(f".//{KML}Placemark")) == 3
    g = gpx_parse(one(conv.convert(kmz, "geo", "GPX")))
    same_pts(g["trks"][0][1][0], SEG1)
    same_pts(g["trks"][0][1][1], SEG2)
    assert [w[1] for w in g["wpts"]] == ["बिग बेन", "ロンドン・アイ 🎡"]


def test_kmz_reads_first_kml_when_no_doc_kml(tmp_path):
    kml = geo.kml_text(geo.read(make_gpx(tmp_path / "a.gpx")))
    kmz = tmp_path / "other.kmz"
    with zipfile.ZipFile(kmz, "w") as z:
        z.writestr("images/icon.png", b"\x89PNG")
        z.writestr("files/tour.kml", kml)
    doc = geo.read(kmz)
    assert len(doc.of("wpt")) == 2 and len(doc.of("trk")[0].segments) == 2


# ---------------------------------------------------------------- KML / GeoJSON inputs
KML_IN = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
<Document><name>Mixed</name>
 <Style id="s"><LineStyle><color>ff0000ff</color></LineStyle></Style>
 <Folder><name>Inner</name>
  <Placemark><name>Café</name><description><![CDATA[<b>Good</b> coffee]]></description>
   <TimeStamp><when>2024-05-01T08:00:00Z</when></TimeStamp>
   <ExtendedData><Data name="rating"><value>5</value></Data></ExtendedData>
   <Point><coordinates>2.2945, 48.8584, 35.5</coordinates></Point></Placemark>
 </Folder>
 <Placemark><name>Line</name><styleUrl>#s</styleUrl>
  <LineString><coordinates>
    2.1,48.1,10 2.2,48.2,20
    2.3,48.3,30
  </coordinates></LineString></Placemark>
 <Placemark><name>Park</name><Polygon>
  <outerBoundaryIs><LinearRing><coordinates>2,48 2.01,48 2.01,48.01 2,48.01 2,48</coordinates></LinearRing></outerBoundaryIs>
  <innerBoundaryIs><LinearRing><coordinates>2.004,48.004 2.006,48.004 2.006,48.006 2.004,48.004</coordinates></LinearRing></innerBoundaryIs>
 </Polygon></Placemark>
 <Placemark><name>Multi</name><MultiGeometry>
   <Point><coordinates>3,49</coordinates></Point>
   <LineString><coordinates>3,49 3.1,49.1</coordinates></LineString>
   <LineString><coordinates>3.2,49.2 3.3,49.3</coordinates></LineString>
 </MultiGeometry></Placemark>
 <Placemark><name>Ride</name><gx:Track>
   <when>2024-05-01T09:00:00Z</when><when>2024-05-01T09:00:10.5Z</when>
   <gx:coord>4.0 50.0 100</gx:coord><gx:coord>4.001 50.001 101.5</gx:coord>
 </gx:Track></Placemark>
</Document></kml>"""


def test_kml_geometries_to_geojson(tmp_path):
    src = tmp_path / "mixed.kml"
    src.write_text(KML_IN, encoding="utf-8")
    data = json.loads(one(conv.convert(src, "geo", "GEOJSON")).read_text("utf-8"))
    by = {}
    for f in data["features"]:
        by.setdefault(f["properties"].get("name"), []).append(f)
    cafe = by["Café"][0]
    assert cafe["geometry"]["coordinates"] == [2.2945, 48.8584, 35.5]
    assert cafe["properties"]["time"] == "2024-05-01T08:00:00Z"
    assert cafe["properties"]["rating"] == "5"
    assert cafe["properties"]["description"] == "<b>Good</b> coffee"
    assert by["Line"][0]["geometry"] == {"type": "LineString",
                                         "coordinates": [[2.1, 48.1, 10], [2.2, 48.2, 20], [2.3, 48.3, 30]]}
    park = by["Park"][0]["geometry"]
    assert park["type"] == "Polygon" and len(park["coordinates"]) == 2
    assert park["coordinates"][1][0] == park["coordinates"][1][-1] == [2.004, 48.004]
    kinds = sorted(f["geometry"]["type"] for f in by["Multi"])
    assert kinds == ["MultiLineString", "Point"]
    ride = by["Ride"][0]
    assert ride["geometry"]["coordinates"] == [[4.0, 50.0, 100.0], [4.001, 50.001, 101.5]]
    assert ride["properties"]["coordTimes"] == ["2024-05-01T09:00:00Z", "2024-05-01T09:00:10.5Z"]
    assert data["name"] == "Mixed"


def test_geojson_to_gpx_and_kml(tmp_path):
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"name": "शिखर", "elevation_src": "dem", "time": "2023-07-04T12:00:00+02:00"},
         "geometry": {"type": "Point", "coordinates": [86.9250227, 27.9881206, 8848.86]}},
        {"type": "Feature", "properties": {"name": "Trail", "coordTimes": [["2023-07-04T10:00:00Z", "2023-07-04T10:01:00Z"],
                                                                         ["2023-07-04T10:05:00Z", "2023-07-04T10:06:00Z"]]},
         "geometry": {"type": "MultiLineString", "coordinates": [[[86.9, 27.9], [86.91, 27.91]],
                                                                 [[86.92, 27.92], [86.93, 27.93]]]}},
        {"type": "Feature", "properties": {"name": "Zone"},
         "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]],
                                                              [[[5, 5], [6, 5], [6, 6], [5, 5]]]]}},
        {"type": "Feature", "properties": None, "geometry": None},
    ]}
    src = tmp_path / "everest.geojson"
    src.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    g = gpx_parse(one(conv.convert(src, "geo", "GPX")))
    (wp, name, _), = g["wpts"]
    assert name == "शिखर" and wp == (27.9881206, 86.9250227, 8848.86, datetime(2023, 7, 4, 10, tzinfo=timezone.utc))
    trail = [t for t in g["trks"] if t[0] == "Trail"][0][1]
    assert trail[1][1] == (27.93, 86.93, None, datetime(2023, 7, 4, 10, 6, tzinfo=timezone.utc))
    zone = [t for t in g["trks"] if t[0] == "Zone"][0][1]
    assert len(zone) == 2 and zone[0][0][:2] == zone[0][-1][:2]          # polygon rings as closed segments

    root = ET.parse(one(conv.convert(src, "geo", "KML"))).getroot()
    zone_pm = [pm for pm in root.iter(f"{KML}Placemark") if pm.findtext(f"{KML}name") == "Zone"][0]
    assert len(zone_pm.findall(f"{KML}MultiGeometry/{KML}Polygon")) == 2
    summit = [pm for pm in root.iter(f"{KML}Placemark") if pm.findtext(f"{KML}name") == "शिखर"][0]
    assert summit.find(f".//{KML}Data[@name='elevation_src']/{KML}value").text == "dem"


def test_geojson_bare_geometry_and_projected_crs(tmp_path):
    src = tmp_path / "bare.geojson"
    src.write_text('{"type":"LineString","coordinates":[[10,20],[11,21]]}')
    assert len(geo.read(src).of("trk")[0].segments[0]) == 2
    bad = tmp_path / "utm.geojson"
    bad.write_text('{"type":"FeatureCollection","crs":{"type":"name","properties":{"name":"EPSG:32633"}},'
                   '"features":[{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[500000,4649776]}}]}')
    with pytest.raises(UserError, match="projected"):
        geo.read(bad)
    bad.write_text('{"type":"Point","coordinates":[500000,4649776]}')
    with pytest.raises(UserError, match="latitude/longitude"):
        geo.read(bad)


# ---------------------------------------------------------------- CSV
def test_csv_rows(tmp_path):
    src = make_gpx(tmp_path / "walk.gpx")
    out = one(conv.convert(src, "geo", "CSV"))
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")        # BOM so Excel reads UTF-8
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig", newline="")))
    assert len(rows) == 2 + 6
    assert rows[0]["type"] == "waypoint" and rows[1]["name"] == "ロンドン・アイ 🎡"
    trk = [r for r in rows if r["type"] == "track"]
    assert [r["segment"] for r in trk] == ["1"] * 3 + ["2"] * 3
    for r, p in zip(trk, SEG1 + SEG2):
        assert (float(r["lat"]), float(r["lon"]), float(r["ele"])) == p[:3]
        assert datetime.fromisoformat(r["time"].replace("Z", "+00:00")) == p[3]


# ---------------------------------------------------------------- Shapefile
def test_shapefile_zip_written_and_read_back(tmp_path):
    shapefile = pytest.importorskip("shapefile")
    src = make_gpx(tmp_path / "walk.gpx")
    out = one(conv.convert(src, "geo", "SHP"))
    assert out.name == "walk shapefile.zip"
    ex = tmp_path / "ex"
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert {"walk_points.shp", "walk_points.shx", "walk_points.dbf", "walk_points.prj",
                "walk_lines.shp", "walk_lines.dbf"} <= names
        z.extractall(ex)
    raw = (ex / "walk_lines.shp").read_bytes()
    assert struct.unpack(">i", raw[:4])[0] == 9994                # shapefile magic
    assert struct.unpack("<i", raw[32:36])[0] == 13               # PolyLineZ
    assert "WGS_1984" in (ex / "walk_lines.prj").read_text()
    r = shapefile.Reader(str(ex / "walk_lines.shp"))
    (shape,) = r.shapes()
    assert list(shape.parts) == [0, 3]
    for (x, y), z, p in zip(shape.points, shape.z, SEG1 + SEG2):
        assert (y, x, z) == p[:3]
    assert r.record(0)["name"] == "Morning walk 朝"
    pr = shapefile.Reader(str(ex / "walk_points.shp"))
    assert [rec["name"] for rec in pr.records()] == ["बिग बेन", "ロンドン・アイ 🎡"]

    # .shp as a source (sidecars beside it) -> GPX
    g = gpx_parse(one(conv.convert(ex / "walk_lines.shp", "geo", "GPX")))
    same_pts(g["trks"][0][1][1], [p[:3] for p in SEG2])


def test_shapefile_polygon_with_hole(tmp_path):
    shapefile = pytest.importorskip("shapefile")
    src = tmp_path / "mixed.kml"
    src.write_text(KML_IN, encoding="utf-8")
    out = one(conv.convert(src, "geo", "SHP"))
    ex = tmp_path / "ex"
    zipfile.ZipFile(out).extractall(ex)
    r = shapefile.Reader(str(ex / "mixed_polygons.shp"))
    shp = r.shapes()[0]
    rings = [shp.points[a:b] for a, b in zip(shp.parts, list(shp.parts[1:]) + [len(shp.points)])]
    assert len(rings) == 2
    assert geo._signed_area(rings[0]) < 0 < geo._signed_area(rings[1])   # outer CW, hole CCW
    doc = geo.read(ex / "mixed_polygons.shp")
    (poly,) = doc.of("poly")
    assert poly.name == "Park" and len(poly.polygons) == 1 and len(poly.polygons[0]) == 2


def test_projected_shapefile_rejected(tmp_path):
    shapefile = pytest.importorskip("shapefile")
    w = shapefile.Writer(str(tmp_path / "utm"), shapeType=shapefile.POINT)
    w.field("name", "C", 10)
    w.point(500000, 4649776)
    w.record("x")
    w.close()
    (tmp_path / "utm.prj").write_text('PROJCS["WGS_1984_UTM_Zone_33N",GEOGCS["GCS_WGS_1984"]]')
    with pytest.raises(UserError, match="projected"):
        geo.read(tmp_path / "utm.shp")
    (tmp_path / "utm.dbf").unlink()
    (tmp_path / "utm.prj").unlink()
    with pytest.raises(UserError, match="shapefile"):
        geo.read(tmp_path / "utm.shp")


# ---------------------------------------------------------------- PNG preview
def test_png_preview(tmp_path):
    from PIL import Image
    src = make_gpx(tmp_path / "walk.gpx")
    out = one(conv.convert(src, "geo", "PNG"))
    with Image.open(out) as im:
        im.verify()
    im = Image.open(out).convert("RGB")
    assert im.width == 1600 and 700 < im.height < 2200
    raw = im.tobytes()
    px = [raw[i:i + 3] for i in range(0, len(raw), 3)]
    track = sum(1 for p in px if abs(p[0] - 217) < 25 and abs(p[1] - 72) < 25 and abs(p[2] - 15) < 25)
    wpt = sum(1 for p in px if abs(p[0] - 201) < 20 and abs(p[1] - 42) < 20 and abs(p[2] - 42) < 20)
    assert track > 2000 and wpt > 40
    # a single point still renders with a sensible frame
    one_pt = tmp_path / "pin.geojson"
    one_pt.write_text('{"type":"Point","coordinates":[139.6917,35.6895]}')
    with Image.open(one(conv.convert(one_pt, "geo", "PNG"))) as im2:
        assert im2.width == 1600


# ---------------------------------------------------------------- tools
def test_distance_one_degree_of_latitude(tmp_path):
    a, b = geo.Pt(10.0, 20.0), geo.Pt(11.0, 20.0)
    assert geo.haversine(a, b) == pytest.approx(111195, abs=5)
    assert geo.haversine(geo.Pt(0, 0), geo.Pt(0, 1)) == pytest.approx(111195, abs=5)
    src = tmp_path / "deg.gpx"
    src.write_text('<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"><trk><trkseg>'
                   '<trkpt lat="10" lon="20"/><trkpt lat="11" lon="20"/></trkseg></trk></gpx>')
    txt = one(formats.family("geo").tools[0].run([src])).read_text("utf-8")
    assert "111.20 km" in txt          # 111.195 km


def test_stats_known_values(tmp_path):
    k = 0.01                                   # 0.01° of latitude = 1111.95 m
    pts = [(45.0, 7.0, 100.0, 0), (45.0 + k, 7.0, 150.0, 600), (45.0 + 2 * k, 7.0, 120.0, 1200),
           (45.0 + 2 * k, 7.0, 120.5, 1800)]                    # last 10 min: standing still
    body = "".join(f'<trkpt lat="{la}" lon="{lo}"><ele>{e}</ele><time>{iso(T0 + timedelta(seconds=s))}</time></trkpt>'
                   for la, lo, e, s in pts)
    src = tmp_path / "hike.gpx"
    src.write_text(f'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"><trk><name>Hike</name>'
                   f"<trkseg>{body}</trkseg></trk></gpx>")
    st = geo.stats(geo.read(src))
    assert st["distance_m"] == pytest.approx(2223.9, abs=0.5)
    assert st["gain_m"] == 50 and st["loss_m"] == 30
    assert st["duration_s"] == 1800 and st["moving_s"] == 1200
    assert st["bbox"] == (45.0, 7.0, 45.02, 7.0)
    out = one(geo.tool_stats([src]))
    assert out.name == "hike stats.txt"
    txt = out.read_text("utf-8")
    for s in ("2.22 km", "+50 m", "-30 m", "0:30:00", "Moving time:      0:20:00", "4.4 km/h", "6.7 km/h",
              "Hike"):
        assert s in txt, s


def test_reverse(tmp_path):
    src = make_gpx(tmp_path / "walk.gpx")
    out = one(geo.tool_reverse([src]))
    assert out.name == "walk reversed.gpx"
    g = gpx_parse(out)
    segs = g["trks"][0][1]
    same_pts(segs[0], [(la, lo, e, None) for la, lo, e, _ in reversed(SEG2)])
    same_pts(segs[1], [(la, lo, e, None) for la, lo, e, _ in reversed(SEG1)])
    assert len(g["wpts"]) == 2
    kml = tmp_path / "mixed.kml"
    kml.write_text(KML_IN, encoding="utf-8")
    assert one(geo.tool_reverse([kml])).suffix == ".kml"


def test_simplify(tmp_path):
    # 1001 points along two straight legs with ≤ 1 m zig-zag noise: RDP keeps ~3 points
    pts = []
    for i in range(501):
        pts.append((46.0 + i * 1e-5, 8.0 + (1e-5 if i % 2 else 0) * 0.5))
    for i in range(1, 501):
        pts.append((46.005, 8.0 + i * 1e-5))
    body = "".join(f'<trkpt lat="{la!r}" lon="{lo!r}"/>' for la, lo in pts)
    src = tmp_path / "zig.gpx"
    src.write_text(f'<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"><trk><trkseg>{body}</trkseg></trk></gpx>')
    out = one(geo.tool_simplify([src]))
    g = gpx_parse(out)
    kept = g["trks"][0][1][0]
    assert 3 <= len(kept) <= 6
    assert out.name == f"zig simplified 1001→{len(kept)} pts.gpx"
    assert kept[0][:2] == pts[0] and kept[-1][:2] == pts[-1]
    # every original point lies within 5 m of the simplified line
    proj = [geo.Pt(la, lo) for la, lo, *_ in kept]
    for la, lo in pts[::7]:
        seg_d = min(_dist_to_seg((la, lo), (a.lat, a.lon), (b.lat, b.lon)) for a, b in zip(proj, proj[1:]))
        assert seg_d <= 5.0 + 1e-6


def _dist_to_seg(p, a, b):
    k = math.pi / 180 * geo.EARTH_R
    c = math.cos(math.radians(p[0]))
    px, py, ax, ay, bx, by = p[1] * k * c, p[0] * k, a[1] * k * c, a[0] * k, b[1] * k * c, b[0] * k
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


# ---------------------------------------------------------------- hostile / broken input
BOMB = """<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>
<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="1" lon="2"><name>&lol3;</name></wpt></gpx>"""
XXE = """<?xml version="1.0"?><!DOCTYPE kml [<!ENTITY x SYSTEM "file:///etc/passwd">]>
<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>&x;</name><Point><coordinates>1,2</coordinates></Point></Placemark></kml>"""


def test_malicious_xml_rejected(tmp_path):
    bomb = tmp_path / "bomb.gpx"
    bomb.write_text(BOMB)
    with pytest.raises(UserError, match="safety"):
        conv.convert(bomb, "geo", "KML")
    xxe = tmp_path / "xxe.kml"
    xxe.write_text(XXE)
    with pytest.raises(UserError, match="safety"):
        conv.convert(xxe, "geo", "GPX")
    kmz = tmp_path / "bomb.kmz"
    with zipfile.ZipFile(kmz, "w") as z:
        z.writestr("doc.kml", BOMB.replace("gpx", "kml"))
    with pytest.raises(UserError, match="safety"):
        conv.convert(kmz, "geo", "GPX")
    assert not list(tmp_path.glob("*.kml")) or [p.name for p in tmp_path.glob("*.kml")] == ["xxe.kml"]


def test_kmz_zip_bomb_rejected(tmp_path):
    kmz = tmp_path / "huge.kmz"
    with zipfile.ZipFile(kmz, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", b"<kml>" + b" " * (40 * 1024 * 1024) + b"</kml>")
    assert kmz.stat().st_size < 1024 * 1024
    with pytest.raises(UserError, match="too large"):
        geo.read(kmz)


@pytest.mark.parametrize("name,content,msg", [
    ("cut.gpx", '<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="1" lon="2">', "valid XML"),
    ("wrong.gpx", "<html><body>hi</body></html>", "GPX"),
    ("empty.gpx", '<gpx xmlns="http://www.topografix.com/GPX/1/1"></gpx>', "No points"),
    ("nan.gpx", '<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="abc" lon="2"/></gpx>', "number"),
    ("far.gpx", '<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="95" lon="2"/></gpx>', "latitude"),
    ("bad.geojson", '{"type": "FeatureCollection", "features": [', "valid GeoJSON"),
    ("odd.geojson", '{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":"x"}}', "malformed"),
    ("bad.kmz", "not a zip", "damaged"),
    ("bad.kml", '<kml xmlns="http://www.opengis.net/kml/2.2"><Document/></kml>', "No points"),
])
def test_bad_input_friendly_errors(tmp_path, name, content, msg):
    p = tmp_path / name
    p.write_text(content)
    with pytest.raises(UserError, match=msg):
        conv.convert(p, "geo", "GEOJSON" if not name.endswith("geojson") else "GPX")


def test_never_overwrites(tmp_path):
    src = make_gpx(tmp_path / "walk.gpx")
    a = one(conv.convert(src, "geo", "KML"))
    b = one(conv.convert(src, "geo", "KML"))
    assert a.name == "walk.kml" and b.name == "walk (1).kml"
    kml = tmp_path / "walk.kml"
    gpx = one(conv.convert(kml, "geo", "GPX"))
    assert gpx.name == "walk (1).gpx" and src.read_text("utf-8").count("<trkpt") == 6


def test_cli_convert(tmp_path):
    src = make_gpx(tmp_path / "walk.gpx")
    r = subprocess.run([sys.executable, "-m", "dropdial", "convert", str(src), "--to", "GEOJSON"],
                       capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1],
                       env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"}, timeout=120)
    assert r.returncode == 0, r.stderr
    out = tmp_path / "walk.geojson"
    assert json.loads(out.read_text("utf-8"))["features"][2]["geometry"]["type"] == "MultiLineString"
