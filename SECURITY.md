# Security policy

## Supported versions

Security fixes go into the
[latest release](https://github.com/prithwirajmukherjee15-cmd/DropDial/releases/latest) only. DropDial tells you
when a newer version is out, so please check that the problem still happens in the latest release before you
report it.

## Reporting a vulnerability

Please don't report security problems in a public issue.

Report them privately instead:

1. Open the [Security tab](https://github.com/prithwirajmukherjee15-cmd/DropDial/security) of the repository.
2. Click **Report a vulnerability**.
3. Describe the problem and send the report.

It helps to include:

- your DropDial version and operating system;
- what an attacker could do, and what they need for it (for example, "the user drops a file I sent them");
- the steps that show the problem. If a crafted file triggers it, attach it or explain how to make one.

## What to expect

- You'll get a first reply within a week, usually sooner.
- Once the problem is confirmed, the fix is worked on privately and released as soon as it's ready.
- When the fix is out, the advisory is published. You're credited in it unless you'd rather not be.
- If the report turns out not to be a security problem, you'll get an explanation, and it may move to a normal
  issue with your agreement.

DropDial is a small project looked after by one person, so please allow a little time.

## Scope

**Files DropDial opens are untrusted input.** People drop files they downloaded or were sent. These are in scope:

- **Archives:** extracting ZIP, 7Z or TAR files writes outside its output folder, creates a link or device file,
  or gets past the size limits meant to stop zip bombs.
- **XML and markup:** SVG, Word documents, e-books, spreadsheets and other XML-based files that make DropDial read
  local files, reach the network or use huge amounts of memory.
- **Documents and images:** a PDF, Word file, e-book or image that makes DropDial run code, crash in a way you can
  control, or write somewhere other than its output folder.
- **Overwriting data:** any way to make DropDial change or replace an original file, or write over an existing file.
  It should only ever create new files.
- **Network code:** the update check and the download of files dragged from a web browser. These are the only parts
  of DropDial that talk to the network.
- **Local entry points:** the command line, watch folders, recipes (which are plain JSON and may be shared), and
  the right-click / "Send to" hand-off to the running app.

**Out of scope:**

- Bugs inside the libraries DropDial uses (Qt, Pillow, PyMuPDF, ffmpeg and others) that DropDial can't work around.
  Please report those to the library's own project. Do tell us if DropDial should require a newer, fixed version.
- The Windows SmartScreen and macOS Gatekeeper warnings. They appear because releases aren't code-signed yet. See
  [First launch](README.md#first-launch).
- Attacks that need someone who can already run programs as you on your computer.

## What DropDial does on the network

DropDial converts files on your own computer. It never uploads your files, and it has no telemetry, analytics or
crash reporting.

It connects to the internet in two cases only:

1. **Update check.** Shortly after it starts, and then every few hours, DropDial asks `api.github.com` for the list
   of DropDial releases. Nothing about you or your files is sent. Turn it off in **Settings → Check for updates
   automatically**.
2. **Files dragged from a web browser.** If you drag a picture or a link out of a browser and drop it on the dial,
   DropDial downloads that one file into your Downloads folder, then converts it. Only `http` and `https` links are
   downloaded, and nothing happens until you drop it on a slice.

A few buttons open a page in your own web browser, such as the project page, a release page, or a map of a photo's
GPS location. DropDial itself sends nothing in those cases.
