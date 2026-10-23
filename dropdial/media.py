"""Video and audio, powered by ffmpeg.

ffmpeg is found in this order: $DROPDIAL_FFMPEG, the system PATH, then the copy that ships
with the `imageio-ffmpeg` package (installed with DropDial, so it works out of the box).
Every function takes a source path and returns the output path(s), written next to the
source like the rest of DropDial. Nothing here imports Qt."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from .util import NotSmaller, UserError, report_progress, sibling

VIDEO_TARGETS = ["MP4", "WEBM", "MOV", "GIF", "MP3"]
AUDIO_TARGETS = ["MP3", "M4A", "WAV", "FLAC", "OGG"]
VIDEO_TOOLS = ["Compress", "Audio", "Mute", "Frame", "Rotate"]
AUDIO_TOOLS = ["Normalize", "Trim silence", "Compress"]

_EVEN = "scale=trunc(iw/2)*2:trunc(ih/2)*2"   # H.264 needs even dimensions


# ---------------------------------------------------------------- finding ffmpeg
@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    env = os.environ.get("DROPDIAL_FFMPEG")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


def available() -> bool:
    return ffmpeg_path() is not None


def _need() -> str:
    exe = ffmpeg_path()
    if not exe:
        raise UserError("Video and audio need ffmpeg. Install it (or `pip install imageio-ffmpeg`) "
                        "and try again.")
    return exe


def _popen_kwargs() -> dict:
    if sys.platform == "win32":
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW: no console flashing up
    return {}


# ---------------------------------------------------------------- probing
@dataclass
class MediaInfo:
    duration: float = 0.0          # seconds
    width: int = 0
    height: int = 0
    fps: float = 0.0
    vcodec: str = ""
    acodec: str = ""
    rotation: int = 0
    hdr: bool = False               # HLG or PQ (iPhone HDR, HDR10): needs tone mapping for normal screens

    @property
    def has_video(self) -> bool:
        return bool(self.vcodec) and self.vcodec not in ("mjpeg", "png")  # cover art isn't video

    @property
    def has_audio(self) -> bool:
        return bool(self.acodec)


_DUR = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VID = re.compile(r"Stream #\S+.*?Video:\s*([a-z0-9_]+)[^\n]*?,\s*(\d{2,5})x(\d{2,5})")
_AUD = re.compile(r"Stream #\S+.*?Audio:\s*([a-z0-9_]+)")
_FPS = re.compile(r"([\d.]+)\s*fps")
_ROT = re.compile(r"rotate\s*:\s*(-?\d+)|rotation of\s*(-?[\d.]+)")


def parse_probe(text: str) -> MediaInfo:
    info = MediaInfo()
    m = _DUR.search(text)
    if m:
        h, mi, s = m.groups()
        info.duration = int(h) * 3600 + int(mi) * 60 + float(s)
    for m in _VID.finditer(text):
        codec = m.group(1)
        if codec in ("mjpeg", "png") and info.vcodec:
            continue
        info.vcodec, info.width, info.height = codec, int(m.group(2)), int(m.group(3))
        line = text[m.start(): text.find("\n", m.start())]
        f = _FPS.search(line)
        if f:
            info.fps = float(f.group(1))
        info.hdr = "arib-std-b67" in line or "smpte2084" in line
        if codec not in ("mjpeg", "png"):
            break
    m = _AUD.search(text)
    if m:
        info.acodec = m.group(1)
    m = _ROT.search(text)
    if m:
        info.rotation = int(float(m.group(1) or m.group(2))) % 360
    return info


def probe(src: str | Path) -> MediaInfo:
    """Read duration, size and codecs from ffmpeg's banner (no ffprobe needed)."""
    exe = _need()
    r = subprocess.run([exe, "-hide_banner", "-i", str(src)], capture_output=True, text=True,
                       errors="replace", **_popen_kwargs())
    info = parse_probe(r.stderr)
    if not info.vcodec and not info.acodec:
        raise UserError("This file doesn't look like audio or video ffmpeg can read.")
    return info


# ---------------------------------------------------------------- running
def run_ffmpeg(args: list, out: Path, duration: float = 0.0,
               progress: Callable[[float], None] | None = None) -> Path:
    """Run ffmpeg writing to a temp file next to `out`, then rename (no half-written files)."""
    exe = _need()
    out = Path(out)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    cmd = [exe, "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
           "-progress", "pipe:1", "-nostats", *[str(a) for a in args], str(tmp)]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                errors="replace", **_popen_kwargs())
        assert proc.stdout is not None
        report = progress or report_progress
        for line in proc.stdout:
            if duration > 0 and line.startswith("out_time_us="):
                try:
                    report(min(1.0, int(line.split("=", 1)[1]) / 1e6 / duration))
                except ValueError:
                    pass
        err = proc.stderr.read() if proc.stderr else ""
        if proc.wait() != 0 or not tmp.exists():
            last = [ln for ln in err.strip().splitlines() if ln.strip()]
            raise UserError("ffmpeg couldn't process this file: {detail}", detail=last[-1]) if last else \
                UserError("ffmpeg couldn't process this file.")
        os.replace(tmp, out)
        return out
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


