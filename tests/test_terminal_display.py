"""Tests for geometry snapshots, backend capability and reservation ownership.

Several of these are the named regressions from design section 13.1. Where one is, its
docstring says which mutation it has to catch -- a test that passes both with and without the
defect it is named for is worse than no test, because it reports coverage that is not there.
"""

import io

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.output.vt100 import Vt100_Output

from cmd2.reserved_output import ReservedOutput
from cmd2.terminal_display import Geometry, PhysicalTerminal, TerminalDisplay


def make_output(rows: int = 24, cols: int = 80) -> tuple[Vt100_Output, io.StringIO]:
    """Build a real Vt100_Output over a string buffer, with a settable size."""
    stream = io.StringIO()
    size = Size(rows=rows, columns=cols)
    output = Vt100_Output(stream, lambda: size)
    return output, stream


class Screen:
    """A resizable terminal size, settable between activations.

    Deliberately not a Vt100_Output subclass. Backend capability is decided by exact class
    identity, so a subclass would be treated as an unqualified backend and never reserve --
    which is the intended posture, and would make these tests pass for the wrong reason.
    """

    def __init__(self, rows: int, columns: int) -> None:
        self.rows = rows
        self.columns = columns

    def size(self) -> Size:
        return Size(rows=self.rows, columns=self.columns)


class HomegrownOutput:
    """An output cmd2 has never qualified. Capability must not guess in its favour."""


def make_resizable_output(rows: int = 24, columns: int = 80) -> tuple[Vt100_Output, io.StringIO, Screen]:
    """Build a real Vt100_Output whose size can be changed later."""
    stream = io.StringIO()
    screen = Screen(rows, columns)
    return Vt100_Output(stream, screen.size), stream, screen


class TestGeometry:
    def test_usable_rows_subtracts_the_reservation_exactly_once(self) -> None:
        """The double-subtraction mutation: at 24 rows with 1 reserved, 22 is the wrong answer."""
        geometry = Geometry(generation=1, physical_rows=24, columns=80, reserved_rows=1)
        assert geometry.usable_rows == 23

    def test_virtual_size_is_one_reservation_shorter_than_physical(self) -> None:
        geometry = Geometry(generation=1, physical_rows=24, columns=80, reserved_rows=1)
        assert geometry.physical_size == Size(rows=24, columns=80)
        assert geometry.virtual_size == Size(rows=23, columns=80)

    def test_width_is_carried_through_unchanged(self) -> None:
        """Reserving rows must not narrow the terminal."""
        geometry = Geometry(generation=1, physical_rows=24, columns=132, reserved_rows=2)
        assert geometry.virtual_size.columns == 132

    def test_multiple_reserved_rows_are_all_withheld(self) -> None:
        assert Geometry(generation=1, physical_rows=24, columns=80, reserved_rows=3).usable_rows == 21

    def test_a_snapshot_cannot_be_mutated(self) -> None:
        """Geometry is a generation, not a variable: changes make a new snapshot."""
        geometry = Geometry(generation=1, physical_rows=24, columns=80, reserved_rows=1)
        with pytest.raises(AttributeError):
            geometry.physical_rows = 30  # type: ignore[misc]

    @pytest.mark.parametrize(("rows", "reserved"), [(3, 1), (4, 2), (24, 1), (24, 22)])
    def test_eligible_when_at_least_two_usable_rows_remain(self, rows: int, reserved: int) -> None:
        assert Geometry(generation=1, physical_rows=rows, columns=80, reserved_rows=reserved).is_eligible

    @pytest.mark.parametrize(("rows", "reserved"), [(2, 1), (1, 1), (3, 2), (24, 23), (24, 24), (24, 0)])
    def test_ineligible_below_the_two_usable_row_floor(self, rows: int, reserved: int) -> None:
        """One usable row is not a narrower region; the terminal ignores it outright."""
        assert not Geometry(generation=1, physical_rows=rows, columns=80, reserved_rows=reserved).is_eligible


