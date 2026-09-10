"""Tests for choosing and owning reserved rendering across a cmd2 command loop.

The lifetime boundary is the point of these: the reservation is established after the intro
has been printed and released however the loop ends, so the terminal a user gets back at the
shell is the one they started with.
"""

import io
from typing import Any

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.shortcuts import PromptSession

import cmd2


class TtyStringIO(io.StringIO):
    """A stream that claims to be a terminal, as the backend requires."""

    def isatty(self) -> bool:
        return True


class Harness:
    """A cmd2 application whose main session renders to a terminal the test can read."""

    def __init__(self, mode: str = "reserved", rows: int = 24, toolbar: Any = "STATUS") -> None:
        self.stream = TtyStringIO()
        self.size = Size(rows=rows, columns=80)
        self.backend = Vt100_Output(self.stream, lambda: self.size)
        self._pipe = create_pipe_input()
        self.pipe = self._pipe.__enter__()
        self.app = cmd2.Cmd(allow_cli_args=False, bottom_toolbar_mode=mode)
        self.app.main_session = PromptSession(input=self.pipe, output=self.backend, bottom_toolbar=toolbar)
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


class TestSelection:
    def test_legacy_reserves_nothing(self) -> None:
        harness = Harness(mode="legacy")
        try:
            with harness.app._reserved_toolbar_context():
                assert harness.app.reserved_toolbar is None
            assert harness.written() == ""
        finally:
            harness.close()

    def test_reserved_owns_the_terminal_for_the_body(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                assert toolbar.is_active is True
                assert "\x1b[1;23r" in harness.written()
            assert harness.app.reserved_toolbar is None
        finally:
            harness.close()

    def test_the_reservation_is_released_when_the_loop_ends(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                harness.clear()
            assert "\x1b[r" in harness.written()
        finally:
            harness.close()

    def test_the_reservation_is_released_when_the_loop_raises(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with pytest.raises(ZeroDivisionError), harness.app._reserved_toolbar_context():
                raise ZeroDivisionError
            assert harness.app.reserved_toolbar is None
            assert "\x1b[r" in harness.written()
        finally:
            harness.close()

    def test_auto_falls_back_when_no_toolbar_is_configured(self) -> None:
        harness = Harness(mode="auto", toolbar=None)
        try:
            with harness.app._reserved_toolbar_context():
                assert harness.app.reserved_toolbar is None
        finally:
            harness.close()

    def test_auto_reserves_on_a_qualified_terminal(self) -> None:
        harness = Harness(mode="auto")
        try:
            with harness.app._reserved_toolbar_context():
                assert harness.app.reserved_toolbar is not None
        finally:
            harness.close()

    def test_forcing_reserved_without_a_toolbar_fails_before_the_loop(self) -> None:
        """The caller ruled out legacy rendering; falling back would ignore that."""
        harness = Harness(mode="reserved", toolbar=None)
        try:
            with pytest.raises(ValueError, match="toolbar"), harness.app._reserved_toolbar_context():
                pass
        finally:
            harness.close()

    def test_a_terminal_too_short_to_reserve_still_runs(self) -> None:
        """The floor is not an error: the loop runs, with the toolbar rendered natively."""
        harness = Harness(mode="reserved", rows=2)
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                assert toolbar.is_active is False
        finally:
            harness.close()


class TestPaintedToolbar:
    def test_the_toolbar_is_painted_on_the_reserved_row(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                assert "\x1b[24;1H" in harness.written()
                assert "STATUS" in harness.written()
        finally:
            harness.close()

    def test_the_content_comes_from_the_session_as_it_is_now(self) -> None:
        """Assigning a new provider mid-session has to reach the band."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                harness.app.main_session.bottom_toolbar = "REPLACED"
                harness.clear()
                assert toolbar.refresh() is True
                painter = toolbar.painter
                assert painter is not None
                assert painter.last_frame is not None
                row = "".join(cell.char for cell in painter.last_frame.rows[0])
                assert row.startswith("REPLACED")
        finally:
            harness.close()

    def test_a_callable_provider_is_resolved(self) -> None:
        """cmd2 sets ``bottom_toolbar`` to a method; the band must call it, not print it."""
        harness = Harness(mode="reserved", toolbar=lambda: "FROM CALLABLE")
        try:
            with harness.app._reserved_toolbar_context():
                painter = harness.app.reserved_toolbar.painter  # type: ignore[union-attr]
                assert painter is not None
                assert painter.last_frame is not None
                row = "".join(cell.char for cell in painter.last_frame.rows[0])
                assert row.startswith("FROM CALLABLE")
        finally:
            harness.close()
