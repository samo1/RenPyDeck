"""Discovery of the games RenPyDeck knows about.

Two folders make up the library (see :mod:`renpydeck.config`):

* the **download folder** holds games as compressed archives — these are
  *downloaded* games, waiting to be installed;
* the **game folder** holds one sub-folder per extracted game — these are
  *installed* games, ready to be launched.

Both are scanned and merged into a single, alphabetically sorted list of
:class:`GameEntry` objects. A game that has been installed *and* still has its
archive around shows up once, as a single entry that knows about both paths.
"""

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
    """Return an entry for every extracted game in the game folder."""
    entries = []
    for path in _list_dir(game_dir):
        if path.name.startswith(".") or not path.is_dir():
            continue
        entries.append(GameEntry(name=path.name, install_dir=path))
    return entries


def find_games(download_dir: str, game_dir: str) -> list[GameEntry]:
    """Scan both folders and return the merged library, sorted by name."""
    entries: dict[str, GameEntry] = {}

    for entry in find_installed(game_dir):
        entries[_match_key(entry.name)] = entry

    for entry in find_downloaded(download_dir):
        # An archive is keyed by its stem, which is what it extracts to.
        key = _match_key(archive_stem(entry.name) or entry.name)
        installed = entries.get(key)
        if installed is not None:
            # Same game, already installed: keep the folder name as the title.
            installed.archive = entry.archive
        else:
            entries[key] = entry

    return sorted(entries.values(), key=lambda entry: entry.sort_key)