class TestBackendCapability:
    """Capability comes from backend identity, never from shell name, TERM, or isinstance."""

    def test_vt100_backend_is_qualified(self) -> None:
        output, _ = make_output()
        assert PhysicalTerminal(output).supports_reservation

    def test_dummy_output_is_not_a_terminal(self) -> None:
        terminal = PhysicalTerminal(DummyOutput())
        supported, reason = terminal.capability()
        assert not supported
        assert "not a terminal" in reason

    def test_an_unknown_backend_gets_compatibility_rendering(self) -> None:
        """A wrong guess corrupts the screen, so an unrecognized backend is never assumed good."""

        supported, reason = PhysicalTerminal(HomegrownOutput()).capability()
        assert not supported
        assert "not a qualified backend" in reason

    def test_isinstance_of_output_is_not_enough_on_its_own(self) -> None:
        """Windows10_Output satisfies isinstance without inheriting the interface, and legacy
        Win32Output satisfies it while having no VT scroll margins at all. A capability check
        that accepted every Output would inject DECSTBM into a console that cannot honour it.
        """
        from prompt_toolkit.output import Output

        homegrown = DummyOutput()
        assert isinstance(homegrown, Output)
        assert not PhysicalTerminal(homegrown).supports_reservation

    def test_the_physical_layer_refuses_to_wrap_the_adapter(self) -> None:
        """Sizing from the adapter would subtract the reservation a second time."""
        output, _ = make_output()
        display = TerminalDisplay(output)
        display.acquire()
        with pytest.raises(TypeError, match="not the reserved adapter"):
            PhysicalTerminal(display.output)


class TestPhysicalGeometry:
    def test_size_comes_from_the_unwrapped_backend(self) -> None:
        output, _ = make_output(rows=40, cols=100)
        assert PhysicalTerminal(output).physical_size() == Size(rows=40, columns=100)

    def test_measure_stamps_the_generation_and_reservation(self) -> None:
        output, _ = make_output(rows=24)
        geometry = PhysicalTerminal(output).measure(generation=7, reserved_rows=2)
        assert (geometry.generation, geometry.physical_rows, geometry.reserved_rows) == (7, 24, 2)
        assert geometry.usable_rows == 22

    def test_buffer_id_is_none_where_the_backend_has_no_viewport_notion(self) -> None:
        output, _ = make_output()
        assert PhysicalTerminal(output).buffer_id() is None


class TestAcquisition:
    def test_acquiring_installs_the_region_and_flushes_it(self) -> None:
        """A region merely buffered is a reservation only promised."""
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        assert display.acquire()
        assert stream.getvalue() == "\x1bD\x1b[1A\x1b7\x1b[1;23r\x1b8"
        assert not output._buffer

    def test_releasing_restores_full_screen_margins_immediately(self) -> None:
        """Margins left installed would trap every later line of shell output inside them."""
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        stream.truncate(0), stream.seek(0)
        display.release()
        assert stream.getvalue() == "\x1b7\x1b[24;1H\x1b[0m\x1b[J\x1b[r\x1b8"
        assert not output._buffer

    def test_the_region_is_reset_when_the_body_raises(self) -> None:
        output, stream = make_output(rows=24)

        def blow_up() -> None:
            stream.truncate(0), stream.seek(0)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"), TerminalDisplay(output):
            blow_up()
        assert stream.getvalue() == "\x1b7\x1b[24;1H\x1b[0m\x1b[J\x1b[r\x1b8"

    def test_release_is_idempotent(self) -> None:
        """Cleanup paths call this freely; a second reset would move the cursor again."""
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        display.release()
        stream.truncate(0), stream.seek(0)
        display.release()
        display.release()
        assert stream.getvalue() == ""

    def test_nested_leases_share_one_region(self) -> None:
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        with display:
            stream.truncate(0), stream.seek(0)
            with display:
                assert display.lease_depth == 2
            assert stream.getvalue() == "", "the inner release tore down a shared reservation"
            assert display.is_reserved
        assert not display.is_reserved

    def test_an_unqualified_backend_is_left_alone(self) -> None:
        """Compatibility rendering means no sequences at all, not a narrower region."""
        display = TerminalDisplay(DummyOutput())
        assert not display.acquire()
        assert not display.is_reserved
        assert display.output is display.terminal.output

    def test_a_fresh_size_is_read_at_every_activation(self) -> None:
        """Geometry frozen at construction is wrong the moment the window is resized."""
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        assert display.geometry is not None
        assert display.geometry.usable_rows == 23
        display.release()

        screen.rows = 40
        stream.truncate(0), stream.seek(0)
        display.acquire()
        assert stream.getvalue() == "\x1bD\x1b[1A\x1b7\x1b[1;39r\x1b8"
        assert display.geometry is not None
        assert display.geometry.usable_rows == 39

    def test_each_activation_is_a_new_generation(self) -> None:
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        assert display.geometry is not None
        first = display.geometry.generation
        display.release()
        display.acquire()
        assert display.geometry is not None
        assert display.geometry.generation > first

    def test_reserved_rows_must_be_at_least_one(self) -> None:
        output, _ = make_output()
        with pytest.raises(ValueError, match="at least 1"):
            TerminalDisplay(output, reserved_rows=0)


