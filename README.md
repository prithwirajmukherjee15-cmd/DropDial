<p align="center">
  <img src="docs/banner.png" alt="DropDial: drag a file, press Shift, drop it on the dial" width="100%">
</p>

<p align="center">
  <b>A free, open-source file converter you use by dragging.</b><br>
  Drag any file, press <kbd>Shift</kbd>, and drop it on a slice of the glass dial that opens at your cursor.
</p>

<p align="center">
  <a href="https://dropdial-app.netlify.app"><b>Website</b></a> ·
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><b>Download</b></a> ·
  <a href="#install">Install</a> ·
  <a href="#first-launch">First launch</a> ·
  <a href="#formats">Formats</a> ·
  <a href="#command-line">Command line</a> ·
  <a href="#development">Development</a>
</p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml"><img src="https://github.com/prithwirajmukherjee15-cmd/DropDial/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest"><img src="https://img.shields.io/github/v/release/prithwirajmukherjee15-cmd/DropDial?color=d8ad62&label=release" alt="Latest release"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases"><img src="https://img.shields.io/github/downloads/prithwirajmukherjee15-cmd/DropDial/total?color=a87a34" alt="Downloads"></a>
  <img src="https://img.shields.io/badge/Windows-10%20%7C%2011-2b2f3a" alt="Windows 10 | 11">
  <img src="https://img.shields.io/badge/macOS-11%2B-2b2f3a" alt="macOS 11+">
  <img src="https://img.shields.io/badge/Linux-x64-2b2f3a" alt="Linux x64">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-e3be7a" alt="MIT license"></a>
</p>

<p align="center"><b>English</b> · <a href="README.hi.md">हिन्दी</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.de.md">Deutsch</a> · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.ja.md">日本語</a> · <a href="README.ko.md">한국어</a> · <a href="README.zh-CN.md">简体中文</a> · <a href="README.ru.md">Русский</a> · <a href="README.ar.md">العربية</a></p>

<p align="center">
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg"><img src="docs/btn-mac-arm.svg" alt="Download for macOS (Apple Silicon)" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg"><img src="docs/btn-mac-intel.svg" alt="Download for macOS (Intel)" height="56"></a>
  <br>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe"><img src="docs/btn-win.svg" alt="Download for Windows" height="56"></a>
  <a href="https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb"><img src="docs/btn-linux.svg" alt="Download for Linux" height="56"></a>
</p>

> [!IMPORTANT]
> **Opening DropDial for the first time?** Windows and macOS show a one-time security warning because the app isn't code-signed yet. It's safe, and it takes 10 seconds to get past. **[See First launch ↓](#first-launch)**

<table>
  <tr>
    <td width="33%" valign="top"><b>Right at your cursor</b><br>No app window to open. The dial appears where you already are, with only the formats that make sense for the files you drag.</td>
    <td width="33%" valign="top"><b>140+ file types, no other software</b><br>Images, camera RAW, PDF, Word, Excel, e-books, video, audio, subtitles, archives, fonts, 3D models and map files work without Office or anything else installed.</td>
    <td width="33%" valign="top"><b>Stays on your computer</b><br>Nothing is uploaded. DropDial works offline and saves the result next to the original, never over it.</td>
  </tr>
</table>

## See it in action

<p align="center">
  <img src="docs/demo.gif" alt="Dragging a photo, pressing Shift, and dropping it on Compress" width="760">
</p>

## Install

Download from [Releases](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest).

- **macOS 11+**: open the `.dmg` ([Apple Silicon](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-apple-silicon.dmg) · [Intel](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-mac-intel.dmg)) and drag DropDial to Applications. Or paste this into Terminal: it picks the right build, installs it with no security prompt, and updates it when you run it again:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/DropDial/main/install-mac.sh | bash
  ```
- **Windows 10/11**: run [`DropDial-Setup.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-Setup.exe) (installs for your user, no admin rights; adds the right-click menu, *Send to*, and start with Windows), or use the portable [`DropDial.exe`](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial.exe).
- **Linux x64** (Debian 12+, Ubuntu 23.04+, Mint…): `sudo apt install ./DropDial-linux-amd64.deb` ([download](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-amd64.deb)). The Shift gesture needs X11; on Wayland, use Home's drop zone or right-click → **Open With → DropDial**.
- **Linux ARM64** (Ubuntu 24.04+, Debian 13+, Raspberry Pi OS 13 64-bit…): `sudo apt install ./DropDial-linux-arm64.deb` ([download](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest/download/DropDial-linux-arm64.deb)).

DropDial lives in the menu bar / system tray. It tells you when a new version is out.

