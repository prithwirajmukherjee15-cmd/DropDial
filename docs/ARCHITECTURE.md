# How DropDial works

DropDial is a single Python app built on PySide6 (Qt). It sits in the tray (the menu bar on macOS), waits for a
Shift+drag, shows a glass dial under the cursor, and runs whatever slice the file is dropped on. All the file
work happens in plain Python "engines" that know nothing about the UI, so the command line, watch folders and tests
use exactly the same code.

```
 trigger.py                 radial.py                     app.py                     engines
 ┌──────────────┐  Shift+   ┌───────────────────┐  drop   ┌──────────────┐  Job on   ┌───────────────────┐
 │ poll mouse + │  drag ──▶ │ RadialMenu pops   │ ──────▶ │ run_item()   │ ───────▶  │ convert / imaging │
 │ trigger key  │           │ at the cursor     │ on a    │ picks the    │ QThread-  │ media / formats/  │
 │ every 15 ms  │           │ (glass + liquid)  │ slice   │ action       │ Pool      │ recipes           │
 └──────────────┘           └───────────────────┘         └──────────────┘           └─────────┬─────────┘
                                                                                                │ files written
                              toasts.py ◀── report.summarize() ◀───────────────────────────────┘
                              result card   + history.add()
```

## 1. Spotting the Shift+drag (`trigger.py`)

`DropDialWatcher` polls the global input state every 15 ms with a `QTimer`. Polling needs no admin rights and
can't stall the system the way a broken input hook can.

- **Windows:** `GetAsyncKeyState` for the left button, the trigger key and Escape.
- **macOS:** `NSEvent.pressedMouseButtons` and `modifierFlags` (`platform_mac.py`). No Accessibility or Input
  Monitoring permission is needed.
- **Linux (X11):** `XQueryPointer` and `XQueryKeymap` through libX11 with ctypes (`platform_linux.py`). Wayland
  doesn't expose global input, so there the trigger is off and the other ways in (below) still work.

When the left button is held, the mouse has moved at least 10 px and the trigger key (Shift, Ctrl or Alt, chosen
in Settings) is down, the watcher emits `show_menu`. Tapping the key again while the dial is open flips to the next
ring (Convert → Tools → Recipes). If no file drag reaches the dial (the user was moving a window or selecting text),
it hides itself again.

## 2. The dial (`radial.py`, `glass.py`, `liquid.py`)

`RadialMenu.popup()` moves the dial to the cursor and, **before** it appears, takes a snapshot of the screen behind
it. On macOS this uses `CGWindowListCreateImage` to capture what is below the drag window, so Finder's drag picture
stays out. On Windows and X11 the drag image is hidden or painted over during capture.

A blurred copy of the snapshot is drawn at once. In parallel a `QRunnable` on the thread pool runs `liquid.py`,
which refracts the snapshot through the dial's shape (edge lensing, colour fringing, a specular rim). It replaces
the quick version about 60 ms later. `glass.py` holds the shared look: blur, tints, the stylesheet, and helpers
used by every DropDial window.

## 3. Getting the dragged files

The dial is an ordinary drop target, so the files arrive through the OS's drag and drop (`dragEnterEvent`,
`dropEvent`). Two details make it feel instant:

- **macOS:** the watcher also reads the drag pasteboard (`platform_mac.drag_files`), so the right slices show
  before the cursor even touches the dial.
- **Windows and X11:** the OS only tells a window about a drag once the mouse moves over it, so the dial nudges the
  cursor by 1 px and back.

Drops are always accepted as *copy*, so a Shift (move) drop can never delete the original. Drags from a web browser
carry a URL rather than a file. `web.py` turns them into `WebItem`s, and the file is downloaded to the Downloads
folder only after a slice is picked.

`DropDialApp.build_rings()` decides what the rings contain for the dragged files: built-in categories from
`util.category()`, plug-in families from `formats/`, tools, and the recipes that fit.

## 4. Running the action (`app.py`)

A drop calls `DropDialApp.activate()`, which downloads any browser items first and then calls `run_item()`. That
picks the work: a conversion, a tool, a recipe, a plug-in family's convert or tool, or an editor window from
`tools.py` (Crop, Annotate, Redact and others open a window first and save when the user confirms).

The work runs as a `Job` (a `QRunnable`) on `QThreadPool.globalInstance()`, so the UI never blocks. A result card
from `toasts.py` shows a spinner and progress while it runs. When the job finishes:

