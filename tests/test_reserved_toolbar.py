"""Tests for owning the reservation across one command loop.

Binding is the part that has to be exactly right. The renderer keeps its own reference to the
output it was built with, so changing only ``Application.output`` leaves the renderer drawing
through the unwrapped backend -- over the reserved row. Restoration has to be just as exact:
a backend left wrapped after the loop ends would report a short terminal to whatever runs next.
"""

import io
from typing import Any

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.filters import Condition
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.shortcuts import PromptSession

from cmd2.reserved_output import ReservedOutput
from cmd2.reserved_toolbar import ReservedToolbar, native_toolbar_container
from cmd2.toolbar_painter import ToolbarPainter


class TtyStringIO(io.StringIO):
    """A stream that claims to be a terminal, as the backend requires."""

    def isatty(self) -> bool:
        return True


class Harness:
    """A prompt session over a terminal whose size the test controls."""

    def __init__(self, rows: int = 24, columns: int = 80, toolbar: Any = "STATUS") -> None:
        self.stream = TtyStringIO()
        self.size = Size(rows=rows, columns=columns)
        self.backend = Vt100_Output(self.stream, lambda: self.size)
        self._pipe = create_pipe_input()
        self.pipe = self._pipe.__enter__()
        self.session: PromptSession[str] = PromptSession(input=self.pipe, output=self.backend, bottom_toolbar="STATUS")
        self.toolbar = ReservedToolbar(self.session, lambda: self.session.bottom_toolbar)
        self.clear()

    def close(self) -> None:
        """Release the pipe input."""
        self._pipe.__exit__(None, None, None)

    def clear(self) -> None:
        """Discard everything written so far."""
        self.stream.truncate(0)
        self.stream.seek(0)

    def written(self) -> str:
        """Everything written since the last clear."""
        return self.stream.getvalue()

    @property
    def app(self) -> Any:
        """The session's application."""
        return self.session.app


