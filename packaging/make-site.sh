#!/usr/bin/env bash
#
# Lay out the website that publishes RenPyDeck's Flatpak repository.
#
# Usage: packaging/make-site.sh SITE_DIR SITE_URL
#
# Run after a signed release build (build-flatpak.sh with RENPYDECK_GPG_KEY
# set); the key id is read from that same variable to embed its public half.
# SITE_URL is where SITE_DIR will be served from, with a trailing slash, e.g.
# https://samo1.github.io/RenPyDeck/. The site holds:
#
#   repo/                              the Flatpak (OSTree) repository itself
#   renpydeck.flatpakrepo              adds the repository as a source —
#                                      opening it in Discover offers to add it
#   sk.meluzina.RenPyDeck.flatpakref   installs the app and adds the source in
#                                      one go
#   index.html, icon.svg               a landing page linking the two
#
# The repository is rebuilt from scratch for every release and holds only the
# latest version; clients update from whatever commit they have, so no history
# needs to be kept.
#
set -euo pipefail

if [ $# -ne 2 ]; then
    echo "Usage: $0 SITE_DIR SITE_URL" >&2
    exit 1
fi
SITE_DIR="$1"
SITE_URL="${2%/}/"
GPG_KEY="${RENPYDECK_GPG_KEY:?set RENPYDECK_GPG_KEY to the key the repository was signed with}"

APP_ID="sk.meluzina.RenPyDeck"
APP_BRANCH="stable"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$PROJECT_ROOT/build/flatpak-repo"

if [ ! -f "$REPO_DIR/summary.sig" ]; then
    echo "$REPO_DIR has no signed summary; run build-flatpak.sh with RENPYDECK_GPG_KEY first" >&2
    exit 1
fi

rm -rf "$SITE_DIR"
mkdir -p "$SITE_DIR"

# The repository minus OSTree's local scratch space, which is never served.
cp -r "$REPO_DIR" "$SITE_DIR/repo"
rm -rf "$SITE_DIR/repo/tmp" "$SITE_DIR/repo/.lock"

install -m644 "$SCRIPT_DIR/$APP_ID.svg" "$SITE_DIR/icon.svg"

# Both files carry the public key inline, base64-encoded, so adding the
# repository needs nothing else to trust it.
GPG_KEY_BASE64="$(gpg --export "$GPG_KEY" | base64 -w 0)"

cat > "$SITE_DIR/renpydeck.flatpakrepo" <<EOF
[Flatpak Repo]
Title=RenPyDeck
Url=${SITE_URL}repo/
Homepage=https://github.com/samo1/RenPyDeck
Comment=Game manager and launcher for Ren'Py games on the Steam Deck
Icon=${SITE_URL}icon.svg
DefaultBranch=$APP_BRANCH
GPGKey=$GPG_KEY_BASE64
EOF

cat > "$SITE_DIR/$APP_ID.flatpakref" <<EOF
[Flatpak Ref]
Name=$APP_ID
Branch=$APP_BRANCH
Title=RenPyDeck
Url=${SITE_URL}repo/
SuggestRemoteName=renpydeck
Homepage=https://github.com/samo1/RenPyDeck
Icon=${SITE_URL}icon.svg
RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo
IsRuntime=false
GPGKey=$GPG_KEY_BASE64
EOF

cat > "$SITE_DIR/index.html" <<EOF
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RenPyDeck</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto;
         padding: 0 1rem; line-height: 1.5; }
  header { display: flex; align-items: center; gap: 1rem; }
  header img { width: 64px; height: 64px; }
  code { word-break: break-all; }
</style>
</head>
<body>
<header>
  <img src="icon.svg" alt="">
  <h1>RenPyDeck</h1>
</header>
<p>Game manager and launcher for Ren'Py games on the Steam Deck.</p>

<h2>Install on the Steam Deck</h2>
<p>In Desktop Mode, open <a href="$APP_ID.flatpakref">$APP_ID.flatpakref</a>.
Discover installs RenPyDeck and adds this repository as a source, so updates arrive
through Discover like any other app's.</p>
<p>To only add the source, open <a href="renpydeck.flatpakrepo">renpydeck.flatpakrepo</a>
instead and install RenPyDeck from Discover afterwards.</p>

<h2>From a terminal</h2>
<pre><code>flatpak install --user ${SITE_URL}$APP_ID.flatpakref</code></pre>

<p>A single-file bundle of every version is attached to its
<a href="https://github.com/samo1/RenPyDeck/releases">release on GitHub</a>.</p>
</body>
</html>
EOF

echo ">> Site written to $SITE_DIR"
