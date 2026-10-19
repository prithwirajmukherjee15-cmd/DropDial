"""Helpers for driving Windows like a person: real mouse/keyboard input, Explorer and
Desktop icon lookup through UI Automation, screen recording. Used by the demo video
and the end-to-end test on GitHub's Windows machines."""
from __future__ import annotations

import ctypes
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import pyautogui
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
user32 = ctypes.windll.user32 if sys.platform == "win32" else None
try:  # the Windows console is cp1252; never let a "→" crash a run
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.03

R_PETAL = 109  # (R_IN + R_OUT) / 2 in radial.py
LOG = None
T0 = 0.0


def set_log(path: Path):
    global LOG
    LOG = open(path, "w", encoding="utf-8")


def log(*a):
    msg = " ".join(str(x) for x in a)
    try:
        print(msg, flush=True)
    except Exception:
        pass
    if LOG:
        LOG.write(f"[{time.time() - T0 if T0 else 0:7.2f}] {msg}\n")
        LOG.flush()


def shot(path: Path):
    try:
        ImageGrab.grab().save(path)
    except Exception as e:
        log("screenshot failed", e)


# ------------------------------------------------------------------ machine setup
def set_resolution(w: int, h: int):
    class DEVMODE(ctypes.Structure):
        _fields_ = [("dmDeviceName", ctypes.c_wchar * 32), ("dmSpecVersion", ctypes.c_ushort),
                    ("dmDriverVersion", ctypes.c_ushort), ("dmSize", ctypes.c_ushort),
                    ("dmDriverExtra", ctypes.c_ushort), ("dmFields", ctypes.c_ulong),
                    ("dmPositionX", ctypes.c_long), ("dmPositionY", ctypes.c_long),
                    ("dmDisplayOrientation", ctypes.c_ulong), ("dmDisplayFixedOutput", ctypes.c_ulong),
                    ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
                    ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
                    ("dmCollate", ctypes.c_short), ("dmFormName", ctypes.c_wchar * 32),
                    ("dmLogPixels", ctypes.c_ushort), ("dmBitsPerPel", ctypes.c_ulong),
                    ("dmPelsWidth", ctypes.c_ulong), ("dmPelsHeight", ctypes.c_ulong),
                    ("dmDisplayFlags", ctypes.c_ulong), ("dmDisplayFrequency", ctypes.c_ulong),
                    ("dmICMMethod", ctypes.c_ulong), ("dmICMIntent", ctypes.c_ulong),
                    ("dmMediaType", ctypes.c_ulong), ("dmDitherType", ctypes.c_ulong),
                    ("dmReserved1", ctypes.c_ulong), ("dmReserved2", ctypes.c_ulong),
                    ("dmPanningWidth", ctypes.c_ulong), ("dmPanningHeight", ctypes.c_ulong)]
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    if user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):
        dm.dmPelsWidth, dm.dmPelsHeight = w, h
        dm.dmFields = 0x80000 | 0x100000
        log("ChangeDisplaySettings ->", user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0))


def prepare_desktop(wallpaper_colors=("#ffb36b", "#ff5f6d", "#c2508f", "#7b8cff")):
    from dropdial.imaging import gradient
    set_resolution(1920, 1080)
    time.sleep(1)
    p = Path(os.environ.get("TEMP", r"C:\Temp")) / "dropdial_wall.bmp"
    gradient((1920, 1080), list(wallpaper_colors), 160).save(p)
    user32.SystemParametersInfoW(20, 0, str(p), 3)
    subprocess.run(["taskkill", "/F", "/IM", "ServerManager.exe"], capture_output=True)
    adv = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
    subprocess.run(["reg", "add", adv, "/v", "HideFileExt", "/t", "REG_DWORD", "/d", "0", "/f"], capture_output=True)
    # DropDial: skip the welcome window
    subprocess.run(["reg", "add", r"HKCU\Software\DropDial\DropDial", "/v", "welcomed", "/t", "REG_SZ",
                    "/d", "true", "/f"], capture_output=True)
    user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 1000, None)
    dismiss_system_dialogs()
    pyautogui.hotkey("win", "d")
    time.sleep(1.2)


def dismiss_system_dialogs():
    """GitHub's Windows image sometimes shows a 'paging file' warning; close small OK dialogs."""
    try:
        for w in uia().windows():
            try:
                r = w.rectangle()
                if r.width() > 800 or "DropDial" in w.window_text():
                    continue
                ok = w.child_window(title="OK", control_type="Button")
                if ok.exists(timeout=0.2):
                    log("closing dialog:", w.window_text())
                    ok.invoke()
            except Exception:
                pass
    except Exception as e:
        log("dialog sweep failed", e)


def copy_app_log(dest: Path):
    src = Path(os.environ.get("LOCALAPPDATA", "")) / "DropDial" / "log.txt"
    try:
        if src.exists():
            dest.write_bytes(src.read_bytes())
    except Exception:
        pass


def desktop_dir() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()) / "Desktop"


def start_app(extra_env: dict | None = None) -> subprocess.Popen:
    env = dict(os.environ)
    env["DROPDIAL_RECORDING"] = "1"
    env.update(extra_env or {})
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return subprocess.Popen([str(pyw if pyw.exists() else sys.executable), "-m", "dropdial", "--quiet"],
                            cwd=str(ROOT), env=env)


