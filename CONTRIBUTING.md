# Contributing to DropDial

Thanks for your interest in DropDial. Bug reports, format ideas, fixes and new converters are all welcome.
This page explains how to get set up and what a good change looks like.

## Reporting a bug or asking for a format

Please use the issue forms. They ask for the details that make a problem quick to fix.

- **[Bug report](https://github.com/prithwirajmukherjee15-cmd/DropDial/issues/new?template=bug_report.yml)**:
  something broke, a result looks wrong, or the dial doesn't open.
- **[Format request](https://github.com/prithwirajmukherjee15-cmd/DropDial/issues/new?template=format_request.yml)**:
  a file type DropDial can't read or write yet.
- **[Feature request](https://github.com/prithwirajmukherjee15-cmd/DropDial/issues/new?template=feature_request.yml)**:
  a new tool, recipe step or setting.

Found a security problem? Please don't open a public issue. See [SECURITY.md](SECURITY.md).

Before you open a bug, check that it still happens in the
[latest release](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest), and search the existing issues.

## Development setup

You need Python 3.12 (the version CI uses) and Git. Everything else comes from `requirements.txt`, including a
copy of ffmpeg (through `imageio-ffmpeg`), so video and audio work without a separate install.

### Windows

```powershell
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pytest
python -m dropdial
```

### macOS

```bash
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
python -m dropdial
```

macOS may ask to give your terminal **Screen Recording** permission. It's optional: it only lets the glass show
the windows behind the dial. Without it you see your wallpaper instead.

### Linux

```bash
sudo apt install python3-venv libxcb-cursor0 libxkbcommon-x11-0
git clone https://github.com/prithwirajmukherjee15-cmd/DropDial.git
cd DropDial
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
python -m dropdial
```

The Shift-while-dragging trigger needs an X11 session. On Wayland you can still test everything through the tray
icon, Home, the command line and `python -m dropdial some-file.jpg`.

### Running the app and the command line

- `python -m dropdial` starts the app. It lives in the tray (menu bar on macOS).
- `python -m dropdial photo.jpg` opens the dial for that file without dragging.
- `python -m dropdial --help` lists the command-line tools, such as `python -m dropdial convert a.heic --to jpg`.
- Errors are written to a log file: `%LOCALAPPDATA%\DropDial\log.txt` on Windows,
  `~/Library/Logs/DropDial/log.txt` on macOS and `~/.local/share/DropDial/log.txt` on Linux.

### Running the tests

On Linux, run Qt without a screen:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

On Windows and macOS, plain `python -m pytest -q` works. Set `QT_QPA_PLATFORM=offscreen` there too if you'd
rather not see test windows flash by.

Tests never touch your real recipes, history or watch folders: `tests/conftest.py` points `DROPDIAL_HOME` at a
temporary folder for every test.

## Project layout

```
dropdial/
  app.py          the tray app: builds the dial's rings, runs the picked action as a background job
  trigger.py      watches the global mouse and Shift key to spot a Shift+drag
  radial.py       the dial itself: rings, slices, drag and drop, hit testing
  glass.py        the glass look shared by the dial and every window (blur, rim, styles)
  liquid.py       the liquid-glass renderer (refracts a snapshot of the screen behind the dial)
  convert.py      format conversions for images, PDFs, Word, text, SVG and e-books
  imaging.py      image and PDF processing behind the tools (no UI, so it's easy to test)
  media.py        video and audio through ffmpeg
  formats/        plug-in file families (spreadsheets, archives, fonts…), one module each
  recipes.py      several steps in one drop, stored as plain JSON
  watch.py        watch folders (polling, so it works the same everywhere)
  history.py      the list of everything DropDial made, with undo
  cli.py          the command line; it never imports Qt
  home.py         the Home window: a drop zone and recent results
  web.py          files dragged out of a web browser (downloads them first)
  updates.py      the update check against GitHub releases
  tools.py        editor windows: Compress, Resize, Crop, Edit, Annotate, Redact…
  toasts.py       the result cards in the corner
  panels.py       History, Recipes and Watch folders windows
  settings.py     settings storage and the Settings and Welcome windows
  report.py       turns "what just happened" into the short text on a result card
  util.py         shared helpers: output paths, file categories, UserError
  platform_mac.py / platform_linux.py   OS-specific input, screen capture and start at login
demo/             end-to-end scripts that drive a real desktop (Windows, macOS, Linux) in CI
packaging/        Linux .deb build, macOS DMG background, README art scripts
installer/        Windows installer (Inno Setup), version info, macOS entitlements
tests/            the pytest suite
```

[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) explains how these pieces fit together.

## Coding style

- Follow PEP 8, with lines up to 120 characters.
- Add type hints to new functions.
- Import heavy libraries (PySide6, PyMuPDF, numpy, Pillow plugins and so on) **inside** the functions that need
  them. Many modules load when the app starts, and the command line must stay fast and free of Qt.
- Errors the user can fix should raise `util.UserError` with one short, friendly sentence. For example:
  "Only web links (http/https) can be downloaded." The message is shown as-is on the result card or in the
  terminal, so leave out tracebacks and jargon.
- Never overwrite or change an input file. Build every output path with `util.sibling(src, ...)`. It follows the
  "where results go" setting and picks a new name if the file already exists.
- Keep UI code out of the engines (`convert.py`, `imaging.py`, `media.py`, `recipes.py`, `watch.py`, `formats/`),
  so the command line, watch folders and tests can use them.
- Write comments in English, and explain *why* when the code alone doesn't make it clear.

## Adding a file format

New formats usually go in a new module under `dropdial/formats/`. Each module registers a family with its
extensions, targets and tools, and the dial, command line, watch folders and `dropdial formats` pick it up
automatically. Read [docs/ADDING-A-CONVERTER.md](docs/ADDING-A-CONVERTER.md) for the full walkthrough.

If the format needs a new dependency, add it to `requirements.txt` and check that the PyInstaller build in
`DropDial.spec` still bundles it.

## Tests

Every change in behaviour should come with a test.

- **Check the output, not just that a file exists.** Open the result with a different library than the one that
  wrote it, and check what matters: pixel colours, page count, text, duration, that metadata is really gone.
- **No binary fixtures in the repository.** Generate inputs inside the test, in pytest's `tmp_path`: draw an image
  with Pillow, build a PDF with PyMuPDF, make a short clip with ffmpeg.
- **Skip, don't fail, when an optional tool is missing.** Use `pytest.skip` or `pytest.mark.skipif` (see
  `needs_ffmpeg` in the existing tests).
- **No network.** Tests that need a server start a local one.
- Keep tests fast. CI runs the suite on Windows, macOS and Linux for every push.

The scripts in `demo/` drive the real app on real desktops in CI. You don't need to run them locally, but if your
change affects the dial or dragging, look at the end-to-end results on your pull request.

## Commits and pull requests

1. Fork the repository and create a branch from `main`.
2. Make one change per pull request. Unrelated fixes are easier to review on their own.
3. Write commit messages in the imperative, with a short first line: "Add RAW to JPG conversion",
   "Fix crop handles on high-DPI screens".
4. Run the tests on your OS before you push.
5. Open the pull request and fill in the template. Say which OS you tried it on. Add a screenshot for UI changes.

CI must pass before a pull request is merged. If a test fails only on an OS you don't have, say so in the pull
request and we'll work it out together.

## Releasing (maintainer)

1. Bump the version in every place it appears:
   - `__version__` in `dropdial/__init__.py`
   - `CFBundleShortVersionString`, `CFBundleVersion` and `CFBundleGetInfoString` in `DropDial.spec`
   - `filevers`, `prodvers`, `FileVersion` and `ProductVersion` in `installer/version_info.txt`
   - the fallback `AppVersion` in `installer/DropDial.iss`, and the version passed to `build-deb.sh` in
     `.github/workflows/build.yml`
2. Add a `## x.y.z` section at the top of `CHANGELOG.md` describing what changed, in plain words.
3. Merge to `main`, then tag and push:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

4. The build workflow tests and builds every platform and publishes the GitHub release with the downloads.

Tags must be semantic versions with a `v` prefix (`v1.2.0`). The app's update notice reads GitHub releases,
ignores drafts and pre-releases, and compares the version in the tag with its own `__version__`.

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Licence

DropDial is released under the [MIT License](LICENSE). By contributing, you agree that your contribution is
released under the same licence.
