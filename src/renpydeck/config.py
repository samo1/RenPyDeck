"""Configuration handling for RenPyDeck.

The configuration follows the XDG Base Directory specification: it lives in an
INI file at ``$XDG_CONFIG_HOME/renpydeck/config.ini`` (typically
``~/.config/renpydeck/config.ini``). Inside the Flatpak sandbox the same call
resolves to the app's private config directory automatically.

If the file does not exist yet, sensible defaults are written on first load:

* **Download folder** — the desktop's standard *Downloads* directory.
* **Game folder** — ``$XDG_DATA_HOME/renpydeck/games`` (e.g.
  ``~/.local/share/renpydeck/games``), the conventional, always-writable
  location for application-managed data.
"""

import configparser
import sys
from pathlib import Path

from gi.repository import GLib

#: Sub-directory name used under the XDG config/data directories.
APP_DIR_NAME = "renpydeck"

#: INI section/keys used in the config file.
_SECTION = "folders"
_KEY_DOWNLOAD = "download"
_KEY_GAME = "game"


def config_dir() -> Path:
    """Return the directory holding RenPyDeck's configuration file."""
    return Path(GLib.get_user_config_dir()) / APP_DIR_NAME


def config_file() -> Path:
    """Return the path to RenPyDeck's configuration file."""
    return config_dir() / "config.ini"


def default_download_dir() -> str:
    """The desktop's standard Downloads folder (with a sensible fallback)."""
    path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    if not path:
        # Headless or unusual setups may not define the special dir.
        path = str(Path(GLib.get_home_dir()) / "Downloads")
    return path


def default_game_dir() -> str:
    """The default location for extracted/installed games."""
    return str(Path(GLib.get_user_data_dir()) / APP_DIR_NAME / "games")


class Config:
    """In-memory view of the configuration, backed by the INI file."""

    def __init__(self, download_dir: str, game_dir: str):
        self.download_dir = download_dir
        self.game_dir = game_dir

    @classmethod
    def load(cls) -> "Config":
        """Load the configuration, creating it with defaults if absent."""
        path = config_file()
        if not path.exists():
            config = cls(default_download_dir(), default_game_dir())
            config.save()
            return config

        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        download = parser.get(
            _SECTION, _KEY_DOWNLOAD, fallback=default_download_dir()
        )
        game = parser.get(_SECTION, _KEY_GAME, fallback=default_game_dir())
        return cls(download, game)

    def ensure_directories(self) -> None:
        """Create the configured folders if they don't exist yet.

        Failures (e.g. a read-only or sandbox-restricted location) are logged
        rather than raised, so a misconfigured path never blocks startup.
        """
        for path in (self.download_dir, self.game_dir):
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
            except OSError as error:
                print(
                    f"RenPyDeck: could not create directory {path!r}: {error}",
                    file=sys.stderr,
                )

    def save(self) -> None:
        """Write the configuration back to disk, creating the dir if needed."""
        path = config_file()
        path.parent.mkdir(parents=True, exist_ok=True)

        parser = configparser.ConfigParser()
        parser[_SECTION] = {
            _KEY_DOWNLOAD: self.download_dir,
            _KEY_GAME: self.game_dir,
        }
        with open(path, "w", encoding="utf-8") as handle:
            parser.write(handle)
