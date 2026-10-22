"""Checks GitHub for a newer DropDial release.

The only network request DropDial makes on its own: one small call to api.github.com shortly
after start and then every few hours (Settings → "Check for updates" turns it off). Nothing
about you or your files is sent.
"""
from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

from . import __version__

REPO = "prithwirajmukherjee15-cmd/DropDial"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=20"
RELEASES = f"https://github.com/{REPO}/releases"


@dataclass
class Update:
    version: str
    url: str
    notes: str = ""


def parse_version(text: str) -> tuple[int, ...] | None:
    """'v1.2.3' / 'DropDial 1.2' -> (1, 2, 3) / (1, 2, 0); None if there's no version in it."""
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def newest(releases: list[dict], current: str = __version__) -> Update | None:
    """The newest proper release (not a draft or pre-release) newer than `current`."""
    cur = parse_version(current) or (0, 0, 0)
    best, best_v = None, cur
    for r in releases:
        if r.get("draft") or r.get("prerelease"):
            continue
        v = parse_version(r.get("tag_name", "")) or parse_version(r.get("name", ""))
        if v and v > best_v:
            best, best_v = r, v
    if best is None:
        return None
    return Update(".".join(map(str, best_v)), best.get("html_url") or RELEASES, (best.get("body") or "")[:2000])


def check(timeout: float = 10) -> Update | None:
    """Ask GitHub; returns None when up to date, offline or rate-limited."""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"DropDial/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
            data = json.loads(resp.read(2_000_000).decode("utf-8"))
    except Exception:  # noqa: BLE001 - offline, blocked, rate-limited: try again later
        return None
    return newest(data if isinstance(data, list) else [])
