"""Contract tests for the prompt_toolkit internals the reserved-row design depends on.

These lock assumptions that are *not* part of prompt_toolkit's public API. They exist so a
dependency upgrade fails loudly here rather than silently breaking terminal rendering, and
so the Windows-only facts are exercised by CI, which is the only place they can run.

Each test names the design requirement it protects.
"""

import inspect
import sys

import pytest
from prompt_toolkit.output import DummyOutput, Output
from prompt_toolkit.renderer import Renderer
from prompt_toolkit.styles import default_ui_style

WINDOWS_ONLY = pytest.mark.skipif(sys.platform != "win32", reason="Windows backend is importable only on Windows")


def make_renderer(output: Output) -> Renderer:
    return Renderer(default_ui_style(), output)


class TestCursorPositionArithmetic:
    """Protects the geometry model: physical CPR rows against a virtual total."""

    def test_available_height_is_rows_minus_row_plus_one(self) -> None:
        """The reserved-row geometry model depends on this exact formula."""
        output = DummyOutput()
        renderer = make_renderer(output)
        renderer.report_absolute_cursor_row(5)
        assert renderer._min_available_height == output.get_size().rows - 5 + 1

    def test_cursor_in_the_reserved_band_yields_nonpositive_height(self) -> None:
        """The R5 hazard: a CPR answered from the reserved row reports no usable height.

        With the region anchored at row 1, a virtual height of U and a physical cursor on
        row H > U gives a nonpositive result. On a VT backend -- where there is no native
        rows-below query to fall back on -- that leaves height_is_known false, so the
        toolbar is not drawn at all, with no error.
        """
        physical_rows, reserved = 24, 1
        usable = physical_rows - reserved

        class Vt100LikeOutput(DummyOutput):
            """A virtual size, and no native rows-below query -- as on POSIX."""

            def get_size(self):  # type: ignore[no-untyped-def]
                size = super().get_size()
                return type(size)(rows=usable, columns=size.columns)

            def get_rows_below_cursor_position(self) -> int:
                raise NotImplementedError

        renderer = make_renderer(Vt100LikeOutput())
        renderer.report_absolute_cursor_row(physical_rows)  # cursor parked in the band
        assert renderer._min_available_height <= 0
        assert not renderer.height_is_known

    def test_a_cursor_inside_the_usable_region_keeps_height_known(self) -> None:
        """Positive pair for the hazard above: the same setup, cursor in the usable area."""
        physical_rows, reserved = 24, 1
        usable = physical_rows - reserved

        class Vt100LikeOutput(DummyOutput):
            def get_size(self):  # type: ignore[no-untyped-def]
                size = super().get_size()
                return type(size)(rows=usable, columns=size.columns)

            def get_rows_below_cursor_position(self) -> int:
                raise NotImplementedError

        renderer = make_renderer(Vt100LikeOutput())
        renderer.report_absolute_cursor_row(usable)  # last usable row
        assert renderer._min_available_height == 1
        assert renderer.height_is_known


class TestEraseInterceptionPoints:
    """Protects the bounded-erase design: both destructive paths go through Output."""

    def test_output_interface_exposes_both_erase_operations(self) -> None:
        assert callable(getattr(Output, "erase_down", None))
        assert callable(getattr(Output, "erase_screen", None))

    def test_renderer_erase_goes_through_output_erase_down(self) -> None:
        """`renderer.erase()` must remain interceptable at the Output boundary."""
        calls: list[str] = []

        class RecordingOutput(DummyOutput):
            def erase_down(self) -> None:
                calls.append("erase_down")

        make_renderer(RecordingOutput()).erase()
        assert "erase_down" in calls

    def test_renderer_clear_goes_through_output_erase_screen(self) -> None:
        """Ctrl-L must remain interceptable; an unbounded ED2 would wipe the reserved row."""
        calls: list[str] = []

        class RecordingOutput(DummyOutput):
            def erase_screen(self) -> None:
                calls.append("erase_screen")

        make_renderer(RecordingOutput()).clear()
        assert "erase_screen" in calls


class TestDiffBaseline:
    """Protects the discarded-frame recovery contract (design section 7.2.1)."""

    def test_renderer_starts_with_no_diff_baseline(self) -> None:
        assert make_renderer(DummyOutput())._last_screen is None

    def test_reset_clears_the_diff_baseline(self) -> None:
        renderer = make_renderer(DummyOutput())
        renderer._last_screen = object()  # type: ignore[assignment]
        renderer.reset()
        assert renderer._last_screen is None


@WINDOWS_ONLY
class TestWindowsBackendContract:
    """Windows facts the design relies on. CI is the only place these can run."""

    def test_windows10_output_is_a_registered_virtual_subclass(self) -> None:
        """isinstance succeeds, but it is not in the MRO -- capability checks must not
        rely on inheritance."""
        from prompt_toolkit.output.windows10 import Windows10_Output

        assert issubclass(Windows10_Output, Output)
        assert Output not in Windows10_Output.__mro__

    def test_geometry_is_delegated_natively(self) -> None:
        """Adapting get_size() alone is insufficient; available height comes from Win32."""
        from prompt_toolkit.output.windows10 import Windows10_Output

        source = inspect.getsource(Windows10_Output.__getattr__)
        assert "get_size" in source
        assert "get_rows_below_cursor_position" in source

    def test_inner_vt100_output_has_a_zero_size_stub(self) -> None:
        """Anything wrapping Windows10_Output must never consult vt100_output.get_size()."""
        from prompt_toolkit.output.windows10 import Windows10_Output

        assert "Size(0, 0)" in inspect.getsource(Windows10_Output.__init__)

    def test_legacy_win32_erase_down_is_a_separate_implementation(self) -> None:
        """The VT sequence replacement does not reach legacy Win32Output."""
        from prompt_toolkit.output.vt100 import Vt100_Output
        from prompt_toolkit.output.win32 import Win32Output

        assert Win32Output.erase_down is not Vt100_Output.erase_down
