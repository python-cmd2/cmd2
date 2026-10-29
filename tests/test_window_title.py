"""Window title behavior through real prompt-toolkit output and applications."""

import asyncio
import contextvars
import io
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

import pytest
from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.application.current import set_app
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import DummyInput, create_pipe_input
from prompt_toolkit.output import DummyOutput, Output
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.shortcuts import PromptSession

import cmd2


class TtyStream(io.StringIO):
    def isatty(self):
        return True


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
    return Vt100_Output(stream, lambda: Size(rows=24, columns=80), enable_cpr=False)


def test_title_during_a_command_uses_the_instance_terminal(monkeypatch):
    stream = TtyStream()
    foreign = TtyStream()
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = make_app(monkeypatch, pipe_input, title_output(stream))
        app.do_work = lambda _statement: app.set_window_title("Working…")
        app.onecmd_plus_hooks("work")
        assert stream.getvalue() == "\x1b]2;Working…\x07"
        assert foreign.getvalue() == ""
        assert isinstance(app.main_session.output, Output)
        assert app.main_session.output.stdout is stream
        assert app.main_session.output.get_size() == Size(rows=24, columns=80)


@pytest.mark.parametrize("from_worker", [False, True])
@pytest.mark.parametrize("custom_prompt", [False, True])
def test_title_before_during_and_after_a_real_prompt(monkeypatch, from_worker, custom_prompt):
    stream = TtyStream()
    foreign = TtyStream()
    observed = []
    errors = []
    workers = []
    run = Application.run
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = make_app(monkeypatch, pipe_input, title_output(stream))
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
    assert observed == [True]
    assert "\x1b]2;Before\x07" in stream.getvalue()
    assert "\x1b]2;After\x07" in stream.getvalue()
    assert foreign.getvalue() == ""


@pytest.mark.parametrize("interrupt", [False, True])
def test_worker_titles_during_a_real_select_and_after_cleanup(monkeypatch, interrupt):
    stream = TtyStream()
    foreign = TtyStream()
    observed = []
    errors = []
    run = Application.run

    def run_menu(menu, *args, **kwargs):
        sent = False
        workers = []

        def update_title():
            try:
                app.set_window_title("Menu")
                observed.append("\x1b]2;Menu\x07" in stream.getvalue())
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
        app = make_app(monkeypatch, pipe_input, title_output(stream))
        monkeypatch.setattr(Application, "run", run_menu)
        if interrupt:
            with pytest.raises(KeyboardInterrupt):
                app.select(["sweet", "salty"])
        else:
            assert app.select(["sweet", "salty"]) == "sweet"
        app.set_window_title("Finished")

    assert not errors
    assert observed == [True]
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
        app.set_window_title("After interrupt")

    assert "\x1b]2;Setting up\x07" in stream.getvalue()
    assert "\x1b]2;After interrupt\x07" in stream.getvalue()
    assert foreign.getvalue() == ""


@pytest.mark.parametrize("operation", ["set_title", "flush"])
@pytest.mark.parametrize("from_worker", [False, True])
def test_title_output_errors_reach_the_caller_during_a_prompt(monkeypatch, operation, from_worker):
    stream = TtyStream()
    caught = []
    loop_errors = []
    workers = []

    class FailingOutput(Vt100_Output):
        fail_flush = False

        def set_title(self, title):
            if operation == "set_title" and title == "Fail":
                raise OSError("terminal closed")
            super().set_title(title)
            if title == "Fail":
                self.fail_flush = operation == "flush"

        def flush(self):
            if self.fail_flush:
                self.fail_flush = False
                raise OSError("terminal closed")
            super().flush()

    output = FailingOutput(stream, lambda: Size(rows=24, columns=80), enable_cpr=False)
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

    assert caught == ["terminal closed"]
    assert not loop_errors


