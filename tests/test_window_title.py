"""Window title behavior through real prompt-toolkit output and applications."""

import asyncio
import contextlib
import contextvars
import io
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import pytest
from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import DummyInput, create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.shortcuts import PromptSession

import cmd2


class TtyStream(io.StringIO):
    def isatty(self):
        return True


class TitleOutput(Vt100_Output):
    """VT100 output which records the event loop, if any, that wrote each title."""

    def __init__(self, stream):
        super().__init__(stream, lambda: Size(rows=24, columns=80), enable_cpr=False)
        self.title_loops = {}

    def set_title(self, title):
        try:
            self.title_loops[title] = asyncio.get_running_loop()
        except RuntimeError:
            self.title_loops[title] = None
        super().set_title(title)


def make_app(monkeypatch, pipe_input, output):
    # Use the real VT100 driver on every platform without requiring a physical console.
    with monkeypatch.context() as terminal:
        terminal.setattr("cmd2.cmd2.create_input", lambda **_kwargs: pipe_input)
        terminal.setattr("cmd2.cmd2.create_output", lambda **_kwargs: output)
        app = cmd2.Cmd(stdin=TtyStream(), stdout=output.stdout, allow_cli_args=False)
    output.flush()
    output.stdout.seek(0)
    output.stdout.truncate()
    return app


def title_output(stream):
    return TitleOutput(stream)


def test_title_during_a_command_uses_the_instance_terminal(monkeypatch):
    stream = TtyStream()
    foreign = TtyStream()
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = make_app(monkeypatch, pipe_input, title_output(stream))
        app.do_work = lambda _statement: app.set_window_title("Working…")
        app.onecmd_plus_hooks("work")
        assert stream.getvalue() == "\x1b]2;Working…\x07"
        assert foreign.getvalue() == ""


def test_title_uses_the_ambient_app_session_output_for_sys_stdout(monkeypatch):
    stream = TtyStream()
    output = title_output(stream)
    monkeypatch.setattr(sys, "stdout", TtyStream())
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=output):
        monkeypatch.setattr("cmd2.cmd2.create_input", lambda **_kwargs: pipe_input)
        app = cmd2.Cmd(stdin=TtyStream(), allow_cli_args=False)
        assert app.main_session.output is output
        app.set_window_title("Ambient")

    assert stream.getvalue().endswith("\x1b]2;Ambient\x07")


@pytest.mark.parametrize("from_worker", [False, True])
@pytest.mark.parametrize("custom_prompt", [False, True])
def test_title_before_during_and_after_a_real_prompt(monkeypatch, from_worker, custom_prompt):
    stream = TtyStream()
    foreign = TtyStream()
    output = title_output(stream)
    observed = []
    errors = []
    workers = []
    prompt_loops = []
    run = Application.run
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = make_app(monkeypatch, pipe_input, output)
        app.set_window_title("Before")
        sent = False

        def update_title(prompt_app):
            try:
                app.set_window_title("During")
                observed.append("\x1b]2;During\x07" in stream.getvalue())
            except BaseException as error:  # noqa: BLE001
                errors.append(error)
            finally:
                prompt_app.loop.call_soon_threadsafe(lambda: prompt_app.exit(result="done"))

        def after_render(prompt_app):
            nonlocal sent
            if sent:
                return
            sent = True
            prompt_loops.append(prompt_app.loop)
            if from_worker:
                worker = threading.Thread(target=contextvars.Context().run, args=(update_title, prompt_app), daemon=True)
                workers.append(worker)
                worker.start()
            else:
                update_title(prompt_app)

        def run_prompt(prompt_app, *args, **kwargs):
            prompt_app.after_render += after_render
            kwargs["set_exception_handler"] = False
            return run(prompt_app, *args, **kwargs)

        monkeypatch.setattr(Application, "run", run_prompt)
        if custom_prompt:
            result = app.read_input("custom> ")
        else:
            result = app._read_raw_input("prompt> ", app.main_session, set_exception_handler=False)
        for worker in workers:
            worker.join(timeout=5)
            assert not worker.is_alive()
        app.set_window_title("After")

    assert result == "done"
    assert not errors
    # A worker's title is written asynchronously on the prompt's event loop, so it may or may not be in the stream when
    # set_window_title() returns. Only a call on the loop thread is guaranteed to have written it by then.
    assert len(observed) == 1
    if not from_worker:
        assert observed == [True]
    assert output.title_loops["During"] is prompt_loops[0]
    assert output.title_loops["Before"] is None
    assert output.title_loops["After"] is None
    assert "\x1b]2;Before\x07" in stream.getvalue()
    assert "\x1b]2;During\x07" in stream.getvalue()
    assert "\x1b]2;After\x07" in stream.getvalue()
    assert foreign.getvalue() == ""


