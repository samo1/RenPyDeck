"""RenPyDeck application entry point.

The window opens on the **library** — a single alphabetically sorted list of
every game RenPyDeck can see, whether it is still a downloaded archive or an
already extracted (installed) game. Each entry shows only the actions that
apply to it: *Install* for a downloaded archive, *Launch* for an installed
game, *Remove* for either.

Behind the library sits the **configuration screen** for choosing the two
folders RenPyDeck works with — the *Download folder* (where downloaded game
archives live) and the *Game folder* (where games are extracted/installed).

Everything lives in **one window**, as pages of an ``Adw.NavigationView``:
screens, questions, errors and the folder browser alike. RenPyDeck opens no
dialogs and no second windows at all, because in the Steam Deck's gaming mode
(the gamescope session) a second window may never be shown — and the system
folder picker, which needs the XDG desktop portal, would simply hang there.

The Steam Deck's gaming mode hides window decorations, so the window carries its
own in-window header bar with an **Exit** button — there is no titlebar close
button to rely on.

*Install* unpacks an archive into the game folder (see
:mod:`renpydeck.installer`), *Launch* runs an installed game (see
:mod:`renpydeck.launcher`) and *Remove* deletes it for good (see
:mod:`renpydeck.remover`), after asking. All three work on a worker thread with
the library's buttons disabled until they finish — so a big archive never
freezes the window, and only one game runs at a time.
"""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gio, Adw, GLib  # noqa: E402

from . import __version__
from .config import Config
from .folderchooser import FolderChooserPage
from .games import GameEntry, find_games
from .installer import InstallError, install
from .launcher import LaunchError, run
from .remover import RemoveError, describe, remove
from .touchscroll import enable_drag_scrolling

APP_ID = "sk.meluzina.RenPyDeck"


