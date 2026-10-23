"""Structured data files: JSON, JSON Lines, YAML, TOML, XML, Apple property lists and vCards.

Conventions (documented here because they decide what the output looks like):

* Everything is loaded into plain Python data first (dicts, lists, scalars), then written out.
  YAML is read with `safe_load` only, XML through defusedxml (no entities, no external
  references), property lists through `plistlib` (which rejects entity declarations).
* XML <-> data: attributes become "@name" keys, an element's own text next to attributes or
  children becomes "#text", repeated child elements become a list, namespace declarations
  become "@xmlns" / "@xmlns:p" keys and prefixed names stay "p:tag". Leaf text that is a
  canonical number or true/false is read back as that value and an empty element as null, so
  JSON -> XML -> JSON gives back the same data. Data that isn't a single-key object is wrapped
  in <root>, and a top-level list is written as <items><item/>…</items>; both wrappers are
  removed again when read (so a document whose root is <root> loses that name). Known limits: a one-item list comes back as a single value, an empty list or
  object disappears, and keys that aren't valid XML names are made valid ("first name" ->
  "first_name").
* TOML has no null and no top-level list: a top-level list is written as {"items": [...]}, and a
  null value stops the conversion with a message saying where it is. Property lists also have no
  null and stop the same way.
* Dates and times (YAML, TOML, plist) become ISO-8601 strings where the target has no date type
  (JSON, CSV, XLSX, XML); binary data (plist <data>, YAML !!binary) becomes base64 text.
* CSV / XLSX need a table: a list of objects (or an object holding exactly one such list, not
  counting XML "@" attributes, or an object whose values are all objects, which gets a "key"
  column). Nested objects are flattened
  to "a.b" columns; lists inside a record are written as compact JSON in one cell.
"""
from __future__ import annotations

import base64
import csv
import datetime as dt
import io
import json
import math
import re
from pathlib import Path

from . import Family, Tool, register
from ..util import UserError, sibling

MAX_BYTES = 64 * 1024 * 1024      # bigger structured files are almost certainly not meant for this
MAX_NODES = 5_000_000             # stops YAML alias "billion laughs" expanding into huge output
MAX_DEPTH = 400
MAX_COLUMNS = 1000
MAX_PDF_LINES = 100_000
PDF_COLUMNS = 84                  # monospace characters per line on a Letter page

EXT_FORMAT = {".json": "JSON", ".jsonl": "JSONL", ".ndjson": "JSONL", ".yaml": "YAML",
              ".yml": "YAML", ".toml": "TOML", ".xml": "XML", ".plist": "PLIST", ".vcf": "VCF"}

_TARGETS = {
    "JSON": ["YAML", "TOML", "XML", "JSONL", "PLIST", "CSV", "XLSX", "PDF"],
    "JSONL": ["JSON", "YAML", "TOML", "XML", "PLIST", "CSV", "XLSX", "PDF"],
    "YAML": ["JSON", "TOML", "XML", "JSONL", "PLIST", "CSV", "XLSX", "PDF"],
    "TOML": ["JSON", "YAML", "XML", "PLIST", "CSV", "XLSX", "PDF"],
    "XML": ["JSON", "YAML", "TOML", "PLIST", "CSV", "XLSX", "PDF"],
    # for a property list, XML / BINARY mean the two plist encodings
    "PLIST": ["JSON", "YAML", "TOML", "XML", "BINARY", "CSV", "XLSX", "PDF"],
    "VCF": ["CSV", "XLSX", "JSON", "TXT"],
}

HINTS = {
    "JSON": "For apps and APIs", "YAML": "Readable config", "TOML": "Config file",
    "XML": "Tagged XML markup", "JSONL": "One record per line", "PLIST": "Apple property list",
    "BINARY": "Binary property list", "CSV": "Plain table", "XLSX": "Opens in Excel",
    "PDF": "Printable listing", "TXT": "Readable contact list",
    "Pretty": "Re-indent neatly", "Minify": "Strip whitespace",
}


