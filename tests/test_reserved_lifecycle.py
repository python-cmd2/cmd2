"""Tests for choosing and owning reserved rendering across a cmd2 command loop.

The lifetime boundary is the point of these: the reservation is established after the intro
has been printed and released however the loop ends, so the terminal a user gets back at the
shell is the one they started with.
"""

import io
from typing import Any

import pytest
from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.shortcuts import PromptSession

import cmd2
from cmd2.reserved_toolbar import native_toolbar_container


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
        # The command's output and the toolbar's paints share one terminal, as they do in
        # life: the stream cmd2 writes to is the stream the backend renders to.
        self.app.stdout = self.stream
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


class TestCommandOutputRouting:
    def test_reserved_mode_serializes_output_instead_of_proxying_it(self) -> None:
        """The proxy's erase-and-redraw is the flicker; the reservation removes the need."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                display = harness.app._command_toolbar
                assert display is not None
                assert display._proxy is None
                assert display._streams
                assert all(stream.serializer is not None for stream in display._streams)
        finally:
            harness.close()

    def test_legacy_mode_still_proxies(self) -> None:
        harness = Harness(mode="legacy")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                display = harness.app._command_toolbar
                assert display is not None
                assert display._proxy is not None
                assert all(stream.serializer is None for stream in display._streams)
        finally:
            harness.close()

    def test_command_output_reaches_the_terminal(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                harness.clear()
                harness.app.poutput("command output")
                assert "command output" in harness.written()
        finally:
            harness.close()

    def test_command_output_tells_the_bridge_inside_the_write(self) -> None:
        """The Stage 3 contract: the invalidation is part of the emitting transaction."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                bridge = toolbar.bridge
                assert bridge is not None
                harness.app.poutput("command output")
                assert bridge.needs_resynchronization is True
                assert bridge.prompt_anchor is None
        finally:
            harness.close()

    def test_the_display_reports_itself_active_while_serialized(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                display = harness.app._command_toolbar
                assert display is not None
                assert display.is_active is True
        finally:
            harness.close()

    def test_the_streams_are_given_back_when_the_display_stops(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                with harness.app._command_toolbar_context():
                    display = harness.app._command_toolbar
                    assert display is not None
                    streams = list(display._streams)
                assert all(stream.serializer is None for stream in streams)
                assert harness.app.stdout is harness.app.stdout
        finally:
            harness.close()


class TestSuspension:
    """Two kinds of pause, and each site says which one it means."""

    def test_finalization_keeps_the_rows(self) -> None:
        """The ordinary end of a command: the toolbar must still be there afterwards."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                harness.clear()
                harness.app._run_cmdfinalization_hooks(False, None)
                assert toolbar.display.is_reserved is True
                assert "\x1b[r" not in harness.written()
        finally:
            harness.close()

    def test_quiescing_keeps_the_rows(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                harness.clear()
                with harness.app._quiesce_bottom_toolbar():
                    assert toolbar.display.is_reserved is True
                assert "\x1b[r" not in harness.written()
        finally:
            harness.close()

    def test_suspending_gives_the_rows_back(self) -> None:
        """A program that inherits the terminal knows nothing about a scroll region."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                harness.clear()
                with harness.app.suspend_bottom_toolbar():
                    assert toolbar.display.is_reserved is False
                    assert "\x1b[r" in harness.written()
                assert toolbar.display.is_reserved is True
        finally:
            harness.close()

    def test_the_band_is_repainted_when_the_terminal_comes_back(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                with harness.app.suspend_bottom_toolbar():
                    harness.clear()
                assert "STATUS" in harness.written()
        finally:
            harness.close()

    def test_coming_back_leaves_recovery_owed(self) -> None:
        """Another program owned the screen; nothing may be diffed against what it left."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                bridge = toolbar.bridge
                assert bridge is not None
                with harness.app.suspend_bottom_toolbar():
                    pass
                assert bridge.needs_resynchronization is True
        finally:
            harness.close()

    def test_only_the_outermost_suspension_takes_the_rows_back(self) -> None:
        """The interval between the inner and outer exits is still the guest's terminal."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                with harness.app.suspend_bottom_toolbar():
                    assert toolbar.display.is_reserved is False
                    with harness.app.suspend_bottom_toolbar():
                        assert toolbar.display.is_reserved is False
                    # The inner context is done, the outer one is not: the guest still owns
                    # the terminal, so nothing may have been reinstalled here.
                    assert toolbar.display.is_reserved is False
                assert toolbar.display.is_reserved is True
        finally:
            harness.close()

    def test_an_inner_suspension_paints_nothing(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app.suspend_bottom_toolbar():
                harness.clear()
                with harness.app.suspend_bottom_toolbar():
                    pass
                written = harness.written()
                assert "\x1b[1;23r" not in written
                assert "STATUS" not in written
        finally:
            harness.close()

    def test_suspension_restores_the_rows_when_the_body_raises(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                with pytest.raises(ZeroDivisionError), harness.app.suspend_bottom_toolbar():
                    raise ZeroDivisionError
                assert toolbar.display.is_reserved is True
        finally:
            harness.close()

    def test_legacy_suspension_is_unchanged(self) -> None:
        harness = Harness(mode="legacy")
        try:
            with harness.app._reserved_toolbar_context(), harness.app.suspend_bottom_toolbar():
                assert harness.app.reserved_toolbar is None
        finally:
            harness.close()


class TestSuspensionWithALiveDisplay:
    """A pause that does not stop the display leaves two programs sharing the terminal."""

    def test_quiescing_stops_the_command_display(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                display = harness.app._command_toolbar
                assert display is not None
                assert display.app.is_running is True
                with harness.app._quiesce_bottom_toolbar():
                    assert display.app.is_running is False
                assert display.app.is_running is True
        finally:
            harness.close()

    def test_suspending_stops_the_command_display(self) -> None:
        """The guest owns the terminal, so cmd2's input reader must not be reading it."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                display = harness.app._command_toolbar
                assert display is not None
                with harness.app.suspend_bottom_toolbar():
                    assert display.app.is_running is False
                assert display.app.is_running is True
        finally:
            harness.close()

    def test_output_is_serialized_again_after_a_suspension(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context(), harness.app._command_toolbar_context():
                display = harness.app._command_toolbar
                assert display is not None
                with harness.app.suspend_bottom_toolbar():
                    assert all(stream.serializer is None for stream in display._streams)
                assert all(stream.serializer is not None for stream in display._streams)
        finally:
            harness.close()


class TestHandoffRecovery:
    def test_the_prompt_origin_is_forgotten_across_a_handoff(self) -> None:
        """The guest moved the cursor; recovery would otherwise repaint over its output."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                bridge = toolbar.bridge
                assert bridge is not None
                bridge.set_prompt_anchor(7)

                with harness.app.suspend_bottom_toolbar():
                    pass

                assert bridge.prompt_anchor is None
                harness.clear()
                with set_app(harness.app.main_session.app):
                    bridge.resynchronize()
                assert "\x1b[7;1H" not in harness.written()
        finally:
            harness.close()

    def test_a_terminal_too_short_on_return_gives_the_toolbar_back(self) -> None:
        """No region means no band to paint in, so the native toolbar has to render again."""
        harness = Harness(mode="reserved", rows=24)
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                container = native_toolbar_container(harness.app.main_session)
                assert container is not None
                assert container.filter() is False

                with harness.app.suspend_bottom_toolbar():
                    harness.size = Size(rows=2, columns=80)

                assert toolbar.display.is_reserved is False
                assert toolbar.is_active is False
                assert container.filter() is True
        finally:
            harness.close()

    def test_a_terminal_that_grows_back_takes_the_rows_again(self) -> None:
        harness = Harness(mode="reserved", rows=24)
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                with harness.app.suspend_bottom_toolbar():
                    harness.size = Size(rows=2, columns=80)
                assert toolbar.is_active is False

                harness.size = Size(rows=24, columns=80)
                with harness.app.suspend_bottom_toolbar():
                    pass
                assert toolbar.is_active is True
        finally:
            harness.close()


class TestRefreshCadence:
    """The band is repainted after each frame the terminal actually received.

    Driving a real render here would need a running event loop -- a prompt session loads its
    history through one -- so the wiring is checked here and the behaviour it hangs on, that a
    committed frame notifies and an uncommitted one does not, is covered against a real
    renderer in the bridge's own tests.
    """

    def test_a_committed_frame_repaints_the_band(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                bridge = toolbar.bridge
                assert bridge is not None
                assert bridge._frame_committed_handler == toolbar.refresh

                harness.app.main_session.bottom_toolbar = "UPDATED"
                harness.clear()
                bridge._frame_committed_handler()

                painter = toolbar.painter
                assert painter is not None
                assert painter.last_frame is not None
                row = "".join(cell.char for cell in painter.last_frame.rows[0])
                assert row.startswith("UPDATED")
                assert "UPDATED" in harness.written()
        finally:
            harness.close()


class TestPromptSuspension:
    """The main prompt is inside the reservation; other prompts are not, yet."""

    def test_the_main_prompt_keeps_the_rows(self) -> None:
        """The toolbar has to survive every ordinary command, prompt included."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                seen: list[bool] = []
                harness.app.main_session.prompt = lambda *a, **k: (
                    seen.append(  # type: ignore[method-assign]
                        toolbar.display.is_reserved
                    )
                    or ""
                )

                harness.clear()
                harness.app._read_raw_input("> ", harness.app.main_session)

                assert seen == [True]
                assert "\x1b[r" not in harness.written()
        finally:
            harness.close()

    def test_the_main_prompt_leaves_the_native_toolbar_hidden(self) -> None:
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                container = native_toolbar_container(harness.app.main_session)
                assert container is not None
                seen: list[bool] = []
                harness.app.main_session.prompt = lambda *a, **k: (
                    seen.append(  # type: ignore[method-assign]
                        container.filter()
                    )
                    or ""
                )

                harness.app._read_raw_input("> ", harness.app.main_session)
                assert seen == [False]
        finally:
            harness.close()

    def test_another_session_still_gets_the_terminal_to_itself(self) -> None:
        """A prompt cmd2 has not bound to the reservation renders outside it, for now."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None
                other = PromptSession(input=harness.pipe, output=harness.backend)
                seen: list[bool] = []
                other.prompt = lambda *a, **k: seen.append(toolbar.display.is_reserved) or ""  # type: ignore[method-assign]

                harness.app._read_raw_input("> ", other)

                assert seen == [False]
                assert toolbar.display.is_reserved is True
        finally:
            harness.close()


class TestSurvivingDisplay:
    def test_the_rows_are_not_released_for_a_terminal_we_do_not_own(self) -> None:
        """A guest cannot be given rows back while another reader still holds the terminal."""
        harness = Harness(mode="reserved")
        try:
            with harness.app._reserved_toolbar_context():
                toolbar = harness.app.reserved_toolbar
                assert toolbar is not None

                # Stand in for a display whose thread never stopped.
                harness.app._display_holding_terminal = StuckDisplay()

                harness.clear()
                with pytest.raises(RuntimeError, match="terminal"), harness.app.suspend_bottom_toolbar():
                    pass

                assert toolbar.display.is_reserved is True
                assert "\x1b[r" not in harness.written()
        finally:
            harness.close()


class StuckDisplay:
    """A command display whose thread will not finish."""

    thread_is_alive = True

    def complete_abandoned_shutdown(self) -> bool:
        """Report that the teardown cannot be finished while the thread runs."""
        return False