def start_recording(out: Path) -> subprocess.Popen:
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [exe, "-y", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "1", "-i", "desktop",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", str(out)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=open(out.with_suffix(".ffmpeg.txt"), "w"),
                            stderr=subprocess.STDOUT)


def stop_recording(p: subprocess.Popen):
    try:
        p.stdin.write(b"q")
        p.stdin.flush()
        p.wait(timeout=90)
    except Exception as e:
        log("ffmpeg stop error", e)
        p.kill()


# ------------------------------------------------------------------ UI automation
def uia():
    from pywinauto import Desktop
    return Desktop(backend="uia")


def find_window(title_re: str, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            w = uia().window(title_re=title_re)
            if w.exists(timeout=0.3):
                return w
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"window not found: {title_re}")


def window_gone(title_re: str, timeout=10) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if not uia().window(title_re=title_re).exists(timeout=0.2):
                return True
        except Exception:
            return True
        time.sleep(0.2)
    return False


def open_explorer(folder: Path, rect=(0.03, 0.07, 0.40, 0.72)):
    subprocess.Popen(["explorer", str(folder)])
    ex = find_window(f".*{folder.name}.*", 20)
    ex.set_focus()
    sw, sh = pyautogui.size()
    user32.ShowWindow(ex.handle, 1)
    user32.MoveWindow(ex.handle, int(sw * rect[0]), int(sh * rect[1]), int(sw * rect[2]), int(sh * rect[3]), True)
    time.sleep(0.8)
    pyautogui.hotkey("ctrl", "shift", "2")  # large icons
    time.sleep(0.8)
    return ex


def _item_rect(container, name: str):
    stem = name.rsplit(".", 1)[0]
    import re
    item = container.child_window(title_re=f"^{re.escape(stem)}(\\..*)?$", control_type="ListItem", found_index=0)
    item.wait("exists", timeout=8)
    return item, item.rectangle()


def item_center(container, name: str):
    """Icon position via UI Automation; retried, since UIA occasionally throws transient COM errors."""
    last = None
    for attempt in range(4):
        try:
            _, r = _item_rect(container, name)
            return (r.left + r.right) // 2, r.top + int((r.bottom - r.top) * 0.38)
        except Exception as e:  # COMError / timeout
            last = e
            log(f"item lookup retry {attempt + 1} for {name}: {type(e).__name__}")
            time.sleep(0.6)
    raise last


def desktop_view():
    return uia().window(class_name="Progman")


def refresh(container):
    try:
        container.set_focus()
    except Exception:
        pass
    pyautogui.press("f5")
    time.sleep(0.8)


# ------------------------------------------------------------------ gestures
def glide(x, y, dur=0.45):
    pyautogui.moveTo(x, y, duration=dur, tween=pyautogui.easeInOutQuad)


def petal_xy(center, n, i, r=R_PETAL):
    span = 360 / n
    a = math.radians(90 - i * span)
    return int(center[0] + r * math.cos(a)), int(center[1] - r * math.sin(a))


def drag_open_menu(src, nudge=(620, 40), key="shift"):
    """Press on a file, drag it, press the trigger key → menu opens at the cursor."""
    glide(*src, 0.5)
    time.sleep(0.15)
    pyautogui.mouseDown()
    time.sleep(0.12)
    for k in range(1, 9):
        pyautogui.moveTo(src[0] + k * 4, src[1] + k * 2)
        time.sleep(0.02)
    glide(src[0] + nudge[0], src[1] + nudge[1], 0.55)
    time.sleep(0.15)
    pyautogui.keyDown(key)
    # hold the mouse still: the dial must fill in by itself (no wiggle to wake the drag)
    time.sleep(0.7)
    cur = pyautogui.position()
    return menu_center(cur)


def menu_center(cur, size=400):
    """The menu is kept fully on screen, so near an edge its centre isn't the cursor."""
    sw, sh = pyautogui.size()
    half = size // 2
    return (min(max(cur[0], half), sw - half), min(max(cur[1], half), sh - half))


def switch_ring(key="shift"):
    pyautogui.keyUp(key)
    time.sleep(0.25)
    pyautogui.keyDown(key)
    time.sleep(0.12)
    pyautogui.keyUp(key)
    time.sleep(0.45)


def drop(key="shift"):
    pyautogui.mouseUp()
    time.sleep(0.15)
    pyautogui.keyUp(key)


def click_title(win, title: str, pause=0.4, dur=0.35):
    """Click a control by its label, preferring buttons (a window title can share the text)."""
    b = None
    end = time.time() + 6
    while b is None and time.time() < end:
        for ct in ("Button", "CheckBox", None):
            kw = {"title": title, "found_index": 0}
            if ct:
                kw["control_type"] = ct
            c = win.child_window(**kw)
            if c.exists(timeout=0.1):
                b = c
                break
        if b is None:
            time.sleep(0.2)
    if b is None:
        raise RuntimeError(f"control not found: {title!r}")
    r = b.rectangle()
    glide((r.left + r.right) // 2, (r.top + r.bottom) // 2, dur)
    pyautogui.click()
    time.sleep(pause)


def image_area(win):
    """Rectangle of the biggest custom widget (the image canvas) inside a tool window."""
    best = None
    for c in win.descendants():
        try:
            if c.element_info.control_type in ("Custom", "Pane", "Group") and not c.window_text():
                r = c.rectangle()
                a = r.width() * r.height()
                if r.width() > 200 and r.height() > 150 and (best is None or a > best[0]):
                    best = (a, r)
        except Exception:
            pass
    return best[1] if best else None
