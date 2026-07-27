"""An in-window folder browser.

RenPyDeck cannot use ``Gtk.FileDialog``: it goes through the XDG desktop
portal, and in the Steam Deck's gaming mode (the gamescope session) the portal
is not reachable, so the picker never appears while its modal request leaves
the window looking frozen. Nothing here opens a window or talks to the portal —
the browser is an ordinary page pushed onto the window's navigation stack.

It shows the folders inside the current one, a few *places* worth jumping to,
an **Up** button, and a button that picks whatever folder is currently open.
Folders that cannot be read (outside the Flatpak sandbox, say) are shown as
such rather than silently omitted, so it is clear when a permission is missing.
"""

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib  # noqa: E402

from .config import default_download_dir, default_game_dir
from .touchscroll import enable_drag_scrolling


class FolderChooserPage(Adw.NavigationPage):
    """A page that browses folders and hands back the one the user picks."""

    def __init__(self, title, start_path, on_selected, on_exit):
        super().__init__(title=title)

        self.on_selected = on_selected
        self.path = self._starting_path(start_path)

        toolbar_view = Adw.ToolbarView()
        self.set_child(toolbar_view)

        header = Adw.HeaderBar()  # its back button cancels the choice

        self.up_button = Gtk.Button(label="Up")
        self.up_button.connect("clicked", self.on_up_clicked)
        header.pack_start(self.up_button)

        exit_button = Gtk.Button(label="Exit")
        exit_button.add_css_class("destructive-action")
        exit_button.connect("clicked", on_exit)
        header.pack_end(exit_button)

        use_button = Gtk.Button(label="Use this folder")
        use_button.add_css_class("suggested-action")
        use_button.connect("clicked", self.on_use_clicked)
        header.pack_end(use_button)

        toolbar_view.add_top_bar(header)

        self.scroller = Gtk.ScrolledWindow(vexpand=True)
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        enable_drag_scrolling(self.scroller)  # the Deck's touchscreen
        toolbar_view.set_content(self.scroller)

        self._show_current()

    # -- Navigation --------------------------------------------------------

    @staticmethod
    def _starting_path(start_path) -> Path:
        """Fall back to the nearest existing parent, or home, if need be."""
        candidate = Path(start_path) if start_path else Path(GLib.get_home_dir())
        while not candidate.is_dir() and candidate != candidate.parent:
            candidate = candidate.parent
        return candidate

    def _go_to(self, path):
        self.path = path
        self._show_current()

    def on_up_clicked(self, _button):
        self._go_to(self.path.parent)

    def on_use_clicked(self, _button):
        self.on_selected(str(self.path))

    # -- Contents ----------------------------------------------------------

    def _show_current(self):
        self.up_button.set_sensitive(self.path.parent != self.path)

        # Deliberately not an Adw.PreferencesPage: that brings a scrolled
        # window of its own, which would scroll instead of ours — and ours is
        # the one that can be dragged by finger.
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.set_margin_top(18)
        content.set_margin_bottom(18)
        content.set_margin_start(12)
        content.set_margin_end(12)

        places = self._places_group()
        if places is not None:
            content.append(places)
        content.append(self._folders_group())

        self.scroller.set_child(Adw.Clamp(child=content))
        self.scroller.get_vadjustment().set_value(0)  # a new folder starts at the top

    def _places_group(self):
        """Shortcuts to the folders a Steam Deck user actually needs."""
        candidates = [
            ("Home", Path(GLib.get_home_dir())),
            ("Downloads", Path(default_download_dir())),
            ("RenPyDeck games", Path(default_game_dir())),
            ("SD card and other drives", Path("/run/media")),
        ]

        group = Adw.PreferencesGroup(title="Places")
        seen = set()
        added = False
        for name, path in candidates:
            if path in seen or not path.is_dir():
                continue
            seen.add(path)
            group.add(self._folder_row(name, path, subtitle=str(path)))
            added = True
        return group if added else None

    def _folders_group(self):
        group = Adw.PreferencesGroup(title="Folders in this location")
        group.set_description(str(self.path))

        try:
            children = sorted(
                (child for child in self.path.iterdir()
                 if child.is_dir() and not child.name.startswith(".")),
                key=lambda child: child.name.casefold(),
            )
        except OSError as error:
            group.add(self._plain_row(f"This folder cannot be read: {error.strerror}."))
            return group

        if not children:
            group.add(self._plain_row("No sub-folders here."))
            return group

        for child in children:
            group.add(self._folder_row(child.name, child))
        return group

    def _folder_row(self, title, path, subtitle=None):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_use_markup(False)
        row.set_title_lines(0)
        row.set_activatable(True)
        row.connect("activated", lambda _row, target=path: self._go_to(target))
        row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        return row

    @staticmethod
    def _plain_row(text):
        row = Adw.ActionRow(title=text)
        row.set_use_markup(False)
        row.set_title_lines(0)
        row.set_sensitive(False)
        return row
