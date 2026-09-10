"""Tests for preparing, committing and recovering renderer frames.

Several of these are the named regressions from design section 13.2. The property underneath
all of them is that a frame the terminal never received must never become the baseline the
next frame is diffed against: upstream advances its own state while it renders, so discarding
the *output* is only half of discarding the frame.

The renderer here is a real prompt-toolkit renderer driving a real application, so the
recorded operations and the flags left behind are the ones production would see.
"""

import io
import threading
from collections import deque
from concurrent.futures import Future
from typing import Any

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Point, Size
from prompt_toolkit.input import DummyInput
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.output.vt100 import Vt100_Output

from cmd2.output_recorder import PreflightFacts
from cmd2.prompt_toolkit_bridge import (
    PromptToolkitBridge,
    ReservedModeFailureError,
)
from cmd2.terminal_display import TerminalDisplay
from cmd2.terminal_transaction import TerminalLock, current_transaction


class TtyStringIO(io.StringIO):
    """A stream that claims to be a terminal, so the backend will use cursor reports."""

    def isatty(self) -> bool:
        return True


class Harness:
    """A real application over a reserved terminal, with the stream it writes to."""

    def __init__(
        self,
        rows: int = 24,
        columns: int = 40,
        reserved_rows: int = 1,
        content: Any = "hello",
        lock: TerminalLock | None = None,
    ) -> None:
        self.stream = TtyStringIO()
        self.size = Size(rows=rows, columns=columns)
        self.backend = Vt100_Output(self.stream, lambda: self.size)
        self.display = TerminalDisplay(self.backend, reserved_rows=reserved_rows)
        assert self.display.acquire() is True
        self.lock = lock or TerminalLock()
        self.app: Application[Any] = Application(
            layout=Layout(Window(FormattedTextControl(content))),
            output=self.display.output,
            input=DummyInput(),
        )
        self.bridge = PromptToolkitBridge(renderer=self.app.renderer, display=self.display, lock=self.lock)
        self.bridge.set_prompt_anchor(1)
        self.clear()

    @property
    def renderer(self) -> Any:
        """The application's renderer."""
        return self.app.renderer

    def clear(self) -> str:
        """Take everything written so far, leaving the stream empty."""
        written = self.stream.getvalue()
        self.stream.truncate(0)
        self.stream.seek(0)
        return written

    def written(self) -> str:
        """What has been written since the last clear."""
        return self.stream.getvalue()

    def prepare(self) -> Any:
        """Prepare one frame, as the bridge's caller would."""
        with set_app(self.app):
            return self.bridge.prepare(self.app)

    def render(self) -> bool:
        """Prepare and commit one frame."""
        prepared = self.prepare()
        assert prepared is not None
        return self.bridge.commit(prepared)

    def resize(self, rows: int, columns: int = 40) -> None:
        """Resize the terminal and re-establish the reservation for the new geometry."""
        self.size = Size(rows=rows, columns=columns)
        self.display.reconfigure()

    def resynchronize(self) -> None:
        """Run recovery in the application's context."""
        with set_app(self.app):
            self.bridge.resynchronize()


class TestPreparation:
    def test_preparation_writes_nothing_to_the_terminal(self) -> None:
        harness = Harness()
        assert harness.prepare() is not None
        assert harness.written() == ""

    def test_render_callbacks_run_before_terminal_commit(self) -> None:
        """Named test 13.2: layout and style callbacks must not run inside the transaction."""
        seen: list[object] = []

        def content() -> str:
            seen.append(current_transaction())
            return "hello"

        harness = Harness(content=content)
        assert harness.prepare() is not None
        assert seen
        assert all(state is None for state in seen)

    def test_the_prepared_frame_is_what_gets_emitted(self) -> None:
        harness = Harness()
        assert harness.render() is True
        assert "hello" in harness.written()

    def test_preparation_does_not_advance_the_backend(self) -> None:
        """A discarded frame must leave no trace in the backend's own buffering."""
        harness = Harness()
        harness.prepare()
        harness.backend.flush()
        assert harness.written() == ""

    def test_the_application_renders_against_the_usable_height(self) -> None:
        """The reservation is subtracted once: 24 physical rows, one reserved, 23 usable."""
        harness = Harness(rows=24, reserved_rows=1)
        prepared = harness.prepare()
        assert prepared is not None
        assert prepared.batch.facts.size == Size(rows=23, columns=40)

    def test_a_failing_preparation_reports_and_asks_for_resynchronization(self) -> None:
        def boom() -> str:
            raise RuntimeError("layout failed")

        harness = Harness(content=boom)
        assert harness.prepare() is None
        assert harness.bridge.needs_resynchronization is True
        assert isinstance(harness.bridge.take_pending_error(), RuntimeError)
        assert harness.written() == ""

    def test_no_frame_is_prepared_while_resynchronization_is_owed(self) -> None:
        harness = Harness()
        harness.bridge.require_resynchronization("test")
        assert harness.prepare() is None


