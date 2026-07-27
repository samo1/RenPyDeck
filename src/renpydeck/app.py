"""RenPyDeck application entry point.

The window opens on the **library** — a single alphabetically sorted list of
every game RenPyDeck can see, whether it is still a downloaded archive or an
already extracted (installed) game. Each entry offers *Install*, *Launch* and
*Remove*; a button is enabled only when it makes sense for that entry's state.

Behind the library sits the **configuration screen** for choosing the two
folders RenPyDeck works with — the *Download folder* (where downloaded game
archives live) and the *Game folder* (where games are extracted/installed).
The two screens share one window via an ``Adw.NavigationView``; the only popup
is the system folder picker (``Gtk.FileDialog``), which routes through the XDG
desktop portal when running inside the Flatpak sandbox.

The Steam Deck's gaming mode hides window decorations, so the window carries its
own in-window header bar with an **Exit** button — there is no titlebar close
button to rely on.

*Install* unpacks an archive into the game folder (see
:mod:`renpydeck.installer`); it runs on a worker thread so a big archive does
not freeze the window. *Launch* and *Remove* land in later milestones and are
inert for now.
"""

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gio, Adw, GLib  # noqa: E402

from . import __version__
from .config import Config
from .games import GameEntry, find_games
from .installer import InstallError, install

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

        header = Adw.HeaderBar()

        self.settings_button = Gtk.Button(label="Settings")
        self.settings_button.connect("clicked", self.on_settings_clicked)
        header.pack_start(self.settings_button)

        self.refresh_button = Gtk.Button(label="Refresh")
        self.refresh_button.connect("clicked", lambda _button: self.refresh_library())
        header.pack_start(self.refresh_button)

        exit_button = Gtk.Button(label="Exit")
        exit_button.add_css_class("destructive-action")
        exit_button.connect("clicked", self.on_exit_clicked)
        header.pack_end(exit_button)

        toolbar_view.add_top_bar(header)

        # The list is rebuilt from scratch on every scan, so the scroller's
        # child is swapped rather than mutated in place.
        self.library_scroller = Gtk.ScrolledWindow(vexpand=True)
        self.library_scroller.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
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
        """Build one list row: the game's name plus its three action buttons."""
        row = Adw.ActionRow(title=game.name, subtitle=self._describe(game))
        row.set_use_markup(False)  # names are plain text, not Pango markup
        row.set_title_lines(0)  # wrap long archive names instead of clipping

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.set_valign(Gtk.Align.CENTER)

        install = Gtk.Button(label="Install")
        install.set_sensitive(game.is_downloaded)
        install.connect("clicked", self.on_install_clicked, game)
        buttons.append(install)

        # Launch and Remove land in later milestones; for now the buttons only
        # show which operations apply to this entry.
        launch = Gtk.Button(label="Launch")
        launch.add_css_class("suggested-action")
        launch.set_sensitive(game.is_installed)
        buttons.append(launch)

        remove = Gtk.Button(label="Remove")
        remove.add_css_class("destructive-action")
        remove.set_sensitive(game.is_downloaded or game.is_installed)
        buttons.append(remove)

        self.game_buttons += [install, launch, remove]

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

    def _set_busy(self, busy: bool) -> None:
        """Lock (or unlock) the actions that must not overlap an install."""
        self.busy = busy
        self.refresh_button.set_sensitive(not busy)
        self.settings_button.set_sensitive(not busy)
        if busy:
            for button in self.game_buttons:
                button.set_sensitive(False)

    def _show_error(self, heading: str, body: str) -> None:
        dialog = Adw.AlertDialog(heading=heading, body=body)
        dialog.add_response("close", "Close")
        dialog.present(self)

    # -- Configuration screen ----------------------------------------------

    def _build_settings_page(self) -> Adw.NavigationPage:
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()  # shows a back button inside a NavigationView
        exit_button = Gtk.Button(label="Exit")
        exit_button.add_css_class("destructive-action")
        exit_button.connect("clicked", self.on_exit_clicked)
        header.pack_end(exit_button)
        toolbar_view.add_top_bar(header)

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

    def _make_folder_row(self, title, subtitle, on_choose):
        """Build an Adw.ActionRow showing a folder path plus a Choose button."""
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_subtitle_selectable(True)

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
        """Open the system folder picker (a portal-backed popup when sandboxed)."""
        dialog = Gtk.FileDialog()
        dialog.set_title(title)
        dialog.set_modal(True)
        if current_path:
            dialog.set_initial_folder(Gio.File.new_for_path(current_path))

        dialog.select_folder(self, None, self._on_folder_chosen, on_selected)

    def _on_folder_chosen(self, dialog, result, on_selected):
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            # The user cancelled, or the portal denied the request.
            return
        if folder is not None:
            on_selected(folder.get_path())

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