@pytest.mark.parametrize("interrupt", [False, True])
def test_worker_titles_during_a_real_select_and_after_cleanup(monkeypatch, interrupt):
    stream = TtyStream()
    foreign = TtyStream()
    output = title_output(stream)
    errors = []
    menu_loops = []
    run = Application.run

    def run_menu(menu, *args, **kwargs):
        sent = False
        workers = []

        def update_title():
            try:
                app.set_window_title("Menu")
            except BaseException as error:  # noqa: BLE001
                errors.append(error)
            finally:
                if interrupt:
                    menu.loop.call_soon_threadsafe(lambda: menu.exit(exception=KeyboardInterrupt))
                else:
                    menu.loop.call_soon_threadsafe(lambda: menu.exit(result="sweet"))

        def after_render(_sender):
            nonlocal sent
            if not sent:
                sent = True
                menu_loops.append(menu.loop)
                worker = threading.Thread(target=contextvars.Context().run, args=(update_title,), daemon=True)
                workers.append(worker)
                worker.start()

        menu.after_render += after_render
        try:
            return run(menu, *args, set_exception_handler=False, **kwargs)
        finally:
            for worker in workers:
                worker.join(timeout=5)
                assert not worker.is_alive()

    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = make_app(monkeypatch, pipe_input, output)
        monkeypatch.setattr(Application, "run", run_menu)
        if interrupt:
            with pytest.raises(KeyboardInterrupt):
                app.select(["sweet", "salty"])
        else:
            assert app.select(["sweet", "salty"]) == "sweet"
        assert app._select_app_session is None
        app.set_window_title("Finished")

    assert not errors
    assert output.title_loops["Menu"] is menu_loops[0]
    assert output.title_loops["Finished"] is None
    assert "\x1b]2;Menu\x07" in stream.getvalue()
    assert "\x1b]2;Finished\x07" in stream.getvalue()
    assert foreign.getvalue() == ""


def test_instance_titles_do_not_cross_between_concurrent_select_menus(monkeypatch):
    streams = [TtyStream(), TtyStream()]
    rendered = [threading.Event(), threading.Event()]
    menus = []
    run = Application.run

    def run_menu(menu, *args, **kwargs):
        index = next(index for index, stream in enumerate(streams) if menu.output.stdout is stream)
        menus.append(menu)
        menu.after_render += lambda _sender: rendered[index].set()
        return run(menu, *args, set_exception_handler=False, **kwargs)

    monkeypatch.setattr(Application, "run", run_menu)
    with ExitStack() as stack:
        inputs = [stack.enter_context(create_pipe_input()) for _ in streams]
        apps = [
            make_app(monkeypatch, pipe_input, title_output(stream)) for pipe_input, stream in zip(inputs, streams, strict=True)
        ]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(app.select, ["selected"]) for app in apps]
            try:
                assert all(event.wait(timeout=5) for event in rendered)
                apps[0].set_window_title("A")
                apps[1].set_window_title("B")
                inputs[0].send_text("\r")
                assert results[0].result(timeout=5) == "selected"
                apps[0].set_window_title("A finished")
                apps[1].set_window_title("B active")
            finally:
                for menu in menus:
                    loop = menu.loop
                    if loop is not None and loop.is_running():
                        loop.call_soon_threadsafe(lambda menu=menu: menu.exit(result="selected"))
                for result in results:
                    result.result(timeout=5)

    assert "\x1b]2;A\x07" in streams[0].getvalue()
    assert "\x1b]2;A finished\x07" in streams[0].getvalue()
    assert "\x1b]2;B\x07" not in streams[0].getvalue()
    assert "\x1b]2;B\x07" in streams[1].getvalue()
    assert "\x1b]2;B active\x07" in streams[1].getvalue()
    assert "\x1b]2;A\x07" not in streams[1].getvalue()


