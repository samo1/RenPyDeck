"""Workarounds for known defects in individual games.

Some games ship with a piece of their developer's tooling still switched on,
and it gets in the way of playing. Each such defect RenPyDeck knows about is a
:class:`Patch`: the script file that gives it away, and a small Ren'Py script
that neutralises it. Ren'Py loads loose ``.rpy`` files from a game's ``game``
folder alongside the ``.rpa`` archives the rest of the game is packed in, so a
fix is one extra file — the game's own files are never touched, and deleting
the file undoes it.

A defect is recognised by **file name** alone. Most games ship only compiled
``.rpyc`` scripts, which cannot be read safely without the engine (they are
pickles), but every script's name is listed in plain view in the archive's
index. That index sits at the end of the ``.rpa`` file and stays small even when
the archive holds gigabytes, so checking a game costs one short read per
archive.

This module does no GTK work; :func:`renpydeck.launcher.run` applies the
patches just before it starts a game, which covers games installed before a
patch was known as well as games unpacked by hand.
"""

import io
import os
import pickle
import zlib
from dataclasses import dataclass
from pathlib import Path

#: Prefix of every file RenPyDeck adds to a game, so they are easy to tell
#: apart from the game's own scripts.
PATCH_PREFIX = "zz_renpydeck_"

#: Archive formats whose index can be found: the header line is the format tag
#: followed by the index offset in hex (and, for 3.x, an obfuscation key that
#: only matters for the archive's contents, not for the names in the index).
_RPA_TAGS = (b"RPA-2.0", b"RPA-3.0", b"RPA-3.2")

#: Upper bound on an index worth reading. Real indexes are a few hundred
#: kilobytes at most; a bigger "index" means a corrupt or foreign file.
_MAX_INDEX_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class Patch:
    """A known defect, how to recognise it, and the script that fixes it."""

    #: Short identifier; the fix is written to ``game/zz_renpydeck_<name>.rpy``.
    name: str
    #: Base name (without ``.rpy``/``.rpyc``) of a script that only the
    #: affected games ship.
    marker: str
    #: The Ren'Py script dropped into the game's ``game`` folder.
    script: str

    @property
    def filename(self) -> str:
        return f"{PATCH_PREFIX}{self.name}.rpy"


PATCHES = (
    # A note-taking panel the developer of "Much Bigger Than my Boyfriend" uses
    # to mark broken images and sounds while testing, shown from `label start`.
    # Its text input is always focused and sits above everything else, so it
    # takes every typed key — Shift+A types an "A" into the note instead of
    # opening Ren'Py's accessibility menu. It is part of the developer's own
    # `ADDON_*` toolkit, so their other games may carry it too.
    Patch(
        name="notes_panel",
        marker="ADD_write_errors",
        script=(
            "# Added by RenPyDeck. The game ships with its developer's notes\n"
            "# panel switched on; its text input swallows keyboard shortcuts\n"
            "# such as Shift+A. This replaces the panel with nothing.\n"
            "init 999:\n"
            "    screen notes_screen():\n"
            "        pass\n"
        ),
    ),
)


def apply_patches(game_root: str | Path) -> list[str]:
    """Add the fix for every known defect the game in *game_root* has.

    *game_root* is the folder holding the launch script and the ``game``
    folder. Returns the names of the patches that apply, whether their file
    was written now or was already in place. Raises `OSError` when a fix
    cannot be written.
    """
    game_dir = Path(game_root) / "game"
    if not game_dir.is_dir():
        return []

    scripts = script_names(game_dir)
    applied = []
    for patch in PATCHES:
        if patch.marker not in scripts:
            continue
        target = game_dir / patch.filename
        try:
            current = target.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != patch.script:
            target.write_text(patch.script, encoding="utf-8")
        applied.append(patch.name)
    return applied


def script_names(game_dir: Path) -> set[str]:
    """Base names of every Ren'Py script the game ships, loose or archived.

    A script counts whether it is a ``.rpy`` source or a compiled ``.rpyc``,
    and whichever folder it sits in, so ``ADDON/foo.rpyc`` contributes
    ``foo``.
    """
    names = set()
    for dirpath, _dirnames, filenames in os.walk(game_dir):
        for filename in filenames:
            if filename.lower().endswith(".rpa"):
                files = _archive_files(Path(dirpath) / filename)
            else:
                files = [filename]
            for path in files:
                stem, dot, suffix = path.rpartition("/")[2].rpartition(".")
                if dot and suffix.lower() in ("rpy", "rpyc"):
                    names.add(stem)
    return names


class _IndexUnpickler(pickle.Unpickler):
    """Unpickles an archive index without ever constructing an object.

    An index is plain data — a dict of file names to lists of tuples — so any
    request for a class means the file is not what it claims to be. Refusing
    every class is what makes reading a downloaded archive's pickle safe.
    """

    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"unexpected {module}.{name} in archive index")


def _archive_files(archive: Path) -> list[str]:
    """The file names listed in a ``.rpa`` archive's index.

    An archive that cannot be read — an unknown format, a custom one some
    games use to hide their files, or a damaged file — lists nothing.
    """
    try:
        with archive.open("rb") as file:
            header = file.readline(256).split()
            if len(header) < 2 or header[0] not in _RPA_TAGS:
                return []
            file.seek(int(header[1], 16))
            compressed = file.read(_MAX_INDEX_BYTES + 1)
        if len(compressed) > _MAX_INDEX_BYTES:
            return []
        index = _IndexUnpickler(
            io.BytesIO(zlib.decompress(compressed)),
            encoding="utf-8",
            errors="replace",
        ).load()
    except Exception:  # a damaged pickle can fail in many ways
        return []
    if not isinstance(index, dict):
        return []
    return [
        name.decode("utf-8", "replace") if isinstance(name, bytes) else name
        for name in index
        if isinstance(name, (str, bytes))
    ]