class TestCommitValidation:
    def test_stale_prepared_frame_never_becomes_diff_baseline(self) -> None:
        """Named test 13.2: intervening output retires the batch without emitting it."""
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.clear()

        harness.bridge.note_managed_write()
        assert harness.bridge.commit(prepared) is False

        assert harness.written() == ""
        assert harness.renderer._last_screen is None
        assert harness.bridge.needs_resynchronization is True

    def test_a_resize_between_prepare_and_commit_retires_the_batch(self) -> None:
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.size = Size(rows=12, columns=40)
        harness.display.reconfigure()
        harness.clear()
        assert harness.bridge.commit(prepared) is False
        assert harness.written() == ""

    def test_an_owner_change_retires_the_batch(self) -> None:
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.note_owner_change()
        assert harness.bridge.commit(prepared) is False

    def test_a_content_invalidation_does_not_authorize_a_stale_batch(self) -> None:
        """Content generation is tracked separately so it cannot mask a real invalidation."""
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.note_managed_write()
        harness.bridge.note_content_change()
        assert harness.bridge.commit(prepared) is False

    def test_a_content_invalidation_alone_does_not_retire_a_batch(self) -> None:
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.note_content_change()
        assert harness.bridge.commit(prepared) is True

    def test_the_committed_frame_is_the_next_diff_baseline(self) -> None:
        harness = Harness()
        harness.render()
        assert harness.renderer._last_screen is not None
        assert harness.bridge.needs_resynchronization is False

    def test_uncommitted_frame_metadata_is_not_dispatched(self) -> None:
        """Named test 13.2: provisional handlers and windows stay invisible until commit."""
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.note_managed_write(prompt_anchor=1)
        assert harness.bridge.can_dispatch_input is False
        assert harness.bridge.commit(prepared) is False
        assert harness.bridge.can_dispatch_input is False
        harness.resynchronize()
        assert harness.bridge.can_dispatch_input is True


class TestPartialCommitFailure:
    def test_partial_commit_failure_does_not_replay_frame(self) -> None:
        """Named test 13.2: some bytes are already out; replaying would duplicate them."""
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.clear()

        failures = {"count": 0}
        real_write = harness.backend.write_raw

        def failing_write_raw(data: str) -> None:
            failures["count"] += 1
            if failures["count"] == 3:
                raise OSError("terminal went away")
            real_write(data)

        harness.backend.write_raw = failing_write_raw  # type: ignore[method-assign]
        assert harness.bridge.commit(prepared) is False
        harness.backend.write_raw = real_write  # type: ignore[method-assign]

        assert isinstance(harness.bridge.take_pending_error(), OSError)
        assert harness.bridge.needs_resynchronization is True
        assert harness.renderer._last_screen is None
        emitted = harness.clear()

        # The batch is not replayed: a retry would duplicate whatever already reached the
        # terminal, and nothing here knows how much that was.
        assert harness.bridge.commit(prepared) is False
        assert harness.written() == ""
        assert emitted != ""

    def test_failed_cleanup_stops_reserved_emission(self) -> None:
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None

        def always_fails(data: str) -> None:
            raise OSError("terminal went away")

        harness.backend.write_raw = always_fails  # type: ignore[method-assign]
        assert harness.bridge.commit(prepared) is False
        assert harness.bridge.reserved_emission_stopped is True

    def test_nothing_is_prepared_once_reserved_emission_has_stopped(self) -> None:
        harness = Harness()
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        assert harness.prepare() is None


class TestRecovery:
    def test_discarded_frame_resynchronizes_terminal_modes(self) -> None:
        """Named test 13.2: a latched flag never re-emits its sequence on its own."""
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        # Preparation advanced the flag even though the terminal saw nothing.
        assert harness.renderer._bracketed_paste_enabled is True
        harness.bridge.note_managed_write(prompt_anchor=1)
        harness.bridge.commit(prepared)
        harness.clear()

        harness.resynchronize()
        written = harness.written()
        assert "\x1b[?2004h" in written  # bracketed paste, re-established physically
        assert harness.renderer._bracketed_paste_enabled is True
        assert harness.renderer._last_screen is None
        assert harness.renderer._last_size is None
        assert harness.renderer._last_style is None
        assert harness.renderer._last_cursor_shape is None

    def test_recovery_restores_the_baseline_only_after_a_full_frame(self) -> None:
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.note_managed_write(prompt_anchor=1)
        harness.bridge.commit(prepared)
        harness.resynchronize()
        harness.clear()
        assert harness.render() is True
        assert "hello" in harness.written()

    def test_discarded_frame_recovers_current_prompt_origin(self) -> None:
        """Named test 13.2: intervening output scrolled the prompt; the stale cursor is wrong."""
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.note_managed_write()
        harness.bridge.set_prompt_anchor(9)
        harness.bridge.commit(prepared)
        harness.clear()

        harness.resynchronize()
        assert "\x1b[9;1H" in harness.written()
        assert harness.renderer._cursor_pos == Point(x=0, y=0)

    def test_recovery_without_a_known_origin_fails_explicitly(self) -> None:
        """Guessing an origin would paint the prompt over committed output."""
        harness = Harness()
        harness.bridge.forget_prompt_anchor()
        harness.backend.enable_cpr = False
        with pytest.raises(ReservedModeFailureError), set_app(harness.app):
            harness.bridge.resynchronize()

    def test_recovery_invalidates_provisional_mouse_metadata(self) -> None:
        harness = Harness()
        harness.render()
        handlers = harness.renderer.mouse_handlers
        harness.resynchronize()
        assert harness.renderer.mouse_handlers is not handlers

    def test_recovery_reestablishes_available_height_from_the_origin(self) -> None:
        """A visible marker does not prove prompt geometry; height has to be re-established.

        Zeroing it would leave ``height_is_known`` false while input was allowed to resume,
        which is the same invalid state recovery exists to leave behind.
        """
        harness = Harness(rows=24, reserved_rows=1)
        harness.bridge.set_prompt_anchor(6)
        harness.renderer._min_available_height = 17
        harness.resynchronize()
        assert harness.renderer._min_available_height == 23 - 6 + 1
        assert harness.renderer.height_is_known is True

    def test_recovery_does_not_use_the_upstream_reset(self) -> None:
        """Upstream reset() emits operations and rewrites available-height bookkeeping."""
        harness = Harness()
        calls: list[int] = []
        harness.renderer.reset = lambda *args, **kwargs: calls.append(1)  # type: ignore[method-assign]
        harness.resynchronize()
        assert calls == []

    def test_the_narrow_reset_names_fields_this_prompt_toolkit_has(self) -> None:
        """A version contract: a renamed upstream field must fail here, not silently do nothing."""
        harness = Harness()
        for name in (
            "_last_screen",
            "_last_size",
            "_last_style",
            "_last_cursor_shape",
            "_cursor_pos",
            "_min_available_height",
            "_bracketed_paste_enabled",
            "_mouse_support_enabled",
            "_cursor_key_mode_reset",
            "mouse_handlers",
        ):
            assert hasattr(harness.renderer, name), name