class TestTwoRowFloor:
    """The named regression ``test_one_usable_row_releases_reservation``."""

    def test_one_usable_row_never_installs_a_degenerate_region(self) -> None:
        """A terminal ignores ``1;1r`` and then scrolls straight through the reserved row.

        The failure is total, not degraded, so the only correct response is to release. This
        must catch a mutation that clamps the region to one row instead of refusing it.
        """
        output, stream = make_output(rows=2)
        display = TerminalDisplay(output)
        assert not display.acquire()
        assert not display.is_reserved
        assert "\x1b[1;1r" not in stream.getvalue()
        assert stream.getvalue() == ""

    def test_full_geometry_and_the_plain_backend_are_used_while_released(self) -> None:
        output, _ = make_output(rows=2)
        display = TerminalDisplay(output)
        display.acquire()
        assert display.geometry is None
        assert display.output.get_size() == Size(rows=2, columns=80)
        assert not isinstance(display.output, ReservedOutput)

    def test_shrinking_below_the_floor_releases_an_installed_region(self) -> None:
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        assert display.is_reserved

        screen.rows = 2
        stream.truncate(0), stream.seek(0)
        assert not display.reconfigure()
        assert not display.is_reserved
        assert stream.getvalue() == "\x1b7\x1b[r\x1b8", "margins must be restored, not narrowed"

    def test_growing_back_above_the_floor_reacquires(self) -> None:
        output, _stream, screen = make_resizable_output(rows=2, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        assert not display.is_reserved

        screen.rows = 24
        assert display.reconfigure()
        assert display.is_reserved
        assert display.geometry is not None
        assert display.geometry.usable_rows == 23

    def test_reconfigure_does_nothing_without_a_lease(self) -> None:
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        assert not display.reconfigure()
        assert stream.getvalue() == ""


class TestResize:
    def test_reconfigure_installs_the_region_for_the_new_height(self) -> None:
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()

        screen.rows = 40
        stream.truncate(0), stream.seek(0)
        assert display.reconfigure()
        assert stream.getvalue() == "\x1b7\x1b[1;39r\x1b8"

    def test_a_width_change_alone_is_still_a_new_generation(self) -> None:
        """Toolbar height is measured against the width, so a rewrap can change the reservation."""
        output, _stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        assert display.geometry is not None
        before = display.geometry.generation

        screen.columns = 40
        display.reconfigure()
        assert display.geometry is not None
        assert display.geometry.columns == 40
        assert display.geometry.generation > before


class TestScreenBufferHandoff:
    def test_entering_the_alternate_screen_restores_full_margins(self) -> None:
        """The program taking over knows nothing about a reservation."""
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        stream.truncate(0), stream.seek(0)
        display.release_region_for_handoff()
        assert stream.getvalue() == "\x1b7\x1b[24;1H\x1b[0m\x1b[J\x1b[r\x1b8"
        assert not display.is_reserved

    def test_the_lease_survives_a_handoff(self) -> None:
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        display.release_region_for_handoff()
        assert display.lease_depth == 1

    def test_returning_measures_afresh_rather_than_restoring_the_old_snapshot(self) -> None:
        """A program that resized the window in between would otherwise pin the toolbar
        to a row that is no longer the bottom one."""
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        display.release_region_for_handoff()

        screen.rows = 40
        stream.truncate(0), stream.seek(0)
        display.reacquire_region_after_handoff()
        assert stream.getvalue() == "\x1bD\x1b[1A\x1b7\x1b[1;39r\x1b8"
        assert display.geometry is not None
        assert display.geometry.usable_rows == 39

    def test_returning_to_a_terminal_below_the_floor_stays_released(self) -> None:
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        display.release_region_for_handoff()

        screen.rows = 2
        stream.truncate(0), stream.seek(0)
        display.reacquire_region_after_handoff()
        assert not display.is_reserved
        assert stream.getvalue() == ""

    def test_a_handoff_return_without_a_handoff_does_nothing(self) -> None:
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        stream.truncate(0), stream.seek(0)
        display.reacquire_region_after_handoff()
        assert stream.getvalue() == ""


class TestFailedAcquisition:
    def test_a_failed_install_leaves_full_screen_margins_behind(self) -> None:
        """A half-installed region is worse than none: the shell would inherit it."""
        output, _stream = make_output(rows=24)

        def explode(_sequence: str) -> None:
            raise OSError("write failed")

        display = TerminalDisplay(output)
        display.terminal.write_margin_change = explode  # type: ignore[method-assign]
        with pytest.raises(OSError, match="write failed"):
            display.acquire()

        display.terminal.write_margin_change = PhysicalTerminal(output).write_margin_change  # type: ignore[method-assign]
        assert not display.is_reserved

    def test_a_failed_install_does_not_leave_a_lease_held(self) -> None:
        """A lease left behind would make the next release a no-op and strand the margins."""
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)
        calls: list[str] = []

        def explode(_sequence: str) -> None:
            calls.append("attempted")
            if len(calls) == 1:
                raise OSError("write failed")

        display.terminal.write_margin_change = explode  # type: ignore[method-assign]
        with pytest.raises(OSError, match="write failed"):
            display.acquire()
        assert display.lease_depth == 0
        assert calls == ["attempted", "attempted"], "the region reset was not attempted"


