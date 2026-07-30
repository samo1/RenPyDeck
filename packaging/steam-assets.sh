#!/usr/bin/env bash
#
# Render the artwork Steam shows for RenPyDeck when it is added as a non-Steam
# game. Everything is drawn from the same motif as the application icon, so the
# library tile, the banner and the logo look like one thing.
#
# Output: dist/steam-assets/ — five PNGs, each named after what Steam calls it
# and the size it wants:
#
#   grid-600x900.png      the tile in the library grid (and in Game Mode)
#   capsule-920x430.png   the wide capsule, e.g. for the most recent game
#   hero-1920x620.png     the banner across the top of the game's page
#   logo-1280x720.png     transparent wordmark, drawn over the hero
#   icon-256x256.png      the small icon in list views and the shortcut
#
# The same five are then packed into dist/RenPyDeck-steam-assets.zip, which is
# the single file to attach to a release: the images are generated rather than
# committed, so a release is where users get them.
#
# Requires: rsvg-convert (librsvg).
#   Fedora/SteamOS: sudo dnf install librsvg2-tools
#   Debian/Ubuntu:  sudo apt install librsvg2-bin
#   Arch:           sudo pacman -S librsvg
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$PROJECT_ROOT/dist/steam-assets"
BUNDLE="$PROJECT_ROOT/dist/RenPyDeck-steam-assets.zip"

if ! command -v rsvg-convert >/dev/null; then
    echo "rsvg-convert is required (package librsvg2-tools / librsvg2-bin)." >&2
    exit 1
fi

# Start from an empty folder, so a renamed or dropped asset cannot linger and
# end up in the release archive.
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# The application icon's palette, so every asset matches the app itself.
BLUE_LIGHT="#3584e4"
BLUE_DARK="#1c4fa0"
INK_TOP="#1f232b"
INK_BOTTOM="#101319"
# Cantarell is GNOME's UI font; the rest are fallbacks for other machines.
FONT="Cantarell, Inter, DejaVu Sans, sans-serif"

# render <file> <width> <height>  — SVG source arrives on stdin.
render() {
    local name="$1" width="$2" height="$3"
    rsvg-convert --width "$width" --height "$height" \
        --output "$OUT_DIR/$name" /dev/stdin
    echo "   $name  (${width}x${height})"
}

# The icon mark: rounded blue tile, play triangle, deck bar underneath. Drawn
# in a 128-unit box so it can be placed at any size with a transform.
mark() {
    cat <<SVG
    <g transform="$1">
      <rect x="8" y="8" width="112" height="112" rx="24" fill="url(#tile)"/>
      <path d="M52 40 L92 64 L52 88 Z" fill="#ffffff"/>
      <rect x="36" y="98" width="56" height="8" rx="4" fill="#ffffff" opacity="0.85"/>
    </g>
SVG
}

# Gradients shared by every asset.
defs() {
    cat <<SVG
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="$BLUE_LIGHT"/>
      <stop offset="1" stop-color="$BLUE_DARK"/>
    </linearGradient>
    <linearGradient id="ink" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="$INK_TOP"/>
      <stop offset="1" stop-color="$INK_BOTTOM"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.42" r="0.62">
      <stop offset="0" stop-color="$BLUE_LIGHT" stop-opacity="0.42"/>
      <stop offset="1" stop-color="$BLUE_LIGHT" stop-opacity="0"/>
    </radialGradient>
    <!-- The hero's own glow, off to one side and faded out well before the
         edges: on a shape narrower than the gradient the fall-off gets cut
         off and the cut shows up as an arc. -->
    <radialGradient id="glowWide" cx="0.72" cy="0.45" r="0.55">
      <stop offset="0" stop-color="$BLUE_LIGHT" stop-opacity="0.38"/>
      <stop offset="1" stop-color="$BLUE_LIGHT" stop-opacity="0"/>
    </radialGradient>
  </defs>
SVG
}

echo ">> Writing Steam artwork to $OUT_DIR"

# -- The library tile: portrait, the one Game Mode shows -------------------
render grid-600x900.png 600 900 <<SVG
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900">
  $(defs)
  <rect width="600" height="900" fill="url(#ink)"/>
  <rect width="600" height="900" fill="url(#glow)"/>
  $(mark "translate(150 210) scale(2.34)")
  <text x="300" y="690" text-anchor="middle" font-family="$FONT"
        font-size="76" font-weight="800" fill="#ffffff">RenPyDeck</text>
  <text x="300" y="746" text-anchor="middle" font-family="$FONT"
        font-size="30" font-weight="500" fill="#ffffff" opacity="0.62">Ren'Py games, ready to play</text>
  <rect x="240" y="792" width="120" height="6" rx="3" fill="$BLUE_LIGHT" opacity="0.9"/>
</svg>
SVG

# -- The wide capsule ------------------------------------------------------
render capsule-920x430.png 920 430 <<SVG
<svg xmlns="http://www.w3.org/2000/svg" width="920" height="430" viewBox="0 0 920 430">
  $(defs)
  <rect width="920" height="430" fill="url(#ink)"/>
  <rect width="920" height="430" fill="url(#glow)"/>
  $(mark "translate(72 87) scale(2.0)")
  <text x="368" y="216" font-family="$FONT" font-size="72"
        font-weight="800" fill="#ffffff">RenPyDeck</text>
  <text x="372" y="266" font-family="$FONT" font-size="28"
        font-weight="500" fill="#ffffff" opacity="0.62">Ren'Py games, ready to play</text>
</svg>
SVG

# -- The hero banner: background only, the logo is drawn over it -----------
render hero-1920x620.png 1920 620 <<SVG
<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="620" viewBox="0 0 1920 620">
  $(defs)
  <rect width="1920" height="620" fill="url(#ink)"/>
  <rect width="1920" height="620" fill="url(#glowWide)"/>
  <!-- The play mark alone, well inside the frame: Steam crops the hero at
       several aspect ratios, and a shape that touches an edge looks cut. -->
  <g opacity="0.13" transform="translate(912 -266) scale(9)">
    <path d="M52 40 L92 64 L52 88 Z" fill="#ffffff"/>
  </g>
  <rect y="612" width="1920" height="8" fill="$BLUE_LIGHT" opacity="0.55"/>
</svg>
SVG

# -- The logo: transparent, sits on top of the hero ------------------------
render logo-1280x720.png 1280 720 <<SVG
<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  $(defs)
  $(mark "translate(268 236) scale(1.6)")
  <text x="500" y="392" font-family="$FONT" font-size="118"
        font-weight="800" fill="#ffffff">RenPyDeck</text>
  <text x="506" y="452" font-family="$FONT" font-size="38"
        font-weight="500" fill="#ffffff" opacity="0.66">Ren'Py games, ready to play</text>
</svg>
SVG

# -- The small icon --------------------------------------------------------
render icon-256x256.png 256 256 < "$SCRIPT_DIR/sk.meluzina.RenPyDeck.svg"

# -- One archive to attach to a release ------------------------------------
# Packed with Python's zipfile rather than the `zip` command: Python is a given
# in this project, another tool is not. The folder goes in whole, so unpacking
# gives a tidy steam-assets/ rather than five loose files.
echo ">> Packing $(basename "$BUNDLE")"
rm -f "$BUNDLE"
python3 -m zipfile -c "$BUNDLE" "$OUT_DIR"

echo
echo ">> Done."
echo "   Images:  $OUT_DIR"
echo "   Archive: $BUNDLE  (attach this to the release)"
echo
echo "   In Steam: right-click RenPyDeck in your library and use"
echo "   Manage → Set custom artwork for each image."