class TestInvalidationCoalescing:
    def test_repeated_invalidation_yields_to_managed_output(self) -> None:
        """Named test 13.2: contention coalesces into one redraw and does not spin."""
        harness = Harness()
        scheduled: list[int] = []
        harness.bridge.set_redraw_scheduler(lambda: scheduled.append(1))

        for _ in range(5):
            harness.bridge.note_managed_write(prompt_anchor=1)

        assert len(scheduled) == 1
        assert harness.bridge.redraw_pending is True

        harness.resynchronize()
        assert harness.render() is True
        assert harness.bridge.redraw_pending is False

    def test_a_redraw_is_requested_again_after_it_is_served(self) -> None:
        harness = Harness()
        scheduled: list[int] = []
        harness.bridge.set_redraw_scheduler(lambda: scheduled.append(1))
        harness.bridge.note_managed_write(prompt_anchor=1)
        harness.resynchronize()
        harness.render()
        harness.bridge.note_managed_write(prompt_anchor=1)
        assert len(scheduled) == 2


class TestCursorPositionReports:
    def test_cpr_uses_row_one_coordinate_contract(self) -> None:
        """A valid row yields exactly U - r + 1 because the region is anchored at row one."""
        harness = Harness(rows=24, reserved_rows=1)
        assert harness.bridge.request_cursor_position() is True
        assert harness.bridge.report_cursor_row(4) is True
        assert harness.renderer._min_available_height == 23 - 4 + 1

    def test_cpr_in_reserved_band_is_rejected(self) -> None:
        """Named test 13.1: the upstream formula gives zero at U+1 and negative below it."""
        harness = Harness(rows=24, reserved_rows=1)
        harness.bridge.request_cursor_position()
        assert 23 - 24 + 1 == 0
        assert harness.bridge.report_cursor_row(24) is False
        assert harness.renderer._min_available_height == 0
        assert harness.bridge.needs_resynchronization is True

        deeper = Harness(rows=24, reserved_rows=2)
        deeper.bridge.request_cursor_position()
        assert 22 - 24 + 1 == -1
        assert deeper.bridge.report_cursor_row(24) is False
        assert deeper.renderer._min_available_height == 0

    def test_a_rejected_reply_settles_the_pending_request(self) -> None:
        """A stuck future would leave the renderer waiting for a report that never comes."""
        harness = Harness()
        harness.bridge.request_cursor_position()
        harness.bridge.report_cursor_row(24)
        assert harness.renderer.waiting_for_cpr is False

    def test_an_uncorrelated_late_reply_is_dropped(self) -> None:
        harness = Harness()
        assert harness.bridge.report_cursor_row(4) is False
        assert harness.renderer._min_available_height == 0

    def test_a_stale_generation_reply_cannot_satisfy_a_newer_request(self) -> None:
        """Named test 13.2: replies correlate by order, and the wire carries no generation."""
        harness = Harness()
        harness.bridge.request_cursor_position()
        harness.size = Size(rows=12, columns=40)
        harness.display.reconfigure()
        harness.bridge.note_geometry_change()
        harness.bridge.request_cursor_position()

        # The first reply belongs to the request made before the resize.
        assert harness.bridge.report_cursor_row(4) is False
        assert harness.renderer._min_available_height == 0
        # The second one is the current generation's and is accepted.
        assert harness.bridge.report_cursor_row(4) is True
        assert harness.renderer._min_available_height == 11 - 4 + 1

    def test_cpr_request_cannot_interleave_with_paint(self) -> None:
        """The request is emitted in its own transaction, never inside another one."""
        harness = Harness()
        seen: list[object] = []
        real_ask = harness.backend.ask_for_cpr

        def watched_ask() -> None:
            seen.append(current_transaction())
            real_ask()

        harness.backend.ask_for_cpr = watched_ask  # type: ignore[method-assign]
        harness.bridge.request_cursor_position()
        assert len(seen) == 1
        state = seen[0]
        assert state is not None
        assert state.kind == "cursor position request"

    def test_no_request_is_made_when_the_backend_does_not_answer(self) -> None:
        harness = Harness()
        harness.backend.enable_cpr = False
        assert harness.bridge.request_cursor_position() is False


