"""Tests for the prototype of a bottom toolbar drawn by a Textual host."""

import asyncio
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading

import pytest
from prompt_toolkit.formatted_text import ANSI, HTML

import cmd2
from cmd2 import textual_toolbar
from cmd2.textual_toolbar import HOST_SOCKET_ENV, ToolbarReporter, render_ansi

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="the host needs Unix sockets and textual-tty")


@pytest.fixture
def host_socket(monkeypatch):
    """A listening socket whose path a hosted application would find in its environment."""
    # Not pytest's temporary directory: a Unix socket's path is limited to about a hundred
    # bytes, and that one is longer when the tests run in parallel.
    directory = tempfile.mkdtemp(prefix="c2", dir="/tmp")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        path = os.path.join(directory, "t.sock")
        listener.bind(path)
        listener.listen(1)
        monkeypatch.setenv(HOST_SOCKET_ENV, path)
        yield listener
    finally:
        listener.close()
        shutil.rmtree(directory, ignore_errors=True)


def received(connection: socket.socket, count: int) -> list[str]:
    """Read that many toolbar documents from a reporter."""
    reader = connection.makefile("r")
    return [json.loads(reader.readline())["toolbar"] for _ in range(count)]


def plain(rendered: str) -> str:
    """What is left of rendered content without its styles."""
    return re.sub(r"\x1b\[[0-9;]*m", "", rendered)


class TestRendering:
    def test_plain_text_is_sent_as_it_is(self) -> None:
        assert plain(render_ansi("hello")) == "hello"
        assert set(re.findall(r"\x1b\[[0-9;]*m", render_ansi("hello"))) == {"\x1b[0m"}

    def test_nothing_renders_as_nothing_to_show(self) -> None:
        assert plain(render_ansi(None)) == ""

    def test_styles_become_graphic_rendition_sequences(self) -> None:
        rendered = render_ansi([("fg:ansigreen bold", "idle"), ("", " rest")])
        assert "\x1b[0;32;1midle\x1b[0m rest" in rendered

    def test_rows_are_separated_by_a_newline_alone(self) -> None:
        assert plain(render_ansi("one\ntwo")) == "one\ntwo"

    @pytest.mark.parametrize(
        ("content", "style"),
        [(HTML("<b>bold</b> text"), "\x1b[0;1mbold"), (ANSI("\x1b[31mred\x1b[0m text"), "\x1b[0;31mred")],
    )
    def test_anything_prompt_toolkit_formats_is_understood(self, content, style) -> None:
        rendered = render_ansi(content)
        assert plain(rendered).endswith(" text")
        assert style in rendered

    def test_nothing_but_styles_is_sent(self) -> None:
        """The renderer turns autowrap on as it starts, which is no business of the host's."""
        assert "\x1b[?7h" not in render_ansi("hello")


@posix_only
class TestReporter:
    def test_content_is_sent_at_once_and_then_when_it_changes(self, host_socket) -> None:
        content = ["first"]
        with ToolbarReporter(lambda: content[0], interval=0.01) as reporter:
            connection, _ = host_socket.accept()
            with connection:
                assert received(connection, 1) == [render_ansi("first")]
                content[0] = "second"
                reporter.poke()
                assert received(connection, 1) == [render_ansi("second")]

    def test_unchanged_content_is_not_sent_again(self, host_socket) -> None:
        calls = threading.Event()
        count = [0]

        def content() -> str:
            count[0] += 1
            if count[0] >= 4:
                calls.set()
            return "same" if count[0] < 6 else "different"

        with ToolbarReporter(content, interval=0.01):
            connection, _ = host_socket.accept()
            with connection:
                assert calls.wait(5)
                assert received(connection, 2) == [render_ansi("same"), render_ansi("different")]

    def test_a_failing_callback_keeps_the_last_content(self, host_socket) -> None:
        state = ["good"]

        def content() -> str:
            if state[0] == "bad":
                raise RuntimeError("toolbar callback failed")
            return state[0]

        with ToolbarReporter(content, interval=0.01) as reporter:
            connection, _ = host_socket.accept()
            with connection:
                assert received(connection, 1) == [render_ansi("good")]
                state[0] = "bad"
                reporter.poke()
                state[0] = "better"
                reporter.poke()
                assert received(connection, 1) == [render_ansi("better")]

    def test_a_host_which_has_gone_ends_the_reporting(self, host_socket) -> None:
        content = ["first"]
        reporter = ToolbarReporter(lambda: content[0], interval=0.01)
        reporter.start()
        connection, _ = host_socket.accept()
        connection.close()
        host_socket.close()
        # Sending to a closed connection fails within a write or two.
        for number in range(200):
            content[0] = f"change {number}"
            reporter.poke()
            if reporter._thread is not None and not reporter._thread.is_alive():
                break
            threading.Event().wait(0.01)
        assert reporter._thread is not None
        assert not reporter._thread.is_alive()
        reporter.stop()

    def test_an_interval_of_zero_uses_the_default(self) -> None:
        assert ToolbarReporter(lambda: "", interval=0)._interval == textual_toolbar.DEFAULT_INTERVAL


