"""Liquid-glass renderer.

Apple's Liquid Glass is not frosted acrylic. The look comes from:
  * lensing: light bends strongly in a thin bezel at the edges, the middle stays clear
  * chromatic dispersion in that bezel (R, G and B bend by different amounts) -> rainbow fringe
  * a specular rim that follows the shape, brightest on the side facing the light
  * a light blur + saturation boost of what's behind, and a tint that adapts to it

We have a snapshot of what's behind the window (taken just before it appears), so we can
actually refract it per pixel with a signed distance field of the shape."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass
class GlassStyle:
    bezel: float = 22.0        # px width of the curved edge where light bends
    strength: float = 16.0     # max displacement in px at the very edge
    dispersion: float = 0.32   # extra bend for blue vs red (rainbow fringe)
    blur: float = 2.2          # Liquid Glass stays fairly clear
    saturation: float = 1.45
    spec: float = 0.95         # specular rim intensity
    light: tuple[float, float] = (-0.55, -0.83)  # direction *towards* the light (top-left)


# ---------------------------------------------------------------- signed distance fields
def sdf_rounded_rect(w: int, h: int, x0: float, y0: float, x1: float, y1: float, r: float) -> np.ndarray:
    """Negative inside. Coordinates in pixels."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    qx = np.abs(xs - cx) - hx
    qy = np.abs(ys - cy) - hy
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    inside = np.minimum(np.maximum(qx, qy), 0)
    return outside + inside - r


def sdf_circle(w: int, h: int, cx: float, cy: float, r: float) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    return np.hypot(xs - cx, ys - cy) - r


def sdf_ring_sector(w: int, h: int, cx: float, cy: float, r0: float, r1: float,
                    a0: float, a1: float, round_r: float = 10.0) -> np.ndarray:
    """Annular sector between angles a0..a1 (degrees, CCW from +x, y up) with rounded corners."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    dx, dy = xs - cx, cy - ys
    rad = np.hypot(dx, dy)
    mid = math.radians((a0 + a1) / 2)
    half = math.radians((a1 - a0) / 2)
    ang = np.arctan2(dy, dx) - mid
    ang = (ang + np.pi) % (2 * np.pi) - np.pi
    # distance to the radial (straight) sides: perpendicular distance in the rotated frame
    side = rad * np.sin(np.abs(ang) - half)
    side = np.where(np.abs(ang) - half > np.pi / 2, rad, side)
    # distance to the arcs
    ring = np.maximum(r0 - rad, rad - r1)
    # shrink then round (classic rounded-SDF trick)
    rr = round_r
    ring_s = ring + rr
    side_s = side + rr
    outside = np.hypot(np.maximum(ring_s, 0), np.maximum(side_s, 0))
    inside = np.minimum(np.maximum(ring_s, side_s), 0)
    return outside + inside - rr


def union(*fields: np.ndarray) -> np.ndarray:
    out = fields[0]
    for f in fields[1:]:
        out = np.minimum(out, f)
    return out


# ---------------------------------------------------------------- rendering
def _bilinear(img: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    x = np.clip(x, 0, w - 1.001)
    y = np.clip(y, 0, h - 1.001)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    fx, fy = x - x0, y - y0
    a = img[y0, x0]
    b = img[y0, x0 + 1]
    c = img[y0 + 1, x0]
    d = img[y0 + 1, x0 + 1]
    return (a * (1 - fx) * (1 - fy) + b * fx * (1 - fy) + c * (1 - fx) * fy + d * fx * fy)


def luminance(rgb: np.ndarray, mask: np.ndarray | None = None) -> float:
    l = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]) / 255
    if mask is not None and mask.sum() > 0:
        return float((l * mask).sum() / mask.sum())
    return float(l.mean())


def render(backdrop: Image.Image, sdf: np.ndarray, style: GlassStyle = GlassStyle(),
           tint: tuple[int, int, int, float] | None = None) -> tuple[Image.Image, bool]:
    """Return (RGBA glass image, is_light). `backdrop` must match sdf's size."""
    h, w = sdf.shape
    bg = backdrop.convert("RGB").resize((w, h)) if backdrop.size != (w, h) else backdrop.convert("RGB")
    soft = bg.filter(ImageFilter.GaussianBlur(style.blur)) if style.blur > 0 else bg
    soft = ImageEnhance.Color(soft).enhance(style.saturation)
    src = np.asarray(soft, dtype=np.float32)

    depth = -sdf                                   # >0 inside
    alpha = np.clip(0.5 - sdf, 0, 1)               # anti-aliased coverage
    gy, gx = np.gradient(sdf)
    norm = np.hypot(gx, gy) + 1e-6
    nx, ny = gx / norm, gy / norm                  # outward normal (image coords, y down)

    # lens profile: a quarter-circle bezel -> displacement grows steeply towards the edge
    t = np.clip(1 - depth / style.bezel, 0, 1)
    profile = 1 - np.sqrt(np.clip(1 - t * t, 0, 1))
    out = src.copy()
    band = (profile > 0) & (alpha > 0)          # only the bezel bends light
    by, bx = np.nonzero(band)
    if by.size:
        nxb, nyb, pb = nx[band], ny[band], profile[band]
        fx, fy = bx.astype(np.float32), by.astype(np.float32)
        for ch, k in enumerate((1 - style.dispersion, 1.0, 1 + style.dispersion)):
            mag = style.strength * pb * k
            # sample from further inside: the rim bends the scene like a thick lens edge
            out[by, bx, ch] = _bilinear(src[..., ch], fx - nxb * mag, fy - nyb * mag)
    inside = alpha > 0
    is_light = luminance(np.asarray(bg, np.float32), alpha) > 0.62

    # adaptive tint keeps text legible on any wallpaper
    if tint is None:
        tint = (236, 232, 246, 0.14) if is_light else (18, 14, 30, 0.26)
    tr, tg, tb, ta = tint
    out = out * (1 - ta) + np.array([tr, tg, tb], np.float32) * ta

    if is_light:
        # on light backgrounds the curved edge reads as a soft grey bevel, so the
        # white specular line on top of it stays visible
        out -= (profile ** 1.6)[..., None] * np.array([62, 60, 54], np.float32)
        out -= (np.clip(1 - depth / 1.6, 0, 1) * (alpha > 0))[..., None] * 40
    else:
        # inner bezel glow (light gathering in the curved edge)
        out += (profile ** 2)[..., None] * 38

    # specular rim: thin bright line, strongest where the edge faces the light
    lx, ly = style.light
    facing = np.clip(nx * lx + ny * ly, 0, 1)
    back = np.clip(-(nx * lx + ny * ly), 0, 1)
    rim = np.clip(1 - depth / 2.2, 0, 1) * inside
    rim2 = np.clip(1 - depth / 7.0, 0, 1) * inside
    spec = rim * (0.35 + 0.65 * facing ** 1.4) + rim2 * facing ** 3 * 0.35 + rim * back ** 2 * 0.45
    out += spec[..., None] * 255 * style.spec

    out = np.clip(out, 0, 255).astype(np.uint8)
    rgba = np.dstack([out, (alpha * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA"), is_light


def shadow(sdf: np.ndarray, spread: float = 14.0, opacity: float = 0.32, offset: tuple[int, int] = (0, 6)) -> Image.Image:
    """Soft drop shadow outside the shape."""
    d = np.roll(np.roll(sdf, offset[1], axis=0), offset[0], axis=1)
    a = np.clip(1 - np.maximum(d, 0) / spread, 0, 1) ** 2 * opacity
    a = np.where(sdf < 0, 0, a)  # never darken under the glass itself
    h, w = sdf.shape
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")