class TestRecoveryEdges:
    def test_recovery_after_reserved_emission_stopped_is_refused(self) -> None:
        harness = Harness()
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        with pytest.raises(ReservedModeFailureError), set_app(harness.app):
            harness.bridge.resynchronize()

    def test_an_unknown_origin_asks_the_terminal_and_stays_owed(self) -> None:
        """The reply establishes the origin; recovery is not finished until it arrives."""
        harness = Harness()
        harness.bridge.require_resynchronization("test")
        harness.bridge.forget_prompt_anchor()
        harness.clear()
        harness.resynchronize()
        assert "\x1b[6n" in harness.written()
        assert harness.bridge.needs_resynchronization is True

    def test_a_cursor_report_establishes_the_prompt_origin(self) -> None:
        harness = Harness()
        harness.bridge.forget_prompt_anchor()
        harness.bridge.request_cursor_position()
        assert harness.bridge.report_cursor_row(6) is True
        assert harness.bridge.prompt_anchor == 6

    def test_mouse_support_is_established_when_the_application_wants_it(self) -> None:
        harness = Harness()
        harness.renderer.mouse_support = lambda: True
        harness.clear()
        harness.resynchronize()
        assert "\x1b[?1000h" in harness.written()
        assert harness.renderer._mouse_support_enabled is True

    def test_a_rejected_reply_resolves_a_renderer_future(self) -> None:
        """Whoever asked is waiting; a rejected reply still has to settle that bookkeeping."""
        harness = Harness()
        pending: Future[None] = Future()
        harness.renderer._waiting_for_cpr_futures.append(pending)
        harness.bridge.request_cursor_position()
        assert harness.bridge.report_cursor_row(24) is False
        assert pending.done() is True


class TestBookkeeping:
    def test_content_invalidations_are_counted(self) -> None:
        harness = Harness()
        assert harness.bridge.content_generation == 0
        harness.bridge.note_content_change()
        assert harness.bridge.content_generation == 1

    def test_the_prompt_anchor_is_reported(self) -> None:
        harness = Harness()
        assert harness.bridge.prompt_anchor == 1
        harness.bridge.forget_prompt_anchor()
        assert harness.bridge.prompt_anchor is None

    def test_only_one_frame_is_in_flight_at_a_time(self) -> None:
        """Two provisional frames would mean two claims on the renderer's state."""
        harness = Harness()
        assert harness.prepare() is not None
        assert harness.prepare() is None


class TestReviewRegressions:
    def test_a_batch_prepared_against_a_stale_size_is_not_committed(self, monkeypatch: Any) -> None:
        """Review finding 1: facts and generations must describe the same terminal."""
        harness = Harness(rows=24)
        capture = PreflightFacts.capture

        def capture_then_resize(output: Any) -> PreflightFacts:
            facts = capture(output)
            harness.resize(12)
            return facts

        monkeypatch.setattr(PreflightFacts, "capture", staticmethod(capture_then_resize))
        prepared = harness.prepare()
        monkeypatch.undo()
        assert prepared is not None
        assert prepared.batch.facts.size == Size(rows=23, columns=40)
        harness.clear()
        assert harness.bridge.commit(prepared) is False
        assert harness.written() == ""

    def test_a_frame_is_not_committed_while_recovery_is_owed(self) -> None:
        """Review finding 1: an invalidated preparation must not become committable.

        Owing a recovery retires the frame in flight, and that retirement is the single
        mechanism commit checks -- so this asserts it happened, not only that the commit was
        refused, since a refusal for some other reason would prove nothing.
        """
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.require_resynchronization("something invalidated the terminal")
        assert harness.bridge.in_flight is None
        harness.clear()
        assert harness.bridge.commit(prepared) is False
        assert harness.written() == ""

    def test_abandoning_reserved_emission_retires_the_frame_in_flight(self) -> None:
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        assert harness.bridge.in_flight is None
        assert harness.bridge.commit(prepared) is False

    def test_input_cannot_be_dispatched_while_a_frame_is_being_prepared(self) -> None:
        """Review finding 2: the renderer's state is provisional from the first callback on."""
        seen: list[bool] = []
        harness = Harness(content=lambda: seen.append(harness.bridge.can_dispatch_input) or "hello")
        harness.prepare()
        assert seen
        assert not any(seen)

    def test_a_recursive_preparation_is_refused(self) -> None:
        """Review finding 2: two provisional frames would both claim the renderer's state."""
        recursive: list[Any] = []

        def content() -> str:
            with set_app(harness.app):
                recursive.append(harness.bridge.prepare(harness.app))
            return "hello"

        harness = Harness(content=content)
        assert harness.prepare() is not None
        assert recursive == [None]

    def test_managed_output_between_frames_invalidates_the_baseline(self) -> None:
        """Review finding 3: the committed cursor relationship does not survive a write."""
        harness = Harness()
        assert harness.render() is True
        harness.bridge.note_managed_write()
        assert harness.bridge.needs_resynchronization is True
        assert harness.prepare() is None

    def test_a_managed_write_can_supply_the_new_prompt_origin(self) -> None:
        """The layer that emitted the output is the one that knows where it ended."""
        harness = Harness()
        harness.render()
        harness.bridge.note_managed_write(prompt_anchor=7)
        assert harness.bridge.prompt_anchor == 7
        harness.clear()
        harness.resynchronize()
        assert "\x1b[7;1H" in harness.written()

    def test_recovery_refuses_an_anchor_outside_the_usable_region(self) -> None:
        """Review finding 5: a shrunken terminal makes a remembered row point into the band."""
        harness = Harness(rows=24)
        harness.bridge.set_prompt_anchor(20)
        harness.resize(12)
        harness.bridge.note_geometry_change()
        harness.clear()
        harness.resynchronize()
        assert "\x1b[20;1H" not in harness.written()
        assert harness.bridge.prompt_anchor is None
        assert harness.bridge.needs_resynchronization is True

    def test_an_out_of_range_anchor_falls_back_when_the_terminal_cannot_report(self) -> None:
        harness = Harness(rows=24)
        harness.bridge.set_prompt_anchor(20)
        harness.resize(12)
        harness.backend.enable_cpr = False
        with pytest.raises(ReservedModeFailureError), set_app(harness.app):
            harness.bridge.resynchronize()

    def test_the_resynchronization_reason_is_reported(self) -> None:
        harness = Harness()
        assert harness.bridge.resynchronization_reason is None
        harness.bridge.require_resynchronization("a command wrote to the terminal")
        assert harness.bridge.resynchronization_reason == "a command wrote to the terminal"
        harness.resynchronize()
        assert harness.bridge.resynchronization_reason is None

    def test_a_write_from_inside_a_layout_callback_retires_the_frame(self) -> None:
        """The operations were recorded against a terminal that moved on mid-render."""

        def content() -> str:
            harness.bridge.note_managed_write()
            return "hello"

        harness = Harness(content=content)
        assert harness.prepare() is None
        assert harness.bridge.needs_resynchronization is True
        assert harness.bridge.can_dispatch_input is False

    def test_a_cursor_report_is_validated_against_the_screen_when_released(self) -> None:
        """With no reservation the whole screen is usable, and the band no longer exists."""
        harness = Harness(rows=24)
        harness.display.release()
        harness.bridge.request_cursor_position()
        assert harness.bridge.report_cursor_row(24) is True
        assert harness.renderer._min_available_height == 24 - 24 + 1


