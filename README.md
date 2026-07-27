# RenPyDeck

A game manager and launcher for **Ren'Py** games, designed first and foremost for the **Steam Deck**.

RenPyDeck keeps your collection of downloaded Ren'Py games in one place and turns the
download → install → play → uninstall lifecycle into a few taps in a clean graphical
interface. It handles the fiddly parts — unpacking archives into tidy subfolders and
fixing up the file permissions Linux needs — so you can get straight to playing.

---

## Features

- **Graphical game manager** with two clear lists: games you've **downloaded** (archives,
  ready to install) and games you've **installed** (extracted, ready to play).
- **One-click install** — unpacks a downloaded archive into your games folder.
- **One-click launch** — runs an installed game.
- **One-click removal** — deletes a game's files (and its archive, if it still has one)
  after a confirmation prompt.
- **Many archive formats** — handles `.zip`, `.tar.bz2`, `.rar`, and other common
  compressed formats Ren'Py games are distributed in.
- **Configurable folder locations** for your downloads and your installed games.
- **Steam Deck friendly** — includes an on-screen **Exit** button, because the Deck's
  gaming mode hides window decorations (so there's no close button to rely on).
- **Linux-first** — support is decided by what's *inside* the archive, not by its
  filename: a game is playable only if it ships a Linux launch script. Windows-only
  games are detected and ignored, even when a "linux"-named archive isn't one (and vice
  versa).
- **Automatic permission fixing** — sets the executable bit on the game's launch shell
  script and on the Linux runtime under its `lib` folder (the platform binary, `python`,
  `pythonw`, and the `.so` shared libraries), so games run even when the archive forgot to.
- **Tidy installs** — every game is always extracted into its own subfolder, even when the
  archive doesn't contain a top-level folder of its own, and even when the launch script
  is buried a level or two down.
- **Distributed as a single-file Flatpak bundle** — easy to install and run on the Steam Deck.

---

## How it works

RenPyDeck is built around two folders that you configure:

| Folder | Purpose | Default example |
| --- | --- | --- |
| **Download folder** | Holds your downloaded games as **compressed archives** (`.zip`, `.tar.bz2`, `.rar`, …). | `download/` |
| **Games folder** | Holds your **extracted, installed** games. | `games/` |

The application scans both folders to build its two lists.

### The game lifecycle

1. **Download** — Place a game's compressed archive into your **Download folder**. (RenPyDeck
   manages your library; downloading the archives themselves is up to you.) The game then
   appears in the **downloaded games** list.
