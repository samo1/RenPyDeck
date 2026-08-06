"""Discovery of the games RenPyDeck knows about.

Two folders make up the library (see :mod:`renpydeck.config`):

* the **download folder** holds games as compressed archives — these are
  *downloaded* games, waiting to be installed;
* the **game folder** holds one sub-folder per extracted game — these are
  *installed* games, ready to be launched.

Both are scanned and merged into a single, alphabetically sorted list of
:class:`GameEntry` objects. A game that has been installed *and* still has its
archive around shows up once, as a single entry that knows about both paths.

This module also locates the **game root** inside an extracted game — the
folder holding the ``renpy`` engine folder and the ``*.sh`` launch script next
to it. Both installing (which refuses anything without that pair) and launching
(which runs the script) need it.

That same search decides which sub-folders of the game folder count as
installed games at all: only a folder RenPyDeck could actually launch is
listed, so whatever else the user keeps there stays out of the library.
Archives are *not* opened for the equivalent check — reading a multi-gigabyte
archive on every scan would make the library slow to open — so a downloaded
game is only found out to be unplayable when it is installed.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

#: Archive extensions treated as downloaded games. Longest first, so that
#: ``.tar.bz2`` wins over ``.bz2`` when stripping the suffix off a name.
ARCHIVE_SUFFIXES = (
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tar.zst",
    ".tbz2",
    ".tgz",
    ".txz",
    ".tar",
    ".zip",
    ".rar",
    ".7z",
)

#: How far below a game's folder its root — the folder with ``renpy`` and the
#: launch script — is allowed to sit. An archive wraps the game in a folder or
#: two at most, so anything deeper is not a game root. Installing applies the
#: same limit, so that what installs is exactly what the library then shows;
#: for the library it also keeps the scan to a folder listing or two per game
#: instead of a walk through its thousands of files.
GAME_ROOT_DEPTH = 2


def archive_stem(filename: str) -> str | None:
    """Return *filename* without its archive extension, or ``None``.

    ``None`` means the name does not look like a supported archive at all.
    """
    lowered = filename.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if lowered.endswith(suffix) and len(filename) > len(suffix):
            return filename[: -len(suffix)]
    return None


def _match_key(name: str) -> str:
    """Normalise a name so an archive and its extracted folder line up.

    Archive and folder names for the same game rarely match character for
    character (``CORRUPTING_JOY-0.03.pc.zip`` extracts to
    ``CORRUPTING_JOY-0.03-pc/``), so separators and case are dropped.
    """
    return "".join(char for char in name.lower() if char.isalnum())


@dataclass
class GameEntry:
    """One game in the library, in either or both of its two states."""

    name: str
    archive: Path | None = None
    install_dir: Path | None = None

    @property
    def is_downloaded(self) -> bool:
        """True when an archive is available to install from."""
        return self.archive is not None

    @property
    def is_installed(self) -> bool:
        """True when the game is extracted in the game folder."""
        return self.install_dir is not None

    @property
    def sort_key(self) -> str:
        return self.name.casefold()

    @property
    def key(self) -> str:
        """The game's identity, the same before and after it is installed.

        An archive is keyed by its stem, which is what it extracts to, so the
        archive and the folder it becomes agree on this. :func:`find_games`
        merges the two folders on it, and the library holds a game's selection
        across a rescan by it.
        """
        return _match_key(archive_stem(self.name) or self.name)


def _list_dir(path: str) -> list[Path]:
    """List a folder's entries, tolerating a missing or unreadable path."""
    try:
        return sorted(Path(path).iterdir())
    except OSError as error:
        print(f"RenPyDeck: could not read {path!r}: {error}", file=sys.stderr)
        return []


def find_downloaded(download_dir: str) -> list[GameEntry]:
    """Return an entry for every archive in the download folder."""
    entries = []
    for path in _list_dir(download_dir):
        if path.name.startswith(".") or not path.is_file():
            continue
        if archive_stem(path.name) is None:
            continue
        entries.append(GameEntry(name=path.name, archive=path))
    return entries


def find_installed(game_dir: str) -> list[GameEntry]:
    """Return an entry for every *launchable* extracted game in the game folder.

    A sub-folder only counts as an installed game when it holds a Ren'Py game
    with a Linux launch script (see :func:`find_launch_script`). Anything else
    the folder happens to contain — a Windows-only release, an unrelated
    folder, the leftovers of an interrupted extraction — is passed over rather
    than listed with a *Launch* button that could not work.
    """
    entries = []
    for path in _list_dir(game_dir):
        if path.name.startswith(".") or not path.is_dir():
            continue
        if find_launch_script(path, max_depth=GAME_ROOT_DEPTH) is None:
            continue
        entries.append(GameEntry(name=path.name, install_dir=path))
    return entries


def _walk_engine_dirs(root: Path, max_depth: int | None = None):
    """Yield folders under *root* that contain a ``renpy`` sub-folder.

    Every Ren'Py game ships the engine, so this is what marks a game root —
    searched for at any depth by default, because archives wrap the game in a
    folder (or two) inconsistently. *root* itself is checked first and the walk
    is lazy, so a caller that only wants the game root — the usual case, and
    usually right at the top — stops it after a single folder listing.

    *max_depth* bounds how far below *root* to descend; ``None`` means the
    whole tree. Older games carry further ``renpy`` folders deep inside
    ``lib/.../python2.7/``, which a bound also keeps out of the way — those
    have no launch script beside them either.
    """
    for dirpath, dirnames, _filenames in os.walk(root):
        directory = Path(dirpath)
        depth = len(directory.relative_to(root).parts)
        for name in dirnames:
            if name.lower() == "renpy":
                yield directory
        if max_depth is not None and depth >= max_depth:
            dirnames.clear()  # deep enough; do not descend any further


def has_engine_dir(root: Path, max_depth: int | None = None) -> bool:
    """Whether anything under *root* looks like a Ren'Py game at all.

    True when a ``renpy`` folder is there — with or without the launch script
    that would make it playable here, which is what tells a Windows-only
    release apart from something that is not a Ren'Py game.
    """
    return next(_walk_engine_dirs(root, max_depth), None) is not None


def find_launch_script(root: Path, max_depth: int | None = None) -> Path | None:
    """The Linux launch script of the game under *root*, if it has one.

    The script is the ``*.sh`` file sitting next to the ``renpy`` folder; its
    parent folder is the game root the script must be run from. A game without
    one is a Windows-only release the Steam Deck cannot run.
    """
    for directory in _walk_engine_dirs(root, max_depth):
        try:
            scripts = sorted(
                path
                for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() == ".sh"
            )
        except OSError:
            continue  # unreadable folder: no script we could run
        if not scripts:
            continue
        # Ren'Py names the launcher after the game and puts <Game>.py beside
        # it; prefer that pair when a game ships extra shell scripts.
        for script in scripts:
            if script.with_suffix(".py").is_file():
                return script
        return scripts[0]
    return None


def find_games(download_dir: str, game_dir: str) -> list[GameEntry]:
    """Scan both folders and return the merged library, sorted by name."""
    entries: dict[str, GameEntry] = {}

    for entry in find_installed(game_dir):
        entries[entry.key] = entry

    for entry in find_downloaded(download_dir):
        installed = entries.get(entry.key)
        if installed is not None:
            # Same game, already installed: keep the folder name as the title.
            installed.archive = entry.archive
        else:
            entries[entry.key] = entry

    return sorted(entries.values(), key=lambda entry: entry.sort_key)
