"""Installing a downloaded game.

Installing means: unpack the archive from the download folder into the game
folder, check that it really is a game RenPyDeck can run — a Ren'Py game that
runs on Linux, or an HTML game — and fix up the file permissions such a game
needs. Whether the archive is then thrown away is
the user's choice (see :mod:`renpydeck.config`); by default it is kept, so the
game can be installed again without downloading it a second time.

What is unpacked has to hold either a ``renpy`` folder (the engine, which every
Ren'Py game ships) with a ``*.sh`` launch script beside it (the Linux
launcher), or — with no ``renpy`` folder anywhere — an HTML page to open as an
HTML game. Anything else, a Windows-only Ren'Py release included, is refused,
and the archive is left where it was.

The extracted files always land in a **new folder named after the archive**
(without its extension). Archives are inconsistent — some carry a top-level
folder of their own, some spill their files loose — and always creating the
folder ourselves keeps installed games consistently named either way.

Extraction is done with the standard library for zip and tar archives, and with
whichever external extractor is available for the rest (`.rar`, `.7z`). The
GNOME runtime the Flatpak is built on ships ``bsdtar``, which reads all of
them.

This module does no GTK work: it is called from a worker thread so a big
archive never freezes the interface.
"""

import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from .games import (
    GAME_ROOT_DEPTH,
    archive_stem,
    find_launch_script,
    find_web_page,
    has_engine_dir,
    has_windows_program,
)

#: Extensions handled in-process by the standard library.
_ZIP_SUFFIXES = (".zip",)
_TAR_SUFFIXES = (
    ".tar",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tar.zst",
    ".tbz2",
    ".tgz",
    ".txz",
)

#: External extractors tried in order for everything else, most preferred
#: first. Each entry maps the tool name to a function building its argv.
#: ``bsdtar`` (libarchive) comes first because it is part of the GNOME runtime
#: and handles rar and 7z as well as everything else.
_EXTRACTORS = (
    ("bsdtar", lambda archive, dest: ["bsdtar", "-x", "-f", str(archive), "-C", str(dest)]),
    ("7zz", lambda archive, dest: ["7zz", "x", "-y", f"-o{dest}", str(archive)]),
    ("7z", lambda archive, dest: ["7z", "x", "-y", f"-o{dest}", str(archive)]),
    ("7za", lambda archive, dest: ["7za", "x", "-y", f"-o{dest}", str(archive)]),
    ("unar", lambda archive, dest: ["unar", "-q", "-D", "-o", str(dest), str(archive)]),
    ("unrar", lambda archive, dest: ["unrar", "x", "-y", "-idq", str(archive), f"{dest}/"]),
)

#: Prefix for the temporary folder an install is staged in. Staging keeps a
#: failed or interrupted extraction from leaving a half-installed game behind
#: under its final name.
_STAGING_PREFIX = ".renpydeck-installing-"


class InstallError(Exception):
    """Raised when a game could not be installed; the message is user-facing."""


def install_name(archive: Path) -> str:
    """The folder name *archive* installs into: its name minus the extension."""
    return archive_stem(archive.name) or archive.stem


def install(
    archive: Path,
    game_dir: str | Path,
    delete_archive: bool = False,
) -> Path:
    """Install *archive* into *game_dir* and return the created folder.

    With *delete_archive* the archive file is deleted once the game is in
    place. On failure — including an archive that turns out to hold no game
    RenPyDeck can run — nothing is left behind and the archive is kept either way, so
    the install can be retried or the game replaced.
    """
    archive = Path(archive)
    game_dir = Path(game_dir)
    target = game_dir / install_name(archive)

    if not archive.is_file():
        raise InstallError(f"The archive {archive.name} is gone.")
    if target.exists():
        # Not necessarily a game shown in the library: a folder that holds no
        # launchable game is not listed there, so name the folder rather than
        # telling the user to remove an entry they cannot see.
        raise InstallError(
            f"A folder named “{target.name}” is already in the game folder. "
            f"Remove or rename it before installing this archive."
        )

    staging = game_dir / (_STAGING_PREFIX + target.name)
    shutil.rmtree(staging, ignore_errors=True)
    try:
        staging.mkdir(parents=True)
    except OSError as error:
        raise InstallError(f"Could not write to the game folder: {error}") from error

    try:
        _extract(archive, staging)
        find_game_root(staging, archive.name)
        fix_permissions(staging)
        staging.rename(target)
    except InstallError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    except OSError as error:
        shutil.rmtree(staging, ignore_errors=True)
        raise InstallError(f"Could not install {archive.name}: {error}") from error

    if delete_archive:
        # The archive has served its purpose and the user asked for the space
        # back. This is a hard delete — the file does not go to the trash.
        try:
            archive.unlink()
        except OSError as error:
            raise InstallError(
                f"{target.name} was installed, but its archive could not be "
                f"deleted: {error}"
            ) from error

    return target


# -- Extraction -----------------------------------------------------------


def _extract(archive: Path, dest: Path) -> None:
    """Unpack *archive* into the (existing, empty) folder *dest*."""
    lowered = archive.name.lower()
    try:
        if lowered.endswith(_ZIP_SUFFIXES):
            with zipfile.ZipFile(archive) as zip_file:
                zip_file.extractall(dest)  # sanitises member paths
            return
        if lowered.endswith(_TAR_SUFFIXES):
            with tarfile.open(archive) as tar_file:
                tar_file.extractall(dest, filter="data")
            return
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as error:
        raise InstallError(f"Could not unpack {archive.name}: {error}") from error

    _extract_externally(archive, dest)