2. **Install** — Select a downloaded game and choose **Install**. RenPyDeck unpacks the
   archive into your **Games folder**:
   - The game is always placed in its **own subfolder** (named after the archive), so loose
     files never spill into your Games folder. This holds whether the archive contains its
     files at the top level *or* already wraps them in its own folder.
   - After extraction, RenPyDeck **fixes executable permissions**: every `*.sh` launch
     script in the game — wherever it sits in the tree — and everything inside the game's
     `lib` folder, which is searched for rather than assumed to be at the top.
   - Once the game is unpacked, its **archive is deleted** from the Download folder. This is
     a hard delete: the file does not go to the trash.
   - Support is decided by **content, not filename**, regardless of whether the archive is
     named `-win`, `-pc`, `-linux` or anything else. What was unpacked must contain a
     **`renpy` folder** (the engine — every Ren'Py game ships it) with a **`*.sh` launch
     script beside it** (the Linux launcher). If either is missing the install is refused,
     nothing is added to the Games folder, and the archive is kept.
3. **Play** — Choose **Launch** on an installed game. RenPyDeck runs the game's `*.sh`
   script from the game root — the folder holding `renpy` — with that folder as the working
   directory, which is what the script expects. The game takes over in its own window;
   RenPyDeck waits behind it with its buttons disabled, so only one game runs at a time.
4. **Remove** — Choose **Remove** to delete a game from the library. RenPyDeck asks for
   confirmation first, naming exactly what will go, and then deletes whatever the entry
   consists of: the extracted game, its archive, or both. This is a hard delete — nothing
   goes to the trash and nothing can be undone.

---

## For end users

### Installing RenPyDeck

RenPyDeck ships as a **single-file Flatpak bundle**. To install it on your Steam Deck (or any
Linux machine):

```bash
flatpak install RenPyDeck.flatpak
```

Then launch it from your applications menu (in Desktop Mode), or add it to Steam as a
non-Steam game to launch it from Gaming Mode.

### First run

1. Open **Settings** and set your **Download folder** and **Games folder** locations.
2. Put your game archives into the Download folder.
3. Use the interface to **install**, **launch**, and **remove** games.

### Using it on the Steam Deck

Because the Steam Deck doesn't show window decorations by default, RenPyDeck includes an
on-screen **Exit** button. Use it to close the application — you don't need a title bar's
close button.

---

## Configuration

RenPyDeck stores its settings in a plain **INI** file, following the XDG Base Directory
specification:

```
$XDG_CONFIG_HOME/renpydeck/config.ini      # usually ~/.config/renpydeck/config.ini
```

When run as a Flatpak the same path is redirected into the app's private config directory,
e.g. `~/.var/app/sk.meluzina.RenPyDeck/config/renpydeck/config.ini`.

The file is created automatically on first launch with sensible defaults, and is rewritten
whenever you change a folder in the configuration screen. It looks like this:

```ini
[folders]
download = /home/deck/Downloads
game = /home/deck/.local/share/renpydeck/games
```

| Key | Meaning | Default |
| --- | --- | --- |
| `download` | Folder scanned for downloaded game archives. | Your desktop's standard **Downloads** folder (`XDG_DOWNLOAD_DIR`). |
| `game` | Folder where games are extracted/installed. | `$XDG_DATA_HOME/renpydeck/games` (e.g. `~/.local/share/renpydeck/games`). |

Both folders are created on startup if they don't already exist. You can edit the file by
hand, but it's easier to use the in-app configuration screen.

### Choosing folders outside the sandbox (Flatpak)

The Flatpak ships with read-write access to your **Downloads** folder
(`--filesystem=xdg-download`) — write access is needed because installing a game deletes
its archive — and the default game folder lives in the app's own always-writable data
directory. With those defaults, no extra setup is needed.

If you want to point RenPyDeck at a location **outside** the sandbox — for example games on
a Steam Deck **SD card** (`/run/media/...`) or any other custom folder — the app needs
permission to reach it. The folder picker can grant temporary access to a chosen folder via
the desktop portal, but for a location RenPyDeck must read on every launch it's more reliable
to grant a persistent permission. Either use **[Flatseal](https://flathub.org/apps/com.github.tchx84.Flatseal)**
to add the folder, or run `flatpak override`, for example:

```bash
# Access to a different download location (e.g. the SD card):
flatpak override --user --filesystem=/run/media/deck sk.meluzina.RenPyDeck

# Access to a custom game/install location:
flatpak override --user --filesystem=/run/media/deck/Games sk.meluzina.RenPyDeck
```

Replace the paths to match where your folders actually are. To grant access to your whole
home directory instead, use `--filesystem=home`. Both locations need read-write access: the
**game** location so games can be installed and uninstalled there, and the **download**
location so an installed game's archive can be deleted.

---

## For developers

### Tech stack

- **Language:** Python — a natural fit alongside the Ren'Py engine, which is itself
  Python-based.
- **UI:** **GTK 4** via **PyGObject** (`gi`), presenting the downloaded and installed game
  lists and the install / run / uninstall / exit actions.
- **Packaging:** A single-file **Flatpak bundle** built on the **GNOME 49 runtime** (which
  already ships Python 3 + GTK 4 + PyGObject, so no extra dependencies are bundled).
- **Unpacking:** zip and tar archives are handled by the Python standard library. Formats it
  cannot read (`.rar`, `.7z`) are passed to external extractors — **`bsdtar`** (part of the
  GNOME runtime, and able to read both), then `7z`/`7zz`/`7za`, `unar` and `unrar` when
  running outside the Flatpak. Each installed tool is tried in turn until one succeeds,
  because being installed does not mean a tool can read the archive: Fedora's 7-Zip, for
  example, ships without the RAR decoder. Installs run on a worker thread, so a
  multi-gigabyte archive never freezes the window.

### Project layout

```
RenPyDeck/
├── src/
│   └── renpydeck/                  # the Python application package
│       ├── __init__.py             #   package metadata (version)
│       ├── __main__.py             #   enables `python -m renpydeck`
│       ├── app.py                  #   GTK 4 application + main window
│       ├── config.py               #   INI configuration (folder locations)
│       ├── games.py                #   scans both folders into the game list
│       ├── installer.py            #   unpacking + permission fixing
│       ├── launcher.py             #   running an installed game
│       └── remover.py              #   deleting a game's files
├── packaging/
│   ├── build-flatpak.sh            # builds the single-file Flatpak bundle
│   ├── renpydeck.sh                # in-sandbox launcher (sets PYTHONPATH)
│   ├── sk.meluzina.RenPyDeck.desktop      # desktop entry
│   ├── sk.meluzina.RenPyDeck.metainfo.xml # AppStream metadata
│   └── sk.meluzina.RenPyDeck.svg          # application icon
├── download/   # Example download folder (downloaded game archives live here)
├── games/      # Example games folder (extracted/installed games live here)
├── plan.txt    # The original project plan
└── README.md   # This file
```

> Note: the Download and Games folders are **configurable** at runtime — the folders above
> are just the bundled examples/defaults. They (and the generated `build/` and `dist/`
> directories) are git-ignored.

### Running the app without packaging

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

### Packaging the app into a Flatpak

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

### Anatomy of a Ren'Py game

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

### Key behaviors to be aware of

- **Linux-only support:** A game is installable only if its unpacked tree contains a `renpy`
  folder with a `*.sh` launch script in the same folder. The pair is searched for at any
  depth, since archives wrap the game in a folder (or two) inconsistently; the first match
  is the game root. Detection is content-based, not filename-based, so Windows-only payloads
  are refused however the archive is named. Note that older games also carry `renpy` folders
  deep inside `lib/.../python2.7/` — those have no launch script beside them and are
  correctly skipped.
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

### Bundled examples

The repository ships with example games that demonstrate the range of inputs the installer
must handle. They map archive → extracted result:

| Download archive | Format | Extracted folder | Notable trait |
| --- | --- | --- | --- |
| `CORRUPTING_JOY-0.03.pc.zip` | zip | `CORRUPTING_JOY-0.03.pc/` | Script at top level; py3 lib + Windows lib bundled together |
| `My_New_Paranormal_Life-0.6-linux.tar.bz2` | tar.bz2 | `My_New_Paranormal_Life-0.6-linux/MNPL-0.6-linux/` | Launch script nested one folder deeper |
| `Mythos-1.1.0.0-market.zip` | zip | `Mythos-1.1.0.0-market/` | Ships Linux, Windows *and* macOS (`.app`) payloads |
| `NetorareWifeMisumi-LustfulAwakening-1.0.1-win.zip` | zip | `NetorareWifeMisumi-LustfulAwakening-1.0.1-win/` | `-win` name, but supported — older `lib/linux-x86_64` layout |
| `Rent_a_Boyfriend_Prologue.rar` | rar | `Rent_a_Boyfriend_Prologue/Rent a Boyfriend Demo/` | RAR archive; nested folder name contains spaces |

---

## Roadmap / status

This README describes RenPyDeck's intended, complete feature set as captured in `plan.txt`.
Core goals:

- [x] Configurable download and games folders
- [x] List downloaded and installed games
- [x] Install (unpack), run, and uninstall games
- [x] Support multiple archive formats (`.zip`, `.tar.bz2`, `.rar`, …)
- [x] Always extract into a per-game subfolder
- [x] Locate the launch script even when nested or named with spaces
- [x] Fix executable permissions for the launch script and the Linux `lib` runtime
- [x] Detect support by content (Linux `.sh`), not by archive filename
- [x] Handle both `lib/py3-linux-*` and older `lib/linux-*` runtime layouts
- [x] On-screen Exit button for Steam Deck
- [x] Single-file Flatpak distribution