@lru_cache(maxsize=1)
def _can_tonemap() -> bool:
    try:
        r = subprocess.run([_need(), "-hide_banner", "-filters"], capture_output=True, text=True,
                           errors="replace", **_popen_kwargs())
        return " zscale " in r.stdout and " tonemap " in r.stdout
    except Exception:
        return False


TONEMAP = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
           "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
SDR_TAGS = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]


def _video_filters(info: MediaInfo, *extra: str) -> str:
    """Filter chain: HDR -> SDR tone mapping (iPhone HDR would look washed out otherwise),
    then any extra steps, then even dimensions (H.264 / yuv420p need them)."""
    chain = []
    if info.hdr and _can_tonemap():
        chain.append(TONEMAP)
    chain += [e for e in extra if e]
    chain.append(_EVEN)
    return ",".join(chain)


def _limit_short_side(info: MediaInfo, limit: int | None) -> str:
    """Scale so the *shorter* side is at most `limit`: '1080p' then means 1920x1080 or
    1080x1920, and portrait phone videos aren't shrunk to 608 px wide."""
    if not limit or min(info.width, info.height) <= limit:
        return ""
    return f"scale='if(gt(iw,ih),-2,min(iw,{limit}))':'if(gt(iw,ih),min(ih,{limit}),-2)'"


def _mp4_audio(info: MediaInfo) -> list:
    """Copy audio that MP4 players understand; re-encode the rest (PCM, Opus, Vorbis…) to AAC."""
    if not info.has_audio:
        return ["-an"]
    if info.acodec in ("aac", "mp3", "alac", "ac3", "eac3"):
        return ["-c:a", "copy"]
    return ["-c:a", "aac", "-b:a", "192k"]


def _ensure_smaller(src, out: Path) -> Path:
    if out.stat().st_size >= Path(src).stat().st_size:
        out.unlink()
        raise NotSmaller("{name} is already well compressed: a smaller copy would look worse. "
                         "Nothing was saved.", name=Path(src).name)
    return out


def _audio_args(target: str) -> list:
    return {
        "MP3": ["-c:a", "libmp3lame", "-q:a", "2"],
        "M4A": ["-c:a", "aac", "-b:a", "192k"],
        "WAV": ["-c:a", "pcm_s16le"],
        "FLAC": ["-c:a", "flac"],
        "OGG": ["-c:a", "libvorbis", "-q:a", "5"],
    }[target]


def _h264(crf: int = 23, preset: str = "medium") -> list:
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]


