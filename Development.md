# Developing RenPyDeck

Everything behind the scenes: the tech stack, the project layout, how to run RenPyDeck from
source, how the Flatpak bundle is built, and the details of Ren'Py games and of RenPyDeck's
own behaviour that the code depends on.

For what RenPyDeck does and how to install and use it, see [README.md](README.md).

---

## Tech stack

- **Language:** Python — a natural fit alongside the Ren'Py engine, which is itself
  Python-based.
- **UI:** **GTK 4** + **libadwaita** via **PyGObject** (`gi`), presenting the game list and
  the install / launch / remove / exit actions. Every screen is an `Adw.NavigationPage` in a
  single `Adw.NavigationView` — no `Gtk.FileDialog`, no `Adw.AlertDialog`, no second
  windows, because the Deck's gaming mode does not reliably show them (see the Steam Deck
  notes under [Features](README.md#features)).
- **Packaging:** A single-file **Flatpak bundle** built on the **GNOME 49 runtime** (which
  already ships Python 3 + GTK 4 + PyGObject, so no extra dependencies are bundled).
- **Unpacking:** zip and tar archives are handled by the Python standard library. Formats it
  cannot read (`.rar`, `.7z`) are passed to external extractors — **`bsdtar`** (part of the
  GNOME runtime, and able to read both), then `7z`/`7zz`/`7za`, `unar` and `unrar` when
  running outside the Flatpak. Each installed tool is tried in turn until one succeeds,
  because being installed does not mean a tool can read the archive: Fedora's 7-Zip, for
  example, ships without the RAR decoder. Installs run on a worker thread, so a
  multi-gigabyte archive never freezes the window.

## Project layout

```
RenPyDeck/
├── src/
│   └── renpydeck/                  # the Python application package
│       ├── __init__.py             #   package metadata (version)
│       ├── __main__.py             #   enables `python -m renpydeck`
│       ├── app.py                  #   GTK 4 application + main window
│       ├── config.py               #   INI configuration (folder locations)
│       ├── folderchooser.py        #   in-window folder browser (no portal)
│       ├── games.py                #   scans both folders into the game list
│       ├── installer.py            #   unpacking + permission fixing
│       ├── launcher.py             #   running an installed game
│       ├── patcher.py              #   workarounds for known defects in games
│       ├── remover.py              #   deleting a game's files
│       └── touchscroll.py          #   drag/flick scrolling for the touchscreen
├── .github/workflows/
│   └── release.yml                 # manual release: tag, GitHub release, Flatpak repo
├── packaging/
│   ├── build-flatpak.sh            # builds the Flatpak repository and single-file bundle
│   ├── make-site.sh                # lays out the published Flatpak repository website
│   ├── set-version.py              # writes a release's version into the sources
│   ├── steam-assets.sh             # renders the Steam library artwork
│   ├── renpydeck.sh                # in-sandbox launcher (sets PYTHONPATH)
│   ├── sk.meluzina.RenPyDeck.desktop      # desktop entry
│   ├── sk.meluzina.RenPyDeck.metainfo.xml # AppStream metadata
│   └── sk.meluzina.RenPyDeck.svg          # application icon
├── download/        # Example download folder (downloaded game archives live here)
├── games/           # Example games folder (extracted/installed games live here)
├── LICENSE          # GPL-3.0 text; also installed into the Flatpak
├── README.md        # What RenPyDeck is, and how to install and use it
└── Development.md   # This file
```

> Note: the Download and Games folders are **configurable** at runtime — the folders above
> are just the bundled examples/defaults. They (and the generated `build/` and `dist/`
> directories) are git-ignored.

## Running the app without packaging

For day-to-day development you can run straight from the source tree — no Flatpak build
required. You need **Python 3**, **GTK 4**, and **PyGObject** installed on your system.

```bash
# Fedora / Steam Deck (SteamOS):
sudo dnf install python3-gobject gtk4
# Debian / Ubuntu:
sudo apt install python3-gi gir1.2-gtk-4.0
# Arch:
sudo pacman -S python-gobject gtk4
```

Then launch the application from the project root in either of these equivalent ways:

```bash
# Option A — run the package as a module (recommended):
PYTHONPATH=src python3 -m renpydeck

# Option B — run the app module directly:
PYTHONPATH=src python3 src/renpydeck/app.py
```

The `PYTHONPATH=src` part tells Python where to find the `renpydeck` package; without it
the import will fail.

## Packaging the app into a Flatpak

The whole bundle is produced by a single script:

```bash
./packaging/build-flatpak.sh
```

This writes the single-file bundle to **`dist/RenPyDeck.flatpak`** — the one file you copy
to the Steam Deck.

**Prerequisites** (one-time): the matching GNOME **Platform** and **SDK**, and AppStream's
**compose** addon on the host. The script builds with plain `flatpak` (no `flatpak-builder`
needed):

```bash
flatpak remote-add --if-not-exists flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
sudo dnf install appstream-compose      # Debian/Ubuntu: sudo apt install appstream-compose
```

Under the hood the script runs the standard `flatpak` build steps:

```bash
flatpak build-init   build/flatpak-build sk.meluzina.RenPyDeck org.gnome.Sdk org.gnome.Platform 49
# ... copy app files into build/flatpak-build/files ...
appstreamcli compose --no-net --prefix=/ --origin=sk.meluzina.RenPyDeck \
    --result-root=build/flatpak-build/files \
    --data-dir=build/flatpak-build/files/share/app-info/xmls \
    --icons-dir=build/flatpak-build/files/share/app-info/icons/flatpak \
    build/flatpak-build/files
flatpak build-finish build/flatpak-build --command=renpydeck \
    --share=ipc --socket=wayland --socket=fallback-x11 --socket=pulseaudio \
    --device=dri --filesystem=xdg-download --filesystem=~/.renpy:create
flatpak build-export build/flatpak-repo build/flatpak-build stable
flatpak build-update-repo --title=RenPyDeck --default-branch=stable … build/flatpak-repo
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
    build/flatpak-repo dist/RenPyDeck.flatpak sk.meluzina.RenPyDeck stable
```

**Install and run the bundle** (locally to test, or on the Steam Deck after copying the file):

```bash
flatpak install --user RenPyDeck.flatpak
flatpak run sk.meluzina.RenPyDeck
```

To uninstall it again:

```bash
flatpak uninstall --user sk.meluzina.RenPyDeck
```

### What a software store shows

Everything KDE Discover (or GNOME Software) prints about the app — its name, author, icon
and description — comes from `packaging/sk.meluzina.RenPyDeck.metainfo.xml`, but *not*
directly: stores read the **catalog** form of that file, `share/app-info/xmls/<id>.xml.gz`
with rasterised icons beside it, which is what the `appstreamcli compose` step above
generates. `flatpak build-bundle` copies it into the bundle, so opening `RenPyDeck.flatpak`
in Discover shows a proper entry rather than a nameless one. Skip the compose step and the
bundle carries no store metadata at all: that is what made Discover call the author
*unknown*.

The compose step runs on the **host**, against the build's files, the way `flatpak-builder`
does it — not inside `flatpak build` with the SDK's copy of `appstreamcli`. `appstreamcli`
decodes the icon through **glycin**, which isolates image loading in a sandbox of its own.
On the host that is plain bubblewrap; inside a Flatpak sandbox glycin has to ask the Flatpak
portal instead, which only works in a full desktop session. In CI the loader fails with
"app/… not installed", the SVG cannot be read, and compose reports `file-read-error` and
produces an empty catalog.

The author itself is the `<developer>` block:

```xml
<developer id="sk.meluzina">
  <name>Samuel Valis</name>
</developer>
<developer_name>Samuel Valis</developer_name>
```

The licence a store shows is the SPDX id in `<project_license>` (`GPL-3.0-or-later`) — not
the `LICENSE` file, which stores never read. The file is nevertheless installed into the
bundle at `/app/share/licenses/sk.meluzina.RenPyDeck/LICENSE`, because the GPL asks for its
terms to be conveyed with the binary and the bundle is all a Deck user receives. Do not
confuse `<project_license>` with `<metadata_license>` above it: the latter covers the
metainfo file itself, not the program.

The `id` is a reverse-DNS name for the *developer*, not the app, and is what a store uses to
group everything published under it; the name is the string shown as the author.
`developer_name` is the pre-AppStream-1.0 spelling of the same name, kept for stores on
older AppStream (SteamOS has lagged the desktop distributions here) — `appstreamcli
validate` reports it as deprecated, which is expected rather than a problem. Check the file
with:

```bash
appstreamcli validate packaging/sk.meluzina.RenPyDeck.metainfo.xml
```

## Releasing

Releases are made by the **Release** workflow (`.github/workflows/release.yml`), started by
hand from the repository's *Actions* tab with the version to release:

```bash
gh workflow run release.yml -f version=0.2.0
```

It runs in a privileged Fedora 43 container: `flatpak build` and glycin both need
bubblewrap to create namespaces. In order, it:

1. refuses a version that is not `MAJOR.MINOR.PATCH`, or whose `v<version>` tag already
   exists;
2. writes the version into `src/renpydeck/__init__.py` and adds a `<release>` to the
   metainfo with `packaging/set-version.py`. A `<release>` entry for the version that is
   already there, with release notes written by hand, is kept as it is. A version older
   than the newest release in the metainfo is refused;
3. builds the Flatpak signed with the repository key, then lays out the repository website
   with `packaging/make-site.sh`;
4. commits the version change to `main`, tags it `v<version>`, and pushes both together;
5. creates the GitHub release, with notes generated from the commits and
   `RenPyDeck-<version>.flatpak` attached;
6. deploys the website to GitHub Pages.

Everything that can fail on bad input happens before step 4, so a failed run leaves nothing
behind. If a later step fails, finish it by hand: the tag already exists, so rerunning the
workflow for the same version is refused.

### The Flatpak repository

The website at `https://samo1.github.io/RenPyDeck/` serves:

| Path | What it is |
| --- | --- |
| `repo/` | the Flatpak (OSTree) repository |
| `renpydeck.flatpakrepo` | adds the repository as a source (opened in Discover, it offers to add it) |
| `sk.meluzina.RenPyDeck.flatpakref` | installs the app and adds the source in one step |
| `index.html` | a landing page linking the two |

The repository is **rebuilt from scratch for every release** and holds only the latest
version. A client updates from whatever commit it has installed, so no history has to be
stored anywhere. The single-file bundle records the repository's URL and key
(`build-bundle --repo-url --gpg-keys`), so an install from the bundle is updated from the
repository as well, under a remote named `renpydeck-origin`. The bundle also names Flathub
as the place to get the GNOME runtime from (`--runtime-repo`).

The repository is **GPG-signed**, because Flatpak, and so Discover, will not add an unsigned
remote without extra flags. Both `.flatpakrepo` and `.flatpakref` carry the public key
inline. The private key exists only as the `FLATPAK_GPG_PRIVATE_KEY` repository secret, plus
any backup you keep. Losing it means every user has to remove and re-add the source, because
releases signed with a new key fail verification against the old one.

To build a signed release locally, for example to test the repository, set the same two
variables the workflow sets, then serve `site/` over HTTP:

```bash
RENPYDECK_GPG_KEY=<key id> RENPYDECK_REPO_URL=http://localhost:8000/repo/ \
    ./packaging/build-flatpak.sh
RENPYDECK_GPG_KEY=<key id> ./packaging/make-site.sh site http://localhost:8000/
python3 -m http.server --directory site
```

### One-time setup

- **Signing key:** a dedicated key without a passphrase, stored as the secret:

  ```bash
  export GNUPGHOME=$(mktemp -d)
  gpg --batch --pinentry-mode loopback --passphrase '' \
      --quick-gen-key "RenPyDeck Flatpak repository <samuel.valis@meluzina.sk>" ed25519 sign never
  gpg --armor --export-secret-keys | gh secret set FLATPAK_GPG_PRIVATE_KEY
  gpg --armor --export-secret-keys > renpydeck-flatpak-key.asc   # back this up somewhere safe
  ```

- **GitHub Pages**, served by Actions rather than from a branch:

  ```bash
  gh api -X POST repos/samo1/RenPyDeck/pages -f build_type=workflow
  ```

## Rendering the Steam library artwork

Added to Steam as a non-Steam game, RenPyDeck gets a blank tile unless artwork is set for
it. The images for that are generated rather than kept as binaries in the repository:

```bash
./packaging/steam-assets.sh
```

They land in `dist/steam-assets/` — `grid-600x900.png` (the library tile Gaming Mode
shows), `capsule-920x430.png`, `hero-1920x620.png`, `logo-1280x720.png` (transparent, drawn
over the hero) and `icon-256x256.png` — and the same five are packed into
**`dist/RenPyDeck-steam-assets.zip`**. That archive is the release asset to attach beside
`RenPyDeck.flatpak`; the README tells users to download it and how to apply it in Steam.
The folder is emptied before each run, so an asset that was renamed or dropped cannot
survive in the archive, and the packing uses Python's `zipfile` module rather than the
`zip` command — Python is a given here, another tool is not.

The script needs **`rsvg-convert`** (`librsvg2-tools` on Fedora/SteamOS, `librsvg2-bin` on
Debian/Ubuntu, `librsvg` on Arch). Each asset is an inline SVG built from the same motif as
`packaging/sk.meluzina.RenPyDeck.svg` — the rounded blue tile, the play triangle, the deck
bar — with the palette and the wordmark set once at the top of the file, so changing the
application icon or the tagline means editing one place and re-running. Text is rendered
with Cantarell, GNOME's UI font, falling back to Inter and DejaVu Sans on machines without
it.

Two things the layouts are deliberately careful about, both of which looked wrong before:
the hero carries no wordmark (Steam draws the logo on top of it, so the name would appear
twice) and nothing in it touches an edge, because Steam crops the hero at several aspect
ratios and a clipped shape reads as a mistake.

## Anatomy of a Ren'Py game

Understanding the layout Ren'Py produces is key to the install logic. A typical extracted
game looks like this:

```
<GameName>/
├── <GameName>.sh        # Linux/Steam Deck launch script  ← must be executable
├── <GameName>.py        # entry point (used by all platforms)
├── <GameName>.exe       # Windows launcher (ignored on the Deck)
├── <GameName>.app/      # macOS bundle (ignored on the Deck)
├── game/                # the actual game scripts & assets
├── renpy/               # the Ren'Py engine
└── lib/
    ├── py3-linux-x86_64/    # Linux runtime  ← contents must be executable
    │   ├── <GameName>       #   the real binary the .sh execs
    │   ├── python, pythonw
    │   ├── librenpython.so, libsteam_api.so, …
    │   └── zsync, zsyncmake
    ├── py3-windows-x86_64/  # Windows runtime (ignored on the Deck)
    └── python3.x/           # shared pure-Python stdlib
```

The `.sh` script resolves the platform at runtime (`lib/$PYTHON-$PLATFORM`, e.g.
`lib/py3-linux-x86_64`) and execs the binary there that matches the script's basename
(falling back to `renpy`). That's why both the script **and** the platform binary/libraries
need the executable bit.

A few important real-world variations the installer must tolerate:

- **Two `lib` layouts.** Newer (Python 3) games use `lib/py3-linux-x86_64/`; older
  (Python 2) games use `lib/linux-x86_64/` (no `py3-` prefix) and carry many more bundled
  `.so` files. Both must have their Linux binaries and libraries made executable.
- **Misleading archive names.** An archive named `…-win.zip` can still contain a full Linux
  runtime and `.sh` script (and is therefore supported), while a `…-pc`/`…-market` archive
  may bundle Windows, Linux, and macOS payloads together. Never trust the filename — inspect
  for the Linux launch script.
- **Nested game roots.** The launch script isn't always at the top of the archive. It may
  live inside a wrapper folder (e.g. `My_New_Paranormal_Life-0.6-linux/MNPL-0.6-linux/MNPL.sh`)
  or a folder with spaces (e.g. `Rent a Boyfriend Demo/RentaBoyfriend.sh`). Locate it by
  searching, don't assume a fixed depth.

## Key behaviors to be aware of

- **Linux-only support:** A game is installable only if its unpacked tree contains a `renpy`
  folder with a `*.sh` launch script in the same folder. The pair is searched for down to
  two folders below the top, since archives wrap the game in a folder (or two)
  inconsistently; the first match is the game root, and an archive that buries the game
  deeper than that is refused rather than installed into a game the library would not show.
  Detection is content-based, not filename-based, so Windows-only payloads are refused
  however the archive is named. Note that older games also carry `renpy` folders deep inside
  `lib/.../python2.7/` — those have no launch script beside them and are correctly skipped.
- **Only launchable installs are listed:** the same `renpy` + `*.sh` search runs over each
  sub-folder of the Games folder, and one without a launch script never appears in the
  library — no *Launch* button that could not work, and no rows for folders that are not
  games. The search stops at the first game root it finds, so listing the library costs
  about one folder listing per game rather than a walk through every game's thousands of
  files. Archives are deliberately *not* opened for the same check: an unsupported one is
  only found out when it is installed, and the install refuses it then.
- **Selection reveals the actions:** the library list selects one row at a time, and a row's
  buttons are hidden unless it is the selected one. A click selects a row before activating
  it, so a second click on the row that is already selected is what deselects it. Dragging
  the list to scroll never selects anything: the scroll gesture claims the touch once it has
  moved, which cancels the row's pending click. Focus is deliberately parked on a header
  button whenever the list is rebuilt, because focus entering a single-selection list would
  otherwise select the first game on its own.
- **The selection survives a rescan:** every scan builds a new list, but the game that was
  selected is selected again in it, so installing a game leaves its row open with *Launch*
  where *Install* used to be, rather than dropping the user back to a list with nothing
  picked. Archive and installed folder are matched on the same normalised key the library
  merges the two folders on (`GameEntry.key`), which is what lets a row keep its selection
  through the rename from `Some_Game-1.0.zip` to `Some_Game-1.0`. A game that the rescan no
  longer finds — it was just removed — simply leaves nothing selected. The list being
  replaced emits one last `row-selected` for *nothing selected* as it is torn down, after
  its successor has already been built; the handler ignores any list that is not the
  current one, or that parting shot would hide the new row's buttons again.
- **Subfolder guarantee:** Extraction always lands inside a subfolder of the Games folder
  (named after the archive). Files are never extracted loose, even if the archive already
  has its own top-level folder.
- **Permission fixing:** After extraction, the executable bit is set on (1) every `*.sh`
  script anywhere in the game and (2) every file under the game's `lib/` folder — the
  platform binary, `python`, `pythonw` and the shared libraries. Only the Linux x86_64
  runtime actually needs it, but its folder name varies between Ren'Py generations, so the
  whole `lib` tree is covered rather than guessed at. Many archives ship these without the
  executable bit, which would otherwise stop the game from launching on the Deck.
- **Staged install:** Extraction happens in a hidden staging folder inside the Games folder,
  and is renamed into place only once both the unpacking and the Linux checks above have
  succeeded — so a failed, refused or interrupted install never leaves a half-unpacked game
  behind. An archive is only deleted (when the setting asks for it) after that, so if
  anything goes wrong it is still there to retry with. Because the checks run on the
  unpacked tree, an unsupported archive
  is unpacked first and then discarded; this keeps one code path for every archive format,
  at the cost of some temporary disk space.
- **One game at a time:** Launching runs the game as a child process and waits for it,
  which is what keeps a second game from being started. A game installed by hand (not
  through RenPyDeck) that never had its permissions fixed gets them fixed on the spot rather
  than failing to start. If the game exits with a non-zero status, RenPyDeck says so — the
  game's own output goes to the terminal RenPyDeck was started from.
- **Known game defects are patched at launch:** just before a game starts, `patcher.py`
  checks it against a list of known defects and drops a fix script into its `game/` folder,
  leaving the game's own files untouched. How defects are recognised, how the fixes work,
  and every individual patch are documented in the comments of `patcher.py` itself.
- **Archives are kept unless asked otherwise:** `install.delete_archive` (off by default)
  decides whether a successful install hard-deletes the archive from the Download folder
  (no trash). Off, the normal state of an installed game is *installed and downloaded*, and
  it is the library entry that carries both paths. A value that is missing or not a boolean
  counts as off — of the two settings, that is the one that destroys nothing.
- **The game and its archive are removed separately:** the row carries a single *Remove*
  button — a list row on a handheld has no space for more — and the choice is made on the
  confirmation page, which offers *Remove game*, *Remove archive* and *Remove both* when
  the entry has both, and one plain *Remove* when it does not. *Install* is hidden once a
  game is installed, since installing over the existing folder would only be refused.
- **Removal is confirmed, then final:** Remove always asks first, naming what it is about to
  delete and, when the entry has two halves, what each answer would leave behind. Nothing
  goes to the trash, and anything already gone counts as removed rather than an error.
- **The game's own `~/.renpy` is shared with the sandbox:** a Ren'Py game keeps its saves in
  `~/.renpy/<save_directory>/` (and, in parallel, in `<game>/game/saves/`), and since
  Ren'Py 8.3 it signs every save with a key in `~/.renpy/tokens/security_keys.txt` —
  a save whose signature is from an unknown key makes the game ask whether the save can be
  trusted, because it was "created on another computer". A Flatpak without home access has
  no `~/.renpy`: `$HOME` inside the sandbox is a throwaway directory, so the game writes
  saves that vanish when RenPyDeck exits and mints a fresh signing key on every launch —
  which makes both saves from outside the launcher and saves from the launcher's own
  previous run untrusted. `--filesystem=~/.renpy:create` hands the game the real folder, so
  a game plays the same whether it was started by RenPyDeck or by anything else.
- **Sound is for the games:** RenPyDeck itself never makes a noise, but a game started
  inside the sandbox without `--socket=pulseaudio` comes up mute (`PulseAudio: Unable to
  connect: Connection refused`) — the socket name is historical, and it is the one PipeWire
  serves on SteamOS. Together with `~/.renpy` above, it is a permission the app holds on the
  games' behalf rather than its own.

## Bundled examples

The repository ships with example games that demonstrate the range of inputs the installer
must handle. They map archive → extracted result:

| Download archive | Format | Extracted folder | Notable trait |
| --- | --- | --- | --- |
| `CORRUPTING_JOY-0.03.pc.zip` | zip | `CORRUPTING_JOY-0.03.pc/` | Script at top level; py3 lib + Windows lib bundled together |
| `My_New_Paranormal_Life-0.6-linux.tar.bz2` | tar.bz2 | `My_New_Paranormal_Life-0.6-linux/MNPL-0.6-linux/` | Launch script nested one folder deeper |
| `Mythos-1.1.0.0-market.zip` | zip | `Mythos-1.1.0.0-market/` | Ships Linux, Windows *and* macOS (`.app`) payloads |
| `NetorareWifeMisumi-LustfulAwakening-1.0.1-win.zip` | zip | `NetorareWifeMisumi-LustfulAwakening-1.0.1-win/` | `-win` name, but supported — older `lib/linux-x86_64` layout |
| `Rent_a_Boyfriend_Prologue.rar` | rar | `Rent_a_Boyfriend_Prologue/Rent a Boyfriend Demo/` | RAR archive; nested folder name contains spaces |
