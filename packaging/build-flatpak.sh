#!/usr/bin/env bash
#
# Build a single-file Flatpak bundle (RenPyDeck.flatpak) for the Steam Deck.
#
# This uses plain `flatpak` (build-init / build-finish / build-export /
# build-bundle) rather than flatpak-builder. Prerequisites are the matching
# GNOME Platform and SDK, and AppStream's compose addon on the host:
#
#   flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
#   sudo dnf install appstream-compose    # Debian/Ubuntu: appstream-compose too
#
# Output: dist/RenPyDeck.flatpak — copy this single file to the Steam Deck and
# install it with:  flatpak install --user RenPyDeck.flatpak
# The Flatpak repository it is bundled from is left in build/flatpak-repo.
#
# Two optional environment variables turn a local build into a release build
# (see .github/workflows/release.yml):
#
#   RENPYDECK_GPG_KEY   GPG key id to sign the repository with (looked up in
#                       $GNUPGHOME). Flatpak refuses to add an unsigned remote
#                       without extra flags, so a published repository is
#                       always signed.
#   RENPYDECK_REPO_URL  URL the repository will be published at. The bundle
#                       records it, together with the signing key, so an
#                       install from the bundle receives updates from there.
#                       Needs RENPYDECK_GPG_KEY.
#
set -euo pipefail

if ! appstreamcli compose --help > /dev/null 2>&1; then
    echo "appstreamcli compose is not available; install AppStream's compose addon" \
        "(the appstream-compose package)" >&2
    exit 1
fi

GPG_KEY="${RENPYDECK_GPG_KEY:-}"
REPO_URL="${RENPYDECK_REPO_URL:-}"
if [ -n "$REPO_URL" ] && [ -z "$GPG_KEY" ]; then
    echo "RENPYDECK_REPO_URL needs RENPYDECK_GPG_KEY: a published repository must be signed" >&2
    exit 1
fi
GPG_SIGN=()
[ -n "$GPG_KEY" ] && GPG_SIGN=(--gpg-sign="$GPG_KEY")

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

# Licence text -> /app/share/licenses/<app-id>/LICENSE
# The GPL asks for its terms to travel with the binary, and the bundle is the
# only thing a user of the Deck receives; the store shows the name of the
# licence from <project_license> in the metainfo, not this file.
install -Dm644 "$PROJECT_ROOT/LICENSE" \
    "$BUILD_DIR/files/share/licenses/$APP_ID/LICENSE"

echo ">> Composing AppStream catalog data (what software stores read)"
# The metainfo file alone is not what a store sees. `flatpak build-export` and
# `build-bundle` pick up the *catalog* form of it — files/share/app-info/xmls
# plus the rasterised icons beside it — and only that is carried inside the
# single-file bundle. Without this step KDE Discover has nothing to go on and
# shows the app with no author, no description and no icon.
#
# This runs on the host, against the build's files, the way flatpak-builder
# does it. appstreamcli decodes the icon through glycin, which sandboxes image
# loaders; inside a `flatpak build` sandbox it has to go through the Flatpak
# portal for that, which fails outside a desktop session (on CI the SVG cannot
# be read and the catalog comes out empty), while on the host it uses
# bubblewrap directly.
appstreamcli compose \
    --no-net \
    --prefix=/ \
    --origin="$APP_ID" \
    --result-root="$BUILD_DIR/files" \
    --data-dir="$BUILD_DIR/files/share/app-info/xmls" \
    --icons-dir="$BUILD_DIR/files/share/app-info/icons/flatpak" \
    "$BUILD_DIR/files"

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
flatpak build-export "${GPG_SIGN[@]}" "$REPO_DIR" "$BUILD_DIR" "$APP_BRANCH"

# The repository-wide metadata a client copies into its remote configuration
# when the repository is added, and the signed summary that lists what is in
# it. The appstream branch generated here is what Discover reads to show the
# app before it is installed.
flatpak build-update-repo "${GPG_SIGN[@]}" \
    --title="RenPyDeck" \
    --comment="Game manager and launcher for Ren'Py games on the Steam Deck" \
    --homepage="https://github.com/samo1/RenPyDeck" \
    --default-branch="$APP_BRANCH" \
    "$REPO_DIR"

echo ">> Creating single-file bundle: $BUNDLE"
# --runtime-repo lets installing the bundle fetch the GNOME runtime from
# Flathub on its own when it is missing.
BUNDLE_OPTIONS=(--runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo)
if [ -n "$REPO_URL" ]; then
    GPG_PUBLIC_KEY="$PROJECT_ROOT/build/signing-key.gpg"
    gpg --export "$GPG_KEY" > "$GPG_PUBLIC_KEY"
    BUNDLE_OPTIONS+=(--repo-url="$REPO_URL" --gpg-keys="$GPG_PUBLIC_KEY")
fi
flatpak build-bundle "${BUNDLE_OPTIONS[@]}" "$REPO_DIR" "$BUNDLE" "$APP_ID" "$APP_BRANCH"

echo
echo ">> Done."
echo "   Bundle: $BUNDLE"
echo
echo "   Copy it to the Steam Deck and install with:"
echo "       flatpak install --user RenPyDeck.flatpak"
echo "   Then run it with:"
echo "       flatpak run $APP_ID"