class RetiringLock:
    """A lock that runs scheduled callbacks at the moments it is handed over.

    This stands in for another writer changing the terminal while a caller waits for it.
    Driving that with two real threads cannot say *where* the waiting thread had got to before
    the lock was released -- the interleaving these tests are about is the one where it is
    already past its own checks -- so the handover itself is the seam to inject at.

    Callbacks are scheduled per acquisition, in order, so an operation that takes the terminal
    more than once can be interrupted at the handover that matters. ``None`` skips one.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._schedule: deque[Any] = deque()

    def schedule(self, *callbacks: Any) -> None:
        """Queue one callback per upcoming acquisition."""
        self._schedule.extend(callbacks)

    def acquire(self, *args: Any, **kwargs: Any) -> bool:
        acquired = self._lock.acquire(*args, **kwargs)
        if self._schedule:
            callback = self._schedule.popleft()
            if callback is not None:
                callback()
        return acquired

    def release(self) -> None:
        self._lock.release()


class TestReviewRegressionsRoundTwo:
    def test_a_managed_write_without_an_origin_forgets_the_old_one(self) -> None:
        """Review finding 1: the output moved the cursor, so the remembered row is stale."""
        harness = Harness()
        harness.render()
        assert harness.bridge.prompt_anchor == 1
        harness.bridge.note_managed_write()
        assert harness.bridge.prompt_anchor is None

        harness.clear()
        harness.resynchronize()
        written = harness.written()
        assert "\x1b[1;1H" not in written
        assert "\x1b[6n" in written
        assert harness.bridge.needs_resynchronization is True

    def test_a_frame_prepared_after_emission_stopped_is_not_published(self) -> None:
        """Review finding 2: stopping is not the same state as owing a recovery."""

        def content() -> str:
            harness.bridge.stop_reserved_emission(OSError("terminal went away"))
            return "hello"

        harness = Harness(content=content)
        assert harness.prepare() is None
        assert harness.bridge.in_flight is None
        assert harness.bridge.reserved_emission_stopped is True

    def test_a_frame_retired_while_the_commit_waits_is_not_emitted(self) -> None:
        """Review finding 3: retirement only replaces an explicit guard if read under the lock."""
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))
        prepared = harness.prepare()
        assert prepared is not None
        harness.clear()

        handover.schedule(lambda: harness.bridge.require_resynchronization("another writer"))
        assert harness.bridge.commit(prepared) is False
        assert harness.written() == ""
        assert harness.bridge.needs_resynchronization is True

    def test_recovery_uses_the_origin_it_finds_after_taking_the_terminal(self) -> None:
        """Review finding: an origin read before the wait describes a terminal someone held."""
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))
        harness.bridge.set_prompt_anchor(1)
        harness.clear()

        handover.schedule(lambda: harness.bridge.note_managed_write(prompt_anchor=7))
        harness.resynchronize()

        written = harness.written()
        assert "\x1b[7;1H" in written
        assert "\x1b[1;1H" not in written
        assert harness.renderer._min_available_height == 23 - 7 + 1
        assert harness.bridge.needs_resynchronization is False

    def test_recovery_completes_before_the_terminal_is_released(self) -> None:
        """Whoever takes the terminal next must not find a recovery still owed."""
        seen: list[bool] = []
        harness = Harness()
        original = harness.bridge._initialize_renderer

        def watched(policy: Any, origin: int) -> None:
            original(policy, origin)
            seen.append(harness.bridge.needs_resynchronization)

        harness.bridge._initialize_renderer = watched  # type: ignore[method-assign]
        harness.bridge.require_resynchronization("test")
        harness.resynchronize()
        assert seen == [False]

    def test_a_cursor_report_invalidated_by_managed_output_is_rejected(self) -> None:
        """Review finding: the write moved the cursor the terminal was sampling."""
        harness = Harness()
        harness.bridge.request_cursor_position()
        harness.bridge.note_managed_write(prompt_anchor=7)
        assert harness.bridge.report_cursor_row(4) is False
        assert harness.bridge.prompt_anchor == 7
        assert harness.renderer._min_available_height == 0

    def test_replies_still_correlate_by_order_after_one_is_invalidated(self) -> None:
        """Rejecting a reply must not desynchronize the queue behind it."""
        harness = Harness()
        harness.bridge.request_cursor_position()
        harness.bridge.note_managed_write(prompt_anchor=7)
        harness.bridge.request_cursor_position()

        assert harness.bridge.report_cursor_row(4) is False
        assert harness.bridge.report_cursor_row(5) is True
        assert harness.bridge.prompt_anchor == 5
        assert harness.renderer._min_available_height == 23 - 5 + 1

    def test_a_reply_cannot_overtake_a_write_that_lands_while_it_waits(self) -> None:
        """Review finding: validating a reply and publishing its origin must be one step."""
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))
        harness.bridge.request_cursor_position()

        handover.schedule(lambda: harness.bridge.note_managed_write(prompt_anchor=7))
        assert harness.bridge.report_cursor_row(4) is False
        assert harness.bridge.prompt_anchor == 7

    def test_a_request_records_the_terminal_it_was_actually_sent_to(self) -> None:
        """A write during acquisition must not make the reply to a later request look stale."""
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))

        handover.schedule(lambda: harness.bridge.note_managed_write(prompt_anchor=7))
        assert harness.bridge.request_cursor_position() is True
        # The request went out after that write, so its reply describes the current terminal.
        assert harness.bridge.report_cursor_row(4) is True
        assert harness.bridge.prompt_anchor == 4

    def test_recovery_that_finds_emission_stopped_writes_nothing(self) -> None:
        """Review finding: rendering can be abandoned while recovery queues for the terminal."""
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))
        harness.bridge.require_resynchronization("test")
        harness.clear()

        handover.schedule(lambda: harness.bridge.stop_reserved_emission(OSError("terminal went away")))
        with pytest.raises(ReservedModeFailureError):
            harness.resynchronize()
        assert harness.written() == ""
        assert harness.bridge.needs_resynchronization is True

    def test_an_unknown_origin_request_that_finds_emission_stopped_writes_nothing(self) -> None:
        """Review finding: recovery's second transaction is a second chance to be abandoned.

        Recovery without an anchor releases the terminal and asks for it again to send the
        cursor request. Emission can be given up in between, and the request would otherwise
        write into a terminal nothing may emit to any more.
        """
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))
        harness.bridge.forget_prompt_anchor()
        harness.bridge.require_resynchronization("test")
        harness.clear()

        # Skip recovery's own transaction; abandon emission as the request takes the terminal.
        handover.schedule(None, lambda: harness.bridge.stop_reserved_emission(OSError("terminal went away")))
        harness.resynchronize()

        assert harness.bridge.reserved_emission_stopped is True
        assert harness.written() == ""
        # Nothing was queued either: a reply now would be answering a request never made.
        assert harness.bridge.report_cursor_row(4) is False

    def test_a_frame_is_not_published_over_an_abandonment(self) -> None:
        """Review finding: checking and publishing must be one step, or one overwrites the other."""
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))
        # Skip the preflight acquisition; abandon emission as the publication takes the lock.
        handover.schedule(None, lambda: harness.bridge.stop_reserved_emission(OSError("terminal went away")))

        assert harness.prepare() is None
        assert harness.bridge.in_flight is None

    def test_a_frame_in_flight_while_emission_is_abandoned_is_not_committed(self) -> None:
        """Retirement alone cannot carry this: a publication can overwrite a retirement.

        The state is built directly because that is the point -- commit must reject a frame
        that is in flight while emission is abandoned, whatever sequence produced that pair,
        rather than trusting that nothing can produce it.
        """
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        harness.bridge._in_flight = prepared
        harness.clear()

        assert harness.bridge.commit(prepared) is False
        assert harness.written() == ""

    def test_a_frame_in_flight_while_recovery_is_owed_is_not_committed(self) -> None:
        harness = Harness()
        prepared = harness.prepare()
        assert prepared is not None
        harness.bridge.require_resynchronization("another writer")
        harness.bridge._in_flight = prepared
        harness.clear()

        assert harness.bridge.commit(prepared) is False
        assert harness.written() == ""


class RecordingTtyStream(TtyStringIO):
    """A terminal that records the transaction each write ran in."""

    def __init__(self) -> None:
        super().__init__()
        self.transactions: list[Any] = []

    def write(self, text: str) -> int:
        self.transactions.append(current_transaction())
        return super().write(text)


class TestRenderInterception:
    """Once bound, prompt-toolkit's own renders go through prepare and commit."""

    def bound(self, content: Any = "hello") -> Harness:
        """Build a harness whose renderer is intercepted by the bridge."""
        harness = Harness(content=content)
        harness.stream_recorder = RecordingTtyStream()
        harness.backend.stdout = harness.stream_recorder
        harness.bridge.bind(harness.app)
        return harness

    def test_a_render_reaches_the_terminal(self) -> None:
        harness = self.bound()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert "hello" in harness.stream_recorder.getvalue()

    def test_a_render_is_emitted_inside_a_terminal_transaction(self) -> None:
        """This is the whole point: renders serialize against paints and command output."""
        harness = self.bound()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert harness.stream_recorder.transactions
        assert all(state is not None for state in harness.stream_recorder.transactions)

    def test_layout_callbacks_still_run_outside_the_transaction(self) -> None:
        seen: list[object] = []

        def content() -> str:
            seen.append(current_transaction())
            return "hello"

        harness = self.bound(content=content)
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert seen
        assert all(state is None for state in seen)

    def test_the_frame_is_committed_rather_than_left_in_flight(self) -> None:
        harness = self.bound()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert harness.bridge.in_flight is None
        assert harness.bridge.can_dispatch_input is True

    def test_preparation_does_not_re_enter_the_interception(self) -> None:
        """The recorded render has to be upstream's, not the wrapper calling itself."""
        harness = self.bound()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        # A recursive wrapper would never terminate; reaching here with output proves it did.
        assert "hello" in harness.stream_recorder.getvalue()

    def test_a_render_owed_recovery_recovers_first(self) -> None:
        harness = self.bound()
        harness.bridge.set_prompt_anchor(3)
        harness.bridge.require_resynchronization("a command wrote")
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert harness.bridge.needs_resynchronization is False
        assert "\x1b[3;1H" in harness.stream_recorder.getvalue()

    def test_a_render_with_no_known_origin_asks_and_waits(self) -> None:
        """Recovery cannot finish without an origin, so this frame is not drawn."""
        harness = self.bound()
        harness.bridge.forget_prompt_anchor()
        harness.bridge.require_resynchronization("a command wrote")
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert "\x1b[6n" in harness.stream_recorder.getvalue()
        assert harness.bridge.needs_resynchronization is True

    def test_an_erase_is_emitted_inside_a_transaction(self) -> None:
        harness = self.bound()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
            harness.stream_recorder.transactions.clear()
            harness.renderer.erase()
        assert harness.stream_recorder.transactions
        assert all(state is not None for state in harness.stream_recorder.transactions)

    def test_an_erase_leaves_recovery_owed(self) -> None:
        """It moved the cursor and cleared the screen below it; nothing may diff against that."""
        harness = self.bound()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
            harness.renderer.erase()
        assert harness.bridge.needs_resynchronization is True

    def test_binding_can_be_undone(self) -> None:
        harness = Harness()
        original_render = harness.renderer.render
        original_erase = harness.renderer.erase
        harness.bridge.bind(harness.app)
        assert harness.renderer.render is not original_render
        harness.bridge.unbind()
        assert harness.renderer.render == original_render
        assert harness.renderer.erase == original_erase

    def test_unbinding_twice_is_harmless(self) -> None:
        harness = Harness()
        harness.bridge.bind(harness.app)
        harness.bridge.unbind()
        harness.bridge.unbind()

    def test_a_stale_frame_emits_nothing_and_asks_for_another(self) -> None:
        """A command write during preparation retires the frame; the redraw is rescheduled."""
        redraws: list[int] = []
        harness = self.bound(content=lambda: harness.bridge.note_managed_write() or "hello")
        harness.bridge.set_redraw_scheduler(lambda: redraws.append(1))
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert harness.stream_recorder.getvalue() == ""
        assert redraws

    def test_binding_twice_keeps_the_first_interception(self) -> None:
        """A second bind would save the wrapper as the original and never unwind."""
        harness = self.bound()
        wrapper = harness.renderer.render
        harness.bridge.bind(harness.app)
        assert harness.renderer.render == wrapper
        harness.bridge.unbind()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert harness.bridge.in_flight is None

    def test_compatibility_rendering_follows_the_release(self) -> None:
        """The fallback is upstream's own renderer -- reached by unbinding, not by calling it."""
        harness = self.bound()
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert harness.stream_recorder.getvalue() == ""

        # What the owner does on release: give the rows back, then unbind.
        harness.display.release()
        harness.bridge.unbind()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert "hello" in harness.stream_recorder.getvalue()
        assert all(state is None for state in harness.stream_recorder.transactions)

    def test_a_frame_that_cannot_be_prepared_asks_for_another(self) -> None:
        redraws: list[int] = []
        harness = self.bound()
        harness.bridge.set_redraw_scheduler(lambda: redraws.append(1))
        with set_app(harness.app):
            prepared = harness.bridge.prepare(harness.app)
            assert prepared is not None
            # A frame is already in flight, so the intercepted render cannot prepare one.
            harness.renderer.render(harness.app, harness.app.layout)
        assert redraws

    def test_a_frame_that_cannot_commit_asks_for_another(self) -> None:
        """Retired between preparing and committing: nothing is emitted, a redraw is asked for."""
        redraws: list[int] = []
        handover = RetiringLock()
        harness = Harness(lock=TerminalLock(lock=handover))
        harness.stream_recorder = RecordingTtyStream()
        harness.backend.stdout = harness.stream_recorder
        harness.bridge.bind(harness.app)
        harness.bridge.set_redraw_scheduler(lambda: redraws.append(1))

        # Preflight and publish take the terminal first; the third acquisition is the commit.
        handover.schedule(None, None, harness.bridge.note_owner_change)
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)

        assert harness.stream_recorder.getvalue() == ""
        assert redraws

    def test_a_clear_is_emitted_inside_a_transaction_and_invalidates(self) -> None:
        harness = self.bound()
        # Upstream's clear() ends by scheduling a cursor-position request on the event loop,
        # which only exists while the application is running. The wrapper is what is under
        # test here, not that scheduling.
        harness.renderer.request_absolute_cursor_position = lambda: None  # type: ignore[method-assign]
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
            harness.stream_recorder.transactions.clear()
            harness.renderer.clear()
        assert harness.stream_recorder.transactions
        assert all(state is not None for state in harness.stream_recorder.transactions)
        assert harness.bridge.needs_resynchronization is True


