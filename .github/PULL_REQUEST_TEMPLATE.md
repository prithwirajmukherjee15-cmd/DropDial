## What does this change, and why?

<!-- A sentence or two. Link the issue if there is one, for example: Fixes #123 -->

## How was it tested?

- Operating system(s) you tried it on: <!-- Windows 11, macOS 15, Debian 12 (X11)… -->
- Tests added or changed: <!-- which test files, or why no test was needed -->
- What you tried in the app: <!-- the file you dropped, the slice you picked, what came out -->

## Screenshots

<!-- For changes to the dial, a window or a result card. Drag images into this box. -->

## Checklist

- [ ] `python -m pytest -q` passes (`QT_QPA_PLATFORM=offscreen` on Linux)
- [ ] New tests check the output's content, and build their input files in `tmp_path` (no binary fixtures)
- [ ] Inputs are never overwritten: outputs use `util.sibling`
- [ ] Problems the user can fix raise `util.UserError` with one friendly sentence
- [ ] New dependencies are in `requirements.txt` and still bundle with `DropDial.spec`
- [ ] The pull request does one thing (unrelated changes go in a separate one)
