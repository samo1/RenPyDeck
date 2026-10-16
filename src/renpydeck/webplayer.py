"""Playing an HTML game inside RenPyDeck's own window.

An HTML game is a web page with its images, sounds and fonts in folders beside
it (see :func:`renpydeck.games.find_web_page`). It plays in a WebKit web view on
a page of the window's ``Adw.NavigationView`` — not in a browser, and not in a
second window, which the Steam Deck's gaming mode may never show. WebKitGTK is
part of the GNOME runtime the Flatpak is built on, so this costs the bundle
nothing.

The game is not opened from a ``file://`` address. WebKit treats every local
file as its own origin there, which breaks the many games that load their
assets with ``fetch`` or ``XMLHttpRequest``. The files are served instead
through a URI scheme of RenPyDeck's own, ``renpydeck-game://local/<folder>/…``,
and only from inside the game being played.

Every game shares that one origin, and its storage — where a SugarCube game
keeps its saves, in ``localStorage`` — is kept in RenPyDeck's data folder for
good (``~/.var/app/sk.meluzina.RenPyDeck/data/renpydeck/web`` in the Flatpak).
The shared origin is deliberate: a new version of a game installs into a new
folder, and its saves still have to be there. Story formats key their saves by
the story, so two games do not mix.

The game stays offline and in place: following a link off the game (to the
author's Patreon, say) or into a new window is refused, since in gaming mode
there is no browser to come back from.
"""

import sys
from pathlib import Path
from urllib.parse import quote, unquote

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")

from gi.repository import Adw, Gio, GLib, GObject, Gtk, WebKit  # noqa: E402

SCHEME = "renpydeck-game"
_HOST = "local"

#: Types the web content cares about, by extension. Guessing from the system's
#: shared MIME database is the fallback, but it answers ``audio/x-vorbis+ogg``
#: and the like, where a page checks for the web's own names.
_MIME_TYPES = {
    ".html": "text/html",
    ".htm": "text/html",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".txt": "text/plain",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".webm": "video/webm",
    ".mp4": "video/mp4",
    ".ogv": "video/ogg",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".wasm": "application/wasm",
}

#: Addresses a game may navigate to without leaving itself.
_LOCAL_PREFIXES = (f"{SCHEME}:", "about:", "data:", "blob:")


def _mime_type(path: Path) -> str:
    known = _MIME_TYPES.get(path.suffix.lower())
    if known is not None:
        return known
    content_type, _uncertain = Gio.content_type_guess(path.name, None)
    return Gio.content_type_get_mime_type(content_type) or "application/octet-stream"


class _GameServer:
    """Answers the ``renpydeck-game:`` requests of the game being played.

    The scheme can only be registered once per web context, and has to be
    before any web view exists, so there is a single server for the whole
    application; each game played points it at its own folder.
    """

    _instance = None

    @classmethod
    def get(cls) -> "_GameServer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # The folder whose files may be served, and the one paths resolve
        # against: the game folder, as the game's own folder name opens each
        # path. None while no game is being played.
        self.game: Path | None = None

        context = WebKit.WebContext.get_default()
        context.register_uri_scheme(SCHEME, self._serve)
        security = context.get_security_manager()
        # A secure origin gets the web features that need one, and a CORS
        # enabled one may fetch() its own files.
        security.register_uri_scheme_as_secure(SCHEME)
        security.register_uri_scheme_as_cors_enabled(SCHEME)

        data = Path(GLib.get_user_data_dir()) / "renpydeck" / "web"
        cache = Path(GLib.get_user_cache_dir()) / "renpydeck" / "web"
        self.session = WebKit.NetworkSession.new(str(data), str(cache))

    def uri_for(self, page: Path) -> str:
        """The address *page*, inside the game being played, is served at."""
        relative = page.relative_to(self.game.parent).as_posix()
        return f"{SCHEME}://{_HOST}/{quote(relative)}"

    def _serve(self, request: WebKit.URISchemeRequest) -> None:
        target = self._resolve(request.get_path())
        if target is None:
            self._not_found(request)
            return
        try:
            size = target.stat().st_size
            stream = Gio.File.new_for_path(str(target)).read(None)
        except (OSError, GLib.Error):
            self._not_found(request)
            return
        request.finish(stream, size, _mime_type(target))

    def _resolve(self, path: str) -> Path | None:
        """The file a request's *path* names, if it may be served at all."""
        if self.game is None:
            return None
        # resolve() also follows symbolic links, so one pointing out of the
        # game is caught by the check below as well.
        target = (self.game.parent / unquote(path).lstrip("/")).resolve()
        if not target.is_relative_to(self.game.resolve()) or not target.is_file():
            return None
        return target

    @staticmethod
    def _not_found(request: WebKit.URISchemeRequest) -> None:
        print(f"RenPyDeck: game asked for missing {request.get_uri()}", file=sys.stderr)
        response = WebKit.URISchemeResponse.new(Gio.MemoryInputStream.new(), 0)
        response.set_status(404, None)
        response.set_content_type("text/plain")
        request.finish_with_response(response)