def test_title_during_interrupted_select_setup_leaves_no_stale_routing(monkeypatch):
    stream = TtyStream()
    foreign = TtyStream()

    def interrupt_before_application(**_kwargs):
        app.set_window_title("Setting up")
        raise KeyboardInterrupt

    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = make_app(monkeypatch, pipe_input, title_output(stream))
        monkeypatch.setattr("cmd2.cmd2.choice", interrupt_before_application)
        with pytest.raises(KeyboardInterrupt):
            app.select(["choice"])
        assert app._select_app_session is None
        app.set_window_title("After interrupt")

    assert "\x1b]2;Setting up\x07" in stream.getvalue()
    assert "\x1b]2;After interrupt\x07" in stream.getvalue()
    assert foreign.getvalue() == ""


class FailingOutput(TitleOutput):
    """Output which fails in either set_title() or flush() when the title is 'Fail'."""

    def __init__(self, stream, operation):
        super().__init__(stream)
        self.operation = operation
        self.fail_flush = False

    def set_title(self, title):
        if self.operation == "set_title" and title == "Fail":
            raise OSError("terminal closed")
        super().set_title(title)
        if title == "Fail":
            self.fail_flush = self.operation == "flush"

    def flush(self):
        if self.fail_flush:
            self.fail_flush = False
            raise OSError("terminal closed")
        super().flush()


@pytest.mark.parametrize("operation", ["set_title", "flush"])
def test_title_output_errors_reach_the_caller_without_a_prompt(monkeypatch, operation):
    output = FailingOutput(TtyStream(), operation)
    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, output)
        with pytest.raises(OSError, match="terminal closed"):
            app.set_window_title("Fail")

        # A failed title isn't retried.
        app._flush_pending_window_title()
        assert app._pending_window_title is None


@pytest.mark.parametrize("operation", ["set_title", "flush"])
@pytest.mark.parametrize("from_worker", [False, True])
def test_title_output_errors_during_a_prompt(monkeypatch, operation, from_worker):
    caught = []
    loop_errors = []
    workers = []
    output = FailingOutput(TtyStream(), operation)
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=output):
        app = make_app(monkeypatch, pipe_input, output)
        sent = False

        def update_title():
            try:
                app.set_window_title("Fail")
            except OSError as error:
                caught.append(str(error))
            finally:
                app.main_session.app.loop.call_soon_threadsafe(lambda: app.main_session.app.exit(result="done"))

        def after_render(_sender):
            nonlocal sent
            if sent:
                return
            sent = True
            app.main_session.app.loop.set_exception_handler(lambda _loop, context: loop_errors.append(context))
            if from_worker:
                worker = threading.Thread(target=contextvars.copy_context().run, args=(update_title,), daemon=True)
                workers.append(worker)
                worker.start()
            else:
                update_title()

        app.main_session.app.after_render += after_render
        assert app._read_raw_input("prompt> ", app.main_session, set_exception_handler=False) == "done"
        for worker in workers:
            worker.join(timeout=5)
            assert not worker.is_alive()

    # The loop's exception handler never hears of the error, so it can't disrupt the prompt.
    assert not loop_errors
    if from_worker:
        # The title was written by an event loop callback, which ignores output errors.
        assert not caught
        assert app._pending_window_title is None
    else:
        assert caught == ["terminal closed"]