class TestHostedApplication:
    def test_prompt_toolkit_draws_no_toolbar_when_hosted(self, monkeypatch) -> None:
        monkeypatch.setenv(HOST_SOCKET_ENV, "/nowhere")
        assert textual_toolbar.is_hosted()
        app = cmd2.Cmd(allow_cli_args=False, enable_bottom_toolbar=True)
        assert app.main_session.bottom_toolbar is None

    def test_prompt_toolkit_draws_the_toolbar_otherwise(self, monkeypatch) -> None:
        monkeypatch.delenv(HOST_SOCKET_ENV, raising=False)
        assert not textual_toolbar.is_hosted()
        app = cmd2.Cmd(allow_cli_args=False, enable_bottom_toolbar=True)
        assert app.main_session.bottom_toolbar is not None

    def test_without_a_terminal_the_application_runs_as_it_always_did(self, monkeypatch) -> None:
        monkeypatch.delenv(HOST_SOCKET_ENV, raising=False)
        assert not textual_toolbar.can_host()  # pytest has taken stdin and stdout

        class App(cmd2.Cmd):
            def cmdloop(self, intro="") -> int:
                return 7

        assert textual_toolbar.run(lambda: App(allow_cli_args=False)) == 7

    @posix_only
    def test_a_hosted_application_reports_its_toolbar_while_its_loop_runs(self, host_socket) -> None:
        seen: list[str] = []

        class App(cmd2.Cmd):
            def get_bottom_toolbar(self) -> str:
                return "from the application"

            def cmdloop(self, intro="") -> int:
                connection, _ = host_socket.accept()
                with connection:
                    seen.extend(received(connection, 1))
                return 5

        assert textual_toolbar.run(lambda: App(allow_cli_args=False, enable_bottom_toolbar=True)) == 5
        assert seen == [render_ansi("from the application")]
        # Programs the application runs must not think they are hosted too.
        assert HOST_SOCKET_ENV not in os.environ


@posix_only
class TestHost:
    def test_the_host_shows_the_program_s_toolbar_and_returns_its_exit_code(self, host_socket) -> None:
        pytest.importorskip("textual_tty")
        from textual.widgets import Static

        # A program which reports a toolbar as a hosted cmd2 application does, waits to be told to go, and exits with 3.
        program = (
            "import json, os, socket, sys\n"
            "s = socket.socket(socket.AF_UNIX)\n"
            f"s.connect({host_socket.getsockname()!r})\n"
            "s.sendall(json.dumps({'toolbar': '\\x1b[0;1mSTATUS\\x1b[0m line'}).encode() + b'\\n')\n"
            "print('program output', flush=True)\n"
            "sys.stdin.readline()\n"
            "sys.exit(3)\n"
        )
        app = textual_toolbar.build_host_app([sys.executable, "-c", program], host_socket)

        async def drive() -> str:
            async with app.run_test() as pilot:
                toolbar = app.query_one("#toolbar", Static)
                for _ in range(200):
                    await pilot.pause(0.02)
                    if "STATUS" in str(toolbar.render()):
                        break
                shown = str(toolbar.render())
                await pilot.press("enter")
                for _ in range(200):
                    await pilot.pause(0.02)
                    if not app.is_running:
                        break
                return shown

        assert asyncio.run(drive()) == "STATUS line"
        assert app.program_exit_code == 3

    def test_a_toolbar_of_two_rows_takes_two_rows_from_the_program(self, host_socket) -> None:
        """The toolbar is as tall as its content, and the terminal the program sees shrinks to make room."""
        pytest.importorskip("textual_tty")
        from textual.widgets import Static

        program = (
            "import json, os, socket, sys, time\n"
            "s = socket.socket(socket.AF_UNIX)\n"
            f"s.connect({host_socket.getsockname()!r})\n"
            "sys.stdin.readline()\n"
            "s.sendall(json.dumps({'toolbar': 'one\\ntwo'}).encode() + b'\\n')\n"
            "sys.stdin.readline()\n"
        )
        app = textual_toolbar.build_host_app([sys.executable, "-c", program], host_socket)

        async def drive() -> tuple[int, int, int, int]:
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.2)
                toolbar = app.query_one("#toolbar", Static)
                before = (toolbar.size.height, app.query_one("#program").size.height)
                await pilot.press("enter")
                for _ in range(200):
                    await pilot.pause(0.02)
                    if toolbar.size.height == 2:
                        break
                after = (toolbar.size.height, app.query_one("#program").size.height)
                await pilot.press("enter")
                for _ in range(200):
                    await pilot.pause(0.02)
                    if not app.is_running:
                        break
                return (*before, *after)

        assert asyncio.run(drive()) == (1, 23, 2, 22)