## First launch

DropDial isn't code-signed yet (signing certificates cost money every year), so Windows and macOS show a warning the **first time only**. All of DropDial's code is public in this repository, and the downloads are built from it automatically by GitHub.

### Windows: “Windows protected your PC”

SmartScreen may show this the first time you run `DropDial-Setup.exe` or `DropDial.exe`.

1. Click **More info**.
2. Click **Run anyway**.

That's it. Windows won't ask again.

### Mac: “Apple could not verify DropDial…”

If you installed with the Terminal line above, you can skip this: there's no warning. With the **.dmg**, macOS says *“Apple could not verify ‘DropDial’ is free of malware that may harm your Mac or compromise your privacy.”* It says this about any app that hasn't been through Apple's paid notarization. To open it:

1. Open **DropDial** from Applications once, and click **Done** on the warning.
2. Open the **Apple menu → System Settings → Privacy & Security**. Scroll down to **“DropDial” was blocked to protect your Mac** and click **Open Anyway**.
3. Enter your password and click **Open Anyway** again to confirm.

Done. macOS remembers the choice, so you only do this once.

<details>
<summary>Prefer Terminal? One command does the same thing</summary>

```bash
xattr -dr com.apple.quarantine /Applications/DropDial.app
```

Then open DropDial normally.
</details>

> [!NOTE]
> On macOS 15 (Sequoia) and later, the old **right-click → Open** shortcut no longer gets past this warning. Use the steps above.

### Mac, optional: Screen Recording

DropDial may ask for **Screen Recording** permission. Allowing it lets the glass dial show the windows behind it. If you don't allow it, everything still works and the glass shows your wallpaper instead. **Nothing is ever recorded, saved or sent anywhere.** You can change this any time in **System Settings → Privacy & Security → Screen & System Audio Recording**.

## Features

- **A dial at the cursor**: drag files, press <kbd>Shift</kbd>, drop them on a format. Only formats that fit the files appear.
- **More than one side**: tap <kbd>Shift</kbd> again, press <kbd>Tab</kbd> or turn the mouse wheel to flip to **More formats**, **Tools** and **Recipes**.
- **Straight from the browser**: drag a picture, a link to a file or a download out of Chrome, Edge, Firefox or Safari. DropDial saves it to Downloads, then converts it.
- **Home**: click the tray / menu-bar icon for a drop zone (no Shift needed) and your recent results with previews. Open, show in folder, convert again or undo.
- **Tools for each kind of file**: compress, resize, crop, edit, annotate, redact, watermark and strip metadata from images; split, merge, rotate, number, protect, unlock and compress PDFs; compress, mute and rotate video; normalise audio; clean subtitles; subset fonts; repair 3D models; trip stats for GPS tracks; and more.
- **Recipes**: chain steps into one slice ("Web-ready", "Email size", "Private"…) or build your own.
- **Watch folders** convert every file that lands in them.
- **Many files at once**, a ZIP slice for a pile of files or a folder, and **History** to find or undo anything.
- **Other ways in**: the right-click menu, *Send to* (Windows), Home's drop zone and the [`dropdial` command](#command-line).
- **Your look**: liquid-glass dial with an accent colour of your choice (Champagne, Rose, Ocean, Emerald, Violet, Silver).

## Screenshots

<table>
  <tr>
    <td width="58%"><img src="docs/screen-home.png" alt="Home: drop zone and recent results with previews"></td>
    <td width="42%"><img src="docs/screen-dial.png" alt="The dial for a spreadsheet: XLSX, PDF, JSON, HTML, DOCX, MD"></td>
  </tr>
  <tr>
    <td align="center"><sub>Home: drop zone and recent results (a 3D render, a GPS map, a font specimen…)</sub></td>
    <td align="center"><sub>The dial for a spreadsheet; flip it for More formats and Tools</sub></td>
  </tr>
</table>

## Formats

