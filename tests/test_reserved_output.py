"""Tests for the virtual output layered over a reserved terminal.

The adapter's whole job is to be honest about two different things at once: the application
must see a terminal one reservation shorter, and the backend must be handed operations that
are correct for the real one.
"""

import io

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import ColorDepth, DummyOutput, Output
from prompt_toolkit.output.vt100 import Vt100_Output

from cmd2.reserved_output import ReservedOutput
from cmd2.terminal_display import Geometry, PhysicalTerminal, TerminalDisplay


def make_output(rows: int = 24, cols: int = 80) -> tuple[Vt100_Output, io.StringIO]:
    stream = io.StringIO()
    return Vt100_Output(stream, lambda: Size(rows=rows, columns=cols)), stream


class Screen:
    """A terminal size that can change between reads."""

    def __init__(self, rows: int, columns: int) -> None:
        self.rows = rows
        self.columns = columns

    def size(self) -> Size:
        return Size(rows=self.rows, columns=self.columns)


def make_shrinkable_output(rows: int = 24, columns: int = 80) -> tuple[Vt100_Output, io.StringIO, Screen]:
    """Build a real Vt100_Output whose size can be changed later."""
    stream = io.StringIO()
    screen = Screen(rows, columns)
    return Vt100_Output(stream, screen.size), stream, screen


def make_reserved(rows: int = 24, cols: int = 80, reserved: int = 1) -> tuple[ReservedOutput, io.StringIO, TerminalDisplay]:
    """Acquire a reservation and return the adapter to render through."""
    output, stream = make_output(rows, cols)
    display = TerminalDisplay(output, reserved_rows=reserved)
    display.acquire()
    stream.truncate(0), stream.seek(0)
    adapter = display.output
    assert isinstance(adapter, ReservedOutput)
    return adapter, stream, display


class TestVirtualGeometry:
    def test_the_application_sees_the_usable_region_as_the_whole_terminal(self) -> None:
        adapter, _, _ = make_reserved(rows=24, reserved=1)
        assert adapter.get_size() == Size(rows=23, columns=80)

    def test_multiple_reserved_rows_are_all_hidden(self) -> None:
        adapter, _, _ = make_reserved(rows=24, reserved=3)
        assert adapter.get_size() == Size(rows=21, columns=80)

    def test_the_physical_layer_still_sees_the_true_height(self) -> None:
        """The one place that must not be fooled. Sizing the region from the virtual view
        subtracts the reservation twice and paints the toolbar over."""
        adapter, _, display = make_reserved(rows=24, reserved=1)
        assert display.terminal.physical_size() == Size(rows=24, columns=80)
        assert adapter.get_size().rows == 23

    def test_the_virtual_size_follows_a_resize(self) -> None:
        output, _stream = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        # Publish a taller generation the way reconfigure() does.
        display._geometry = Geometry(generation=99, physical_rows=40, columns=80, reserved_rows=1)
        assert adapter.get_size() == Size(rows=39, columns=80)


class TestBoundedErases:
    def test_erase_down_uses_delete_line_not_erase_display(self) -> None:
        """ED ignores the scroll margins and would destroy the reserved row."""
        adapter, stream, _ = make_reserved(rows=24)
        adapter.erase_down()
        adapter.flush()
        assert stream.getvalue() == "\x1b[23M"
        assert "\x1b[J" not in stream.getvalue()

    def test_erase_down_clears_the_whole_usable_region(self) -> None:
        """A count of one clears one row; the region needs every usable row."""
        adapter, stream, _ = make_reserved(rows=24, reserved=2)
        adapter.erase_down()
        adapter.flush()
        assert stream.getvalue() == "\x1b[22M"

    def test_erase_screen_homes_inside_the_region_first(self) -> None:
        """Ctrl-L reaches erase_screen. DL clears downward, so covering the usable area
        means starting at its top; an unbounded ED2 would wipe the reserved row."""
        adapter, stream, _ = make_reserved(rows=24)
        adapter.erase_screen()
        adapter.flush()
        assert stream.getvalue() == "\x1b[1;1H\x1b[23M"
        assert "\x1b[2J" not in stream.getvalue()

    def test_the_erase_count_follows_a_resize(self) -> None:
        adapter, stream, display = make_reserved(rows=24)
        display._geometry = Geometry(generation=2, physical_rows=40, columns=80, reserved_rows=1)
        adapter.erase_down()
        adapter.flush()
        assert stream.getvalue() == "\x1b[39M"

    def test_erase_end_of_line_is_left_alone(self) -> None:
        """It is bounded by the line it is on, so the reservation has nothing to add."""
        adapter, stream, _ = make_reserved(rows=24)
        adapter.erase_end_of_line()
        adapter.flush()
        assert stream.getvalue() == "\x1b[K"