def _has(mod: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(mod) is not None


def _available() -> bool:
    return _has("yaml") and _has("defusedxml")


def targets(ext: str) -> list[str]:
    fmt = EXT_FORMAT.get("." + ext.lower().lstrip("."))
    out = list(_TARGETS.get(fmt, []))
    if not _has("tomli_w"):
        out = [t for t in out if t != "TOML"]
    if not _has("openpyxl"):
        out = [t for t in out if t != "XLSX"]
    return out


# ---------------------------------------------------------------- reading
def _read_bytes(src: Path) -> bytes:
    try:
        size = src.stat().st_size
        if size > MAX_BYTES:
            raise UserError(f"{src.name} is too big to convert (over {MAX_BYTES // 2**20} MB).")
        raw = src.read_bytes()
    except OSError as e:
        raise UserError(f"Can't read {src.name}: {e.strerror or e}.") from None
    if not raw.strip():
        raise UserError(f"{src.name} is empty.")
    return raw


def _decode(raw: bytes) -> str:
    for bom, enc in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe\x00\x00", "utf-32"),
                     (b"\x00\x00\xfe\xff", "utf-32"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if raw.startswith(bom):
            return raw.decode(enc, "replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")


def _load_json(text: str, name: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise UserError(f"{name} isn't valid JSON (line {e.lineno}, column {e.colno}: {e.msg}).") from None
    except ValueError as e:   # e.g. integers longer than Python's 4300-digit safety limit
        raise UserError(f"{name} has a value that can't be read: {e}.") from None


def _load_jsonl(text: str, name: str) -> list:
    out = []
    for no, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise UserError(f"{name}: line {no} isn't valid JSON ({e.msg}).") from None
        except ValueError as e:
            raise UserError(f"{name}: line {no} has a value that can't be read ({e}).") from None
    return out


def _load_yaml(text: str, name: str):
    import yaml
    try:
        docs = list(yaml.safe_load_all(text))   # safe loader only: never constructs objects
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark is not None else ""
        raise UserError(f"{name} isn't valid YAML{where}.") from None
    docs = [d for d in docs if d is not None] or [None]
    if len(docs) == 1 and docs[0] is None:
        raise UserError(f"{name} has no data in it.")
    return docs[0] if len(docs) == 1 else docs   # several documents -> a list of them


def _load_toml(text: str, name: str):
    import tomllib
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise UserError(f"{name} isn't valid TOML ({e}).") from None


def _load_plist(raw: bytes, name: str):
    import plistlib
    try:
        return plistlib.loads(raw)
    except Exception:   # InvalidFileException, ExpatError, ValueError, OverflowError…
        raise UserError(f"{name} isn't a valid property list.") from None


def _xml_tree(raw: bytes, name: str):
    """Parse with defusedxml: DOCTYPEs are fine, entity declarations and external references are
    refused (no billion-laughs, no file or network access)."""
    from defusedxml import DefusedXmlException
    from defusedxml.ElementTree import ParseError, iterparse
    try:
        yield from iterparse(io.BytesIO(raw), events=("start-ns", "start", "end"))
    except DefusedXmlException:
        raise UserError(f"{name} uses XML entities, which aren't allowed for safety.") from None
    except ParseError as e:
        raise UserError(f"{name} isn't valid XML ({e}).") from None


_INT_RE = re.compile(r"-?(?:0|[1-9][0-9]{0,14})")   # up to 15 digits: exact in every app
_FLOAT_RE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+(?:[eE][-+]?[0-9]+)?|[eE][-+]?[0-9]+)")


def _infer(text: str):
    """XML text -> value. Only canonical forms are converted, so '007', '1.50' or ' 5' stay text."""
    if text == "true":
        return True
    if text == "false":
        return False
    if _INT_RE.fullmatch(text):
        return int(text)
    if _FLOAT_RE.fullmatch(text):
        f = float(text)
        if math.isfinite(f) and repr(f) == text:
            return f
    return text


def _load_xml(raw: bytes, name: str):
    prefix_of: dict[str, str] = {}     # namespace URI -> prefix as written in the file
    pending: list[tuple[str, str]] = []
    decls: dict[int, list[tuple[str, str]]] = {}
    results: dict[int, tuple[str, object]] = {}
    root = None

    def qname(tag: str) -> str:
        if tag.startswith("{"):
            uri, local = tag[1:].split("}", 1)
            p = prefix_of.get(uri, "")
            return f"{p}:{local}" if p else local
        return tag

    for event, item in _xml_tree(raw, name):
        if event == "start-ns":
            prefix, uri = item
            prefix_of[uri] = prefix
            pending.append((prefix, uri))
        elif event == "start":
            if root is None:
                root = item
            if pending:
                decls[id(item)] = pending
                pending = []
        else:   # end: children are finished, and their tails (mixed text) are known now
            el = item
            attrs = {}
            for p, uri in decls.pop(id(el), []):
                attrs["@xmlns:" + p if p else "@xmlns"] = uri
            for k, v in el.attrib.items():
                attrs["@" + qname(k)] = _infer(v)
            children = [results.pop(id(c)) for c in el]
            if children:
                parts = [el.text or ""] + [c.tail or "" for c in el]
                text = " ".join(p.strip() for p in parts if p.strip())
            else:
                text = el.text or ""
                if not text.strip():
                    text = ""
            del el[:]   # keep memory flat on big files
            if not attrs and not children:
                value = _infer(text) if text else None
            else:
                value = dict(attrs)
                if text:
                    value["#text"] = _infer(text)
                for k, v in children:      # element values are never lists themselves
                    if k not in value:
                        value[k] = v
                    elif isinstance(value[k], list):
                        value[k].append(v)
                    else:
                        value[k] = [value[k], v]
            results[id(el)] = (qname(el.tag), value)
    if root is None:
        raise UserError(f"{name} has no XML elements in it.")
    tag, value = results[id(root)]
    # our own wrappers (see module docstring)
    if tag == "root":
        return value
    if tag == "items" and (value is None or isinstance(value, dict) and set(value) == {"item"}):
        items = [] if value is None else value["item"]
        return items if isinstance(items, list) else [items]
    return {tag: value}


def load(src: Path):
    """Read any supported data file into plain Python data."""
    fmt = EXT_FORMAT.get(src.suffix.lower())
    raw = _read_bytes(src)
    if fmt == "PLIST":
        data = _load_plist(raw, src.name)
    elif fmt == "XML":
        data = _load_xml(raw, src.name)
    elif fmt == "VCF":
        data = parse_vcards(_decode(raw), src.name)
    else:
        text = _decode(raw)
        data = {"JSON": _load_json, "JSONL": _load_jsonl, "YAML": _load_yaml,
                "TOML": _load_toml}[fmt](text, src.name)
    return _normalise(data, src.name)


def _normalise(data, name: str):
    """Copy `data` with string keys, refusing self-references and runaway sizes. YAML aliases
    are shared objects, so a tiny file can stand for an enormous tree; counting every visit
    catches that before anything is written."""
    count = 0
    active: set[int] = set()

    def key(k) -> str:
        if isinstance(k, str):
            return k
        if isinstance(k, bool):
            return "true" if k else "false"
        if k is None:
            return "null"
        if isinstance(k, (dt.date, dt.time)):
            return k.isoformat()
        return str(k)

    def walk(v, depth):
        nonlocal count
        count += 1
        if count > MAX_NODES:
            raise UserError(f"{name} expands to too much data to convert.")
        if depth > MAX_DEPTH:
            raise UserError(f"{name} is nested too deeply to convert.")
        if isinstance(v, (dict, list, tuple)):
            if id(v) in active:
                raise UserError(f"{name} refers to itself, so it can't be written out.")
            active.add(id(v))
            try:
                if isinstance(v, dict):
                    return {key(k): walk(x, depth + 1) for k, x in v.items()}
                return [walk(x, depth + 1) for x in v]
            finally:
                active.discard(id(v))
        if type(v).__name__ == "UID":       # plistlib.UID in keyed archives, shown like plutil
            return {"CF$UID": v.data}
        if isinstance(v, (bytearray, memoryview)):
            return bytes(v)
        return v

    try:
        return walk(data, 0)
    except RecursionError:
        raise UserError(f"{name} is nested too deeply to convert.") from None


# ---------------------------------------------------------------- scalar helpers
def _where(path: str) -> str:
    return path or "the top level"


def _iso(v) -> str:
    return v.isoformat()


def _b64(v: bytes) -> str:
    return base64.b64encode(v).decode("ascii")


def _map(data, fn, path=""):
    """New structure with fn(value, path) applied to every scalar."""
    if isinstance(data, dict):
        return {k: _map(v, fn, f"{path}.{k}" if path else k) for k, v in data.items()}
    if isinstance(data, list):
        return [_map(v, fn, f"{path}[{i}]") for i, v in enumerate(data)]
    return fn(data, path)


def _jsonable(v, path):
    if isinstance(v, (dt.date, dt.time)):
        return _iso(v)
    if isinstance(v, bytes):
        return _b64(v)
    if isinstance(v, float) and not math.isfinite(v):
        raise UserError(f"JSON can't store {v} (at {_where(path)}).")
    return v


def _text(v) -> str | None:
    """Scalar -> text for XML, CSV and the like."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (dt.date, dt.time)):
        return _iso(v)
    if isinstance(v, bytes):
        return _b64(v)
    return str(v)


# ---------------------------------------------------------------- writers (data -> bytes/text)
def _dump_json(data, indent: int | None = 2) -> str:
    data = _map(data, _jsonable)
    if indent is None:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(data, ensure_ascii=False, indent=indent) + "\n"


def _list_of(data, what: str) -> list:
    """The list inside `data`, unwrapping objects that hold just one key ({"items": [...]})."""
    while isinstance(data, dict) and len(data) == 1:
        data = next(iter(data.values()))
    if not isinstance(data, list):
        raise UserError(f"{what} needs a list of records, and this file holds a single object.")
    return data


def _dump_jsonl(data) -> str:
    rows = _list_of(_map(data, _jsonable), "JSON Lines")
    return "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in rows)


def _dump_yaml(data) -> str:
    import yaml

    def fix(v, path):
        if isinstance(v, dt.time):          # TOML local times; YAML has no time type
            return _iso(v)
        return v
    return yaml.safe_dump(_map(data, fix), allow_unicode=True, sort_keys=False,
                          default_flow_style=False, width=120)


def _no_null(fmt):
    def fn(v, path):
        if v is None:
            raise UserError(f"{fmt} can't store empty (null) values, and there's one at {_where(path)}.")
        return v
    return fn


def _dump_toml(data) -> str:
    import tomli_w
    if not isinstance(data, dict):
        data = {"items": data}            # TOML documents must be tables

    def fix(v, path):
        _no_null("TOML")(v, path)
        if isinstance(v, bytes):
            return _b64(v)
        if isinstance(v, int) and not isinstance(v, bool) and not -2**63 <= v < 2**63:
            raise UserError(f"TOML numbers must fit in 64 bits; {_where(path)} is too large.")
        return v
    return tomli_w.dumps(_map(data, fix))


def _dump_plist(data, binary: bool) -> bytes:
    import plistlib

    def fix(v, path):
        _no_null("A property list")(v, path)
        if isinstance(v, int) and not isinstance(v, bool) and not -2**63 <= v < 2**64:
            raise UserError(f"Property list numbers must fit in 64 bits; {_where(path)} is too large.")
        if isinstance(v, dt.datetime):
            if v.tzinfo is not None:
                v = v.astimezone(dt.timezone.utc).replace(tzinfo=None)
            return v
        if isinstance(v, (dt.date, dt.time)):
            return _iso(v)
        return v
    fmt = plistlib.FMT_BINARY if binary else plistlib.FMT_XML
    return plistlib.dumps(_map(data, fix), fmt=fmt, sort_keys=False)


_BAD_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")
_NAME_START = re.compile(r"[^\W\d]|_", re.UNICODE)


def _xml_name(key: str) -> str:
    """A valid XML element/attribute name for `key` ("first name" -> "first_name")."""
    parts = key.split(":")
    if len(parts) > 2:
        parts = ["_".join(parts)]
    fixed = []
    for p in parts:
        p = re.sub(r"[^\w.\-]", "_", p)
        if not p or not _NAME_START.match(p[0]):
            p = "_" + p
        fixed.append(p)
    return ":".join(fixed)


def _xml_text(v, path) -> str | None:
    t = _text(v)
    if t is not None and _BAD_XML_CHARS.search(t):
        raise UserError(f"{_where(path)} contains control characters that XML can't store.")
    return t


def _dump_xml(data) -> str:
    import xml.etree.ElementTree as ET

    def build(tag: str, value, path: str) -> list:
        if isinstance(value, list):
            out = []
            for i, item in enumerate(value):
                p = f"{path}[{i}]"
                if isinstance(item, list):      # list in a list: an element of <item>s
                    el = ET.Element(tag)
                    el.extend(build("item", item, p))
                    out.append(el)
                else:
                    out.extend(build(tag, item, p))
            return out
        el = ET.Element(tag)
        if isinstance(value, dict):
            for k, v in value.items():
                p = f"{path}.{k}" if path else k
                if k.startswith("@") and len(k) > 1 and not isinstance(v, (dict, list)):
                    t = _xml_text(v, p)
                    el.set(_xml_name(k[1:]), "" if t is None else t)
                elif k == "#text" and not isinstance(v, (dict, list)):
                    el.text = _xml_text(v, p)
                else:
                    el.extend(build(_xml_name(k), v, p))
        else:
            el.text = _xml_text(value, path)
        return [el]

    first = next(iter(data)) if isinstance(data, dict) and len(data) == 1 else None
    if (first is not None and not isinstance(data[first], list) and _xml_name(first) == first
            and first not in ("root", "items")):
        root = build(first, data[first], first)[0]       # {"catalog": {...}} -> <catalog>
    elif isinstance(data, list):
        root = ET.Element("items")
        root.extend(build("item", data, ""))
    else:
        root = build("root", data, "")[0]
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


# ---------------------------------------------------------------- tables (CSV / XLSX)
def _records(data) -> list:
    """Data -> list of records for a table (see module docstring)."""
    while isinstance(data, dict):
        # step into a lone object/list; XML attributes and namespaces ("@…") don't count
        inner = [v for k, v in data.items() if not k.startswith("@")]
        if len(inner) != 1 or not isinstance(inner[0], (dict, list)):
            break
        data = inner[0]
    if isinstance(data, dict) and len(data) > 1 and all(isinstance(v, dict) for v in data.values()):
        key = "key"
        while any(key in v for v in data.values()):
            key = "_" + key
        return [{key: k, **v} for k, v in data.items()]
    if not isinstance(data, list):
        raise UserError("A table needs a list of records (like [{...}, {...}]); "
                        "this file holds a single object.")
    return data


def _flatten(rec, prefix="", out=None) -> dict:
    out = {} if out is None else out
    if isinstance(rec, dict) and rec:
        for k, v in rec.items():
            _flatten(v, f"{prefix}.{k}" if prefix else k, out)
    else:
        out[prefix or "value"] = rec
    return out


def _table(data) -> tuple[list[str], list[list]]:
    rows = [_flatten(r) for r in _records(data)]
    if not rows:
        raise UserError("There are no records to put in a table.")
    cols: dict[str, None] = {}
    for r in rows:
        cols.update(dict.fromkeys(r))
        if len(cols) > MAX_COLUMNS:
            raise UserError(f"This data would need more than {MAX_COLUMNS} columns; "
                            "it's too deeply nested for a table.")
    header = list(cols)
    return header, [[r.get(c) for c in header] for r in rows]


def _cell_json(v):
    """Non-scalar cells (lists, empty objects) as compact JSON."""
    return json.dumps(_map(v, _jsonable), ensure_ascii=False, separators=(",", ":"))


def _csv_value(v) -> str:
    if isinstance(v, (list, dict)):
        return _cell_json(v)
    t = _text(v)
    return "" if t is None else t


def _write_csv(header, rows, out: Path) -> None:
    from ..convert import atomic_save

    def write(dst):
        # utf-8 with BOM so Excel shows accents and non-Latin scripts correctly
        with open(dst, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                w.writerow([_csv_value(v) for v in r])
    atomic_save(write, out)


def _write_xlsx(header, rows, out: Path, sheet: str = "Data") -> None:
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter
    from ..convert import atomic_save

    if len(rows) + 1 > 1_048_576:
        raise UserError("That's more rows than Excel allows (1,048,576).")
    if len(header) > 16_384:
        raise UserError("That's more columns than Excel allows.")
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(sheet)
    ws.freeze_panes = "A2"
    for i, h in enumerate(header, 1):
        width = max([len(str(h))] + [len(_csv_value(r[i - 1])) for r in rows[:200]])
        ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 8), 60)

    def cell(v, bold=False):
        if isinstance(v, (list, dict)):
            v = _cell_json(v)
        elif isinstance(v, bool) or v is None or isinstance(v, float):
            pass
        elif isinstance(v, int):
            if abs(v) >= 10**15:      # Excel keeps 15 significant digits: keep big ones exact as text
                v = str(v)
        elif not isinstance(v, str):
            v = _text(v)
        if isinstance(v, float) and not math.isfinite(v):
            v = repr(v)
        if isinstance(v, str):
            v = ILLEGAL_CHARACTERS_RE.sub("", v)
            if len(v) > 32767:
                raise UserError("A value is longer than an Excel cell can hold (32,767 characters).")
        c = WriteOnlyCell(ws, value=v)
        if isinstance(v, str):
            c.data_type = "s"          # never a formula, even if the text starts with "="
        if bold:
            c.font = Font(bold=True)
        return c

    ws.append([cell(h, True) for h in header])
    for r in rows:
        ws.append([cell(v) for v in r])
    atomic_save(lambda dst: wb.save(dst), out)


# ---------------------------------------------------------------- PDF listing
def _display_width(ch: str) -> int:
    import unicodedata
    if unicodedata.combining(ch) or ch in "​‌‍️":
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _wrap(line: str, width: int = PDF_COLUMNS) -> list[str]:
    """Hard-wrap by display width (CJK and emoji count double); continuation lines get '↪ '."""
    out, cur, w = [], "", 0
    for ch in line.expandtabs(4):
        cw = _display_width(ch)
        if w + cw > width and cur:
            out.append(cur)
            cur, w = "  ", 2
        cur += ch
        w += cw
    out.append(cur)
    return out


def _listing_text(src: Path, fmt: str) -> str:
    if fmt in ("YAML", "TOML"):
        load(src)                                # validate; keep the author's layout and comments
        return _decode(_read_bytes(src))
    if fmt == "XML":
        return _pretty_xml(_read_bytes(src), src.name).decode("utf-8")
    if fmt == "PLIST":
        return _dump_plist(load(src), binary=False).decode("utf-8")
    return _dump_json(load(src))


def _write_pdf(src: Path, fmt: str, out: Path) -> None:
    import html
    from ..convert import atomic_save, fitz, html_to_pdf
    lines = []
    for line in _listing_text(src, fmt).splitlines():
        lines.extend(_wrap(line))
        if len(lines) > MAX_PDF_LINES:
            raise UserError(f"{src.name} is too long for a PDF listing (over {MAX_PDF_LINES:,} lines).")
    body = (f"<h3>{html.escape(src.name)}</h3>"
            f"<pre>{html.escape(chr(10).join(lines))}</pre>")

    def write(dst):
        html_to_pdf(body, dst)
        try:   # embed only the glyphs used: CJK and emoji fallback fonts are megabytes each
            doc = fitz.open(dst)
            doc.subset_fonts()
            data = doc.tobytes(garbage=4, deflate=True)
            doc.close()
            Path(dst).write_bytes(data)
        except Exception:
            pass
    atomic_save(write, out)


# ---------------------------------------------------------------- vCard
_VCARD_FIELDS = ("name", "given_name", "family_name", "organisation", "title", "emails",
                 "phones", "addresses", "birthday", "urls", "note")
CSV_COLUMNS = ["Name", "Given name", "Family name", "Organisation", "Title", "Email", "Phone",
               "Address", "Birthday", "Website", "Note"]


def _split_unescaped(s: str, sep: str) -> list[str]:
    parts, cur, i = [], [], 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            cur.append(s[i:i + 2])
            i += 2
            continue
        if ch == sep:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def _unescape(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: "\n" if m.group(1) in "nN" else m.group(1), s)


def _split_quoted(s: str, sep: str) -> list[str]:
    parts, cur, q = [], [], False
    for ch in s:
        if ch == '"':
            q = not q
        if ch == sep and not q:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _vcard_lines(text: str) -> list[str]:
    """Unfold continuation lines (RFC 6350) and vCard 2.1 quoted-printable soft breaks."""
    out: list[str] = []
    # "\r\r\n" comes from files saved through a Windows text-mode writer: one line break, not two
    for line in text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        elif out and out[-1].endswith("=") and "QUOTED-PRINTABLE" in out[-1].split(":", 1)[0].upper():
            out[-1] = out[-1][:-1] + line
        else:
            out.append(line)
    return out


def _parse_prop(line: str):
    # name;params:value — a ':' inside a quoted parameter value doesn't end the name part
    q = False
    for i, ch in enumerate(line):
        if ch == '"':
            q = not q
        elif ch == ":" and not q:
            head, value = line[:i], line[i + 1:]
            break
    else:
        return None
    bits = _split_quoted(head, ";")
    name = bits[0].rsplit(".", 1)[-1].upper()        # drop Apple-style "item1." groups
    params: dict[str, list[str]] = {}
    for b in bits[1:]:
        if "=" in b:
            k, v = b.split("=", 1)
            params.setdefault(k.strip().upper(), []).extend(
                x.strip().strip('"') for x in _split_quoted(v, ","))
        elif b.strip():
            params.setdefault("TYPE", []).append(b.strip())   # vCard 2.1 bare types: ;WORK;VOICE
    enc = [e.upper() for e in params.get("ENCODING", [])]
    if "QUOTED-PRINTABLE" in enc:
        import quopri
        charset = (params.get("CHARSET") or ["utf-8"])[0]
        try:
            value = quopri.decodestring(value.encode("latin-1", "replace")).decode(charset, "replace")
        except LookupError:
            value = quopri.decodestring(value.encode("latin-1", "replace")).decode("utf-8", "replace")
    elif "B" in enc or "BASE64" in enc:
        value = None                                   # photos, sounds, keys: not text
    types = []
    for t in params.get("TYPE", []):
        for x in t.split(","):
            x = x.strip().lower()
            if x and x not in ("internet", "pref", "x400") and x not in types:
                types.append(x)
    return name, types, value


def parse_vcards(text: str, name: str = "file") -> list[dict]:
    contacts, cur = [], None
    for line in _vcard_lines(text):
        if not line.strip():
            continue
        up = line.strip().upper()
        if up == "BEGIN:VCARD":
            cur = {"emails": [], "phones": [], "addresses": [], "urls": []}
            continue
        if up == "END:VCARD":
            if cur is not None:
                contacts.append(_finish_contact(cur))
            cur = None
            continue
        if cur is None:
            continue
        prop = _parse_prop(line)
        if prop is None or prop[2] is None:
            continue
        pname, types, value = prop
        if pname == "FN":
            cur["name"] = _unescape(value).strip()
        elif pname == "N":
            parts = [_unescape(p).strip() for p in _split_unescaped(value, ";")] + [""] * 5
            cur["family_name"], cur["given_name"] = parts[0], parts[1]
            cur["_n"] = parts[:5]
        elif pname == "ORG":
            cur["organisation"] = ", ".join(p for p in (_unescape(x).strip()
                                                        for x in _split_unescaped(value, ";")) if p)
        elif pname == "TITLE":
            cur["title"] = _unescape(value).strip()
        elif pname == "EMAIL":
            v = _unescape(value).strip()
            if v.lower().startswith("mailto:"):
                v = v[7:]
            if v:
                cur["emails"].append({"value": v, "types": types})
        elif pname == "TEL":
            v = _unescape(value).strip()
            if v.lower().startswith("tel:"):
                v = v[4:]
            if v:
                cur["phones"].append({"value": v, "types": types})
        elif pname == "ADR":
            parts = [_unescape(p).strip() for p in _split_unescaped(value, ";")] + [""] * 7
            adr = dict(zip(("po_box", "extended", "street", "locality", "region",
                            "postal_code", "country"), parts[:7]))
            if any(adr.values()):
                cur["addresses"].append({**adr, "types": types})
        elif pname == "BDAY":
            v = value.strip()
            if re.fullmatch(r"\d{8}", v):
                v = f"{v[:4]}-{v[4:6]}-{v[6:]}"
            cur["birthday"] = v
        elif pname == "URL":
            v = _unescape(value).strip()
            if v:
                cur["urls"].append(v)
        elif pname == "NOTE":
            cur["note"] = _unescape(value)
        elif pname == "NICKNAME":
            cur["nickname"] = _unescape(value).strip()
    if not contacts:
        raise UserError(f"{name} doesn't contain any contacts.")
    return contacts


def _finish_contact(c: dict) -> dict:
    n = c.pop("_n", None)
    if not c.get("name"):
        if n:
            c["name"] = " ".join(p for p in (n[3], n[1], n[2], n[0], n[4]) if p)
        if not c.get("name"):
            c["name"] = c.get("organisation") or (c["emails"][0]["value"] if c["emails"] else "")
    out = {k: c.get(k, [] if k in ("emails", "phones", "addresses", "urls") else "")
           for k in _VCARD_FIELDS}
    if c.get("nickname"):
        out["nickname"] = c["nickname"]
    return out


def _format_address(a: dict) -> str:
    city = " ".join(p for p in (a.get("locality"), a.get("region"), a.get("postal_code")) if p)
    return ", ".join(p for p in (a.get("po_box"), a.get("extended"), a.get("street"), city,
                                 a.get("country")) if p)


def _contact_row(c: dict) -> list[str]:
    return [c["name"], c["given_name"], c["family_name"], c["organisation"], c["title"],
            "; ".join(e["value"] for e in c["emails"]),
            "; ".join(p["value"] for p in c["phones"]),
            "\n".join(_format_address(a) for a in c["addresses"]),
            c["birthday"], "; ".join(c["urls"]), c["note"]]


def _contacts_txt(contacts: list[dict]) -> str:
    blocks = []
    for c in contacts:
        lines = [c["name"] or "(no name)"]

        def add(label, value):
            if value:
                lines.append(f"  {label + ':':<14}{value}")
        if c.get("nickname"):
            add("Nickname", c["nickname"])
        add("Organisation", c["organisation"])
        add("Title", c["title"])
        for e in c["emails"]:
            add("Email", e["value"] + (f" ({', '.join(e['types'])})" if e["types"] else ""))
        for p in c["phones"]:
            add("Phone", p["value"] + (f" ({', '.join(p['types'])})" if p["types"] else ""))
        for a in c["addresses"]:
            add("Address", _format_address(a) + (f" ({', '.join(a['types'])})" if a["types"] else ""))
        add("Birthday", c["birthday"])
        for u in c["urls"]:
            add("Website", u)
        if c["note"]:
            note = c["note"].splitlines() or [""]
            add("Note", note[0])
            lines.extend(" " * 16 + n for n in note[1:])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def _vescape(s: str) -> str:
    return (s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Fold at 75 octets without splitting a UTF-8 character (RFC 6350 §3.2)."""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > 75:
            out.append(cur)
            cur, size = " ", 1
        cur += ch
        size += n
    out.append(cur)
    return "\r\n".join(out)


_CSV_ALIASES = {
    "name": ("name", "full name", "fn", "display name", "contact name"),
    "given": ("given name", "first name", "firstname", "given"),
    "family": ("family name", "last name", "lastname", "surname", "family"),
    "org": ("organisation", "organization", "company", "org", "organisation name",
            "organization name", "organization 1 - name"),
    "title": ("title", "job title", "position", "organization 1 - title"),
    "address": ("address", "home address", "work address", "street address", "postal address"),
    "birthday": ("birthday", "bday", "birth date", "date of birth", "dob"),
    "url": ("website", "url", "web page", "homepage", "web site"),
    "note": ("note", "notes"),
}


def _csv_role(header: str) -> str | None:
    h = re.sub(r"\s+", " ", header.strip().lower().replace("_", " "))
    if any(w in h for w in ("type", "label")):
        return None
    for role, names in _CSV_ALIASES.items():
        if h in names:
            return role
    if h.startswith(("email", "e-mail", "mail")):
        return "email"
    if h.startswith(("phone", "mobile", "tel", "cell")) or h in ("home phone", "work phone"):
        return "phone"
    return None


def csv_to_vcards(src: str | Path) -> list[Path]:
    """CSV with contact columns (Name, Email, Phone…; common Outlook/Google headers work) -> one
    .vcf holding every contact (vCard 3.0). CSV files belong to the spreadsheet family, which
    can offer this as its VCF target."""
    src = Path(src)
    text = _decode(_read_bytes(src))
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    try:
        rows = list(csv.reader(io.StringIO(text), dialect))
    except csv.Error as e:
        raise UserError(f"{src.name} isn't a readable CSV file ({e}).") from None
    if len(rows) < 2:
        raise UserError(f"{src.name} has no contact rows under its header.")
    roles = [_csv_role(h) for h in rows[0]]
    if not {"name", "given", "family", "email", "phone", "org"} & set(roles):
        raise UserError(f"{src.name} has no contact columns (like Name, Email or Phone).")
    cards = []
    for row in rows[1:]:
        f: dict[str, list[str]] = {}
        for role, cell in zip(roles, row):
            cell = cell.strip()
            if role and cell:
                f.setdefault(role, []).append(cell)

        def one(role):
            return " ".join(f.get(role, []))

        def many(role, sep=";"):
            return [x.strip() for v in f.get(role, []) for x in v.split(sep) if x.strip()]
        given, family = one("given"), one("family")
        fn = one("name") or " ".join(p for p in (given, family) if p) or one("org")
        emails, phones = many("email"), many("phone")
        if not (fn or emails or phones):
            continue
        fn = fn or (emails or phones)[0]
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{_vescape(fn)}"]
        if given or family:
            lines.append(f"N:{_vescape(family)};{_vescape(given)};;;")
        else:
            lines.append(f"N:;{_vescape(fn)};;;")
        if one("org"):
            lines.append(f"ORG:{_vescape(one('org'))}")
        if one("title"):
            lines.append(f"TITLE:{_vescape(one('title'))}")
        lines += [f"EMAIL;TYPE=INTERNET:{_vescape(e)}" for e in emails]
        lines += [f"TEL:{_vescape(p)}" for p in phones]
        for a in many("address", "\n"):
            lines.append(f"ADR:;;{_vescape(a)};;;;")
        if one("birthday"):
            lines.append(f"BDAY:{_vescape(one('birthday'))}")
        lines += [f"URL:{_vescape(u)}" for u in many("url")]
        if f.get("note"):
            lines.append(f"NOTE:{_vescape(chr(10).join(f['note']))}")
        lines.append("END:VCARD")
        cards.append("\r\n".join(_fold(x) for x in lines))
    if not cards:
        raise UserError(f"{src.name} has no contacts with a name, email or phone number.")
    from ..convert import atomic_save
    out = sibling(src, ext=".vcf")
    atomic_save(lambda dst: Path(dst).write_bytes(("\r\n".join(cards) + "\r\n").encode("utf-8")), out)
    return [out]


def _convert_vcf(src: Path, target: str) -> list[Path]:
    contacts = load(src)
    if target in ("CSV", "XLSX"):
        out = sibling(src, ext="." + target.lower())
        rows = [_contact_row(c) for c in contacts]
        (_write_csv if target == "CSV" else _write_xlsx)(CSV_COLUMNS, rows, out)
        return [out]
    out = sibling(src, ext=".json" if target == "JSON" else ".txt")
    text = _dump_json(contacts) if target == "JSON" else _contacts_txt(contacts)
    _save_text(text, out)
    return [out]


# ---------------------------------------------------------------- dispatch
def _save_text(text: str, out: Path) -> None:
    _save_bytes(text.encode("utf-8"), out)


def _save_bytes(data: bytes, out: Path) -> None:
    from ..convert import atomic_save
    atomic_save(lambda dst: Path(dst).write_bytes(data), out)


_EXT_FOR = {"JSON": ".json", "JSONL": ".jsonl", "YAML": ".yaml", "TOML": ".toml", "XML": ".xml",
            "PLIST": ".plist", "BINARY": ".plist", "CSV": ".csv", "XLSX": ".xlsx", "PDF": ".pdf",
            "TXT": ".txt"}


def convert(src: Path, target: str) -> list[Path]:
    src = Path(src)
    target = target.upper()
    fmt = EXT_FORMAT.get(src.suffix.lower())
    if fmt is None or target not in _TARGETS.get(fmt, []):
        raise UserError(f"Can't convert {src.suffix or 'this file'} to {target}.")
    try:
        return _convert(src, fmt, target)
    except UnicodeEncodeError:
        raise UserError(f"{src.name} contains broken text characters that can't be saved.") from None
    except RecursionError:
        raise UserError(f"{src.name} is nested too deeply to convert.") from None
    except MemoryError:
        raise UserError(f"{src.name} is too big to convert.") from None


def _convert(src: Path, fmt: str, target: str) -> list[Path]:
    if fmt == "VCF":
        return _convert_vcf(src, target)
    if target == "PDF":
        out = sibling(src, ext=".pdf")
        _write_pdf(src, fmt, out)
        return [out]
    data = load(src)
    if target in ("CSV", "XLSX"):
        header, rows = _table(data)
        out = sibling(src, ext=_EXT_FOR[target])
        (_write_csv if target == "CSV" else _write_xlsx)(header, rows, out)
        return [out]
    if fmt == "PLIST" and target in ("XML", "BINARY"):
        payload = _dump_plist(data, binary=target == "BINARY")
        out = sibling(src, "XML" if target == "XML" else "Binary", ".plist")
        _save_bytes(payload, out)
        return [out]
    if target == "PLIST":
        payload = _dump_plist(data, binary=False)
    else:
        payload = {"JSON": _dump_json, "JSONL": _dump_jsonl, "YAML": _dump_yaml,
                   "TOML": _dump_toml, "XML": _dump_xml}[target](data).encode("utf-8")
    out = sibling(src, ext=_EXT_FOR[target])
    _save_bytes(payload, out)
    return [out]


# ---------------------------------------------------------------- tools
def _strip_blank_text(node) -> None:
    """Remove whitespace-only text between elements (minidom), so the output re-indents cleanly."""
    for child in list(node.childNodes):
        if child.nodeType == child.TEXT_NODE and not child.data.strip():
            if any(c.nodeType == c.ELEMENT_NODE for c in node.childNodes):
                node.removeChild(child)
        elif child.nodeType == child.ELEMENT_NODE:
            _strip_blank_text(child)


def _minidom(raw: bytes, name: str):
    from defusedxml import DefusedXmlException
    from defusedxml.minidom import parseString
    try:
        doc = parseString(raw)
    except DefusedXmlException:
        raise UserError(f"{name} uses XML entities, which aren't allowed for safety.") from None
    except Exception as e:
        raise UserError(f"{name} isn't valid XML ({e}).") from None
    _strip_blank_text(doc.documentElement)
    return doc


def _pretty_xml(raw: bytes, name: str) -> bytes:
    """Re-indent keeping prefixes, comments and processing instructions."""
    doc = _minidom(raw, name)
    return doc.toprettyxml(indent="  ", encoding="utf-8")


def _reformat(path: Path, pretty: bool) -> list[Path]:
    path = Path(path)
    fmt = EXT_FORMAT.get(path.suffix.lower())
    label = "Pretty" if pretty else "Minified"
    try:
        if fmt == "XML":
            raw = _read_bytes(path)
            data = _pretty_xml(raw, path.name) if pretty else _minidom(raw, path.name).toxml(encoding="utf-8")
        elif fmt == "JSON":
            data = _dump_json(load(path), 2 if pretty else None).encode("utf-8")
        elif fmt == "JSONL" and not pretty:
            data = _dump_jsonl(load(path)).encode("utf-8")
        elif fmt == "PLIST" and pretty:
            data = _dump_plist(load(path), binary=False)
        else:
            what = "JSON, XML and property list" if pretty else "JSON, JSON Lines and XML"
            raise UserError(f"{label} works on {what} files.")
    except UnicodeEncodeError:
        raise UserError(f"{path.name} contains broken text characters that can't be saved.") from None
    out = sibling(path, label)
    _save_bytes(data, out)
    return [out]


def pretty(paths: list[Path]) -> list[Path]:
    return [o for p in paths for o in _reformat(p, True)]


def minify(paths: list[Path]) -> list[Path]:
    return [o for p in paths for o in _reformat(p, False)]


register(Family(
    category="data",
    label="Data",
    exts=set(EXT_FORMAT),
    targets=targets,
    convert=convert,
    hints=HINTS,
    tools=[Tool("Pretty", "≣", HINTS["Pretty"], pretty, working="Formatting…"),
           Tool("Minify", "⋯", HINTS["Minify"], minify, working="Minifying…")],
    available=_available,
))
