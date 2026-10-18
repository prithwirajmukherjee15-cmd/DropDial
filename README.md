<p align="center"><img src="dragshift/assets/dragshift.png" width="128" alt="DragShift icon"></p>

<h1 align="center">DragShift 2</h1>

<p align="center"><b>Made by Prithwiraj Mukherjee</b></p>

Convert and edit files on **Mac, Windows and Linux** with a liquid-glass radial menu. Start dragging any file, press **Shift**, and drop it on a slice.

![Convert, Tools and Recipes rings](docs/rings.png)

## ⬇️ Download

| Platform | Direct download |
|---|---|
| 🍎 **Mac** (Apple Silicon: M1, M2, M3, M4) | [**DragShift-mac-apple-silicon.dmg**](https://github.com/prithwirajmukherjee15-cmd/dragshift/releases/latest/download/DragShift-mac-apple-silicon.dmg) |
| 🍎 **Mac** (Intel) | [**DragShift-mac-intel.dmg**](https://github.com/prithwirajmukherjee15-cmd/dragshift/releases/latest/download/DragShift-mac-intel.dmg) |
| 🪟 **Windows** installer (recommended) | [**DragShift-Setup.exe**](https://github.com/prithwirajmukherjee15-cmd/dragshift/releases/latest/download/DragShift-Setup.exe) |
| 🪟 **Windows** portable | [**DragShift.exe**](https://github.com/prithwirajmukherjee15-cmd/dragshift/releases/latest/download/DragShift.exe) |
| 🐧 **Linux** (Debian, Ubuntu, Mint, MX… `.deb`) | [**DragShift-linux-amd64.deb**](https://github.com/prithwirajmukherjee15-cmd/dragshift/releases/latest/download/DragShift-linux-amd64.deb) |

The links always point at the newest build. All releases: [Releases page](../../releases). Install notes for each platform are [below](#install).

**New in 2.0**

- ✨ **Premium look**: a new Midnight & Champagne theme and icon across the menu, windows and notifications.
- 🎬 **Video & audio**: MP4, MOV, MKV, WEBM, AVI → MP4 / WEBM / MOV / **GIF** / MP3, and MP3, WAV, M4A, FLAC, OGG between each other. Tools: compress, extract audio, mute, grab a frame, rotate, normalize loudness, trim silence. ffmpeg comes bundled.
- 📚 **More formats**: SVG → PNG/JPG/WEBP/PDF/ICO, and e-books (EPUB, MOBI, FB2, XPS, CBZ) → PDF/DOCX/TXT.
- ©️ **New tools**: watermark images and PDFs, number PDF pages, unlock a PDF you know the password for.
- ⚡ **Recipes**: several steps in one drop, from a third ring in the menu. *Web-ready* = resize → remove metadata → WebP. Eight built in, and a builder for your own.
- 📂 **Watch folders**: new files in a folder are processed automatically (screenshots → WebP, scans → PDF…).
- 🕘 **History** of everything DragShift made, with open, show, copy and undo.
- ⌨️ **Command line**: `dragshift convert *.heic --to jpg`, `dragshift recipe run web-ready *.png`, `dragshift watch ~/Screenshots --recipe web-ready`.
- 📋 **Copy** button on every notification: paste the result straight into a chat, email or folder.

## Install

**Windows:**

- **DragShift-Setup.exe** (recommended): installs for your user only, so no admin rights are needed. It adds a Start menu entry, an option to start with Windows, a right-click **DragShift…** entry and a **Send to → DragShift** entry. It uninstalls cleanly from Settings → Apps.
- **DragShift.exe**: a portable version you can run from anywhere.

**Mac (easiest, no security warning):** paste this into Terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/dragshift/main/install-mac.sh | bash
```

It picks the right build for your Mac, installs it to Applications and opens it ([see what it does](install-mac.sh)). Run the same line again to update.

Or download the .dmg yourself:
- **DragShift-mac-apple-silicon.dmg**: for Macs with M1, M2, M3 or M4 chips (macOS 11 or later).
- **DragShift-mac-intel.dmg**: for Intel Macs.

Open the .dmg and drag **DragShift** into Applications. DragShift lives in the menu bar and has no Dock icon.

<img src="docs/dmg.png" width="440" alt="The DragShift .dmg window"> You can also right-click any file → **Open With → DragShift**.

**Linux (Debian, Ubuntu, Mint, MX… with XFCE, MATE, Cinnamon or any X11 desktop):** download **DragShift-linux-amd64.deb**, then run:

```bash
sudo apt install ./DragShift-linux-amd64.deb
```

Open **DragShift** from the app menu. It sits in the panel's notification area, and you can turn on *Start at login* in Settings. It works in Thunar, Nautilus, Nemo, Caja, Dolphin and on the desktop, and it also adds **Open With → DragShift** to file right-click menus. It works with or without a compositor: when compositing is off (common on XFCE), the menu and windows are cut to their exact shape, so you won't see black boxes. Builds target Debian 12 or newer (Ubuntu 23.04+).

> **Wayland:** Wayland doesn't let apps read the global Shift and mouse state, so the Shift + drag trigger only works in X11 sessions (XFCE is X11). On GNOME/KDE Wayland, use right-click → **Open With → DragShift**, or pick *"Ubuntu on Xorg"* / *"Plasma (X11)"* at the login screen.

> **First launch on Windows:** SmartScreen may warn because the app isn't code-signed yet. Click **More info → Run anyway**.
>
> **First launch on Mac, if you used the .dmg instead of the Terminal line:** macOS says *"Apple could not verify 'DragShift' is free of malware."* This happens with any app that hasn't paid for Apple's notarization; DragShift's code is all public in this repo. To open it:
> 1. Open DragShift once and click **Done** on the warning.
> 2. Go to  → **System Settings → Privacy & Security**, scroll down to *"DragShift was blocked…"* and click **Open Anyway**. Enter your password and confirm.
> 3. That's it. macOS remembers the choice.
>
> Or, in Terminal: `xattr -dr com.apple.quarantine /Applications/DragShift.app`
> (On macOS 15 and later, the old right-click → Open shortcut no longer skips this warning.)
>
> **Mac, optional:** allow **Screen Recording** when DragShift asks, so the glass can refract the windows behind it. Without it, the glass shows your wallpaper. Nothing is ever saved or sent.

## How to use

1. Start dragging a file in File Explorer, Finder, your Linux file manager or on the desktop.
2. Press **Shift**. The menu opens under your cursor.
3. Drop the file on a slice. The result is saved **next to the original**, and the original is never changed.
4. Tap **Shift** again to switch rings: **Convert → Tools → Recipes**.

![Convert, Tools and Recipes rings](docs/rings.png)

![Result notification](docs/toast.png)

Each action ends with a notification that shows what changed, for example *"2.4 MB → 610 KB · 75% smaller"* or *"2400×1600 → 1200×800"*, with **Open**, **Copy**, **Folder** and **Undo**. Undo moves the new file to the Recycle Bin (Trash on Mac and Linux). Long video jobs show a percentage while they run. Everything you make is also listed in **History** (tray menu).

You can also right-click a file → **DragShift…**, use **Send to → DragShift**, or double-click the tray icon to pick a file.

## What it does

| File | Convert to | Tools |
|---|---|---|
| Images (JPG, PNG, WEBP, HEIC, AVIF, TIFF, BMP, GIF, ICO) | Any of those, or PDF. Several images become one combined PDF | **Compress** (by quality or to a target size such as "under 500 KB", with a before/after preview, several files at once) · **Resize** · **Crop** (ratios, live pixel size, rotate) · **Edit** (Auto, light/colour, rotate, flip, B&W, hold to compare) · **Annotate** (arrows, boxes, numbered steps, text, marker) · **Redact** · **Add BG** · **Metadata** (camera, date, GPS location with a map link; remove location only or remove everything) |
| PDF | JPG or PNG (one per page), DOCX, TXT | Compress · Split · Rotate · Merge (drop several) · **Protect** (AES-256 password) · **Extract images** · Metadata |
| Word (.docx) | PDF (uses Microsoft Word if it's installed, otherwise a built-in renderer), TXT | — |
| Text (.txt, .md, .csv…) | PDF, DOCX | — |
| Video (MP4, MOV, MKV, WEBM, AVI, M4V…) | MP4, WEBM, MOV, GIF (first 30 s, palette-optimised), MP3 | **Compress** (H.264, ≤1080p) · **Audio** (save the sound as MP3) · **Mute** · **Frame** (still image) · **Rotate** |
| Audio (MP3, WAV, M4A, FLAC, OGG…) | Any of those | **Normalize** (−16 LUFS) · **Trim silence** · **Compress** |
| SVG | PNG / JPG / WEBP (crisp at 2048 px), PDF (stays vector), ICO | — |
| E-books (EPUB, MOBI, FB2, XPS, CBZ) | PDF (keeps the table of contents), DOCX, TXT | — |

PDFs also get **Numbers** (page numbers) and **Watermark** (big diagonal stamp, live preview); images get **Watermark** (corner, centre or tiled). A password-protected PDF shows an **Unlock** slice.

### Recipes

A recipe runs several steps with one drop. A step that doesn't fit a file is skipped for that file, so *Email size* shrinks photos, PDFs and videos alike.

| Recipe | Does | For |
|---|---|---|
| ⚡ Web-ready | resize to 2048 px → remove metadata → WebP | images |
| ✉ Email size | resize to 1600 px → photos under 900 KB, PDFs and videos compressed | images, PDFs, videos |
| ⛨ Private | remove camera, GPS and author details | images, PDFs |
| ♥ Social | gradient backdrop at 4:5 → 1350 px → JPG | images |
| ⎙ Scan → PDF | auto-enhance → combine into one PDF → compress | images |
| ⚠ Confidential | tiled CONFIDENTIAL watermark → page numbers | images, PDFs |
| ▶ Share video | 720p H.264 MP4 | videos |
| ♫ Podcast | MP3 → trim silence → normalize loudness | videos, audio |

Open **Recipes…** from the tray to hide the ones you don't use or build your own from 15 steps (convert, resize, compress, remove metadata, watermark, add background, auto-enhance, black & white, rotate, page numbers, combine, extract audio, normalize, trim silence, grab a frame). Recipes are plain JSON, so you can export and share them.

![Recipe builder](docs/recipes.png)

### Watch folders

Tray → **Watch folders…** → pick a folder and what to do with new files (a recipe or a conversion). Files already in the folder are left alone, half-downloaded files are waited for, and results go into a `DragShift` subfolder (or next to the file, if you prefer).

### Command line

Everything is scriptable. On Mac and Linux run the app binary with a command; from source use `python -m dragshift`:

```bash
dragshift convert *.heic --to jpg
dragshift compress photo.jpg --target 500KB
dragshift resize *.png --long 1920 --out ~/Desktop/small
dragshift watermark *.jpg --text "© Jane Doe" --position tile
dragshift pdf merge a.pdf b.pdf          # also: split, rotate, number, protect, unlock, extract, compress
dragshift media gif clip.mov --fps 15    # also: audio, mute, frame, rotate, normalize, trim-silence
dragshift recipe run web-ready ~/Pictures/*.png
dragshift recipe run my-recipe.json *.jpg
dragshift info photo.jpg video.mp4
dragshift watch ~/Screenshots --recipe web-ready   # headless; Ctrl+C to stop
dragshift formats
```

Add `--json` for machine-readable output. The exit code is 1 if any file failed.

**Settings** (tray menu): trigger key (Shift, Ctrl or Alt), where results go (next to the original or a `DragShift` subfolder), JPG/WebP quality, PDF → image resolution, and start at login.

## The look

DragShift 2 uses a **Midnight & Champagne** theme: graphite glass, champagne-gold accents and a pearl rim, with a matching icon. The menu, notifications and windows use real **liquid-glass** rendering. DragShift captures the screen behind each surface and refracts it through the shape. A curved edge bends light, R, G and B bend by slightly different amounts (a subtle colour fringe at the edge), a highlight runs along the rim facing the light, and the tint adapts to what's behind it so text stays readable. The menu renders on a background thread while it pops in, so it still opens instantly.

## Tested on real desktops

Every push runs these jobs on GitHub's Windows, Mac and Linux machines:

- **Build:** unit tests, the portable exe and installer builds, a self-test of each build, and a silent install → run → uninstall check.
- **End-to-end:** a script moves the real mouse to drag files from File Explorer *and* the Desktop, presses Shift, drops on every conversion and tool, drives each tool window, and checks every output file (format, dimensions, page counts, encryption, metadata removed). The results table and a screen recording are saved to the `e2e-output` branch.
- **Mac end-to-end:** real Finder drags with Shift (Quartz mouse and keyboard events) through conversions, PDF tools, merging and the tool windows. Every output is checked, and the run is recorded to the `e2e-mac-output` branch.
- **Mac builds:** `DragShift.app` and the .dmg for Apple Silicon and Intel, each self-tested inside the app bundle.
- **Debian/XFCE:** builds the .deb on Debian 12, installs it, and runs the same kind of end-to-end test in Thunar under XFCE's window manager with the compositor **off**. Real XTest drags with Shift go through conversions, PDF tools, merging, the tool windows and Open With. The results and a recording are saved to the `e2e-linux-output` branch.
- **Demo video:** pushing to the `demo` branch records a showcase video.

## Credits

**DragShift 2 is made by Prithwiraj Mukherjee.** It builds on [DragShift](https://github.com/llamaboi55/DragShift) by llamaboi55: the radial menu, liquid-glass rendering, image/PDF tools and the cross-platform end-to-end test rigs all come from there. 2.0 adds video and audio, SVG and e-books, watermarks, page numbers, unlock, recipes, watch folders, history and the command line.

## License

[MIT](LICENSE): free to use, modify and share.

## Run from source

```bash
pip install -r requirements.txt
python -m dragshift            # the menu app
python -m dragshift --help     # the command line
```

On Linux, PySide6 also needs the Qt XCB libraries: `sudo apt install libxcb-cursor0 libxkbcommon-x11-0`.

Video and audio use ffmpeg from your PATH if you have it, otherwise the copy bundled by `imageio-ffmpeg` (set `DRAGSHIFT_FFMPEG` to point at a specific one). Recipes, watch folders and history live in `%APPDATA%\DragShift`, `~/Library/Application Support/DragShift` or `~/.config/DragShift` (override with `DRAGSHIFT_HOME`).

Tests: `QT_QPA_PLATFORM=offscreen python -m pytest -q`. Logs are written to `%LOCALAPPDATA%\DragShift\log.txt` on Windows, `~/Library/Logs/DragShift/log.txt` on Mac and `~/.local/share/DragShift/log.txt` on Linux.

Windows builds will be code-signed by the SignPath Foundation, which provides free code signing for open-source projects.