def _extract_externally(archive: Path, dest: Path) -> None:
    """Unpack formats the standard library cannot read (rar, 7z, …).

    Every available tool is tried in turn, because being installed does not
    mean a tool can read this particular archive: Fedora's 7-Zip, for one,
    ships without the RAR decoder and rejects rar files outright. Only when
    they have all failed is the install refused, with each tool's complaint.
    """
    attempts = []
    for tool, build_argv in _EXTRACTORS:
        if shutil.which(tool) is None:
            continue
        _clear(dest)  # discard whatever a failed attempt left behind
        try:
            result = subprocess.run(
                build_argv(archive, dest),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            attempts.append(f"{tool}: {error}")
            continue
        if result.returncode == 0:
            return
        attempts.append(f"{tool}: {_failure_reason(result, tool)}")

    if attempts:
        raise InstallError(
            f"Could not unpack {archive.name}. " + "; ".join(attempts) + "."
        )
    raise InstallError(
        f"No tool available to unpack {archive.name}. Install one of: "
        + ", ".join(tool for tool, _ in _EXTRACTORS)
        + "."
    )


def _failure_reason(result: subprocess.CompletedProcess, tool: str) -> str:
    """The most informative line a failed extractor printed."""
    output = (result.stderr or "") + "\n" + (result.stdout or "")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    # Prefer a line that names the problem over a trailing summary.
    for line in lines:
        if "error" in line.lower() or "cannot" in line.lower():
            return line
    return lines[-1] if lines else f"exited with {result.returncode}"


def _clear(directory: Path) -> None:
    """Empty *directory* without removing it."""
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


# -- Validation -----------------------------------------------------------


def find_game_root(root: Path, archive_name: str = "the archive") -> Path:
    """Return the game's root folder inside *root*, or raise `InstallError`.

    For a Ren'Py game the root is the folder that holds both a ``renpy``
    folder and a ``*.sh`` launch script right next to it; a Windows-only
    release has the engine folder but no script. See
    :func:`renpydeck.games.find_launch_script`, which does the searching.
    Without a ``renpy`` folder anywhere, the archive may still be an HTML game,
    whose root is the folder of its start page (see
    :func:`renpydeck.games.find_web_page`) — unless it carries a Windows
    program, which makes it a Windows game built on web pages instead.

    The root also has to be near the top: the library only looks that far when
    it scans installed games, so a game buried deeper would install and then
    not be listed. It is refused here instead.
    """
    # Both searched without a depth limit, so that a game which is merely
    # buried too deep can be told apart from one that is not there at all.
    if has_engine_dir(root):
        script = find_launch_script(root)
        if script is None:
            raise InstallError(
                f"{archive_name} has no Linux launch script (a “.sh” file) next "
                f"to its “renpy” folder — it looks like a Windows-only release, "
                f"which the Steam Deck cannot run."
            )
        game_root = script.parent
    else:
        page = find_web_page(root)
        if page is None and has_windows_program(root):
            raise InstallError(
                f"{archive_name} holds a Windows program (an “.exe” file) but no "
                f"Ren'Py game — it looks like a Windows-only release, which the "
                f"Steam Deck cannot run."
            )
        if page is None:
            raise InstallError(
                f"{archive_name} holds neither a Ren'Py game (a “renpy” folder) "
                f"nor an HTML game (an “.html” page), so RenPyDeck cannot "
                f"install it."
            )
        game_root = page.parent

    depth = len(game_root.relative_to(root).parts)
    if depth > GAME_ROOT_DEPTH:
        raise InstallError(
            f"{archive_name} keeps the game {depth} folders deep inside itself, "
            f"which is deeper than RenPyDeck looks. Repack it with the game "
            f"nearer the top, or unpack it into the game folder yourself."
        )
    return game_root


# -- Post-processing ------------------------------------------------------


def fix_permissions(root: Path) -> int:
    """Make an extracted game runnable and return how many files were fixed.

    Archives routinely lose the executable bit, which leaves the game unable to
    start. Two things need it back:

    * every ``*.sh`` launch script, wherever it sits in the tree;
    * everything inside a ``lib`` folder — the Ren'Py runtime binary, ``python``
      and the shared libraries. Only the Linux x86_64 runtime is actually
      needed, but its folder name varies between Ren'Py generations
      (``lib/py3-linux-x86_64``, ``lib/linux-x86_64``, …), so the whole ``lib``
      tree is covered rather than guessing. The ``lib`` folder itself is
      searched for, because the game root may sit a level or two down inside
      the archive.
    """
    fixed = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        directory = Path(dirpath)
        inside_lib = any(
            part.lower() == "lib" for part in directory.relative_to(root).parts
        )
        for name in filenames:
            if inside_lib or name.lower().endswith(".sh"):
                if _make_executable(directory / name):
                    fixed += 1
    return fixed


def _make_executable(path: Path) -> bool:
    """Add the executable bit to *path*; return whether anything changed."""
    if path.is_symlink():
        # Following a symlink could change permissions outside the game.
        return False
    try:
        mode = path.stat().st_mode
        wanted = mode | 0o111
        if wanted == mode:
            return False
        path.chmod(wanted)
    except OSError:
        # A single stubborn file should not fail the whole install.
        return False
    return True