class AlwaysFailingTtyStream(TtyStringIO):
    """A terminal that has gone away, having possibly emitted something first."""

    def write(self, text: str) -> int:
        super().write(text[:4])
        raise OSError("terminal went away")


class TestReviewRegressionsRoundThree:
    def bound(self, content: Any = "hello") -> Harness:
        """Build a harness whose renderer is intercepted by the bridge."""
        harness = Harness(content=content)
        harness.stream_recorder = RecordingTtyStream()
        harness.backend.stdout = harness.stream_recorder
        harness.bridge.bind(harness.app)
        return harness

    def test_abandoned_emission_renders_nothing_until_the_owner_releases(self) -> None:
        """Review finding: compatibility rendering starts after the release, not before it."""
        harness = self.bound()
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        assert harness.stream_recorder.getvalue() == ""
        assert harness.display.is_reserved is True

    def test_abandoning_emission_tells_the_owner_to_release(self) -> None:
        released: list[int] = []
        harness = self.bound()
        harness.bridge.set_emission_stopped_handler(lambda: released.append(1))
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        assert released == [1]

    def test_a_failed_erase_still_invalidates(self) -> None:
        """Review finding: it emitted something before it raised, and moved the cursor."""
        harness = self.bound()
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        harness.backend.stdout = AlwaysFailingTtyStream()

        with pytest.raises(OSError, match="terminal went away"), set_app(harness.app):
            harness.renderer.erase()
        assert harness.bridge.needs_resynchronization is True

    def test_a_failed_clear_still_invalidates(self) -> None:
        harness = self.bound()
        harness.renderer.request_absolute_cursor_position = lambda: None  # type: ignore[method-assign]
        with set_app(harness.app):
            harness.renderer.render(harness.app, harness.app.layout)
        harness.backend.stdout = AlwaysFailingTtyStream()

        with pytest.raises(OSError, match="terminal went away"), set_app(harness.app):
            harness.renderer.clear()
        assert harness.bridge.needs_resynchronization is True

    def test_clearing_forgets_where_the_prompt_was(self) -> None:
        """Review finding: the clear moved the cursor, so the remembered row is not it."""
        harness = self.bound()
        harness.renderer.request_absolute_cursor_position = lambda: None  # type: ignore[method-assign]
        harness.bridge.set_prompt_anchor(7)
        with set_app(harness.app):
            harness.renderer.clear()
        assert harness.bridge.prompt_anchor is None

        harness.clear()
        harness.stream_recorder.truncate(0)
        harness.stream_recorder.seek(0)
        harness.resynchronize()
        assert "\x1b[7;1H" not in harness.stream_recorder.getvalue()

    def test_clearing_discards_outstanding_cursor_reports(self) -> None:
        """A reply describing the screen before the clear must not establish an origin."""
        harness = self.bound()
        harness.renderer.request_absolute_cursor_position = lambda: None  # type: ignore[method-assign]
        harness.bridge.request_cursor_position()
        with set_app(harness.app):
            harness.renderer.clear()
        assert harness.bridge.report_cursor_row(4) is False
        assert harness.bridge.prompt_anchor is None

    def test_unbinding_leaves_a_newer_method_alone(self) -> None:
        """Review finding: restoring unconditionally discards whatever replaced ours."""
        harness = self.bound()
        replacement = lambda *args, **kwargs: None  # noqa: E731
        harness.renderer.render = replacement  # type: ignore[method-assign]
        harness.bridge.unbind()
        assert harness.renderer.render is replacement

    def test_unbinding_restores_the_methods_that_are_still_ours(self) -> None:
        harness = Harness()
        original_erase = harness.renderer.erase
        harness.bridge.bind(harness.app)
        replacement = lambda *args, **kwargs: None  # noqa: E731
        harness.renderer.render = replacement  # type: ignore[method-assign]
        harness.bridge.unbind()
        assert harness.renderer.render is replacement
        assert harness.renderer.erase == original_erase

    def test_abandoning_emission_twice_notifies_once(self) -> None:
        """The owner releases once; telling it again would release a reservation it re-took."""
        released: list[int] = []
        harness = self.bound()
        harness.bridge.set_emission_stopped_handler(lambda: released.append(1))
        harness.bridge.stop_reserved_emission(OSError("terminal went away"))
        harness.bridge.stop_reserved_emission(OSError("and again"))
        assert released == [1]
        assert str(harness.bridge.take_pending_error()) == "terminal went away"

    def test_a_failed_cleanup_tells_the_owner_to_release(self) -> None:
        """Review finding: the one path that really abandons emission skipped the transition."""
        released: list[int] = []
        harness = self.bound()
        harness.bridge.set_emission_stopped_handler(lambda: released.append(1))

        prepared = harness.bridge.prepare(harness.app)
        assert prepared is not None
        harness.backend.stdout = AlwaysFailingTtyStream()
        assert harness.bridge.commit(prepared) is False

        assert harness.bridge.reserved_emission_stopped is True
        assert released == [1]

    def test_a_reply_in_transit_when_the_screen_cleared_is_not_reused(self) -> None:
        """Review finding: emptying the queue lets the next reply answer the wrong request."""
        harness = self.bound()
        harness.renderer.request_absolute_cursor_position = lambda: None  # type: ignore[method-assign]
        harness.bridge.set_prompt_anchor(7)

        harness.bridge.request_cursor_position()  # request A, about the pre-clear screen
        with set_app(harness.app):
            harness.renderer.clear()
        harness.bridge.request_cursor_position()  # request B, about the cleared screen

        # Reply A arrives late. It describes the screen before the clear.
        assert harness.bridge.report_cursor_row(9) is False
        assert harness.bridge.prompt_anchor is None

        # Reply B is the one that establishes the origin.
        assert harness.bridge.report_cursor_row(4) is True
        assert harness.bridge.prompt_anchor == 4

    def test_the_renderers_own_bookkeeping_is_settled_for_each_stale_reply(self) -> None:
        harness = self.bound()
        harness.renderer.request_absolute_cursor_position = lambda: None  # type: ignore[method-assign]
        harness.bridge.request_cursor_position()
        pending: Future[None] = Future()
        harness.renderer._waiting_for_cpr_futures.append(pending)
        with set_app(harness.app):
            harness.renderer.clear()

        assert harness.bridge.report_cursor_row(9) is False
        assert pending.done() is True