1. `report.summarize()` turns sources and outputs into a short summary ("2.4 MB → 610 KB · 75% smaller").
2. `history.add()` records it (JSON lines in the data folder) for the History window and Undo.
3. The card shows the result with Open, Show in folder and Undo. Errors appear on the card too; a
   `util.UserError` message is shown as-is.

## 5. Engines

These modules never import Qt at module level, take paths, and return the list of files they wrote:

| Module | Handles |
|---|---|
| `convert.py` | Format conversions for images, PDF, Word, text, SVG and e-books |
| `imaging.py` | Image and PDF processing behind the tools (compress, resize, watermark, protect…) |
| `media.py` | Video and audio through ffmpeg (`$DROPDIAL_FFMPEG`, then `PATH`, then the `imageio-ffmpeg` copy) |
| `formats/` | Plug-in families (spreadsheets, data, archives, fonts, raw images…), one module each, registered with `formats.register(Family(...))`. See [ADDING-A-CONVERTER.md](ADDING-A-CONVERTER.md) |
| `recipes.py` | Several steps on temporary copies; only the final result is written. Recipes are plain JSON |

Every output path comes from `util.sibling()`. It follows the "where results go" setting (next to the original or a
`DropDial` subfolder) and adds `(1)`, `(2)`… instead of overwriting anything.

## 6. Other ways in

All of these end up in the same `run_item()` or engines:

- **Home window** (`home.py`): opens from the tray. Dropping files or browser items there, or clicking to pick a
  file, shows the dial in click mode.
- **Right-click → DropDial, Send to, Open With:** a second launch with file paths. `handoff.py` passes them to the
  running copy over a local socket (a named pipe on Windows) before Qt is even imported, then exits.
- **Watch folders** (`watch.py`): the app polls each folder every 2 seconds and processes new files once their size
  stops changing.
- **Command line** (`cli.py`): `dropdial convert *.heic --to jpg` and friends call the engines directly, without Qt.
  `__main__.py` decides between the command line, a hand-off and the app.
- **Update check** (`updates.py`): shortly after start, then every 6 hours, a background job reads the GitHub
  releases list and the tray menu shows "Update available" when a newer semver tag exists. It can be turned off in
  Settings, or with `DROPDIAL_NO_UPDATE_CHECK=1`.

Settings live in `QSettings`. Recipes, history and watch rules live in the data folder (`util.data_dir()`, or
`$DROPDIAL_HOME` when set, which the tests use). The log is `log.txt` in `%LOCALAPPDATA%\DropDial` (Windows),
`~/Library/Logs/DropDial` (macOS) or `~/.local/share/DropDial` (Linux).

## 7. Packaging

- **PyInstaller** (`DropDial.spec`, entry point `run.py`) builds a folder app on every OS, a single portable
  `DropDial.exe` when `ONEFILE=1`, and `DropDial.app` on macOS. It bundles Qt, pillow-heif and the ffmpeg binary.
- **Windows installer:** Inno Setup (`installer/DropDial.iss`) makes a per-user `DropDial-Setup.exe` with the Start
  menu entry, start with Windows, the right-click entry and Send to.
- **Linux:** `packaging/linux/build-deb.sh` wraps the PyInstaller folder into `DropDial-linux-amd64.deb`, built on
  Debian 12 so it runs on Debian 12+ and Ubuntu 23.04+.
- **macOS:** a branded DMG made with `create-dmg` (falling back to plain `hdiutil`), plus `install-mac.sh` for the
  one-line Terminal install. Signing and notarization run only when signing credentials are configured; see
  [MAC-SIGNING.md](MAC-SIGNING.md).

## 8. Continuous integration

| Workflow | What it does |
|---|---|
| `ci.yml` | Quick check on Windows, macOS and Linux: compile, command-line smoke test, `pytest` |
| `build.yml` | Runs the tests, builds every package, self-tests them (`--selftest`), installs and uninstalls the Windows Setup and the .deb, runs the Linux end-to-end test on XFCE, then publishes: pushes to `main` update the rolling "latest" release, and `v*` tags publish a versioned release |
| `e2e.yml`, `e2e-mac.yml` | Drive the real app on a Windows and a macOS desktop with scripted Shift+drags (`demo/e2e_*.py`) and check every output file |
| `demo.yml` | Records the demo video on Windows |