class TestBackendIsNeverModified:
    """The named regression ``test_reserved_output_preserves_existing_backend_methods``."""

    def test_the_backend_is_the_same_object_with_the_same_methods_afterwards(self) -> None:
        output, _ = make_output(rows=24)
        before = {name: getattr(output, name) for name in ("erase_down", "erase_screen", "flush", "write_raw")}
        display = TerminalDisplay(output)
        with display, display:
            assert display.lease_depth == 2
        for name, original in before.items():
            assert getattr(output, name) == original, f"{name} was replaced"
        assert not vars(output).get("erase_down"), "an instance-level shadow was left behind"

    def test_a_callers_own_override_survives_nested_leases(self) -> None:
        """The spike replaced bound methods and had to put them back; wrapping cannot lose one."""
        output, _ = make_output(rows=24)
        calls: list[str] = []

        def caller_override() -> None:
            calls.append("caller")

        output.erase_down = caller_override  # type: ignore[method-assign]
        display = TerminalDisplay(output)
        with display, display:
            pass
        assert output.erase_down is caller_override
        output.erase_down()
        assert calls == ["caller"]

    def test_the_backend_survives_an_exception_inside_the_reservation(self) -> None:
        output, _ = make_output(rows=24)
        original = output.erase_down
        with pytest.raises(RuntimeError), TerminalDisplay(output):
            raise RuntimeError("boom")
        assert output.erase_down == original

    def test_the_unbounded_erase_is_back_after_release(self) -> None:
        """The DL substitution is only sound from column zero, so it must not outlive the
        reservation that guarantees the renderer paths reaching it."""
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        display.release()
        stream.truncate(0), stream.seek(0)
        output.erase_down()
        output.flush()
        assert stream.getvalue() == "\x1b[J"


class WindowsLikeOutput:
    """An outer Windows output: native geometry, and an inner VT object that lies.

    ``Windows10_Output`` delegates a whitelist natively and everything else to an inner
    ``Vt100_Output`` constructed with ``lambda: Size(0, 0)``. Asking that inner object for
    geometry returns zeros, and flushing it directly skips the console-mode handling the
    outer flush performs.
    """

    def __init__(self, rows: int, columns: int, rows_below: int) -> None:
        self.vt100_output = Vt100_Output(io.StringIO(), lambda: Size(rows=0, columns=0))
        self._size = Size(rows=rows, columns=columns)
        self._rows_below = rows_below
        self.flushes = 0

    def get_size(self) -> Size:
        return self._size

    def get_rows_below_cursor_position(self) -> int:
        return self._rows_below

    def flush(self) -> None:
        self.flushes += 1


