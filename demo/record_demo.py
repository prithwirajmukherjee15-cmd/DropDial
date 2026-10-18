"""Records the DropDial showcase video on a real Windows desktop (GitHub Actions runner).
Outputs demo_out/: demo_raw.mp4, steps.json (caption timestamps), results/ (files it made)."""
from __future__ import annotations

import json
import shutil
import time
import traceback
from pathlib import Path

import pyautogui

import winkit as wk
from e2e_windows import make_photo, make_pdf

OUT = wk.ROOT / "demo_out"
OUT.mkdir(exist_ok=True)
DEMO = Path(r"C:\DropDialDemo")
DESK = wk.desktop_dir()
STEPS: list[dict] = []


def step(caption: str):
    STEPS.append({"t": round(time.time() - wk.T0, 2), "caption": caption})
    wk.log("STEP", caption)


def sweep(c, n, order, dwell=0.42):
    for i in order:
        wk.glide(*wk.petal_xy(c, n, i), 0.32)
        time.sleep(dwell)


def menu_layout(path: str, ring: str):
    from dropdial.app import DropDialApp
    rings = DropDialApp.build_rings(None, [path])
    return [i.label for i in rings[ring]]


def main():
    wk.set_log(OUT / "log.txt")
    wk.prepare_desktop()
    shutil.rmtree(DEMO, ignore_errors=True)
    DEMO.mkdir()
    make_photo(DEMO / "Sunset.jpg")
    make_pdf(DEMO / "Report.pdf", DEMO / "Sunset.jpg")
    for f in DESK.glob("Menu*.pdf"):
        f.unlink()
    make_pdf(DESK / "Menu.pdf", DEMO / "Sunset.jpg", pages=3, title="Menu")
    app = wk.start_app()
    time.sleep(5)
    ex = wk.open_explorer(DEMO)
    rec = wk.start_recording(OUT / "demo_raw.mp4")
    time.sleep(1.5)
    wk.T0 = time.time()
    sw, sh = pyautogui.size()
    photo = str(DEMO / "Sunset.jpg")
    try:
        # 1) the menu
        step("Drag any file, then press Shift")
        src = wk.item_center(ex, "Sunset.jpg")
        c = wk.drag_open_menu(src, nudge=(int(sw * 0.36), 70))
        conv = menu_layout(photo, "Convert")
        n = len(conv)
        step("Liquid glass: the menu refracts what's behind it")
        sweep(c, n, [1, 2, 3, 4, 5, 6, 7, 8], 0.38)
        wk.glide(*wk.petal_xy(c, n, conv.index("WEBP")), 0.35)
        time.sleep(0.6)
        wk.shot(OUT / "01_menu.png")
        step("Drop on a format: done instantly, with a summary")
        wk.drop()
        time.sleep(3.2)
        wk.shot(OUT / "02_toast.png")

        # 2) compress to a target size
        step("Tap Shift again for Tools")
        src = wk.item_center(ex, "Sunset.jpg")
        c = wk.drag_open_menu(src, nudge=(int(sw * 0.36), 70))
        wk.switch_ring()
        tools = menu_layout(photo, "Tools")
        sweep(c, len(tools), [1, 2, 3, 4, 5, 6, 7, 0], 0.32)
        wk.drop()
        step("Compress to a target size, with a before/after preview")
        w = wk.find_window("Compress.*", 10)
        time.sleep(1.0)
        wk.click_title(w, "Target size", 0.8)
        wk.click_title(w, "500 KB", 1.0)
        wk.click_title(w, "200 KB", 1.4)
        wk.shot(OUT / "03_compress.png")
        btn = [b for b in w.descendants(control_type="Button") if b.window_text().startswith("Compress")][-1]
        r = btn.rectangle()
        wk.glide((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        pyautogui.click()
        step("It tells you exactly how much it saved")
        time.sleep(1.2)
        # hover the newest toast so it stays, show the buttons
        wk.glide(sw - 220, sh - 90, 0.6)
        time.sleep(2.4)
        wk.shot(OUT / "04_compress_toast.png")

        # 3) annotate with numbered steps
        step("Annotate: arrows, numbered steps, text")
        src = wk.item_center(ex, "Sunset.jpg")
        c = wk.drag_open_menu(src, nudge=(int(sw * 0.36), 70))
        wk.switch_ring()
        wk.glide(*wk.petal_xy(c, len(tools), tools.index("Annotate")), 0.4)
        time.sleep(0.4)
        wk.drop()
        w = wk.find_window("Annotate.*", 10)
        time.sleep(1.0)
        wr = w.rectangle()
        cx, cy = (wr.left + wr.right) // 2, wr.top + int(wr.height() * 0.38)
        wk.glide(cx - 220, cy + 120)
        pyautogui.mouseDown()
        wk.glide(cx + 90, cy - 40, 0.6)
        pyautogui.mouseUp()
        wk.click_title(w, "① Step", 0.3)
        for dx, dy in ((140, -70), (-260, 150), (240, 120)):
            wk.glide(cx + dx, cy + dy, 0.4)
            pyautogui.click()
            time.sleep(0.25)
        wk.click_title(w, "T Text", 0.3)
        wk.glide(cx - 300, cy - 160, 0.4)
        pyautogui.click()
        time.sleep(0.3)
        pyautogui.typewrite("Golden hour", interval=0.05)
        pyautogui.press("enter")
        time.sleep(0.8)
        wk.shot(OUT / "05_annotate.png")
        wk.click_title(w, "Save", 1.2)
        time.sleep(1.5)

        # 4) metadata: location
        step("Metadata: see where a photo was taken, remove just that")
        src = wk.item_center(ex, "Sunset.jpg")
        c = wk.drag_open_menu(src, nudge=(int(sw * 0.36), 70))
        wk.switch_ring()
        wk.glide(*wk.petal_xy(c, len(tools), tools.index("Metadata")), 0.4)
        time.sleep(0.4)
        wk.drop()
        w = wk.find_window("Metadata.*", 10)
        time.sleep(2.0)
        wk.shot(OUT / "06_metadata.png")
        wk.click_title(w, "Remove location only", 1.5)
        time.sleep(1.2)

        # 5) desktop
        step("Works on the Desktop too")
        pyautogui.hotkey("win", "d")
        time.sleep(1.2)
        desk = wk.desktop_view()
        src = wk.item_center(desk, "Menu.pdf")
        c = wk.drag_open_menu(src, nudge=(int(sw * 0.38), 120))
        pdf_conv = menu_layout(str(DESK / "Menu.pdf"), "Convert")
        sweep(c, len(pdf_conv), [1, 2, 3, 0], 0.4)
        wk.drop()
        step("3 pages → 3 JPGs, right next to the PDF")
        time.sleep(3.5)
        wk.shot(OUT / "07_desktop.png")

        # 6) add background
        step("Add BG: gradient backdrop in one drop")
        ex.restore() if hasattr(ex, "restore") else None
        try:
            ex.set_focus()
        except Exception:
            pass
        time.sleep(0.8)
        src = wk.item_center(ex, "Sunset.jpg")
        c = wk.drag_open_menu(src, nudge=(int(sw * 0.36), 70))
        wk.switch_ring()
        wk.glide(*wk.petal_xy(c, len(tools), tools.index("Add BG")), 0.4)
        time.sleep(0.4)
        wk.drop()
        w = wk.find_window("Add BG.*", 10)
        time.sleep(1.2)
        sws = [x for x in w.descendants() if 18 <= x.rectangle().width() <= 34 and 18 <= x.rectangle().height() <= 34
               and not x.window_text().strip()]
        sws.sort(key=lambda x: (x.rectangle().top, x.rectangle().left))
        for k in (3, 1):
            if k < len(sws):
                r = sws[k].rectangle()
                wk.glide((r.left + r.right) // 2, (r.top + r.bottom) // 2, 0.4)
                pyautogui.click()
                time.sleep(0.9)
        wk.click_title(w, "1:1", 1.0)
        wk.shot(OUT / "08_addbg.png")
        wk.click_title(w, "Save with Background", 2.5)
        wk.glide(sw - 220, sh - 90, 0.6)
        time.sleep(2.5)
        wk.shot(OUT / "09_end.png")
    except Exception:
        wk.log("DEMO ERROR\n" + traceback.format_exc())
        wk.shot(OUT / "zz_error.png")
    finally:
        pyautogui.mouseUp()
        pyautogui.keyUp("shift")
        time.sleep(0.5)
        wk.stop_recording(rec)
        app.kill()
        wk.copy_app_log(OUT / "app_log.txt")
        (OUT / "steps.json").write_text(json.dumps(STEPS, indent=1))
        res = OUT / "results"
        res.mkdir(exist_ok=True)
        for f in list(DEMO.iterdir()) + list(DESK.glob("Menu*")):
            if f.is_file():
                shutil.copy(f, res / f.name)
        wk.log("done; files:", sorted(p.name for p in res.iterdir()))


if __name__ == "__main__":
    main()
