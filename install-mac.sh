#!/bin/bash
# DropDial installer for macOS.
#   curl -fsSL https://raw.githubusercontent.com/prithwirajmukherjee15-cmd/dragshift/main/install-mac.sh | bash
# Downloads the right build for this Mac from the latest GitHub release, installs it to
# /Applications and opens it. Files fetched by curl aren't marked "downloaded from the
# internet", so macOS doesn't show the "could not verify" warning. Read it first if you like —
# it's short.
set -euo pipefail

REPO="prithwirajmukherjee15-cmd/dragshift"
case "$(uname -m)" in
  arm64) ASSET="DropDial-mac-apple-silicon.dmg" ;;
  *)     ASSET="DropDial-mac-intel.dmg" ;;
esac
URL="https://github.com/$REPO/releases/latest/download/$ASSET"
TMP="$(mktemp -d)"
trap 'hdiutil detach "$TMP/mnt" -quiet 2>/dev/null || true; rm -rf "$TMP"' EXIT

echo "→ Downloading $ASSET"
curl -fL --progress-bar "$URL" -o "$TMP/DropDial.dmg"

echo "→ Installing to /Applications"
hdiutil attach "$TMP/DropDial.dmg" -mountpoint "$TMP/mnt" -nobrowse -quiet
osascript -e 'quit app "DropDial"' 2>/dev/null || true
pkill -x DropDial 2>/dev/null || true
DEST="/Applications/DropDial.app"
if [ -w /Applications ]; then
  rm -rf "$DEST"; ditto "$TMP/mnt/DropDial.app" "$DEST"
else
  sudo rm -rf "$DEST"; sudo ditto "$TMP/mnt/DropDial.app" "$DEST"
fi
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

echo "→ Opening DropDial (look for it in the menu bar)"
open "$DEST"
echo "✓ Done. Drag any file in Finder and press Shift."
