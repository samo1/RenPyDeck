#!/usr/bin/env bash
#
# Build a single-file Flatpak bundle (RenPyDeck.flatpak) for the Steam Deck.
#
# This uses plain `flatpak` (build-init / build / build-finish / build-export /
# build-bundle) rather than flatpak-builder, so the only prerequisites are the
# matching GNOME Platform and SDK:
#
#   flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
#
# Output: dist/RenPyDeck.flatpak — copy this single file to the Steam Deck and
# install it with:  flatpak install --user RenPyDeck.flatpak
#
set -euo pipefail

APP_ID="sk.meluzina.RenPyDeck"
APP_BRANCH="stable"
RUNTIME_VERSION="49"
SDK="org.gnome.Sdk"
RUNTIME="org.gnome.Platform"

# Resolve paths relative to the project root (parent of this script's dir).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BUILD_DIR="$PROJECT_ROOT/build/flatpak-build"
REPO_DIR="$PROJECT_ROOT/build/flatpak-repo"
DIST_DIR="$PROJECT_ROOT/dist"
BUNDLE="$DIST_DIR/RenPyDeck.flatpak"

echo ">> Cleaning previous build artifacts"
rm -rf "$BUILD_DIR" "$REPO_DIR"
mkdir -p "$DIST_DIR"

echo ">> Initialising build directory"
flatpak build-init "$BUILD_DIR" "$APP_ID" "$SDK" "$RUNTIME" "$RUNTIME_VERSION"

echo ">> Installing application files into /app"
# Python package -> /app/share/renpydeck/renpydeck (importable via launcher's PYTHONPATH)
install -d "$BUILD_DIR/files/share/renpydeck"
cp -r "$PROJECT_ROOT/src/renpydeck" "$BUILD_DIR/files/share/renpydeck/renpydeck"
# Leave local bytecode behind: it is stale the moment the runtime's Python
# differs from the one that produced it, and it only bloats the bundle.
find "$BUILD_DIR/files/share/renpydeck" -name __pycache__ -type d -prune \
    -exec rm -rf {} +

# Launcher -> /app/bin/renpydeck
install -Dm755 "$SCRIPT_DIR/renpydeck.sh" "$BUILD_DIR/files/bin/renpydeck"

# Desktop entry -> /app/share/applications/<app-id>.desktop
install -Dm644 "$SCRIPT_DIR/$APP_ID.desktop" \
    "$BUILD_DIR/files/share/applications/$APP_ID.desktop"

# AppStream metainfo -> /app/share/metainfo/<app-id>.metainfo.xml
install -Dm644 "$SCRIPT_DIR/$APP_ID.metainfo.xml" \
    "$BUILD_DIR/files/share/metainfo/$APP_ID.metainfo.xml"

# Icon -> /app/share/icons/hicolor/scalable/apps/<app-id>.svg
install -Dm644 "$SCRIPT_DIR/$APP_ID.svg" \
    "$BUILD_DIR/files/share/icons/hicolor/scalable/apps/$APP_ID.svg"

echo ">> Composing AppStream catalog data (what software stores read)"
# The metainfo file alone is not what a store sees. `flatpak build-export` and
# `build-bundle` pick up the *catalog* form of it — files/share/app-info/xmls
# plus the rasterised icons beside it — and only that is carried inside the
# single-file bundle. Without this step KDE Discover has nothing to go on and
# shows the app with no author, no description and no icon.
#
# appstreamcli lives in the SDK, so no host package is needed. It loads the
# icon through glycin, which isolates image decoding in a sandbox of its own
# via flatpak-spawn; that needs the session bus and the Flatpak portal, hence
# the two extra options — without them the SVG fails to load and the catalog
# comes out empty.
flatpak build --socket=session-bus --talk-name=org.freedesktop.Flatpak \
    "$BUILD_DIR" \
    appstreamcli compose \
        --no-net \
        --prefix=/app \
        --origin="$APP_ID" \
        --result-root=/ \
        --data-dir=/app/share/app-info/xmls \
        --icons-dir=/app/share/app-info/icons/flatpak \
        /

echo ">> Finishing build (declaring sandbox permissions)"
# The sound socket is for the games, not for RenPyDeck itself, which is silent:
# a game started without it comes up mute ("PulseAudio: Unable to connect").
# The name is historical — it is the same socket PipeWire serves on SteamOS.
#
# ~/.renpy is where every Ren'Py game keeps its saves and, since Ren'Py 8.3,
# the key it signs them with (~/.renpy/tokens/security_keys.txt). Without the
# real folder the sandbox hands the game a throwaway one: saves made here are
# gone when the app exits, and a save made outside the launcher is refused as
# "created on another computer". Shared, a game plays the same either way.
flatpak build-finish "$BUILD_DIR" \
    --command=renpydeck \
    --share=ipc \
    --socket=wayland \
    --socket=fallback-x11 \
    --socket=pulseaudio \
    --device=dri \
    --filesystem=xdg-download \
    --filesystem=~/.renpy:create

echo ">> Exporting build to a local repo"
flatpak build-export "$REPO_DIR" "$BUILD_DIR" "$APP_BRANCH"

echo ">> Creating single-file bundle: $BUNDLE"
flatpak build-bundle "$REPO_DIR" "$BUNDLE" "$APP_ID" "$APP_BRANCH"

echo
echo ">> Done."
echo "   Bundle: $BUNDLE"
echo
echo "   Copy it to the Steam Deck and install with:"
echo "       flatpak install --user RenPyDeck.flatpak"
echo "   Then run it with:"
echo "       flatpak run $APP_ID"
