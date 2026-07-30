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
- **Pick a game, then act on it** — the list shows names and states only. Tap a game to
  select it and its buttons appear on that row; tap it again to put them away. One game is
  selected at a time, so a long library stays readable and no button is ever ambiguous
  about which game it belongs to.
- **One-click install** — unpacks a downloaded archive into your games folder.
- **One-click launch** — runs an installed game.
- **One-click removal** — deletes a game's files (and its archive, if it still has one)
  after a confirmation prompt.
- **Many archive formats** — handles `.zip`, `.tar.bz2`, `.rar`, and other common
  compressed formats Ren'Py games are distributed in.
- **Configurable folder locations** for your downloads and your installed games.
- **Steam Deck friendly** — includes an on-screen **Exit** button, because the Deck's
  gaming mode hides window decorations (so there's no close button to rely on). The
  close/minimise/maximise buttons GTK would draw into the header are hidden as well: Exit
  already does the job, and they are awkward targets on a handheld.
- **Always dark** — the colour scheme reaches an app through the desktop portal, which
  gaming mode does not provide, so Flatpak apps start light there no matter how the desktop
  is set. RenPyDeck asks for dark itself.
- **One window, no dialogs** — questions, errors and even the folder browser are pages
  inside the main window. The Deck's gaming mode (the gamescope session) may never show a
  second window, and the system file picker it would need is unreachable there, so
  RenPyDeck opens neither.
- **Scrolls by finger** — lists can be dragged and flicked on the Deck's touchscreen, which
  gaming mode delivers as ordinary pointer input rather than as touch events (so GTK's own
  kinetic scrolling never sees it). Taps still activate buttons.
- **Linux-first** — support is decided by what's *inside* the archive, not by its
  filename: a game is playable only if it ships a Linux launch script. Windows-only
  games are detected and ignored, even when a "linux"-named archive isn't one (and vice
  versa). The same check decides what the library shows as installed: only a folder
  RenPyDeck can actually start is listed, so whatever else lives in your Games folder
  stays out of the way.
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

The application scans both folders to build its two lists. Every archive in the Download
folder is listed as it is — archives are never opened just to look inside, because reading
gigabytes of compressed data would make the library slow to open. Folders in the Games
folder, on the other hand, are cheap to look into, and only those holding a game RenPyDeck
can launch are listed.

In the library itself, a game is **selected before it is acted on**: rows carry just the
name and the state until you pick one, and only the selected row shows its buttons. Picking
another game moves them there; picking the same one again hides them. Nothing is selected
when the library opens, or after an install, a launch or a removal has finished.

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

RenPyDeck ships as a **single-file Flatpak bundle** (`RenPyDeck.flatpak`). On any Linux
machine it installs from a terminal:

```bash
flatpak install RenPyDeck.flatpak
```

### Installing it on the Steam Deck

No terminal needed — do this in **Desktop Mode**:

1. Copy `RenPyDeck.flatpak` onto the Deck (USB stick, network share, `scp`, however you
   like).
2. **Double-click the file** in the file manager (Dolphin). **Discover** opens showing
   RenPyDeck.
3. Click **Install from local bundle**. Discover pulls in the GNOME runtime the first time,
   which takes a few minutes; after that RenPyDeck appears in the application menu.

To play from **Gaming Mode**, add it to your Steam library while still in Desktop Mode:

4. In Steam, choose **Games → Add a Non-Steam Game to My Library…**. RenPyDeck is already in
   the list of applications — the Flatpak installs a desktop entry, so there is nothing to
   browse for. Tick it and confirm with **Add Selected Programs**.
5. Switch to Gaming Mode. RenPyDeck is under **Non-Steam** in your library.

#### Controller setup for Gaming Mode

Gaming Mode gives a non-Steam app whatever controller layout it is configured with, and the
default one has no mouse wheel — so the game list will not scroll. Before playing, select a
layout that does:

1. Launch RenPyDeck from your library, press the **STEAM** button and open
   **Controller Settings**.
2. Pick the **Web Browser** template (or any community layout meant for desktop apps). Its
   left trackpad is already a scroll wheel, which is what the list needs.
3. If you would rather adjust the layout by hand, choose **Edit Layout → Trackpads → Left
   Trackpad → Scroll Wheel**, and use the cog beside *Scroll* to set the swipe direction to
   **Vertical** if you prefer swiping over circular motion.

The **touchscreen** works without any of this: drag the list to scroll it, flick it to send
it gliding, and tap the buttons as usual.

### First run

1. Open **Settings** and set your **Download folder** and **Games folder** locations.
2. Put your game archives into the Download folder.
3. Use the interface to **install**, **launch**, and **remove** games.

### Using it on the Steam Deck

Because the Steam Deck doesn't show window decorations by default, RenPyDeck includes an
on-screen **Exit** button. Use it to close the application — the usual
close/minimise/maximise buttons are hidden, so Exit is how you leave.

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
permission to reach it. RenPyDeck's folder browser is a plain view of the filesystem as the
sandbox presents it: it cannot grant access to anything the sandbox hides, so a folder you
have not allowed shows up empty or unreadable. Grant it a persistent permission instead —
either use **[Flatseal](https://flathub.org/apps/com.github.tchx84.Flatseal)** to add the
folder, or run `flatpak override`, for example:

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

The internals live in **[Development.md](Development.md)**: the tech stack, the project
layout, running RenPyDeck from source, building the Flatpak bundle, the anatomy of a Ren'Py
game, and the behaviours the implementation depends on.

---

## Roadmap / status

RenPyDeck's intended, complete feature set. Core goals:

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