@posix_only
class TestScrollback:
    """The rows which scroll off the top of the program's screen are kept, and can be looked back at."""

    @staticmethod
    def host(host_socket, lines: int):
        program = (
            "import sys\n"
            f"for number in range({lines}):\n"
            "    print('row', number)\n"
            "print('printed', flush=True)\n"
            "sys.stdin.readline()\n"
        )
        return textual_toolbar.build_host_app([sys.executable, "-c", program], host_socket)

    @staticmethod
    def shown(terminal) -> list[str]:
        return [terminal.render_line(y).text.rstrip() for y in range(terminal.size.height)]

    async def until(self, pilot, predicate) -> bool:
        for _ in range(300):
            await pilot.pause(0.02)
            if predicate():
                return True
        return False

    def test_rows_which_scroll_off_are_kept_and_shown_when_looking_back(self, host_socket) -> None:
        pytest.importorskip("textual_tty")
        app = self.host(host_socket, 100)

        async def drive() -> None:
            async with app.run_test(size=(80, 24)) as pilot:
                terminal = app.query_one("#program")
                assert await self.until(pilot, lambda: "printed" in self.shown(terminal))
                # 23 rows of screen: the last 21 rows of output, "printed", and the row the cursor is on.
                assert self.shown(terminal)[:2] == ["row 79", "row 80"]
                assert len(terminal.scrollback) == 79
                assert [row for row in self.shown(terminal) if row.startswith("row")][-1] == "row 99"

                await pilot.press("shift+pageup")
                assert terminal.back == 22
                assert self.shown(terminal)[0] == "row 57"
                assert self.shown(terminal)[-1] == "row 79"

                await pilot.press("shift+home")
                assert terminal.back == 79
                assert self.shown(terminal)[:2] == ["row 0", "row 1"]

                await pilot.press("shift+pagedown")
                assert self.shown(terminal)[0] == "row 22"

                await pilot.press("shift+end")
                assert terminal.back == 0
                assert self.shown(terminal)[0] == "row 79"

                terminal.look(3)
                await pilot.pause()
                assert self.shown(terminal)[0] == "row 76"
                # Looking further back than there is stops at the oldest row.
                terminal.look(1000)
                assert terminal.back == 79
                await pilot.press("enter")
                assert await self.until(pilot, lambda: not app.is_running)

        asyncio.run(drive())

    def test_typing_returns_to_the_bottom(self, host_socket) -> None:
        pytest.importorskip("textual_tty")
        app = self.host(host_socket, 100)

        async def drive() -> None:
            async with app.run_test(size=(80, 24)) as pilot:
                terminal = app.query_one("#program")
                assert await self.until(pilot, lambda: "printed" in self.shown(terminal))
                await pilot.press("shift+pageup")
                assert terminal.back
                assert "rows back]" in str(app.query_one("#toolbar").render())
                await pilot.press("x")
                assert terminal.back == 0
                assert "rows back]" not in str(app.query_one("#toolbar").render())
                await pilot.press("enter")
                assert await self.until(pilot, lambda: not app.is_running)

        asyncio.run(drive())

    def test_a_shorter_screen_sends_its_top_rows_to_the_scrollback(self, host_socket) -> None:
        """The emulator would cut the bottom rows off, the cursor's among them."""
        pytest.importorskip("textual_tty")
        app = self.host(host_socket, 15)

        async def drive() -> None:
            async with app.run_test(size=(80, 24)) as pilot:
                terminal = app.query_one("#program")
                assert await self.until(pilot, lambda: "printed" in self.shown(terminal))
                assert not terminal.scrollback
                await pilot.resize_terminal(80, 12)
                assert await self.until(pilot, lambda: terminal.size.height == 11)
                # 17 rows were in use: 15 of output, "printed" and the cursor's. Eleven fit.
                assert len(terminal.scrollback) == 6
                assert self.shown(terminal)[0] == "row 6"
                assert "printed" in self.shown(terminal)
                await pilot.press("shift+home")
                assert self.shown(terminal)[0] == "row 0"
                await pilot.press("enter")
                assert await self.until(pilot, lambda: not app.is_running)

        asyncio.run(drive())

    def test_no_more_rows_are_kept_than_the_limit(self, host_socket, monkeypatch) -> None:
        pytest.importorskip("textual_tty")
        monkeypatch.setattr(textual_toolbar, "SCROLLBACK_ROWS", 30)
        app = self.host(host_socket, 100)

        async def drive() -> None:
            async with app.run_test(size=(80, 24)) as pilot:
                terminal = app.query_one("#program")
                assert await self.until(pilot, lambda: "printed" in self.shown(terminal))
                assert len(terminal.scrollback) == 30
                await pilot.press("shift+home")
                assert self.shown(terminal)[0] == "row 49"
                await pilot.press("enter")
                assert await self.until(pilot, lambda: not app.is_running)

        asyncio.run(drive())