@pytest.mark.parametrize("failing", [False, True])
def test_title_is_written_when_the_prompt_finishes_before_running_the_callback(monkeypatch, failing):
    stream = TtyStream()
    output = FailingOutput(stream, "flush") if failing else title_output(stream)
    title = "Fail" if failing else "Finished"
    dropped = []
    workers = []
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=output):
        app = make_app(monkeypatch, pipe_input, output)
        prompt_app = app.main_session.app
        sent = False

        def update_title():
            loop = prompt_app.loop
            schedule = loop.call_soon_threadsafe

            # Simulate the event loop stopping before it runs the title callback.
            def drop_title_callback(callback, *args, **kwargs):
                if getattr(callback, "__func__", None) is cmd2.Cmd._flush_pending_window_title_quietly:
                    dropped.append(callback)
                    return None
                return schedule(callback, *args, **kwargs)

            monkeypatch.setattr(loop, "call_soon_threadsafe", drop_title_callback)
            app.set_window_title(title)
            schedule(lambda: prompt_app.exit(result="done"))

        def after_render(_sender):
            nonlocal sent
            if not sent:
                sent = True
                worker = threading.Thread(target=contextvars.Context().run, args=(update_title,), daemon=True)
                workers.append(worker)
                worker.start()

        prompt_app.after_render += after_render
        assert app._read_raw_input("prompt> ", app.main_session, set_exception_handler=False) == "done"
        for worker in workers:
            worker.join(timeout=5)
            assert not worker.is_alive()

    assert len(dropped) == 1
    assert app._pending_window_title is None
    assert output.title_loops[title] is None
    if not failing:
        # The prompt's cleanup wrote the title after the prompt finished rendering.
        assert stream.getvalue().endswith("\x1b]2;Finished\x07")
    # Otherwise the cleanup's output error didn't replace the prompt's result, which the assertion on "done" checked.


def test_title_error_during_select_cleanup_keeps_the_interrupt(monkeypatch):
    output = FailingOutput(TtyStream(), "flush")

    def interrupt_with_pending_title(**_kwargs):
        # Leave a title for the cleanup, as if the menu's loop stopped before running the title callback.
        app._pending_window_title = "Fail"
        raise KeyboardInterrupt

    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, output)
        monkeypatch.setattr("cmd2.cmd2.choice", interrupt_with_pending_title)
        with pytest.raises(KeyboardInterrupt):
            app.select(["choice"])

    assert app._pending_window_title is None
    assert app._select_app_session is None


def test_prompt_loop_ignores_a_select_session_without_an_app(monkeypatch):
    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, title_output(TtyStream()))
        with create_app_session(input=DummyInput(), output=DummyOutput()) as app_session:
            app._select_app_session = app_session
            assert app_session.app is None
            assert app._get_prompt_loop() is None


def test_title_set_while_writing_a_title_is_written_next(monkeypatch):
    stream = TtyStream()
    errors = []

    class ReentrantOutput(TitleOutput):
        flushing = False
        nested_flush = False

        def set_title(self, title):
            if title == "Outer":
                # Like a signal handler which sets the title while this thread is writing one.
                app.set_window_title("Inner")
            super().set_title(title)

        def flush(self):
            self.nested_flush |= self.flushing
            self.flushing = True
            try:
                if "\x1b]2;Outer\x07" in "".join(self._buffer):
                    # Like a signal handler which runs while this thread is writing to the stream.
                    app.set_window_title("During flush")
                super().flush()
            finally:
                self.flushing = False

    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, ReentrantOutput(stream))

        def set_outer_title():
            try:
                app.set_window_title("Outer")
            except BaseException as error:  # noqa: BLE001
                errors.append(error)

        # Run in a thread so a deadlock fails the test instead of hanging it.
        worker = threading.Thread(target=set_outer_title, daemon=True)
        worker.start()
        worker.join(timeout=5)
        assert not worker.is_alive()

    assert not errors
    # The nested calls didn't write inside the outer write. "During flush" replaced "Inner" before it was written, so
    # only the latest title was written after "Outer".
    assert not app.main_session.output.nested_flush
    assert stream.getvalue() == "\x1b]2;Outer\x07\x1b]2;During flush\x07"
    assert app._pending_window_title is None
    assert not app._writing_window_title