class WindowsLikeScreen:
    """A Windows output whose viewport origin can be moved between reads."""

    class _Window:
        def __init__(self, top: int) -> None:
            self.Left = 0
            self.Top = top

    class _Size:
        X = 92
        Y = 21

    class _Info:
        def __init__(self, top: int) -> None:
            self.srWindow = WindowsLikeScreen._Window(top)
            self.dwSize = WindowsLikeScreen._Size()

    def __init__(self) -> None:
        self.top = 0
        self.rows = 21
        self.written: list[str] = []

    def get_win32_screen_buffer_info(self) -> "WindowsLikeScreen._Info":
        return WindowsLikeScreen._Info(self.top)

    def get_size(self) -> Size:
        return Size(rows=self.rows, columns=92)

    def write_raw(self, data: str) -> None:
        self.written.append(data)

    def flush(self) -> None:
        pass


@pytest.fixture
def qualified_windows_double(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat the Windows test double as a qualified backend.

    Capability is decided by exact class identity, which is what keeps an unrecognized
    backend from having DECSTBM injected into it. These tests are about viewport-origin
    invalidation rather than capability, so the double is qualified explicitly rather than
    by loosening the rule under test elsewhere.
    """
    import cmd2.terminal_display as td

    name = f"{WindowsLikeScreen.__module__}.{WindowsLikeScreen.__qualname__}"
    monkeypatch.setattr(td, "_QUALIFIED_BACKENDS", td._QUALIFIED_BACKENDS | {name})


@pytest.mark.usefixtures("qualified_windows_double")
class TestViewportOrigin:
    def test_buffer_id_records_the_viewport_origin_and_buffer_size(self) -> None:
        screen = WindowsLikeScreen()
        assert PhysicalTerminal(screen).buffer_id() == (0, 0, 92, 21)  # type: ignore[arg-type]

    def test_a_moved_viewport_invalidates_the_generation(self) -> None:
        """Absolute row numbers address different cells after the viewport moves, even
        though width and height are unchanged."""
        screen = WindowsLikeScreen()
        display = TerminalDisplay(screen)  # type: ignore[arg-type]
        display._depth = 1
        display._geometry = display._measure()
        before = display.geometry.generation  # type: ignore[union-attr]

        screen.top = 5
        assert display.revalidate_viewport()
        assert display.geometry is not None
        assert display.geometry.generation > before
        assert display.geometry.buffer_id == (0, 5, 92, 21)

    def test_an_unmoved_viewport_rebuilds_nothing(self) -> None:
        screen = WindowsLikeScreen()
        display = TerminalDisplay(screen)  # type: ignore[arg-type]
        display._depth = 1
        display._geometry = display._measure()
        before = display.geometry.generation  # type: ignore[union-attr]

        assert display.revalidate_viewport()
        assert display.geometry is not None
        assert display.geometry.generation == before

    def test_revalidating_while_released_reports_no_reservation(self) -> None:
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)
        assert not display.revalidate_viewport()


class TestReleasedStateIsInert:
    def test_a_handoff_release_without_a_reservation_does_nothing(self) -> None:
        output, stream = make_output(rows=2)
        display = TerminalDisplay(output)
        display.acquire()
        display.release_region_for_handoff()
        assert stream.getvalue() == ""

    def test_releasing_an_unreserved_lease_emits_nothing(self) -> None:
        """Below the floor there is no region to reset, and an unpaired reset moves the cursor."""
        output, stream = make_output(rows=2)
        display = TerminalDisplay(output)
        display.acquire()
        display.release()
        assert stream.getvalue() == ""


class TestHandoffSuspendsReconfiguration:
    """A handoff keeps the lease deliberately, so lease depth alone does not mean the
    terminal is ours to write margins to."""

    def test_reconfigure_is_inert_while_a_guest_owns_the_terminal(self) -> None:
        """Reinstalling margins here would restrict the screen of the program that has it."""
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        display.release_region_for_handoff()
        stream.truncate(0), stream.seek(0)

        assert not display.reconfigure()
        assert stream.getvalue() == ""
        assert not display.is_reserved

    def test_a_resize_during_a_handoff_is_applied_when_the_terminal_comes_back(self) -> None:
        """The suppressed reconfigure loses nothing: the return path measures afresh."""
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        display.release_region_for_handoff()

        screen.rows = 40
        display.reconfigure()
        stream.truncate(0), stream.seek(0)
        display.reacquire_region_after_handoff()

        assert stream.getvalue() == "\x1bD\x1b[1A\x1b7\x1b[1;39r\x1b8"
        assert display.geometry is not None
        assert display.geometry.usable_rows == 39

    def test_an_ineligible_return_unbinds_the_adapter(self) -> None:
        """Otherwise callers keep getting a virtual view of a terminal with no reservation."""
        output, _stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        assert isinstance(display.output, ReservedOutput)
        display.release_region_for_handoff()

        screen.rows = 2
        display.reacquire_region_after_handoff()

        assert not display.is_reserved
        assert not isinstance(display.output, ReservedOutput)

    def test_callers_render_through_the_backend_while_suspended(self) -> None:
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)
        display.acquire()
        display.release_region_for_handoff()
        assert display.output is output


class TestFailedAcquisitionReturnsTheLease:
    """A lease stranded by a failure makes every later acquire() a no-op at depth two, which
    never retries the installation and never reports why."""

    def test_the_lease_is_returned_when_cleanup_fails_as_well(self) -> None:
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)

        def always_fails(_sequence: str) -> None:
            raise OSError("terminal is gone")

        display.terminal.write_margin_change = always_fails  # type: ignore[method-assign]
        with pytest.raises(OSError, match="terminal is gone"):
            display.acquire()
        assert display.lease_depth == 0

    def test_a_recovered_terminal_can_be_acquired_after_a_total_failure(self) -> None:
        output, stream = make_output(rows=24)
        display = TerminalDisplay(output)

        failing = True

        def sometimes_fails(sequence: str) -> None:
            if failing:
                raise OSError("terminal is gone")
            PhysicalTerminal(output).write_margin_change(sequence)

        display.terminal.write_margin_change = sometimes_fails  # type: ignore[method-assign]
        with pytest.raises(OSError, match="terminal is gone"):
            display.acquire()

        failing = False
        stream.truncate(0), stream.seek(0)
        assert display.acquire()
        assert display.lease_depth == 1
        assert stream.getvalue() == "\x1bD\x1b[1A\x1b7\x1b[1;23r\x1b8"

    def test_a_measurement_failure_returns_the_lease_too(self) -> None:
        """Measuring sits inside the rollback: an ioctl that fails must not strand a lease."""
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)

        def no_size() -> Size:
            raise OSError("ioctl failed")

        output.get_size = no_size  # type: ignore[method-assign]
        with pytest.raises(OSError, match="ioctl failed"):
            display.acquire()
        assert display.lease_depth == 0

    def test_the_original_failure_is_what_propagates(self) -> None:
        """A cleanup that also fails must not mask the error worth reading."""
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)

        def install_fails(_sequence: str) -> None:
            raise OSError("install failed")

        display.terminal.write_margin_change = install_fails  # type: ignore[method-assign]
        with pytest.raises(OSError, match="install failed"):
            display.acquire()


class TestHandoffFromAReleasedTerminal:
    """A terminal below the floor is released but still ours, and a guest can take it from
    that state. Recording ownership only when a region happened to be installed would let a
    later resize reinstall margins over the guest's screen."""

    def test_a_guest_can_take_a_terminal_that_is_below_the_floor(self) -> None:
        output, _stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        screen.rows = 2
        display.reconfigure()
        assert not display.is_reserved

        adapter.enter_alternate_screen()
        screen.rows = 24
        assert not display.reconfigure(), "margins were reinstalled over the guest's screen"
        assert not display.is_reserved

    def test_the_guest_keeps_the_whole_screen(self) -> None:
        output, _stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        screen.rows = 2
        display.reconfigure()
        adapter.enter_alternate_screen()
        screen.rows = 24
        display.reconfigure()
        assert adapter.get_size() == Size(rows=24, columns=80)

    def test_no_margin_sequence_reaches_the_guest(self) -> None:
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        screen.rows = 2
        display.reconfigure()
        adapter.enter_alternate_screen()
        adapter.flush()
        screen.rows = 24
        stream.truncate(0), stream.seek(0)

        display.reconfigure()
        adapter.flush()
        assert stream.getvalue() == ""

    def test_the_reservation_is_established_when_the_guest_hands_it_back(self) -> None:
        """Suspending reconfiguration must not lose the resize that happened during it."""
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        screen.rows = 2
        display.reconfigure()
        adapter.enter_alternate_screen()
        screen.rows = 24
        display.reconfigure()
        adapter.flush()
        stream.truncate(0), stream.seek(0)

        adapter.quit_alternate_screen()
        adapter.flush()
        assert display.is_reserved
        assert "\x1b[1;23r" in stream.getvalue()
        assert display.geometry is not None
        assert display.geometry.usable_rows == 23

    def test_a_handoff_without_a_lease_is_not_recorded(self) -> None:
        """Nothing was ours to hand over, so nothing may be reclaimed later."""
        output, _ = make_output(rows=24)
        display = TerminalDisplay(output)
        display.release_region_for_handoff()
        assert display.acquire()
        assert display.is_reserved


class TestHandoffReturnRestoresEverything:
    """Coming back is an ordinary reconfiguration. Installing margins without rebinding the
    adapter leaves a reserved terminal whose callers hold the plain backend -- and therefore
    unbounded erases running over the reserved row."""

    def test_the_adapter_is_rebound_when_the_region_comes_back(self) -> None:
        output, _stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        screen.rows = 2
        display.reconfigure()
        adapter.enter_alternate_screen()
        screen.rows = 24
        adapter.quit_alternate_screen()

        assert display.is_reserved
        assert isinstance(display.output, ReservedOutput), "callers were left on the backend"
        assert display.output.get_size() == Size(rows=23, columns=80)

    def test_erases_through_the_returned_output_are_bounded(self) -> None:
        """The failure this guards against destroys the reserved row outright."""
        output, stream, screen = make_resizable_output(rows=24, columns=80)
        display = TerminalDisplay(output)
        display.acquire()
        adapter = display.output
        screen.rows = 2
        display.reconfigure()
        adapter.enter_alternate_screen()
        screen.rows = 24
        adapter.quit_alternate_screen()

        display.output.flush()
        stream.truncate(0), stream.seek(0)
        display.output.erase_down()
        display.output.flush()
        assert stream.getvalue() == "\x1b[23M"
        assert "\x1b[J" not in stream.getvalue()

    def test_an_unqualified_backend_is_still_unqualified_after_a_handoff(self) -> None:
        """A refused acquisition still holds a lease, so the handoff flag can be set for a
        backend that was never eligible. Capability has to be re-checked, not assumed."""
        display = TerminalDisplay(DummyOutput())
        assert not display.acquire()
        assert display.lease_depth == 1

        display.release_region_for_handoff()
        display.reacquire_region_after_handoff()

        assert not display.is_reserved
        assert display.geometry is None
        assert display.output is display.terminal.output