class TestBinding:
    def test_starting_binds_the_application_and_its_renderer(self) -> None:
        harness = Harness()
        try:
            assert harness.toolbar.start() is True
            adapter = harness.toolbar.display.output
            assert isinstance(adapter, ReservedOutput)
            assert harness.app.output is adapter
            assert harness.app.renderer.output is adapter
        finally:
            harness.close()

    def test_the_renderer_is_bound_as_well_as_the_application(self) -> None:
        """The renderer holds its own reference; binding only the application misses it."""
        harness = Harness()
        try:
            harness.toolbar.start()
            assert harness.app.renderer.output is harness.app.output
        finally:
            harness.close()

    def test_the_application_sees_the_usable_height(self) -> None:
        harness = Harness(rows=24)
        try:
            harness.toolbar.start()
            assert harness.app.output.get_size() == Size(rows=23, columns=80)
        finally:
            harness.close()

    def test_the_region_is_installed_before_anything_renders(self) -> None:
        harness = Harness(rows=24)
        try:
            harness.toolbar.start()
            assert "\x1b[1;23r" in harness.written()
        finally:
            harness.close()

    def test_stopping_restores_the_original_objects(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            harness.toolbar.stop()
            assert harness.app.output is harness.backend
            assert harness.app.renderer.output is harness.backend
        finally:
            harness.close()

    def test_stopping_releases_the_region(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            harness.clear()
            harness.toolbar.stop()
            assert "\x1b[r" in harness.written()
        finally:
            harness.close()

    def test_stopping_twice_does_nothing_the_second_time(self) -> None:
        """Teardown runs from more than one place; it has to be safe to repeat."""
        harness = Harness()
        try:
            harness.toolbar.start()
            harness.toolbar.stop()
            harness.clear()
            harness.toolbar.stop()
            assert harness.written() == ""
        finally:
            harness.close()

    def test_a_terminal_too_short_to_reserve_binds_nothing(self) -> None:
        """Below the two-row floor there is no reservation, so nothing should be wrapped."""
        harness = Harness(rows=2)
        try:
            assert harness.toolbar.start() is False
            assert harness.app.output is harness.backend
            assert harness.app.renderer.output is harness.backend
            assert harness.toolbar.is_active is False
        finally:
            harness.close()

    def test_the_context_manager_restores_when_the_body_raises(self) -> None:
        harness = Harness()
        try:
            with pytest.raises(ZeroDivisionError), harness.toolbar:
                raise ZeroDivisionError
            assert harness.app.output is harness.backend
            assert harness.toolbar.is_active is False
        finally:
            harness.close()


class TestComponents:
    def test_the_bridge_and_painter_exist_while_active(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            assert harness.toolbar.bridge is not None
            assert harness.toolbar.painter is not None
            assert harness.toolbar.is_active is True
        finally:
            harness.close()

    def test_they_are_gone_once_stopped(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            harness.toolbar.stop()
            assert harness.toolbar.bridge is None
            assert harness.toolbar.painter is None
        finally:
            harness.close()

    def test_the_bridge_is_bound_to_the_application_renderer(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            assert harness.toolbar.bridge is not None
            assert harness.toolbar.bridge._renderer is harness.app.renderer
        finally:
            harness.close()

    def test_the_painter_reads_the_content_provider_dynamically(self) -> None:
        """Assigning a new ``bottom_toolbar`` must reach the band without a restart."""
        harness = Harness()
        try:
            harness.toolbar.start()
            harness.session.bottom_toolbar = "CHANGED"
            painter = harness.toolbar.painter
            assert painter is not None
            prepared = painter.prepare(harness.toolbar.content)
            assert prepared is not None
            assert "CHANGED" in "".join(cell.char for cell in prepared.frame.rows[0])
        finally:
            harness.close()

    def test_one_lock_is_shared_by_the_bridge_and_the_painter(self) -> None:
        """Two locks would serialize each writer against itself and neither against the other."""
        harness = Harness()
        try:
            harness.toolbar.start()
            assert harness.toolbar.painter._lock is harness.toolbar.bridge._lock
        finally:
            harness.close()

    def test_asking_for_the_display_before_starting_says_so(self) -> None:
        harness = Harness()
        try:
            with pytest.raises(RuntimeError, match="not started"):
                _ = harness.toolbar.display
        finally:
            harness.close()

    def test_the_shared_lock_is_reachable(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            assert harness.toolbar.lock is harness.toolbar.painter._lock
        finally:
            harness.close()

    def test_starting_twice_keeps_the_first_reservation(self) -> None:
        """A second start must not stack a lease the single stop would not release."""
        harness = Harness()
        try:
            harness.toolbar.start()
            display = harness.toolbar.display
            assert harness.toolbar.start() is True
            assert harness.toolbar.display is display
            harness.toolbar.stop()
            assert harness.app.output is harness.backend
        finally:
            harness.close()


class TestNativeToolbarSuppression:
    def test_the_native_toolbar_window_is_hidden_while_reserved(self) -> None:
        """Two toolbars would be drawn otherwise: the native one and the painted band."""
        harness = Harness()
        try:
            container = native_toolbar_container(harness.session)
            assert container is not None
            assert container.filter() is True
            harness.toolbar.start()
            assert container.filter() is False
        finally:
            harness.close()

    def test_the_original_filter_is_restored(self) -> None:
        harness = Harness()
        try:
            container = native_toolbar_container(harness.session)
            assert container is not None
            original = container.filter
            harness.toolbar.start()
            harness.toolbar.stop()
            assert container.filter is original
            assert container.filter() is True
        finally:
            harness.close()

    def test_the_window_reappears_even_if_the_filter_is_never_restored(self) -> None:
        """The suppression asks whether the toolbar is active rather than latching a False."""
        harness = Harness()
        try:
            container = native_toolbar_container(harness.session)
            assert container is not None
            harness.toolbar.start()
            suppressed = container.filter
            harness.toolbar.stop()
            assert suppressed() is True
        finally:
            harness.close()

    def test_the_content_provider_is_left_alone(self) -> None:
        """Callers read this attribute to mean 'a toolbar is configured'."""
        harness = Harness()
        try:
            harness.toolbar.start()
            assert harness.session.bottom_toolbar == "STATUS"
        finally:
            harness.close()

    def test_an_unrecognized_layout_is_refused_explicitly(self) -> None:
        harness = Harness()
        try:
            harness.session.app.layout = Layout(Window())
            with pytest.raises(RuntimeError, match="bottom toolbar"):
                harness.toolbar.start()
        finally:
            harness.close()

    def test_an_unrecognized_layout_has_no_container_to_find(self) -> None:
        harness = Harness()
        try:
            harness.session.app.layout = Layout(Window())
            assert native_toolbar_container(harness.session) is None
        finally:
            harness.close()

    def test_a_layout_whose_last_child_is_not_the_toolbar_has_no_container(self) -> None:
        """The shape check is about the toolbar window, not merely about the root's type."""
        harness = Harness()
        try:
            harness.session.app.layout = Layout(HSplit([Window(), Window()]))
            assert native_toolbar_container(harness.session) is None
        finally:
            harness.close()


class TestFirstPaint:
    def test_the_band_is_painted_when_the_reservation_starts(self) -> None:
        """The toolbar has to be there from the first prompt, not from the first refresh."""
        harness = Harness()
        try:
            harness.toolbar.start()
            assert "\x1b[24;1H" in harness.written()
            assert "STATUS" in harness.written()
        finally:
            harness.close()

    def test_refreshing_repaints_changed_content(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            harness.session.bottom_toolbar = "CHANGED"
            harness.clear()
            assert harness.toolbar.refresh() is True
            # Only the cells that differ from "STATUS" are rewritten -- the shared "A" is
            # left alone -- so the band is checked through the frame the painter published
            # rather than by looking for the whole string in the stream.
            painter = harness.toolbar.painter
            assert painter is not None
            assert painter.last_frame is not None
            assert "".join(cell.char for cell in painter.last_frame.rows[0]).startswith("CHANGED")
            assert "\x1b[24;" in harness.written()
        finally:
            harness.close()

    def test_refreshing_unchanged_content_writes_nothing(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            harness.clear()
            assert harness.toolbar.refresh() is False
            assert harness.written() == ""
        finally:
            harness.close()

    def test_a_failing_content_callback_paints_nothing(self) -> None:
        """The painter keeps the last good frame; the refresh simply reports it wrote nothing."""

        def boom() -> str:
            raise RuntimeError("callback failed")

        harness = Harness()
        try:
            harness.toolbar.start()
            harness.toolbar.content = boom
            harness.clear()
            assert harness.toolbar.refresh() is False
            assert harness.written() == ""
        finally:
            harness.close()

    def test_refreshing_while_stopped_does_nothing(self) -> None:
        harness = Harness()
        try:
            assert harness.toolbar.refresh() is False
        finally:
            harness.close()


class TestStartupFailure:
    def test_a_failed_first_paint_leaves_no_reservation_behind(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Review finding: __enter__ raising means __exit__ never runs, so start must roll back."""

        def boom(self: Any, prepared: Any) -> bool:
            raise OSError("terminal went away")

        harness = Harness()
        try:
            monkeypatch.setattr(ToolbarPainter, "paint", boom)
            harness.clear()
            with pytest.raises(OSError, match="terminal went away"):
                harness.toolbar.start()

            assert harness.toolbar.is_active is False
            assert harness.app.output is harness.backend
            assert harness.app.renderer.output is harness.backend
            assert "\x1b[r" in harness.written()
        finally:
            harness.close()

    def test_a_failed_start_restores_the_native_toolbar(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(self: Any, prepared: Any) -> bool:
            raise OSError("terminal went away")

        harness = Harness()
        try:
            container = native_toolbar_container(harness.session)
            assert container is not None
            original = container.filter
            monkeypatch.setattr(ToolbarPainter, "paint", boom)
            with pytest.raises(OSError, match="terminal went away"):
                harness.toolbar.start()
            assert container.filter is original
        finally:
            harness.close()

    def test_a_failed_start_can_be_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Rollback has to leave the object usable, not merely leave the terminal clean."""
        failures = {"count": 1}
        real_paint = ToolbarPainter.paint

        def sometimes(self: Any, prepared: Any) -> bool:
            if failures["count"]:
                failures["count"] -= 1
                raise OSError("terminal went away")
            return bool(real_paint(self, prepared))

        harness = Harness()
        try:
            monkeypatch.setattr(ToolbarPainter, "paint", sometimes)
            with pytest.raises(OSError, match="terminal went away"):
                harness.toolbar.start()
            assert harness.toolbar.is_active is False
            assert harness.toolbar.start() is True
            assert harness.toolbar.is_active is True
        finally:
            harness.close()


class TestRestorationOwnership:
    def test_the_renderer_gets_its_own_original_output_back(self) -> None:
        """Review finding: the renderer's output need not be the application's."""
        harness = Harness()
        try:
            other = Vt100_Output(TtyStringIO(), lambda: Size(rows=24, columns=80))
            harness.app.renderer.output = other

            harness.toolbar.start()
            harness.toolbar.stop()

            assert harness.app.output is harness.backend
            assert harness.app.renderer.output is other
        finally:
            harness.close()

    def test_a_filter_installed_while_reserved_survives_teardown(self) -> None:
        """Review finding: restoring unconditionally discards whatever replaced ours."""
        harness = Harness()
        try:
            container = native_toolbar_container(harness.session)
            assert container is not None
            harness.toolbar.start()

            replacement = Condition(lambda: True)
            container.filter = replacement
            harness.toolbar.stop()

            assert container.filter is replacement
        finally:
            harness.close()

    def test_the_filter_is_restored_when_it_is_still_ours(self) -> None:
        harness = Harness()
        try:
            container = native_toolbar_container(harness.session)
            assert container is not None
            original = container.filter
            harness.toolbar.start()
            harness.toolbar.stop()
            assert container.filter is original
        finally:
            harness.close()


class PartialWriteStream(TtyStringIO):
    """Writes a prefix of chosen flushed batches and then fails, as a real terminal can."""

    def __init__(self, *fail_on_writes: int, keep: int = 12) -> None:
        super().__init__()
        self._writes = 0
        self._fail_on_writes = set(fail_on_writes)
        self._armed = False
        self._keep = keep

    def fail_next(self) -> None:
        """Fail the next flushed batch, whenever it comes.

        Counting batches is brittle -- cleanup after a failure emits one of its own -- so
        tests that care about *which* paint fails arm it directly instead.
        """
        self._armed = True

    def write(self, text: str) -> int:
        self._writes += 1
        if self._armed or self._writes in self._fail_on_writes:
            self._armed = False
            super().write(text[: self._keep])
            raise OSError("terminal went away")
        return super().write(text)


class TestPartialStartupPaint:
    def test_a_half_written_first_paint_leaves_no_state_behind(self) -> None:
        """Review finding: rollback released the margins over a cursor still in the band."""
        harness = Harness()
        try:
            # Batch one installs the margins; batch two is the first paint.
            harness.stream = PartialWriteStream(2)
            harness.backend.stdout = harness.stream
            with pytest.raises(OSError, match="terminal went away"):
                harness.toolbar.start()

            written = harness.stream.getvalue()
            # Wrap mode and cursor are put back before the margins are released, so the
            # release does not save a cursor that is still inside the band.
            assert written.index("\x1b[?7h") < written.index("\x1b[r")
            assert harness.toolbar.is_active is False
            assert harness.app.output is harness.backend
        finally:
            harness.close()


class TestRefreshFailure:
    def make(self, *fail_on_writes: int) -> Harness:
        """Build a toolbar over a terminal that fails the chosen flushed batches.

        Batch one installs the margins and batch two is the first paint, so refreshes start
        at batch three.
        """
        harness = Harness()
        harness.stream = PartialWriteStream(*fail_on_writes)
        harness.backend.stdout = harness.stream
        return harness

    def test_a_failed_paint_does_not_take_the_command_down(self) -> None:
        """The toolbar is cosmetic; the command that was running is not its to interrupt."""
        harness = self.make(3)
        try:
            harness.toolbar.start()
            harness.session.bottom_toolbar = "CHANGED"
            assert harness.toolbar.refresh() is False
        finally:
            harness.close()

    def test_a_failed_paint_makes_the_bridge_resynchronize(self) -> None:
        """Buffering the cursor save does not prove the terminal received it."""
        harness = self.make(3)
        try:
            harness.toolbar.start()
            bridge = harness.toolbar.bridge
            assert bridge is not None
            harness.session.bottom_toolbar = "CHANGED"
            harness.toolbar.refresh()
            assert bridge.needs_resynchronization is True
            assert "cursor" in (bridge.resynchronization_reason or "")
        finally:
            harness.close()

    def test_the_failure_is_reported_once(self) -> None:
        harness = self.make(3)
        try:
            harness.toolbar.start()
            harness.session.bottom_toolbar = "CHANGED"
            harness.toolbar.refresh()
            assert isinstance(harness.toolbar.take_pending_error(), OSError)
            assert harness.toolbar.take_pending_error() is None
        finally:
            harness.close()

    def test_a_terminal_that_keeps_failing_gives_the_rows_back(self) -> None:
        """A terminal that fails twice is not coming back; legacy rendering is the fallback."""
        harness = Harness()
        try:
            harness.toolbar.start()
            container = native_toolbar_container(harness.session)
            assert container is not None

            harness.stream = AlwaysFailingStream()
            harness.backend.stdout = harness.stream
            harness.session.bottom_toolbar = "ONE"
            harness.toolbar.refresh()
            assert harness.toolbar.is_active is True

            harness.session.bottom_toolbar = "TWO"
            harness.toolbar.refresh()
            assert harness.toolbar.is_active is False
            # The native toolbar renders again, which is what "fall back" means here.
            assert container.filter() is True
        finally:
            harness.close()

    def test_a_successful_paint_forgets_earlier_failures(self) -> None:
        """Only *consecutive* failures mean the terminal is gone: fail, recover, fail again."""
        harness = self.make()
        try:
            harness.toolbar.start()
            harness.session.bottom_toolbar = "ONE"
            harness.stream.fail_next()
            assert harness.toolbar.refresh() is False
            harness.toolbar.take_pending_error()

            harness.session.bottom_toolbar = "TWO"
            assert harness.toolbar.refresh() is True

            harness.session.bottom_toolbar = "THREE"
            harness.stream.fail_next()
            assert harness.toolbar.refresh() is False
            # The success in between reset the count, so this is failure one again.
            assert harness.toolbar.is_active is True
        finally:
            harness.close()

    def test_nothing_is_pending_when_nothing_failed(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            assert harness.toolbar.take_pending_error() is None
        finally:
            harness.close()

    def test_an_unreported_content_error_survives_teardown(self) -> None:
        """The painter is dropped on stop; an error it still held would go with it."""

        def boom() -> str:
            raise RuntimeError("callback failed")

        harness = Harness()
        try:
            harness.toolbar.start()
            harness.toolbar.content = boom
            harness.toolbar.refresh()
            harness.toolbar.stop()
            assert isinstance(harness.toolbar.take_pending_error(), RuntimeError)
        finally:
            harness.close()

    def test_a_failing_content_callback_is_reported_too(self) -> None:
        """The painter keeps the last frame; the error still has to reach the user once."""

        def boom() -> str:
            raise RuntimeError("callback failed")

        harness = Harness()
        try:
            harness.toolbar.start()
            harness.toolbar.content = boom
            assert harness.toolbar.refresh() is False
            assert isinstance(harness.toolbar.take_pending_error(), RuntimeError)
        finally:
            harness.close()


class AlwaysFailingStream(TtyStringIO):
    """A terminal that has gone away."""

    def write(self, text: str) -> int:
        raise OSError("terminal went away")


class TestRenderBinding:
    def test_starting_routes_the_application_renders_through_the_bridge(self) -> None:
        harness = Harness()
        try:
            original = harness.app.renderer.render
            harness.toolbar.start()
            assert harness.app.renderer.render is not original
        finally:
            harness.close()

    def test_stopping_gives_the_renderer_its_methods_back(self) -> None:
        harness = Harness()
        try:
            original = harness.app.renderer.render
            harness.toolbar.start()
            harness.toolbar.stop()
            assert harness.app.renderer.render == original
        finally:
            harness.close()

    def test_a_failed_start_unbinds_as_well(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(self: Any, prepared: Any) -> bool:
            raise OSError("terminal went away")

        harness = Harness()
        try:
            original = harness.app.renderer.render
            monkeypatch.setattr(ToolbarPainter, "paint", boom)
            with pytest.raises(OSError, match="terminal went away"):
                harness.toolbar.start()
            assert harness.app.renderer.render == original
        finally:
            harness.close()

    def test_the_redraw_scheduler_asks_the_application(self) -> None:
        """A frame that could not be committed has to come back, and the app owns that."""
        harness = Harness()
        try:
            harness.toolbar.start()
            bridge = harness.toolbar.bridge
            assert bridge is not None
            assert bridge._redraw_scheduler == harness.app.invalidate
        finally:
            harness.close()


class TestAbandonedEmission:
    def test_the_owner_releases_when_the_bridge_gives_up(self) -> None:
        """Rendering cannot resume until the rows are back and the bridge is unbound."""
        harness = Harness()
        try:
            original_render = harness.app.renderer.render
            harness.toolbar.start()
            bridge = harness.toolbar.bridge
            assert bridge is not None
            harness.clear()

            bridge.stop_reserved_emission(OSError("terminal went away"))

            assert harness.toolbar.is_active is False
            assert "\x1b[r" in harness.written()
            assert harness.app.renderer.render == original_render
            assert harness.app.output is harness.backend
        finally:
            harness.close()

    def test_the_failure_is_still_reported(self) -> None:
        harness = Harness()
        try:
            harness.toolbar.start()
            bridge = harness.toolbar.bridge
            assert bridge is not None
            bridge.stop_reserved_emission(OSError("terminal went away"))
            assert isinstance(harness.toolbar.take_pending_error(), OSError)
        finally:
            harness.close()
