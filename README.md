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
- **One-click uninstall** — removes an installed game's files.
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
   - RenPyDeck then locates the game's **Linux launch script** (`*.sh`) — even if it sits a
     folder or two down inside the archive, and even if folders or files contain spaces.
   - After extraction, RenPyDeck **fixes executable permissions** on that launch script and
     on the Linux runtime in the game's `lib` folder, so it can actually start.
   - Support is decided by **content, not filename**. Only games that include a Linux launch
     script are installed; Windows-only games are ignored — regardless of whether the archive
     is named `-win`, `-pc`, `-linux`, or anything else.
3. **Play** — Select an installed game and choose **Run** to launch it.
4. **Uninstall** — Select an installed game and choose **Uninstall** to remove its extracted
   files from the Games folder. The original archive stays in your Download folder, so you
   can reinstall later.

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
3. Use the interface to **install**, **run**, and **uninstall** games.

### Using it on the Steam Deck

Because the Steam Deck doesn't show window decorations by default, RenPyDeck includes an
on-screen **Exit** button. Use it to close the application — you don't need a title bar's
close button.

---

## For developers

### Tech stack

- **Language:** Python — a natural fit alongside the Ren'Py engine, which is itself
  Python-based.
- **UI:** A graphical desktop interface presenting the downloaded and installed game lists
  and the install / run / uninstall / exit actions.
- **Packaging:** A single-file **Flatpak bundle** for distribution.

### Project layout

```
RenPyDeck/
├── download/   # Example download folder (downloaded game archives live here)
├── games/      # Example games folder (extracted/installed games live here)
├── plan.txt    # The original project plan
└── README.md   # This file
```

> Note: the Download and Games folders are **configurable** at runtime — the folders above
> are just the bundled examples/defaults.

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

- **Linux-only support:** A game is installable only if its extracted tree contains a Linux
  launch script (`*.sh`) backed by a Linux `lib` runtime. Detection is content-based, not
  filename-based. Windows-only and macOS-only payloads are ignored.
- **Subfolder guarantee:** Extraction always lands inside a subfolder of the Games folder
  (named after the archive). Files are never extracted loose, even if the archive already
  has its own top-level folder.
- **Permission fixing:** After extraction, the executable bit is set on (1) the launch
  `.sh` script and (2) the Linux runtime under `lib/` — the platform binary, `python`,
  `pythonw`, and the `.so` shared libraries. Many archives ship these without the executable
  bit, which would otherwise stop the game from launching on the Deck.
- **Non-destructive uninstall:** Uninstalling removes extracted files from the Games folder
  only; the source archive in the Download folder is left untouched, so the game can be
  reinstalled later.

### Bundled examples

The repository ships with example games that demonstrate the range of inputs the installer
must handle. They map archive → extracted result:

| Download archive | Format | Extracted folder | Notable trait |
| --- | --- | --- | --- |
| `CORRUPTING_JOY-0.03.pc.zip` | zip | `CORRUPTING_JOY-0.03-pc/` | Script at top level; py3 lib + Windows lib bundled together |
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
