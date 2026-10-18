"""A log of everything DropDial made, so results can be found (or undone) later.
Stored as JSON lines in the data folder; capped so it never grows without bound."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .util import data_dir

MAX_ENTRIES = 500
_LOCK = threading.Lock()


@dataclass
class Entry:
    time: float
    action: str
    title: str
    detail: str
    srcs: list[str] = field(default_factory=list)
    outs: list[str] = field(default_factory=list)
    source: str = "menu"            # menu | watch | cli

    @property
    def existing_outs(self) -> list[Path]:
        return [Path(o) for o in self.outs if Path(o).exists()]

    def when(self, now: float | None = None) -> str:
        now = now or time.time()
        d = now - self.time
        if d < 60:
            return "just now"
        if d < 3600:
            return f"{int(d // 60)} min ago"
        if d < 86400 and time.localtime(now).tm_yday == time.localtime(self.time).tm_yday:
            return time.strftime("%H:%M", time.localtime(self.time))
        return time.strftime("%d %b %H:%M", time.localtime(self.time))


def path() -> Path:
    return data_dir() / "history.jsonl"


def add(result, action: str = "", source: str = "menu") -> Entry | None:
    """Record a report.Result. Returns the entry (or None if nothing was written)."""
    outs = [str(o) for o in getattr(result, "outs", []) or []]
    if not outs:
        return None
    e = Entry(time.time(), action, result.title, result.detail,
              [str(s) for s in getattr(result, "srcs", []) or []], outs, source)
    with _LOCK:
        p = path()
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(e), ensure_ascii=False) + "\n")
        _trim(p)
    return e


def _trim(p: Path) -> None:
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) > MAX_ENTRIES * 1.2:
        tmp = p.with_suffix(".tmp")
        tmp.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n", encoding="utf-8")
        tmp.replace(p)


def entries(limit: int = MAX_ENTRIES) -> list[Entry]:
    """Newest first."""
    p = path()
    if not p.exists():
        return []
    out = []
    with _LOCK:
        lines = p.read_text(encoding="utf-8").splitlines()
    for ln in reversed(lines):
        try:
            out.append(Entry(**json.loads(ln)))
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def clear() -> None:
    with _LOCK:
        try:
            path().unlink()
        except FileNotFoundError:
            pass


def stats() -> dict:
    """Totals for the History window header: files made and bytes saved by compression."""
    made, saved = 0, 0
    for e in entries():
        made += len(e.outs)
        if "Compress" in e.action or e.action.startswith("recipe:"):
            before = sum(Path(s).stat().st_size for s in e.srcs if Path(s).is_file())
            after = sum(o.stat().st_size for o in e.existing_outs)
            if after and before > after:
                saved += before - after
    return {"files": made, "saved": saved}