class TestWindowsOuterOutput:
    """The named regression ``test_windows_outer_output_owns_geometry_and_flush``."""

    def test_geometry_comes_from_the_outer_object_not_the_inner_stub(self) -> None:
        output = WindowsLikeOutput(rows=21, columns=92, rows_below=1)
        assert output.vt100_output.get_size() == Size(rows=0, columns=0)
        assert PhysicalTerminal(output).physical_size() == Size(rows=21, columns=92)  # type: ignore[arg-type]

    def test_flush_goes_through_the_outer_object(self) -> None:
        """The outer flush enables VT processing for the write and restores the console mode."""
        output = WindowsLikeOutput(rows=21, columns=92, rows_below=1)
        display = TerminalDisplay(output)  # type: ignore[arg-type]
        adapter = ReservedOutput(output, display)  # type: ignore[arg-type]
        adapter.flush()
        assert output.flushes == 1

    def test_rows_below_the_cursor_stops_at_the_usable_bottom(self) -> None:
        """Windows answers this natively, so adapting get_size() alone would leave the
        renderer believing it may draw over the reserved rows."""
        output = WindowsLikeOutput(rows=21, columns=92, rows_below=5)
        display = TerminalDisplay(output)  # type: ignore[arg-type]
        display._geometry = Geometry(generation=1, physical_rows=21, columns=92, reserved_rows=1)
        adapter = ReservedOutput(output, display)  # type: ignore[arg-type]
        assert adapter.get_rows_below_cursor_position() == 4

    def test_rows_below_the_cursor_is_never_negative(self) -> None:
        """With the cursor already on the reserved row the honest answer is zero, not -1."""
        output = WindowsLikeOutput(rows=21, columns=92, rows_below=0)
        display = TerminalDisplay(output)  # type: ignore[arg-type]
        display._geometry = Geometry(generation=1, physical_rows=21, columns=92, reserved_rows=1)
        adapter = ReservedOutput(output, display)  # type: ignore[arg-type]
        assert adapter.get_rows_below_cursor_position() == 0

    def test_a_posix_backend_still_raises_so_the_renderer_falls_back_to_cpr(self) -> None:
        adapter, _, _ = make_reserved(rows=24)
        with pytest.raises(NotImplementedError):
            adapter.get_rows_below_cursor_position()


class TestCprCoordinateContract:
    """The named regression ``test_cpr_uses_row_one_coordinate_contract``.

    The renderer computes ``rows_below = U - r + 1`` from a *physical* CPR row against the
    *virtual* height. That is correct only because the region is anchored at row 1, which
    makes ``U`` the last usable physical row index as well as the virtual height. A top
    offset would need an explicit translation; keeping the same subtraction would be wrong.
    """

    @pytest.mark.parametrize(("row", "expected"), [(1, 23), (12, 12), (23, 1)])
    def test_a_valid_row_yields_exactly_u_minus_r_plus_one(self, row: int, expected: int) -> None:
        adapter, _, _ = make_reserved(rows=24, reserved=1)
        usable = adapter.get_size().rows
        assert usable - row + 1 == expected

    def test_the_region_is_anchored_at_row_one(self) -> None:
        """The arithmetic above is only sound because of this."""
        output, stream = make_output(rows=24)
        TerminalDisplay(output).acquire()
        assert stream.getvalue() == "\x1bD\x1b[1A\x1b7\x1b[1;23r\x1b8"

    def test_a_cursor_in_the_reserved_band_gives_a_nonpositive_height(self) -> None:
        """The R5 hazard, stated in geometry terms: rejecting it belongs to the bridge, but
        the arithmetic that makes it detectable is settled here."""
        geometry = Geometry(generation=1, physical_rows=24, columns=80, reserved_rows=1)
        assert geometry.usable_rows - 24 + 1 == 0
        two_reserved = Geometry(generation=1, physical_rows=24, columns=80, reserved_rows=2)
        assert two_reserved.usable_rows - 24 + 1 == -1


