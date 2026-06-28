"""RenPyDeck application entry point.

Current milestone: a single-window **configuration screen** for choosing the two
folders RenPyDeck works with — the *Download folder* (where downloaded game
archives live) and the *Game folder* (where games are extracted/installed).

Everything is kept inside one window. The only popup is the system folder picker
(``Gtk.FileDialog``), which routes through the XDG desktop portal when running
inside the Flatpak sandbox.

The Steam Deck's gaming mode hides window decorations, so the window carries its
own in-window header bar with an **Exit** button — there is no titlebar close
button to rely on.

Later milestones will add the downloaded/installed game lists and the
install / run / uninstall functionality described in the README.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gio, Adw, GLib  # noqa: E402

from . import __version__
from .config import Config

APP_ID = "sk.meluzina.RenPyDeck"


class RenPyDeckWindow(Adw.ApplicationWindow):
    """The main (and currently only) application window."""

    def __init__(self, config: Config, **kwargs):
        super().__init__(**kwargs)

        self.config = config

        self.set_title("RenPyDeck")
        self.set_default_size(800, 480)  # matches the Steam Deck's screen ratio

        # An Adw.ToolbarView gives us an in-window header bar that is visible
        # even on the Steam Deck (where window decorations are hidden).
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        exit_button = Gtk.Button(label="Exit")
        exit_button.add_css_class("destructive-action")
        exit_button.connect("clicked", self.on_exit_clicked)
        header.pack_end(exit_button)
        toolbar_view.add_top_bar(header)

        # The configuration screen itself.
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
