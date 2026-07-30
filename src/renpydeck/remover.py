"""Removing a game from the library.

A library entry can be an extracted game in the game folder, an archive in the
download folder, or both — which is the normal state of an installed game
whose archive was kept. The two are removed independently: the caller passes
the one the user asked to delete, and the other is left alone.

This is a **hard delete**: files are unlinked, not moved to the trash, and
nothing can be undone afterwards. The caller is expected to have asked the user
first.
"""

import shutil
from pathlib import Path


class RemoveError(Exception):
    """Raised when something could not be deleted; the message is user-facing."""


def describe(archive: Path | None, install_dir: Path | None) -> str:
    """Name what :func:`remove` would delete, for a confirmation prompt.

    Names rather than full paths: the two folders are the user's own choice and
    are shown on the configuration screen, so repeating them here would only
    bury the point in a wrapped path.
    """
    items = []
    if install_dir is not None:
        items.append(f"the installed game “{install_dir.name}”")
    if archive is not None:
        items.append(f"the archive “{archive.name}”")
    return " and ".join(items)


def remove(archive: Path | None = None, install_dir: Path | None = None) -> None:
    """Delete the extracted game and/or the archive, permanently.

    Whatever is missing already counts as removed, so a game deleted outside
    RenPyDeck does not turn into an error.
    """
    targets = [path for path in (install_dir, archive) if path is not None]
    if not targets:
        raise RemoveError("There is nothing to remove.")

    failures = []
    for path in targets:
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        except OSError as error:
            failures.append(f"{path.name}: {error}")

    if failures:
        raise RemoveError("Could not remove " + "; ".join(failures) + ".")
