"""RenPyDeck application entry point.

This is the very first milestone: a graphical window that does nothing but show
an **Exit** button. Its only purpose is to prove the application can be packaged
as a Flatpak, installed on the Steam Deck, launched, and cleanly closed.

The Steam Deck's gaming mode hides window decorations, so there is no titlebar
close button to rely on — hence the on-screen Exit button is essential even at
this early stage.

Later milestones will add the downloaded/installed game lists and the
install / run / uninstall functionality described in the README.
"""

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gio  # noqa: E402

from . import __version__

APP_ID = "sk.meluzina.RenPyDeck"


class RenPyDeckWindow(Gtk.ApplicationWindow):
    """The main (and currently only) application window."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("RenPyDeck")
        self.set_default_size(800, 480)  # matches the Steam Deck's screen ratio

        # Vertical layout: title/placeholder on top, Exit button at the bottom.
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        root.set_margin_top(48)
        root.set_margin_bottom(48)
        root.set_margin_start(48)
        root.set_margin_end(48)
        self.set_child(root)

        heading = Gtk.Label()
        heading.set_markup(
            '<span size="xx-large" weight="bold">RenPyDeck</span>'
        )
        root.append(heading)

        subtitle = Gtk.Label(
            label="Game manager and launcher for Ren'Py games on the Steam Deck."
        )
        subtitle.add_css_class("dim-label")
        root.append(subtitle)

        version = Gtk.Label(label=f"Version {__version__}")
        version.add_css_class("dim-label")
        root.append(version)

        # Spacer pushes the Exit button to the bottom of the window.
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        root.append(spacer)

        exit_button = Gtk.Button(label="Exit")
        exit_button.add_css_class("destructive-action")
        exit_button.add_css_class("pill")
        exit_button.set_halign(Gtk.Align.CENTER)
        exit_button.connect("clicked", self.on_exit_clicked)
        root.append(exit_button)

    def on_exit_clicked(self, _button):
        # Close the window; the application quits when its last window closes.
        self.close()


class RenPyDeckApplication(Gtk.Application):
    """The GTK application object."""

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

    def do_activate(self):
        # Reuse the existing window if the app is activated again.
        window = self.props.active_window
        if not window:
            window = RenPyDeckWindow(application=self)
        window.present()


def main(argv=None):
    import sys

    app = RenPyDeckApplication()
    return app.run(argv if argv is not None else sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