class WebGamePage(Adw.NavigationPage):
    """A page of the window playing the HTML game in *game_dir*.

    The page cannot be popped by the usual means — the back button, a swipe
    from the screen's edge, Escape — since a game uses Escape itself and a
    stray swipe on the Deck's touchscreen would throw away unsaved progress.
    The *Quit game* button packed into *header* is the only way out.
    """

    def __init__(self, game_dir: Path, page: Path, header: Adw.HeaderBar):
        super().__init__(title=game_dir.name, can_pop=False)

        self.server = _GameServer.get()
        self.server.game = game_dir

        quit_button = Gtk.Button(label="Quit game")
        quit_button.connect("clicked", self._on_quit_clicked)
        header.pack_start(quit_button)

        self.view = WebKit.WebView(
            network_session=self.server.session,
            # Games play their music from the first screen, before any click.
            website_policies=WebKit.WebsitePolicies(
                autoplay=WebKit.AutoplayPolicy.ALLOW
            ),
            vexpand=True,
        )
        settings = self.view.get_settings()
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_javascript_can_open_windows_automatically(False)
        self.view.connect("decide-policy", self._on_decide_policy)
        # WebKit's context menu is a popover, which gaming mode may not show.
        self.view.connect("context-menu", lambda *_: True)
        self.view.connect("query-tooltip", self._on_query_tooltip)
        self.view.connect("notify::title", self._on_title_changed)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self.view)
        self.set_child(toolbar_view)

        self.connect("shown", lambda _page: self.view.grab_focus())
        self.connect("hidden", self._on_hidden)

        self.view.load_uri(self.server.uri_for(page))

    def _on_quit_clicked(self, _button):
        self.set_can_pop(True)
        self.activate_action("navigation.pop", None)

    def _on_hidden(self, _page):
        # Unload the game now, which stops its music, rather than whenever the
        # page happens to be finalized.
        self.view.load_uri("about:blank")
        self.server.game = None

    def _on_title_changed(self, view, _pspec):
        title = view.get_title()
        if title and not title.startswith("about:"):
            self.set_title(title)

    @staticmethod
    def _on_query_tooltip(view, *_args):
        """Never show a tooltip for the page.

        WebKit turns an element's ``title`` (SugarCube puts one on its UI bar
        buttons) into a GTK tooltip, a pop-up window of its own. The Deck's
        gaming mode sizes it to nothing, and once one has been shown, closing
        RenPyDeck crashes the session's X server, taking Steam down with it.
        The handler runs before WebKit's own, so stopping the emission here is
        what keeps the tooltip from being shown at all.
        """
        GObject.signal_stop_emission_by_name(view, "query-tooltip")
        return False

    def _on_decide_policy(self, _view, decision, decision_type):
        """Keep the game from leaving itself; see the module documentation."""
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            # Something the view cannot show is a download (a save exported to
            # a file, say), and there is nowhere for it to go yet.
            if not decision.is_mime_type_supported():
                decision.ignore()
                return True
            return False

        uri = decision.get_navigation_action().get_request().get_uri()
        if (
            decision_type == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION
            or not uri.startswith(_LOCAL_PREFIXES)
        ):
            print(f"RenPyDeck: the game was kept from opening {uri}", file=sys.stderr)
            decision.ignore()
            return True
        return False