class TestDelegation:
    def test_every_abstract_method_is_implemented_explicitly(self) -> None:
        """__getattr__ would leave the class abstract, and would silently absorb whatever a
        future prompt-toolkit adds without anyone deciding what reservation means for it."""
        for name in Output.__abstractmethods__:
            assert name in vars(ReservedOutput), f"{name} is not implemented explicitly"

    def test_the_adapter_is_instantiable_as_an_output(self) -> None:
        adapter, _, _ = make_reserved()
        assert isinstance(adapter, Output)

    @pytest.mark.parametrize(
        ("method", "args"),
        [
            ("write", ("hello",)),
            ("write_raw", ("\x1b[1m",)),
            ("set_title", ("t",)),
            ("clear_title", ()),
            ("reset_attributes", ()),
            ("disable_autowrap", ()),
            ("enable_autowrap", ()),
            ("cursor_goto", (2, 3)),
            ("cursor_up", (1,)),
            ("cursor_down", (1,)),
            ("cursor_forward", (1,)),
            ("cursor_backward", (1,)),
            ("hide_cursor", ()),
            ("show_cursor", ()),
            ("reset_cursor_shape", ()),
            ("enable_mouse_support", ()),
            ("disable_mouse_support", ()),
            ("enable_bracketed_paste", ()),
            ("disable_bracketed_paste", ()),
            ("reset_cursor_key_mode", ()),
            ("bell", ()),
            ("ask_for_cpr", ()),
        ],
    )
    def test_unaffected_operations_reach_the_backend(self, method: str, args: tuple[object, ...]) -> None:
        calls: list[tuple[str, tuple[object, ...]]] = []

        class Recorder(DummyOutput):
            def __getattribute__(self, name: str):  # type: ignore[no-untyped-def]
                attr = object.__getattribute__(self, name)
                if name == method:

                    def record(*a: object) -> None:
                        calls.append((name, a))

                    return record
                return attr

        recorder = Recorder()
        adapter = ReservedOutput(recorder, TerminalDisplay(recorder))
        getattr(adapter, method)(*args)
        assert calls == [(method, args)]

    def test_encoding_and_color_depth_come_from_the_backend(self) -> None:
        adapter, _, _ = make_reserved()
        assert adapter.encoding() == adapter.wrapped.encoding()
        assert isinstance(adapter.get_default_color_depth(), ColorDepth)

    def test_responds_to_cpr_follows_the_backend(self) -> None:
        adapter, _, _ = make_reserved()
        assert adapter.responds_to_cpr == adapter.wrapped.responds_to_cpr

    def test_stdout_is_the_backends_own_stream(self) -> None:
        adapter, _, _ = make_reserved()
        assert adapter.stdout is adapter.wrapped.stdout

    def test_set_attributes_is_passed_through_with_its_color_depth(self) -> None:
        from prompt_toolkit.styles import Attrs

        seen: list[tuple[Attrs, ColorDepth]] = []

        class Recorder(DummyOutput):
            def set_attributes(self, attrs: Attrs, color_depth: ColorDepth) -> None:
                seen.append((attrs, color_depth))

        recorder = Recorder()
        adapter = ReservedOutput(recorder, TerminalDisplay(recorder))
        attrs = Attrs(
            color=None,
            bgcolor=None,
            bold=True,
            underline=False,
            strike=False,
            italic=False,
            blink=False,
            reverse=False,
            hidden=False,
            dim=False,
        )
        adapter.set_attributes(attrs, ColorDepth.DEPTH_4_BIT)
        assert seen == [(attrs, ColorDepth.DEPTH_4_BIT)]


class TestScreenBufferTransitions:
    def test_entering_the_alternate_screen_restores_full_margins_first(self) -> None:
        adapter, stream, display = make_reserved(rows=24)
        adapter.enter_alternate_screen()
        adapter.flush()
        assert stream.getvalue().startswith("\x1b7\x1b[24;1H\x1b[0m\x1b[J\x1b[r\x1b8"), "margins were left installed"
        assert not display.is_reserved

    def test_leaving_the_alternate_screen_re_establishes_the_region(self) -> None:
        adapter, stream, display = make_reserved(rows=24)
        adapter.enter_alternate_screen()
        adapter.flush()
        stream.truncate(0), stream.seek(0)
        adapter.quit_alternate_screen()
        assert display.is_reserved
        assert "\x1b[1;23r" in stream.getvalue()

    def test_scrolling_the_buffer_revalidates_the_viewport(self) -> None:
        """A moved viewport makes absolute row numbers address different cells, so it
        invalidates the generation even when width and height are unchanged."""
        adapter, _, display = make_reserved(rows=24)
        assert display.geometry is not None
        before = display.geometry.generation
        adapter.scroll_buffer_to_prompt()
        # A VT backend reports no viewport origin, so nothing moved and nothing is rebuilt.
        assert display.geometry is not None
        assert display.geometry.generation == before


