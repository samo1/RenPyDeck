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
│       ├── remover.py              #   deleting a game's files
│       └── touchscroll.py          #   drag/flick scrolling for the touchscreen
├── packaging/
│   ├── build-flatpak.sh            # builds the single-file Flatpak bundle
│   ├── renpydeck.sh                # in-sandbox launcher (sets PYTHONPATH)
│   ├── sk.meluzina.RenPyDeck.desktop      # desktop entry
│   ├── sk.meluzina.RenPyDeck.metainfo.xml # AppStream metadata
│   └── sk.meluzina.RenPyDeck.svg          # application icon
├── download/        # Example download folder (downloaded game archives live here)
├── games/           # Example games folder (extracted/installed games live here)
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

**Prerequisites** (one-time): the matching GNOME **Platform** and **SDK**. The script builds
with plain `flatpak` (no `flatpak-builder` needed):

```bash
flatpak remote-add --if-not-exists flathub \
    https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install flathub org.gnome.Platform//49 org.gnome.Sdk//49
```

Under the hood the script runs the standard `flatpak` build steps:

```bash
flatpak build-init   build/flatpak-build sk.meluzina.RenPyDeck org.gnome.Sdk org.gnome.Platform 49
# ... copy app files into build/flatpak-build/files ...
flatpak build-finish build/flatpak-build --command=renpydeck \
    --share=ipc --socket=wayland --socket=fallback-x11 --device=dri \
    --filesystem=xdg-download
flatpak build-export build/flatpak-repo build/flatpak-build stable
flatpak build-bundle build/flatpak-repo dist/RenPyDeck.flatpak sk.meluzina.RenPyDeck stable
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
  behind. The archive is deleted only after that, so if anything goes wrong it is still
  there to retry with. Because the checks run on the unpacked tree, an unsupported archive
  is unpacked first and then discarded; this keeps one code path for every archive format,
  at the cost of some temporary disk space.
- **One game at a time:** Launching runs the game as a child process and waits for it,
  which is what keeps a second game from being started. A game installed by hand (not
  through RenPyDeck) that never had its permissions fixed gets them fixed on the spot rather
  than failing to start. If the game exits with a non-zero status, RenPyDeck says so — the
  game's own output goes to the terminal RenPyDeck was started from.
- **Archives are consumed:** A successful install hard-deletes the archive from the Download
  folder (no trash). Removing the game later deletes its extracted files the same way;
  playing it again means downloading it again.
- **Removal is confirmed, then final:** Remove always asks first, naming the game folder and
  the archive it is about to delete. Confirming deletes both if both are present — nothing
  goes to the trash, and anything already gone counts as removed rather than an error.

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