def test_quiet_title_flush_ignores_a_closed_stream(monkeypatch):
    stream = TtyStream()
    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, title_output(stream))
        stream.close()
        app._pending_window_title = "Closed"
        app._flush_pending_window_title_quietly()

    assert app._pending_window_title is None
    assert not app._writing_window_title


def test_prompt_cleanup_writes_the_title_after_patch_stdout_exits(monkeypatch):
    events = []

    class RecordingOutput(TitleOutput):
        def set_title(self, title):
            events.append(f"title {title}")
            super().set_title(title)

    @contextlib.contextmanager
    def recording_patch_stdout():
        events.append("patch_stdout enter")
        try:
            yield
        finally:
            events.append("patch_stdout exit")

    def prompt_with_pending_title(*_args, **_kwargs):
        # Leave a title for the cleanup, as if the prompt's loop stopped before running the title callback.
        app._pending_window_title = "Cleanup"
        return "done"

    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, RecordingOutput(TtyStream()))
        monkeypatch.setattr("cmd2.cmd2.patch_stdout", recording_patch_stdout)
        monkeypatch.setattr(app.main_session, "prompt", prompt_with_pending_title)
        assert app._read_raw_input("prompt> ", app.main_session) == "done"

    assert events == ["patch_stdout enter", "patch_stdout exit", "title Cleanup"]


def test_title_falls_back_to_a_terminal_stdout_when_stdin_is_not_a_terminal(monkeypatch):
    stream = TtyStream()
    output = title_output(stream)
    created = []

    def create_title_output(**kwargs):
        created.append(kwargs["stdout"])
        return output

    monkeypatch.setattr("cmd2.cmd2.create_output", create_title_output)
    app = cmd2.Cmd(stdin=io.StringIO(), stdout=stream, allow_cli_args=False)
    assert isinstance(app.main_session.output, DummyOutput)

    # The fallback output is only created once a title needs it.
    assert not created
    app.set_window_title("Piped input")
    app.set_window_title("Again")
    assert created == [stream]
    assert stream.getvalue() == "\x1b]2;Piped input\x07\x1b]2;Again\x07"

    # Titles still reach the terminal while a command's output is redirected.
    app.stdout = io.StringIO()
    app.set_window_title("Redirected")
    assert stream.getvalue().endswith("\x1b]2;Redirected\x07")
    assert app.stdout.getvalue() == ""

    # A replacement session with a real output takes precedence over the fallback.
    replacement = TtyStream()
    with create_pipe_input() as pipe_input:
        app.main_session = PromptSession(input=pipe_input, output=title_output(replacement))
        app.set_window_title("Replacement")
    assert replacement.getvalue().endswith("\x1b]2;Replacement\x07")
    assert "Replacement" not in stream.getvalue()


def test_title_falls_back_when_a_replacement_session_has_no_terminal_output(monkeypatch):
    stream = TtyStream()
    fallback = TtyStream()
    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, title_output(stream))
    assert app._window_title_fallback_output is None

    app.main_session = PromptSession(input=DummyInput(), output=DummyOutput())
    monkeypatch.setattr("cmd2.cmd2.create_output", lambda **_kwargs: title_output(fallback))
    app.set_window_title("Fallback")
    assert fallback.getvalue() == "\x1b]2;Fallback\x07"
    assert stream.getvalue() == ""