# ---------------------------------------------------------------- conversions
def gif_from_video(src: str | Path, fps: int = 12, width: int = 640,
                   max_seconds: float | None = 30.0, progress=None) -> Path:
    """Two-pass palette in one filter graph: far better colours than a plain GIF encode."""
    info = probe(src)
    out = sibling(src, ext=".gif")
    pre = (TONEMAP + ",") if info.hdr and _can_tonemap() else ""
    size = (f"scale='if(gt(iw,ih),min({width},iw),-1)':'if(gt(iw,ih),-1,min({width},ih))':flags=lanczos")
    vf = (f"{pre}fps={fps},{size},split[a][b];"
          f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
    args = ["-i", src]
    dur = info.duration
    if max_seconds and info.duration > max_seconds:
        args += ["-t", max_seconds]
        dur = max_seconds
    return run_ffmpeg(args + ["-filter_complex", vf, "-loop", "0"], out, dur, progress)


def convert_video(src: str | Path, target: str, progress=None) -> list[Path]:
    target = target.upper()
    if target == "GIF":
        return [gif_from_video(src, progress=progress)]
    info = probe(src)
    if target == "MP3":
        if not info.has_audio:
            raise UserError("This video has no sound to save.")
        out = sibling(src, ext=".mp3")
        return [run_ffmpeg(["-i", src, "-vn", *_audio_args("MP3")], out, info.duration, progress)]
    out = sibling(src, ext="." + target.lower())
    args: list = ["-i", src]
    sdr = SDR_TAGS if info.hdr and _can_tonemap() else []
    if target == "WEBM":
        args += ["-vf", _video_filters(info), "-pix_fmt", "yuv420p", "-c:v", "libvpx-vp9", "-crf", "33",
                 "-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "4", *sdr]
        args += ["-c:a", "libopus", "-b:a", "128k"] if info.has_audio else ["-an"]
    else:  # MP4 / MOV
        args += _h264() + ["-vf", _video_filters(info), *sdr]
        args += ["-c:a", "aac", "-b:a", "160k"] if info.has_audio else ["-an"]
        args += ["-movflags", "+faststart"]
    return [run_ffmpeg(args, out, info.duration, progress)]


def convert_audio(src: str | Path, target: str, progress=None) -> list[Path]:
    target = target.upper()
    info = probe(src)
    if not info.has_audio:
        raise UserError("No audio found in this file.")
    out = sibling(src, ext="." + target.lower())
    return [run_ffmpeg(["-i", src, "-vn", "-map_metadata", "0", *_audio_args(target)],
                       out, info.duration, progress)]


def targets_for(cat: str, src_ext: str) -> list[str]:
    cur = src_ext.lower().lstrip(".").upper()
    cur = {"M4V": "MP4", "AIF": "WAV", "AIFF": "WAV"}.get(cur, cur)
    if cat == "video":
        return [t for t in VIDEO_TARGETS if t != cur]
    if cat == "audio":
        return [t for t in AUDIO_TARGETS if t != cur]
    return []


# ---------------------------------------------------------------- video tools
def compress_video(src: str | Path, crf: int = 28, max_height: int | None = 1080,
                   progress=None) -> Path:
    """H.264 at a higher CRF, optionally downscaled. Output is always .mp4 (plays everywhere)."""
    info = probe(src)
    out = sibling(src, "Compressed", ".mp4")
    vf = _video_filters(info, _limit_short_side(info, max_height))
    sdr = SDR_TAGS if info.hdr and _can_tonemap() else []
    args = ["-i", src, *_h264(crf, "medium"), "-vf", vf, *sdr]
    args += ["-c:a", "aac", "-b:a", "128k"] if info.has_audio else ["-an"]
    run_ffmpeg(args + ["-movflags", "+faststart"], out, info.duration, progress)
    return _ensure_smaller(src, out)


def extract_audio(src: str | Path, progress=None) -> Path:
    info = probe(src)
    if not info.has_audio:
        raise UserError("This video has no sound to extract.")
    out = sibling(src, "Audio", ".mp3")
    return run_ffmpeg(["-i", src, "-vn", *_audio_args("MP3")], out, info.duration, progress)


def mute_video(src: str | Path, progress=None) -> Path:
    info = probe(src)
    out = sibling(src, "Muted")
    return run_ffmpeg(["-i", src, "-map", "0:v", "-c", "copy", "-an"], out, info.duration, progress)


def video_frame(src: str | Path, at: float | None = None) -> Path:
    """Grab a still (10% in by default, which skips black intro frames)."""
    info = probe(src)
    t = at if at is not None else info.duration * 0.1
    out = sibling(src, "Frame", ".jpg")
    vf = ["-vf", TONEMAP] if info.hdr and _can_tonemap() else []
    return run_ffmpeg(["-ss", f"{max(0.0, t):.3f}", "-i", src, *vf, "-frames:v", "1", "-q:v", "2"], out)


def rotate_video(src: str | Path, degrees: int = 90, progress=None) -> Path:
    info = probe(src)
    turn = {90: "transpose=1", 180: "transpose=1,transpose=1", 270: "transpose=2"}[degrees % 360]
    out = sibling(src, "Rotated", ".mp4")
    sdr = SDR_TAGS if info.hdr and _can_tonemap() else []
    args = ["-i", src, *_h264(20), "-vf", _video_filters(info, turn), *sdr, *_mp4_audio(info)]
    return run_ffmpeg(args + ["-movflags", "+faststart"], out, info.duration, progress)


# ---------------------------------------------------------------- audio tools
def _same_audio_target(src: str | Path) -> tuple[str, str]:
    ext = Path(src).suffix.lower()
    t = {".mp3": "MP3", ".m4a": "M4A", ".aac": "M4A", ".wav": "WAV", ".flac": "FLAC",
         ".ogg": "OGG"}.get(ext, "MP3")
    return t, "." + t.lower()


def normalize_audio(src: str | Path, progress=None) -> Path:
    """EBU R128 loudness normalisation to -16 LUFS (podcast / streaming level)."""
    info = probe(src)
    t, ext = _same_audio_target(src)
    out = sibling(src, "Normalized", ext)
    return run_ffmpeg(["-i", src, "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", *_audio_args(t)],
                      out, info.duration, progress)


def trim_silence(src: str | Path, threshold_db: int = -50, progress=None) -> Path:
    info = probe(src)
    t, ext = _same_audio_target(src)
    rm = f"silenceremove=start_periods=1:start_threshold={threshold_db}dB:start_silence=0.1"
    out = sibling(src, "Trimmed", ext)
    return run_ffmpeg(["-i", src, "-vn", "-af", f"{rm},areverse,{rm},areverse", *_audio_args(t)],
                      out, info.duration, progress)


def compress_audio(src: str | Path, kbps: int = 96, progress=None) -> Path:
    info = probe(src)
    out = sibling(src, "Compressed", ".mp3")
    run_ffmpeg(["-i", src, "-vn", "-map_metadata", "0", "-c:a", "libmp3lame", "-b:a", f"{kbps}k"],
               out, info.duration, progress)
    return _ensure_smaller(src, out)


def describe(src: str | Path) -> str:
    """Short hub text, e.g. '1:23 · 1920×1080'."""
    try:
        info = probe(src)
    except Exception:
        return ""
    d = int(round(info.duration))
    t = f"{d // 3600}:{d % 3600 // 60:02d}:{d % 60:02d}" if d >= 3600 else f"{d // 60}:{d % 60:02d}"
    return f"{t} · {info.width}×{info.height}" if info.has_video else t
