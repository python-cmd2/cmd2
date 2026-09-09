"""Tests for recording a renderer's output operations instead of performing them.

The property every test here is really about is that preparation leaves the real backend
untouched: not its stream, not its buffered text, not its attribute or cursor caches, not its
console modes. A recorder that quietly used the backend as its sink would pass a test that
only compared the replayed operation list.
"""

import io
from typing import Any

import pytest
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.data_structures import Size
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.styles import Attrs

from cmd2.output_recorder import (
    Operation,
    OperationBatch,
    PreflightFacts,
    RecordingOutput,
    UnrecordableOperationError,
)

ATTRS = Attrs(
    color="ansired",
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


def make_output(rows: int = 24, cols: int = 80) -> tuple[Vt100_Output, io.StringIO]:
    """Build a real Vt100_Output over a string buffer."""
    stream = io.StringIO()
    size = Size(rows=rows, columns=cols)
    return Vt100_Output(stream, lambda: size), stream


def make_recorder(rows: int = 23, cols: int = 80) -> RecordingOutput:
    """Build a recorder over fixed preflight facts."""
    facts = PreflightFacts(
        size=Size(rows=rows, columns=cols),
        rows_below_cursor=None,
        encoding="utf-8",
        default_color_depth=ColorDepth.DEPTH_8_BIT,
        responds_to_cpr=True,
        fileno=7,
    )
    return RecordingOutput(facts)


class TestPreflightFacts:
    def test_facts_are_captured_from_the_backend(self) -> None:
        output, _stream = make_output()
        facts = PreflightFacts.capture(output)
        assert facts.size == Size(rows=24, columns=80)
        assert facts.encoding == output.encoding()
        assert facts.responds_to_cpr == output.responds_to_cpr
        assert facts.default_color_depth == output.get_default_color_depth()

    def test_a_backend_without_a_native_row_count_records_none(self) -> None:
        """POSIX backends raise here and fall back to CPR; that is a fact, not a failure."""
        output, _stream = make_output()
        with pytest.raises(NotImplementedError):
            output.get_rows_below_cursor_position()
        assert PreflightFacts.capture(output).rows_below_cursor is None

    def test_a_backend_without_a_file_descriptor_records_none(self) -> None:
        output = Vt100_Output(io.StringIO(), lambda: Size(rows=24, columns=80))
        assert PreflightFacts.capture(output).fileno is None

    def test_capturing_facts_writes_nothing(self) -> None:
        output, stream = make_output()
        PreflightFacts.capture(output)
        output.flush()
        assert stream.getvalue() == ""


class TestRecording:
    def test_operations_are_recorded_in_order(self) -> None:
        recorder = make_recorder()
        recorder.cursor_goto(3, 5)
        recorder.write("hello")
        recorder.erase_down()
        assert recorder.operations == (
            Operation("cursor_goto", (3, 5)),
            Operation("write", ("hello",)),
            Operation("erase_down", ()),
        )

    def test_a_flush_is_recorded_as_a_boundary(self) -> None:
        """Flush boundaries are operations, not a signal to touch a real stream."""
        recorder = make_recorder()
        recorder.write("hello")
        recorder.flush()
        assert recorder.operations[-1] == Operation("flush", ())

    def test_reads_are_answered_from_the_preflight_facts(self) -> None:
        recorder = make_recorder(rows=23)
        assert recorder.get_size() == Size(rows=23, columns=80)
        assert recorder.encoding() == "utf-8"
        assert recorder.responds_to_cpr is True
        assert recorder.get_default_color_depth() == ColorDepth.DEPTH_8_BIT
        assert recorder.fileno() == 7

    def test_reads_are_not_recorded_as_operations(self) -> None:
        """A read is not something to replay; replaying one would emit nothing anyway."""
        recorder = make_recorder()
        recorder.get_size()
        recorder.encoding()
        assert recorder.operations == ()

    def test_a_missing_native_row_count_raises_as_the_backend_would(self) -> None:
        recorder = make_recorder()
        with pytest.raises(NotImplementedError):
            recorder.get_rows_below_cursor_position()

    def test_a_missing_file_descriptor_raises_as_the_backend_would(self) -> None:
        facts = PreflightFacts(
            size=Size(rows=23, columns=80),
            rows_below_cursor=None,
            encoding="utf-8",
            default_color_depth=ColorDepth.DEPTH_8_BIT,
            responds_to_cpr=True,
            fileno=None,
        )
        with pytest.raises(io.UnsupportedOperation):
            RecordingOutput(facts).fileno()

    def test_the_recorder_holds_no_reference_to_a_backend(self) -> None:
        """The strongest form of 'preparation has no physical side effects'."""
        recorder = make_recorder()
        assert not any(isinstance(value, Vt100_Output) for value in vars(recorder).values())

    def test_a_screen_buffer_transition_cannot_be_recorded(self) -> None:
        """Buffer transitions are ownership boundaries, taken before a frame is prepared."""
        recorder = make_recorder()
        for transition in (recorder.enter_alternate_screen, recorder.quit_alternate_screen):
            with pytest.raises(UnrecordableOperationError):
                transition()

    def test_a_viewport_move_cannot_be_recorded(self) -> None:
        recorder = make_recorder()
        with pytest.raises(UnrecordableOperationError):
            recorder.scroll_buffer_to_prompt()

    def test_a_rejected_operation_is_not_left_in_the_batch(self) -> None:
        recorder = make_recorder()
        recorder.write("hello")
        with pytest.raises(UnrecordableOperationError):
            recorder.enter_alternate_screen()
        assert recorder.operations == (Operation("write", ("hello",)),)


class TestReplay:
    def test_a_batch_replays_its_operations_onto_a_real_backend(self) -> None:
        recorder = make_recorder()
        recorder.cursor_goto(2, 0)
        recorder.write("hello")
        recorder.flush()

        output, stream = make_output()
        recorder.batch().replay(output)
        # Upstream passes cursor_goto's arguments straight into CUP; the recorder is a delay,
        # not a correction, so replay reproduces that byte for byte.
        assert stream.getvalue() == "\x1b[2;0Hhello"

    def test_recording_and_replay_produce_what_the_backend_would_have(self) -> None:
        """The recorder is a delay, not a translation: the bytes must be identical."""
        direct, direct_stream = make_output()
        direct.set_attributes(ATTRS, ColorDepth.DEPTH_8_BIT)
        direct.write("hello")
        direct.erase_end_of_line()
        direct.reset_attributes()
        direct.flush()

        recorder = make_recorder()
        recorder.set_attributes(ATTRS, ColorDepth.DEPTH_8_BIT)
        recorder.write("hello")
        recorder.erase_end_of_line()
        recorder.reset_attributes()
        recorder.flush()

        replayed, replayed_stream = make_output()
        recorder.batch().replay(replayed)
        assert replayed_stream.getvalue() == direct_stream.getvalue()

    def test_a_batch_is_immutable_once_taken(self) -> None:
        """A batch that kept growing after preparation could not be validated at commit."""
        recorder = make_recorder()
        recorder.write("first")
        batch = recorder.batch()
        recorder.write("second")
        assert batch.operations == (Operation("write", ("first",)),)

    def test_replay_stops_at_the_operation_that_failed(self) -> None:
        """Partial replay is a real state; the batch must not paper over it."""

        class FailingOutput(Vt100_Output):
            def erase_down(self) -> None:
                raise OSError("terminal went away")

        recorder = make_recorder()
        recorder.write("hello")
        recorder.erase_down()
        recorder.write("never")

        stream = io.StringIO()
        output = FailingOutput(stream, lambda: Size(rows=24, columns=80))
        with pytest.raises(OSError, match="terminal went away"):
            recorder.batch().replay(output)
        output.flush()
        assert stream.getvalue() == "hello"

    def test_an_empty_batch_replays_nothing(self) -> None:
        output, stream = make_output()
        OperationBatch(operations=(), facts=make_recorder().facts).replay(output)
        output.flush()
        assert stream.getvalue() == ""

    def test_the_batch_carries_the_facts_it_was_prepared_against(self) -> None:
        recorder = make_recorder(rows=23)
        assert recorder.batch().facts.size == Size(rows=23, columns=80)


#: Every operation the recorder defers, with arguments where it takes them. Replaying each one
#: must produce exactly what calling it on the backend produces, so this table is what keeps a
#: mistyped delegation -- a wrong method name, a dropped argument -- from reaching the terminal.
RECORDED_OPERATIONS: list[tuple[str, tuple[Any, ...]]] = [
    ("write", ("hello",)),
    ("write_raw", ("\x1b[7m",)),
    ("set_title", ("cmd2",)),
    ("clear_title", ()),
    ("erase_screen", ()),
    ("erase_down", ()),
    ("erase_end_of_line", ()),
    ("set_attributes", (ATTRS, ColorDepth.DEPTH_8_BIT)),
    ("reset_attributes", ()),
    ("disable_autowrap", ()),
    ("enable_autowrap", ()),
    ("cursor_goto", (4, 2)),
    ("cursor_up", (3,)),
    ("cursor_down", (3,)),
    ("cursor_forward", (3,)),
    ("cursor_backward", (3,)),
    ("hide_cursor", ()),
    ("show_cursor", ()),
    ("set_cursor_shape", (CursorShape.BLOCK,)),
    ("reset_cursor_shape", ()),
    ("enable_mouse_support", ()),
    ("disable_mouse_support", ()),
    ("enable_bracketed_paste", ()),
    ("disable_bracketed_paste", ()),
    ("reset_cursor_key_mode", ()),
    ("ask_for_cpr", ()),
    ("bell", ()),
    ("flush", ()),
]


class TestEveryRecordedOperation:
    @pytest.mark.parametrize(("name", "args"), RECORDED_OPERATIONS, ids=[name for name, _ in RECORDED_OPERATIONS])
    def test_replay_matches_a_direct_call_on_the_backend(self, name: str, args: tuple[Any, ...]) -> None:
        direct, direct_stream = make_output()
        getattr(direct, name)(*args)
        direct.flush()

        recorder = make_recorder()
        getattr(recorder, name)(*args)
        assert recorder.operations[0].name == name

        replayed, replayed_stream = make_output()
        recorder.batch().replay(replayed)
        replayed.flush()
        assert replayed_stream.getvalue() == direct_stream.getvalue()

    def test_a_native_row_count_is_reported_when_the_backend_has_one(self) -> None:
        """Windows answers this natively; the recorded render must see the same number."""
        facts = PreflightFacts(
            size=Size(rows=23, columns=80),
            rows_below_cursor=9,
            encoding="utf-8",
            default_color_depth=ColorDepth.DEPTH_8_BIT,
            responds_to_cpr=True,
            fileno=7,
        )
        assert RecordingOutput(facts).get_rows_below_cursor_position() == 9