def test_title_fallback_is_skipped_when_the_terminal_output_cannot_be_created(monkeypatch):
    attempts = []

    def no_console(**_kwargs):
        attempts.append(True)
        raise ValueError("no console")

    monkeypatch.setattr("cmd2.cmd2.create_output", no_console)
    app = cmd2.Cmd(stdin=io.StringIO(), stdout=TtyStream(), allow_cli_args=False)
    app.set_window_title("Nowhere")
    app.set_window_title("Still nowhere")
    assert app._window_title_fallback_output is None
    assert app.stdout.getvalue() == ""

    # A failure isn't retried for every title.
    assert len(attempts) == 1


def test_title_is_written_directly_when_the_prompt_loop_is_closed(monkeypatch):
    stream = TtyStream()
    output = title_output(stream)
    loop = asyncio.new_event_loop()
    loop.close()
    with create_pipe_input() as pipe_input:
        app = make_app(monkeypatch, pipe_input, output)
        prompt_app = app.main_session.app
        monkeypatch.setattr(prompt_app, "_is_running", True)
        monkeypatch.setattr(prompt_app, "loop", loop)
        app.set_window_title("Closed loop")

    assert stream.getvalue() == "\x1b]2;Closed loop\x07"
    assert app._pending_window_title is None


def test_title_without_terminal_output_is_a_noop():
    app = cmd2.Cmd(stdin=io.StringIO(), stdout=io.StringIO(), allow_cli_args=False)
    app.set_window_title("No terminal")
    assert app.stdout.getvalue() == ""
    assert isinstance(app.main_session.output, DummyOutput)


@pytest.mark.skipif(sys.platform != "win32", reason="Uses the native Win32 title backend")
def test_title_uses_the_native_win32_output_backend(monkeypatch):
    from prompt_toolkit.output.win32 import Win32Output, windll

    # Exercise native set_title/flush without needing a physical console in CI.
    stream = TtyStream()
    output = Win32Output.__new__(Win32Output)
    output.stdout = stream
    output._buffer = []
    titles = []
    monkeypatch.setattr(windll.kernel32, "SetConsoleTitleW", lambda title: titles.append(title) or 1)
    app = cmd2.Cmd(stdin=io.StringIO(), stdout=io.StringIO(), allow_cli_args=False)
    app.main_session.app.output = output
    app.set_window_title("Working…")
    assert titles == ["Working…"]


def test_replacing_main_session_keeps_titles_on_the_new_output():
    stream = TtyStream()
    foreign = TtyStream()
    output = title_output(stream)
    errors = []
    workers = []
    prompt_loops = []
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = cmd2.Cmd(stdin=io.StringIO(), stdout=io.StringIO(), allow_cli_args=False)
        app.main_session = PromptSession(input=pipe_input, output=output)
        app.set_window_title("Before")
        assert "\x1b]2;Before\x07" in stream.getvalue()
        sent = False

        def update_title():
            try:
                app.set_window_title("Replacement prompt")
            except BaseException as error:  # noqa: BLE001
                errors.append(error)
            finally:
                app.main_session.app.loop.call_soon_threadsafe(lambda: app.main_session.app.exit(result="done"))

        def after_render(_sender):
            nonlocal sent
            if not sent:
                sent = True
                prompt_loops.append(app.main_session.app.loop)
                worker = threading.Thread(target=contextvars.Context().run, args=(update_title,), daemon=True)
                workers.append(worker)
                worker.start()

        app.main_session.app.after_render += after_render
        assert app._read_raw_input("replacement> ", app.main_session, set_exception_handler=False) == "done"
        for worker in workers:
            worker.join(timeout=5)
            assert not worker.is_alive()
        app.set_window_title("After")

    assert not errors
    assert output.title_loops["Replacement prompt"] is prompt_loops[0]
    assert "\x1b]2;Replacement prompt\x07" in stream.getvalue()
    assert "\x1b]2;After\x07" in stream.getvalue()
    assert foreign.getvalue() == ""
