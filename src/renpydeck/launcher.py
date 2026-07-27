"""Running an installed game.

A Ren'Py game is started through the ``*.sh`` script that sits next to its
``renpy`` folder. The script resolves the platform at runtime and execs the
matching binary under ``lib/``, and it expects to be run **from the folder it
lives in** — so that folder, the game root, becomes the working directory.

The game takes over the screen in its own window while RenPyDeck waits for it
to exit. Only one game runs at a time; the caller enforces that by waiting on
:func:`run` from a worker thread and keeping the library's buttons disabled
until it returns.
"""

import os
import subprocess
from pathlib import Path

from .games import find_engine_dirs, find_launch_script
from .installer import fix_permissions


class LaunchError(Exception):
    """Raised when a game could not be started; the message is user-facing."""


def find_script(game_dir: str | Path) -> Path:
    """Return the launch script of the game in *game_dir*, or raise."""
    root = Path(game_dir)
    if not root.is_dir():
        raise LaunchError(f"{root.name} is no longer in the game folder.")

    script = find_launch_script(root)
    if script is not None:
        return script

    if find_engine_dirs(root):
        raise LaunchError(
            f"{root.name} has no Linux launch script (a “.sh” file) next to "
            f"its “renpy” folder, so it cannot be started here."
        )
    raise LaunchError(
        f"{root.name} does not look like a Ren'Py game: it has no “renpy” "
        f"folder."
    )


def run(game_dir: str | Path) -> int:
    """Start the game in *game_dir* and block until it exits.

    Returns the game's exit status. The game's own output is left on
    RenPyDeck's stdout/stderr, which is where a crashing game explains itself.
    """
    script = find_script(game_dir)

    if not os.access(script, os.X_OK):
        # A game copied in by hand (rather than installed here) may never have
        # had its permissions fixed; do it now instead of failing.
        fix_permissions(Path(game_dir))

    try:
        process = subprocess.Popen([str(script)], cwd=script.parent)
    except OSError as error:
        raise LaunchError(f"Could not start {script.name}: {error}") from error

    return process.wait()
