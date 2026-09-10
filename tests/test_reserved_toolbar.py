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
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.shortcuts import PromptSession

from cmd2.reserved_output import ReservedOutput
from cmd2.reserved_toolbar import ReservedToolbar


class TtyStringIO(io.StringIO):
    """A stream that claims to be a terminal, as the backend requires."""

    def isatty(self) -> bool:
        return True


class Harness:
    """A prompt session over a terminal whose size the test controls."""

    def __init__(self, rows: int = 24, columns: int = 80) -> None:
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
