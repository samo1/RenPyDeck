"""Drag-to-scroll, for the Steam Deck's touchscreen.

GTK scrolls a list by touch on its own — but only when it *sees* touch events.
In the Deck's gaming mode the touchscreen is delivered as ordinary pointer
input, so a finger drag looks like a mouse press and a mouse move, and the list
stays put.

:func:`enable_drag_scrolling` fixes that by panning the view with any button-1
drag, touch or pointer alike. A press only starts scrolling once it has moved
past the system drag threshold, so tapping a button still activates it; from
that point the gesture is claimed and the button underneath is let off the
hook. Letting go of a flick keeps the list moving and slows it down, which is
what a handheld is expected to do.
"""

import math

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GLib  # noqa: E402

#: How much of its speed a flick keeps per second (0.05 → 95% lost each second).
_FRICTION = 0.05

#: Below this speed (pixels/second) the glide is over.
_MINIMUM_SPEED = 30.0


def enable_drag_scrolling(scroller: Gtk.ScrolledWindow) -> None:
    """Let *scroller* be scrolled by dragging its contents."""
    _DragScroller(scroller)


class _DragScroller:
    """Turns button-1 drags on a scrolled window into vertical scrolling."""

    def __init__(self, scroller: Gtk.ScrolledWindow):
        self.scroller = scroller
        self.claimed = False
        self.start_value = 0.0
        self.speed = 0.0  # pixels/second the value is moving at
        self.last_offset = 0.0
        self.last_time = 0
        self.glide_id = None

        gesture = Gtk.GestureDrag()
        # BUBBLE, so buttons keep working: they see the press first and a tap
        # activates them as usual. The drag still gets the motion that follows,
        # even when the finger came down on a button, and claiming the sequence
        # once it has moved cancels that button's pending click.
        # (CAPTURE would swallow every tap, and denying the sequence to let
        # taps through kills the gesture for good — neither works here.)
        gesture.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        gesture.connect("drag-begin", self.on_drag_begin)
        gesture.connect("drag-update", self.on_drag_update)
        gesture.connect("drag-end", self.on_drag_end)
        scroller.add_controller(gesture)

    # -- The drag itself ---------------------------------------------------

    def on_drag_begin(self, _gesture, _start_x, _start_y):
        self._stop_glide()
        self.claimed = False
        self.start_value = self.scroller.get_vadjustment().get_value()
        self.speed = 0.0
        self.last_offset = 0.0
        self.last_time = GLib.get_monotonic_time()

    def on_drag_update(self, gesture, _offset_x, offset_y):
        if not self.claimed:
            if abs(offset_y) < self._threshold():
                return
            # Far enough to be a scroll rather than a tap: take the sequence
            # away from whatever the finger landed on.
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self.claimed = True

        now = GLib.get_monotonic_time()
        elapsed = (now - self.last_time) / 1_000_000
        if elapsed > 0:
            # The view moves opposite to the finger.
            self.speed = -(offset_y - self.last_offset) / elapsed
        self.last_offset = offset_y
        self.last_time = now

        self._scroll_to(self.start_value - offset_y)

    def on_drag_end(self, _gesture, _offset_x, _offset_y):
        if self.claimed and abs(self.speed) > _MINIMUM_SPEED:
            self._start_glide()

    # -- Gliding to a stop -------------------------------------------------

    def _start_glide(self):
        self.last_time = GLib.get_monotonic_time()
        self.glide_id = self.scroller.add_tick_callback(self._glide)

    def _stop_glide(self):
        if self.glide_id is not None:
            self.scroller.remove_tick_callback(self.glide_id)
            self.glide_id = None

    def _glide(self, _widget, _frame_clock):
        now = GLib.get_monotonic_time()
        elapsed = (now - self.last_time) / 1_000_000
        self.last_time = now

        adjustment = self.scroller.get_vadjustment()
        moved = self._scroll_to(adjustment.get_value() + self.speed * elapsed)
        self.speed *= math.pow(_FRICTION, elapsed)

        if not moved or abs(self.speed) < _MINIMUM_SPEED:
            self.glide_id = None
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # -- Helpers -----------------------------------------------------------

    def _scroll_to(self, value: float) -> bool:
        """Move the view, clamped to its range; False if it could not move."""
        adjustment = self.scroller.get_vadjustment()
        highest = max(
            adjustment.get_lower(),
            adjustment.get_upper() - adjustment.get_page_size(),
        )
        wanted = min(max(value, adjustment.get_lower()), highest)
        if wanted == adjustment.get_value():
            return False
        adjustment.set_value(wanted)
        return True

    def _threshold(self) -> int:
        settings = self.scroller.get_settings()
        return settings.get_property("gtk-dnd-drag-threshold") if settings else 8