class RenPyDeckWindow(Adw.ApplicationWindow):
    """The main (and currently only) application window."""

    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)

        self.config = config
        # Set while an install runs on a worker thread; the library's buttons
        # stay disabled until it finishes, so only one runs at a time.
        self.busy = False
        self.game_buttons: list[Gtk.Button] = []

        self.set_title("RenPyDeck")
        self.set_default_size(800, 480)  # matches the Steam Deck's screen ratio

        # Both screens live in the same window: the library is the root page,
        # the configuration screen is pushed on top of it when requested.
        self.navigation = Adw.NavigationView()
        self.set_content(self.navigation)
        # Coming back from the configuration screen may mean the folders
        # changed, so rescan them.
        self.navigation.connect("popped", lambda *_: self.refresh_library())

        self.settings_page = self._build_settings_page()
        self.navigation.add(self._build_library_page())

        self.refresh_library()

    # -- Library screen ----------------------------------------------------

    def _build_library_page(self) -> Adw.NavigationPage:
        """Build the game list screen shown on launch."""
        toolbar_view = Adw.ToolbarView()

        header = self._make_header()

        self.settings_button = Gtk.Button(label="Settings")
        self.settings_button.connect("clicked", self.on_settings_clicked)
        header.pack_start(self.settings_button)

        self.refresh_button = Gtk.Button(label="Refresh")
        self.refresh_button.connect("clicked", lambda _button: self.refresh_library())
        header.pack_start(self.refresh_button)

        toolbar_view.add_top_bar(header)

        # The list is rebuilt from scratch on every scan, so the scroller's
        # child is swapped rather than mutated in place.
        self.library_scroller = Gtk.ScrolledWindow(vexpand=True)
        self.library_scroller.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        enable_drag_scrolling(self.library_scroller)  # the Deck's touchscreen
        # Toasts report how an install went without covering the list.
        self.toasts = Adw.ToastOverlay(child=self.library_scroller)
        toolbar_view.set_content(self.toasts)

        return Adw.NavigationPage(title="RenPyDeck", child=toolbar_view)

    def refresh_library(self) -> None:
        """Rescan both configured folders and rebuild the game list."""
        games = find_games(self.config.download_dir, self.config.game_dir)
        if games:
            self.library_scroller.set_child(self._build_game_list(games))
        else:
            self.library_scroller.set_child(self._build_empty_state())

    def _build_game_list(self, games: list[GameEntry]) -> Gtk.Widget:
        self.game_buttons = []
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")
        for game in games:
            listbox.append(self._make_game_row(game))

        clamp = Adw.Clamp(child=listbox)
        clamp.set_margin_top(18)
        clamp.set_margin_bottom(18)
        clamp.set_margin_start(12)
        clamp.set_margin_end(12)
        return clamp

    def _build_empty_state(self) -> Gtk.Widget:
        return Adw.StatusPage(
            title="No games found",
            description=(
                "Put game archives in the download folder, or point RenPyDeck "
                "at the folders you already use in Settings."
            ),
        )

    def _make_game_row(self, game: GameEntry) -> Adw.ActionRow:
        """Build one list row: the game's name plus the actions it allows.

        Only the applicable actions get a button — Install for a downloaded
        archive, Launch for an installed game — so a row never shows a control
        that cannot be used.
        """
        row = Adw.ActionRow(title=game.name, subtitle=self._describe(game))
        row.set_use_markup(False)  # names are plain text, not Pango markup
        row.set_title_lines(0)  # wrap long archive names instead of clipping

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.set_valign(Gtk.Align.CENTER)

        if game.is_downloaded:
            install = Gtk.Button(label="Install")
            install.connect("clicked", self.on_install_clicked, game)
            buttons.append(install)
            self.game_buttons.append(install)

        if game.is_installed:
            launch = Gtk.Button(label="Launch")
            launch.add_css_class("suggested-action")
            launch.connect("clicked", self.on_launch_clicked, game)
            buttons.append(launch)
            self.game_buttons.append(launch)

        # Remove applies either way: an entry is downloaded, installed or both.
        remove = Gtk.Button(label="Remove")
        remove.add_css_class("destructive-action")
        remove.connect("clicked", self.on_remove_clicked, game)
        buttons.append(remove)
        self.game_buttons.append(remove)

        row.add_suffix(buttons)
        return row

    @staticmethod
    def _describe(game: GameEntry) -> str:
        if game.is_installed and game.is_downloaded:
            return "Installed — archive still in the download folder"
        if game.is_installed:
            return "Installed"
        return "Downloaded — not installed yet"

    # -- Installing --------------------------------------------------------

    def on_install_clicked(self, button, game: GameEntry):
        """Unpack a downloaded game into the game folder, off the main thread."""
        if self.busy or not game.is_downloaded:
            return

        self._set_busy(True)
        button.set_label("Installing…")

        thread = threading.Thread(
            target=self._install_worker,
            args=(game.archive,),
            daemon=True,
        )
        thread.start()

    def _install_worker(self, archive):
        """Runs on a worker thread — must not touch any widget directly."""
        try:
            installed = install(archive, self.config.game_dir)
        except InstallError as error:
            GLib.idle_add(self._on_install_finished, None, str(error))
        except Exception as error:  # unexpected, but must not kill the thread
            GLib.idle_add(
                self._on_install_finished,
                None,
                f"Unexpected error while installing {archive.name}: {error}",
            )
        else:
            GLib.idle_add(self._on_install_finished, installed, None)

    def _on_install_finished(self, installed, error):
        """Back on the main thread: report the result and rescan the folders."""
        self._set_busy(False)
        self.refresh_library()  # rebuilds the rows with fresh, enabled buttons

        if error is not None:
            self._show_error("Install failed", error)
        else:
            self.toasts.add_toast(Adw.Toast(title=f"Installed {installed.name}"))
        return GLib.SOURCE_REMOVE

    # -- Launching ---------------------------------------------------------

    def on_launch_clicked(self, button, game: GameEntry):
        """Run an installed game, waiting for it on a worker thread.

        The game opens its own window and RenPyDeck stays put behind it with
        everything disabled, so only one game can be running at a time.
        """
        if self.busy or not game.is_installed:
            return

        self._set_busy(True)
        button.set_label("Running…")

        thread = threading.Thread(
            target=self._launch_worker,
            args=(game.install_dir,),
            daemon=True,
        )
        thread.start()

    def _launch_worker(self, install_dir):
        """Runs on a worker thread — must not touch any widget directly."""
        try:
            status = run(install_dir)
        except LaunchError as error:
            GLib.idle_add(self._on_launch_finished, install_dir, None, str(error))
        except Exception as error:  # unexpected, but must not kill the thread
            GLib.idle_add(
                self._on_launch_finished,
                install_dir,
                None,
                f"Unexpected error while running {install_dir.name}: {error}",
            )
        else:
            GLib.idle_add(self._on_launch_finished, install_dir, status, None)

    def _on_launch_finished(self, install_dir, status, error):
        """Back on the main thread: the game window has closed."""
        self._set_busy(False)
        self.refresh_library()  # the game may have been removed meanwhile

        if error is not None:
            self._show_error("Could not run the game", error)
        elif status != 0:
            self._show_error(
                "The game stopped unexpectedly",
                f"{install_dir.name} exited with status {status}. Its own "
                f"output, in the terminal RenPyDeck was started from, usually "
                f"says why.",
            )
        return GLib.SOURCE_REMOVE

    # -- Removing ----------------------------------------------------------

    def on_remove_clicked(self, button, game: GameEntry):
        """Ask first, then delete the game's files for good."""
        if self.busy:
            return

        self._push_message(
            heading=f"Remove {game.name}?",
            body=(
                f"This permanently deletes "
                f"{describe(game.archive, game.install_dir)}. "
                f"There is no way back — the files do not go to the trash."
            ),
            actions=[
                ("Cancel", None, None),
                (
                    "Remove",
                    "destructive-action",
                    lambda: self._start_remove(button, game),
                ),
            ],
        )

    def _start_remove(self, button, game: GameEntry):
        if self.busy:
            return

        self._set_busy(True)
        button.set_label("Removing…")

        thread = threading.Thread(
            target=self._remove_worker,
            args=(game,),
            daemon=True,
        )
        thread.start()

    def _remove_worker(self, game: GameEntry):
        """Runs on a worker thread — must not touch any widget directly."""
        try:
            remove(archive=game.archive, install_dir=game.install_dir)
        except RemoveError as error:
            GLib.idle_add(self._on_remove_finished, game.name, str(error))
        except Exception as error:  # unexpected, but must not kill the thread
            GLib.idle_add(
                self._on_remove_finished,
                game.name,
                f"Unexpected error while removing {game.name}: {error}",
            )
        else:
            GLib.idle_add(self._on_remove_finished, game.name, None)

    def _on_remove_finished(self, name, error):
        """Back on the main thread: report the result and rescan the folders."""
        self._set_busy(False)
        self.refresh_library()

        if error is not None:
            self._show_error("Remove failed", error)
        else:
            self.toasts.add_toast(Adw.Toast(title=f"Removed {name}"))
        return GLib.SOURCE_REMOVE

    def _set_busy(self, busy: bool) -> None:
        """Lock (or unlock) the actions that must not overlap an install."""
        self.busy = busy
        self.refresh_button.set_sensitive(not busy)
        self.settings_button.set_sensitive(not busy)
        if busy:
            for button in self.game_buttons:
                button.set_sensitive(False)

    # -- Messages and questions --------------------------------------------

    def _show_error(self, heading: str, body: str) -> None:
        self._push_message(heading, body, actions=[("Close", None, None)])

    def _push_message(self, heading: str, body: str, actions) -> None:
        """Show a message — or a question — as a page inside the window.

        Not a dialog: in the Steam Deck's gaming mode a second window is at the
        mercy of the compositor, so everything RenPyDeck shows stays part of
        the one window it already has.

        *actions* is a list of ``(label, css_class, callback)``. Every button
        returns to the previous page; a callback, if given, runs afterwards.
        """
        toolbar_view = Adw.ToolbarView()

        # Its back button is the same as Cancel/Close.
        toolbar_view.add_top_bar(self._make_header())

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        buttons.set_halign(Gtk.Align.CENTER)
        for label, css_class, callback in actions:
            button = Gtk.Button(label=label)
            if css_class:
                button.add_css_class(css_class)
            button.connect("clicked", self._on_message_action, callback)
            buttons.append(button)

        status = Adw.StatusPage(
            title=GLib.markup_escape_text(heading),
            description=GLib.markup_escape_text(body),
            child=buttons,
        )
        toolbar_view.set_content(status)

        self.navigation.push(Adw.NavigationPage(title=heading, child=toolbar_view))

    def _on_message_action(self, _button, callback):
        self.navigation.pop()
        if callback is not None:
            callback()

    # -- Configuration screen ----------------------------------------------

    def _build_settings_page(self) -> Adw.NavigationPage:
        toolbar_view = Adw.ToolbarView()

        # Shows a back button inside a NavigationView.
        toolbar_view.add_top_bar(self._make_header())

        page = Adw.PreferencesPage()
        toolbar_view.set_content(page)

        group = Adw.PreferencesGroup(
            title="Folders",
            description=(
                "Choose where RenPyDeck looks for downloaded game archives and "
                "where it installs extracted games."
            ),
        )
        page.add(group)

        self.download_row = self._make_folder_row(
            title="Download folder",
            subtitle=self.config.download_dir,
            on_choose=self.on_choose_download,
        )
        group.add(self.download_row)

        self.game_row = self._make_folder_row(
            title="Game folder",
            subtitle=self.config.game_dir,
            on_choose=self.on_choose_game,
        )
        group.add(self.game_row)

        return Adw.NavigationPage(title="Settings", child=toolbar_view)

    def on_settings_clicked(self, _button):
        self.navigation.push(self.settings_page)

    # -- UI construction helpers ------------------------------------------

    def _make_header(self) -> Adw.HeaderBar:
        """A header bar with the Exit button and no window controls.

        The close/minimise/maximise buttons are GTK's own, drawn into the
        header. They are hidden because the Exit button already closes
        RenPyDeck, and on the Steam Deck those small targets are of no use.
        The navigation back button is a separate thing and stays.
        """
        header = Adw.HeaderBar()
        header.set_show_start_title_buttons(False)
        header.set_show_end_title_buttons(False)

        exit_button = Gtk.Button(label="Exit")
        exit_button.add_css_class("destructive-action")
        exit_button.connect("clicked", self.on_exit_clicked)
        header.pack_end(exit_button)
        return header

    def _make_folder_row(self, title, subtitle, on_choose):
        """Build an Adw.ActionRow showing a folder path plus a Choose button."""
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        # Not selectable: selectable text carries a context menu, and GTK puts
        # that in a popover — another surface the Deck's gaming mode may not
        # show. The path is only there to be read.
        row.set_subtitle_lines(0)

        button = Gtk.Button(label="Choose…")
        button.set_valign(Gtk.Align.CENTER)
        button.add_css_class("flat")
        button.connect("clicked", on_choose)
        row.add_suffix(button)
        row.set_activatable_widget(button)
        return row

    # -- Folder selection --------------------------------------------------

    def on_choose_download(self, _button):
        self._choose_folder(
            title="Select download folder",
            current_path=self.config.download_dir,
            on_selected=self._set_download_dir,
        )

    def on_choose_game(self, _button):
        self._choose_folder(
            title="Select game folder",
            current_path=self.config.game_dir,
            on_selected=self._set_game_dir,
        )

    def _choose_folder(self, title, current_path, on_selected):
        """Browse for a folder on a page of our own.

        The system picker (``Gtk.FileDialog``) is deliberately not used: it
        needs the XDG desktop portal, which the Steam Deck's gaming mode does
        not provide, and a portal request that never answers leaves the window
        looking frozen.
        """
        page = FolderChooserPage(
            title=title,
            start_path=current_path,
            on_selected=lambda path: self._on_folder_chosen(path, on_selected),
            on_exit=self.on_exit_clicked,
        )
        self.navigation.push(page)

    def _on_folder_chosen(self, path, on_selected):
        self.navigation.pop()
        on_selected(path)

    def _set_download_dir(self, path):
        self.config.download_dir = path
        self.download_row.set_subtitle(path)
        self.config.save()  # settings apply (and persist) immediately

    def _set_game_dir(self, path):
        self.config.game_dir = path
        self.game_row.set_subtitle(path)
        self.config.save()

    # -- Actions -----------------------------------------------------------

    def on_exit_clicked(self, _button):
        # Close the window; the application quits when its last window closes.
        self.close()


class RenPyDeckApplication(Adw.Application):
    """The libadwaita application object."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.config = None

    def do_startup(self):
        Adw.Application.do_startup(self)

        # Always dark. The system's colour scheme reaches an app through the
        # desktop portal, which the Deck's gaming mode does not provide, so
        # every Flatpak app starts light there however the desktop is set.
        # (Adw.ColorScheme.PREFER_DARK instead would still follow a desktop
        # that explicitly asks for light.)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)

        # Load (and, on first run, create with defaults) the configuration,
        # then make sure the configured folders actually exist on disk.
        self.config = Config.load()
        self.config.ensure_directories()

    def do_activate(self):
        # Reuse the existing window if the app is activated again.
        window = self.props.active_window
        if not window:
            window = RenPyDeckWindow(config=self.config, application=self)
        window.present()


def main(argv=None):
    import sys

    app = RenPyDeckApplication()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