def test_title_is_not_queued_when_the_loop_stops_during_scheduling(monkeypatch):
    stream = TtyStream()
    output = title_output(stream)
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    loop.call_soon(ready.set)
    schedule = loop.call_soon_threadsafe
    runner = threading.Thread(target=loop.run_forever, daemon=True)

    def stop_before_queuing(callback):
        schedule(loop.stop)
        runner.join(timeout=5)
        assert not runner.is_alive()
        schedule(callback)

    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=output):
        app = make_app(monkeypatch, pipe_input, output)
        app.main_session.app.loop = loop
        runner.start()
        try:
            assert ready.wait(timeout=5)
            monkeypatch.setattr(loop, "call_soon_threadsafe", stop_before_queuing)
            with set_app(app.main_session.app):
                app.set_window_title("Finished")
            assert stream.getvalue() == "\x1b]2;Finished\x07"
        finally:
            if loop.is_running():
                schedule(loop.stop)
            runner.join(timeout=5)
            assert not runner.is_alive()
            app.main_session.app.loop = None
            loop.close()


def test_render_flush_and_fallback_title_writes_are_serialized(monkeypatch):
    stream = TtyStream()
    entered = threading.Event()
    release = threading.Event()
    attempted = threading.Event()
    finished = threading.Event()
    errors = []

    class BlockingOutput(Vt100_Output):
        render_thread = None
        in_render_flush = False
        overlap = False

        def flush(self):
            if threading.get_ident() == self.render_thread:
                self.in_render_flush = True
                entered.set()
                assert release.wait(timeout=5)
                try:
                    super().flush()
                finally:
                    self.in_render_flush = False
            else:
                self.overlap |= self.in_render_flush
                super().flush()

    output = BlockingOutput(stream, lambda: Size(rows=24, columns=80), enable_cpr=False)
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=output):
        app = make_app(monkeypatch, pipe_input, output)
        app.main_session.output.write_raw("Rendered")

        def render():
            output.render_thread = threading.get_ident()
            app.main_session.output.flush()

        def change_title():
            attempted.set()
            try:
                app.set_window_title("Title")
            except BaseException as error:  # noqa: BLE001
                errors.append(error)
            finally:
                finished.set()

        renderer = threading.Thread(target=render, daemon=True)
        worker = threading.Thread(target=contextvars.copy_context().run, args=(change_title,), daemon=True)
        renderer.start()
        try:
            assert entered.wait(timeout=5)
            worker.start()
            assert attempted.wait(timeout=5)
            finished.wait(timeout=0.1)
        finally:
            release.set()
            renderer.join(timeout=5)
            worker.join(timeout=5)
            assert not renderer.is_alive()
            assert not worker.is_alive()

    assert not errors
    assert not output.overlap
    assert stream.getvalue() == "Rendered\x1b]2;Title\x07"


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
    app.main_session.app.renderer.output = output
    app.main_session = app.main_session
    app.set_window_title("Working…")
    assert titles == ["Working…"]


def test_replacing_main_session_keeps_rendering_and_titles_on_the_new_output():
    stream = TtyStream()
    foreign = TtyStream()
    observed = []
    errors = []
    workers = []
    with create_pipe_input() as pipe_input, create_app_session(input=DummyInput(), output=title_output(foreign)):
        app = cmd2.Cmd(stdin=io.StringIO(), stdout=io.StringIO(), allow_cli_args=False)
        app.main_session = PromptSession(input=pipe_input, output=title_output(stream))
        assert app.main_session.output is app.main_session.app.renderer.output
        app.set_window_title("Before")
        assert "\x1b]2;Before\x07" in stream.getvalue()
        sent = False

        def update_title():
            try:
                app.set_window_title("Replacement prompt")
                observed.append("\x1b]2;Replacement prompt\x07" in stream.getvalue())
            except BaseException as error:  # noqa: BLE001
                errors.append(error)
            finally:
                app.main_session.app.loop.call_soon_threadsafe(lambda: app.main_session.app.exit(result="done"))

        def after_render(_sender):
            nonlocal sent
            if not sent:
                sent = True
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
    assert observed == [True]
    assert "\x1b]2;After\x07" in stream.getvalue()
    assert foreign.getvalue() == ""