| From | To |
|---|---|
| **Images**: JPG, PNG, WEBP, HEIC, AVIF, TIFF, GIF, BMP, ICO | each other, PDF, SVG (traced), ICNS, TGA, QOI |
| **Pro images**: camera RAW (CR2, CR3, NEF, ARW, DNG, RAF, ORF, RW2…), PSD, TGA, QOI, JPEG 2000, DDS, ICNS, PPM… | JPG, PNG, TIFF (16-bit for RAW), WEBP, AVIF, HEIC, PDF |
| **Vector**: SVG | PDF (stays vector), PNG, JPG, WEBP, ICO |
| **PDF** | JPG, PNG, DOCX, TXT; merge, split, rotate, compress, number, watermark, protect, unlock, extract images |
| **Documents**: DOCX, TXT, Markdown, HTML, saved web pages (MHTML), reStructuredText | PDF, DOCX, HTML, Markdown, TXT |
| **E-mail**: EML | PDF, DOCX, HTML, TXT; save attachments |
| **Spreadsheets**: XLSX, XLSM, XLS, ODS, CSV, TSV | XLSX, ODS, CSV, TSV, JSON, HTML, PDF, DOCX, Markdown; contacts CSV → VCF; combine, split sheets |
| **Data**: JSON, JSON Lines, YAML, TOML, XML, plist, vCard | each other, CSV, XLSX, PDF |
| **E-books**: EPUB, MOBI, FB2, CBZ, XPS | PDF, DOCX, TXT |
| **Video**: MP4, MOV, MKV, WEBM, AVI, WMV, FLV, M4V, MPEG, 3GP | MP4, WEBM, MOV, GIF, MP3; compress, mute, rotate, still frame (iPhone HDR is tone-mapped) |
| **Audio**: MP3, M4A, AAC, WAV, FLAC, OGG, OPUS, WMA, AIFF | MP3, M4A, WAV, FLAC, OGG; normalise loudness, trim silence, compress |
| **Subtitles**: SRT, WebVTT, ASS/SSA, SBV, MicroDVD, SAMI, LRC, TTML | each other as UTF-8, TXT; clean captions, fix 25 / 23.976 fps timing |
| **Archives**: ZIP, 7Z, TAR, TAR.GZ, TAR.BZ2, TAR.XZ, GZ, BZ2, XZ | extract, ZIP, 7Z, TAR.GZ; any files or folder → one ZIP |
| **Fonts**: TTF, OTF, WOFF, WOFF2, TTC | each other, PNG / PDF specimen; Latin subset, web font kit |
| **3D models**: STL, OBJ, PLY, GLB, glTF, OFF, 3MF | each other, PNG preview; center & ground, repair, decimate |
| **Map data**: GPX, KML, KMZ, GeoJSON, Shapefile | each other, CSV, PNG map; trip stats, reverse, simplify |

Everything works out of the box: the downloads include all the engines (FFmpeg for video and audio).
`dropdial formats` prints the full list for your copy.

## Command line

The `dropdial` command uses the same engines and recipes as the app (from source: `python -m dropdial`).

```bash
dropdial convert *.heic --to jpg
dropdial convert report.md --to pdf
dropdial convert ride.gpx --to kml
dropdial compress photo.jpg --target 500KB
dropdial pdf merge a.pdf b.pdf          # also: split, rotate, number, protect, unlock, extract, compress
dropdial media gif clip.mov --fps 15    # also: audio, mute, frame, rotate, normalize, trim-silence
dropdial recipe run web-ready ~/Pictures/*.png
dropdial watch ~/Screenshots --recipe web-ready
dropdial formats
```

Add `--json` for machine-readable output; the exit code is 1 if any file failed.

## Development

Python 3.12, on Windows, macOS or Linux:

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
pip install -r requirements.txt pytest
python -m dropdial
python -m pytest -q          # on Linux without a display: QT_QPA_PLATFORM=offscreen
```

[Architecture](docs/ARCHITECTURE.md) · [Adding a file format](docs/ADDING-A-CONVERTER.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) · [Security](SECURITY.md)

Pull requests are welcome. If DropDial saves you some clicks, a ⭐ helps other people find it.

## Code signing

DropDial is developed and published by **Prithwiraj Mukherjee**. The Windows and macOS downloads aren't code-signed or notarized yet, which is why the system warns the first time (see [First launch](#first-launch)). Every download is built from this repository's source by GitHub Actions; nothing is built by hand.

### Privacy

DropDial converts files on your own computer and never uploads them. It collects no usage data and sends no telemetry. It connects to the internet only:

- to ask GitHub (`api.github.com`) whether a newer release exists, shortly after start and then every few hours. Turn this off in Settings ("Check for updates automatically").
- to download a file you drag out of your web browser onto the dial.
- when you click a link, which opens your web browser.

## License

MIT, © 2026 Prithwiraj Mukherjee. Bundled third-party components keep their own licenses, listed in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

<p align="center">
  <a href="https://star-history.com/#prithwirajmukherjee15-cmd/DropDial&Date"><img src="https://api.star-history.com/svg?repos=prithwirajmukherjee15-cmd/DropDial&type=Date" alt="Star history" width="600"></a>
</p>

<p align="center"><sub>Made by <b>Prithwiraj Mukherjee</b></sub></p>