class TestFileDescriptorAndCursorShape:
    def test_fileno_comes_from_the_backend(self) -> None:
        """Code that reaches for the real descriptor must not get the adapter's idea of one."""
        adapter, _, _ = make_reserved()
        with pytest.raises(io.UnsupportedOperation):
            adapter.fileno()

    def test_set_cursor_shape_reaches_the_backend(self) -> None:
        from prompt_toolkit.cursor_shapes import CursorShape

        seen: list[CursorShape] = []

        class Recorder(DummyOutput):
            def set_cursor_shape(self, cursor_shape: CursorShape) -> None:
                seen.append(cursor_shape)

        recorder = Recorder()
        adapter = ReservedOutput(recorder, TerminalDisplay(recorder))
        adapter.set_cursor_shape(CursorShape.BLOCK)
        assert seen == [CursorShape.BLOCK]


class TestSuspendedReservation:
    """The adapter outlives its reservation, so every margin-dependent operation must ask.

    A handoff to the alternate screen restores full margins while deliberately keeping the
    lease, and prompt-toolkit holds the output object it was created with. This object
    therefore keeps receiving calls with no region installed.
    """

    def test_erase_down_defers_to_the_backend_while_suspended(self) -> None:
        """DL against an unbounded screen deletes whole lines, including the text to the left
        of a nonzero cursor column that ED would have preserved."""
        adapter, stream, display = make_reserved(rows=24)
        adapter.enter_alternate_screen()
        adapter.flush()
        stream.truncate(0), stream.seek(0)
        adapter.erase_down()
        adapter.flush()
        assert stream.getvalue() == "\x1b[J"
        assert "M" not in stream.getvalue()
        assert not display.is_reserved

    def test_erase_screen_defers_to_the_backend_while_suspended(self) -> None:
        adapter, stream, _ = make_reserved(rows=24)
        adapter.enter_alternate_screen()
        adapter.flush()
        stream.truncate(0), stream.seek(0)
        adapter.erase_screen()
        adapter.flush()
        assert stream.getvalue() == "\x1b[2J"

    def test_the_physical_size_is_reported_while_suspended(self) -> None:
        """Nothing is reserved, so nothing should be hidden."""
        adapter, _, _ = make_reserved(rows=24)
        adapter.enter_alternate_screen()
        assert adapter.get_size() == Size(rows=24, columns=80)

    def test_rows_below_the_cursor_is_unadapted_while_suspended(self) -> None:
        output = WindowsLikeOutput(rows=21, columns=92, rows_below=5)
        display = TerminalDisplay(output)  # type: ignore[arg-type]
        adapter = ReservedOutput(output, display)  # type: ignore[arg-type]
        assert not adapter.is_reserved
        assert adapter.get_rows_below_cursor_position() == 5

    def test_the_bounded_erase_comes_back_when_the_region_does(self) -> None:
        adapter, stream, _ = make_reserved(rows=24)
        adapter.enter_alternate_screen()
        adapter.quit_alternate_screen()
        adapter.flush()
        stream.truncate(0), stream.seek(0)
        adapter.erase_down()
        adapter.flush()
        assert stream.getvalue() == "\x1b[23M"

    def test_a_stale_adapter_stays_safe_after_the_terminal_shrinks(self) -> None:
        """The guest resized the window below the floor. Anything still holding the adapter
        must not keep emitting bounded erases against a terminal with no region."""
        output, stream, screen = make_shrinkable_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        assert isinstance(adapter, ReservedOutput)

        adapter.enter_alternate_screen()
        screen.rows = 2
        adapter.quit_alternate_screen()
        adapter.flush()

        assert not display.is_reserved
        assert not isinstance(display.output, ReservedOutput), "callers were left on the adapter"
        stream.truncate(0), stream.seek(0)
        adapter.erase_down()
        adapter.flush()
        assert stream.getvalue() == "\x1b[J"
