"""Tests which press the completion key at a real prompt and check what ends up on the command line.

The prompt reads its keys from a pipe, so the key bindings, cmd2's completion logic, and
prompt-toolkit's own handling of the results are all exercised together.
"""

import asyncio
import shlex
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.shortcuts import CompleteStyle

import cmd2

pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Don't have a real Windows console with how we are currently running tests in GitHub Actions",
)

TAB = "\t"
ENTER = "\r"
LEFT = "\x1b[D"
CTRL_P = "\x10"
CTRL_R = "\x12"
CTRL_T = "\x14"

# What the prompt has to look like before the next keys are sent
Ready = Callable[[Buffer], bool]


def shows(text: str) -> Ready:
    """Wait for the command line to be exactly this text."""
    return lambda buffer: buffer.text == text


def menu(text: str, count: int) -> Ready:
    """Wait for the command line to be this text with a menu of this many matches and none selected."""

    def ready(buffer: Buffer) -> bool:
        state = buffer.complete_state
        return buffer.text == text and state is not None and len(state.completions) == count and state.complete_index is None

    return ready


def no_menu(buffer: Buffer) -> bool:
    """Wait for the completion menu to close."""
    return buffer.complete_state is None


def press_keys(
    app: cmd2.Cmd,
    steps: list[tuple[str, Ready | None]],
    *,
    complete_in_thread: bool = True,
    editing_mode: EditingMode = EditingMode.EMACS,
    complete_style: CompleteStyle = CompleteStyle.MULTI_COLUMN,
    read: Callable[[], str] | None = None,
) -> str:
    """Send keys to a prompt and return the line it read.

    :param app: the application whose prompt is being typed into
    :param steps: the keys to send, each with what to wait for before sending the next ones.
                  The last keys have to submit the line.
    :param complete_in_thread: whether completion runs in a thread, as it does by default
    :param editing_mode: which set of key bindings the prompt uses
    :param complete_style: how the prompt shows completions
    :param read: function which shows the prompt. Defaults to reading a command line.
    """

    async def send_keys() -> None:
        prompt_app = get_app()
        buffer = prompt_app.current_buffer
        for keys, ready in steps:
            pipe_input.send_text(keys)
            if ready is None:
                continue
            for _ in range(500):
                await asyncio.sleep(0.01)
                try:
                    if ready(buffer):
                        break
                except AssertionError as ex:
                    # End the prompt with the failure, since nothing else would end it
                    prompt_app.exit(exception=ex)
                    return
            else:
                state = buffer.complete_state
                matches = None if state is None else [completion.text for completion in state.completions]
                msg = f"after sending {keys!r} the command line was {buffer.text!r} and the menu had {matches!r}"
                prompt_app.exit(exception=AssertionError(msg))
                return

        # The prompt ends this task when the line is submitted. Don't wait forever for that.
        await asyncio.sleep(5)
        prompt_app.exit(exception=AssertionError(f"the line was never submitted. It was {buffer.text!r}"))

    read_raw_input = app._read_raw_input

    def read_and_send_keys(prompt: Any, session: PromptSession[str], **_kwargs: Any) -> str:
        return read_raw_input(prompt, session, pre_run=lambda: get_app().create_background_task(send_keys()))

    with create_pipe_input() as pipe_input, pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(app, "_read_raw_input", read_and_send_keys)
        app.main_session = PromptSession(
            input=pipe_input,
            output=DummyOutput(),
            completer=app.main_session.completer,
            complete_in_thread=complete_in_thread,
            complete_while_typing=False,
            editing_mode=editing_mode,
            complete_style=complete_style,
            key_bindings=app.main_session.key_bindings,
        )
        if read is None:
            return app._read_command_line(app.prompt)
        return read()


def make_files(directory: Path) -> None:
    """Create the files and directories which the tests complete."""
    for name in ("my file.txt", "sp ace.txt", "spare.txt", "long name a.txt", "long name b.txt"):
        (directory / name).touch()
    for name in ("dd one", "dd two"):
        (directory / name).mkdir()
    (directory / "dd one" / "inner.txt").touch()


class DelimiterApp(cmd2.Cmd):
    """Has a command whose argument is completed one segment at a time, like a path."""

    def do_pick(self, _: cmd2.Statement) -> None:
        """Pick something."""

    def complete_pick(self, text: str, line: str, begidx: int, endidx: int) -> cmd2.Completions:
        return self.delimiter_complete(text, line, begidx, endidx, ["some dir/next", "some file"], "/")


@pytest.fixture
def app(tmp_path, monkeypatch) -> cmd2.Cmd:
    make_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    return cmd2.Cmd()


@pytest.mark.parametrize("complete_in_thread", [True, False])
def test_one_tab_completes_a_match_which_needs_a_quote(app, complete_in_thread) -> None:
    line = press_keys(
        app,
        [
            ("edit my" + TAB, shows('edit "my file.txt" ')),
            (ENTER, None),
        ],
        complete_in_thread=complete_in_thread,
    )
    assert line == 'edit "my file.txt" '


def test_one_tab_adds_the_quote_and_the_shared_prefix_and_opens_the_menu(app) -> None:
    line = press_keys(
        app,
        [
            ("edit lo" + TAB, menu('edit "long name ', 2)),
            (ENTER, None),
        ],
    )
    assert line == 'edit "long name '


def test_one_tab_completes_a_shell_argument_which_needs_a_quote(app) -> None:
    line = press_keys(
        app,
        [
            ("!ls my" + TAB, shows('!ls "my file.txt" ')),
            (ENTER, None),
        ],
    )
    assert line == '!ls "my file.txt" '


@pytest.mark.parametrize(
    ("typed", "completed", "search_text"),
    [
        ("edit spar", "edit spare.txt ", "spar"),
        # The matches found before the quote was inserted are reused afterwards
        ("edit my", 'edit "my file.txt" ', "my"),
    ],
    ids=["no-quote-needed", "quote-needed"],
)
def test_completion_runs_once_for_one_tab(app, monkeypatch, typed, completed, search_text) -> None:
    texts = []
    complete = app.complete

    def counting_complete(text: str, *args: Any, **kwargs: Any) -> cmd2.Completions:
        texts.append(text)
        return complete(text, *args, **kwargs)

    monkeypatch.setattr(app, "complete", counting_complete)

    line = press_keys(
        app,
        [
            (typed + TAB, shows(completed)),
            (ENTER, None),
        ],
    )
    assert line == completed
    assert texts == [search_text]


def test_match_chosen_from_the_menu_closes_its_quote(app) -> None:
    line = press_keys(
        app,
        [
            ('edit "sp' + TAB, menu('edit "sp', 2)),
            # The trailing space keeps another Tab from completing right against the closing quote
            (TAB, shows('edit "sp ace.txt" ')),
            # The first Enter accepts the selection and the second one submits the line
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'edit "sp ace.txt" '
    assert shlex.split(line) == ["edit", "sp ace.txt"]


def test_each_match_in_the_menu_closes_its_quote(app) -> None:
    line = press_keys(
        app,
        [
            ("edit sp" + TAB, menu('edit "sp', 2)),
            (TAB, shows('edit "sp ace.txt" ')),
            (TAB, shows('edit "spare.txt" ')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'edit "spare.txt" '


def test_match_chosen_from_the_menu_keeps_a_closing_quote_which_follows_the_cursor(app) -> None:
    line = press_keys(
        app,
        [
            ('edit "sp"' + LEFT + TAB, menu('edit "sp"', 2)),
            (TAB, shows('edit "sp ace.txt"')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'edit "sp ace.txt"'
    assert shlex.split(line) == ["edit", "sp ace.txt"]


def test_match_chosen_inside_a_quoted_word_stays_inside_its_quotes(app) -> None:
    rest_of_word = '.bak"'
    line = press_keys(
        app,
        [
            ('edit "sp' + rest_of_word + LEFT * len(rest_of_word) + TAB, menu('edit "sp.bak"', 2)),
            (TAB, shows('edit "sp ace.txt.bak"')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'edit "sp ace.txt.bak"'
    assert shlex.split(line) == ["edit", "sp ace.txt.bak"]


def test_match_chosen_in_front_of_another_quoted_word_closes_its_quote(app) -> None:
    rest_of_line = ' "spare.txt"'
    line = press_keys(
        app,
        [
            ('edit "sp' + rest_of_line + LEFT * len(rest_of_line) + TAB, menu('edit "sp "spare.txt"', 2)),
            (TAB, shows('edit "sp ace.txt" "spare.txt"')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert shlex.split(line) == ["edit", "sp ace.txt", "spare.txt"]


def test_match_in_front_of_an_argument_with_a_literal_quote_closes_its_quote(app) -> None:
    rest_of_line = " 'a\"b'"
    line = press_keys(
        app,
        [
            ("shell cat my" + rest_of_line + LEFT * len(rest_of_line) + TAB, shows('shell cat "my file.txt"' + rest_of_line)),
            (ENTER, None),
        ],
    )
    assert shlex.split(line) == ["shell", "cat", "my file.txt", 'a"b']


def test_match_chosen_inside_a_quoted_word_with_an_apostrophe_stays_inside_its_quotes(app) -> None:
    rest_of_word = """ 'copy\""""
    line = press_keys(
        app,
        [
            ('edit "sp' + rest_of_word + LEFT * len(rest_of_word) + TAB, menu('edit "sp' + rest_of_word, 2)),
            (TAB, shows('edit "sp ace.txt' + rest_of_word)),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert shlex.split(line) == ["edit", "sp ace.txt 'copy"]


def test_match_reuses_a_closing_quote_whose_opening_quote_is_missing(app) -> None:
    line = press_keys(
        app,
        [
            # The opening quote is inserted in front of sp, and the quote after the cursor then closes it
            ('edit sp"' + LEFT + TAB, menu('edit "sp"', 2)),
            (TAB, shows('edit "sp ace.txt"')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert shlex.split(line) == ["edit", "sp ace.txt"]


def test_match_in_front_of_a_word_with_an_inch_mark_closes_its_quote(app) -> None:
    rest_of_line = ' 5" nail'
    line = press_keys(
        app,
        [
            ("edit my" + rest_of_line + LEFT * len(rest_of_line) + TAB, shows('edit "my file.txt"' + rest_of_line)),
            (ENTER, None),
        ],
    )
    assert line == 'edit "my file.txt" 5" nail'


def test_match_in_front_of_a_word_with_an_apostrophe_closes_its_quote(app) -> None:
    rest_of_line = " don't"
    line = press_keys(
        app,
        [
            ("edit 'my" + rest_of_line + LEFT * len(rest_of_line) + TAB, shows("edit 'my file.txt'" + rest_of_line)),
            (ENTER, None),
        ],
    )
    assert line == "edit 'my file.txt' don't"


def test_match_chosen_inside_a_quoted_word_in_front_of_a_redirection_stays_inside_its_quotes(app) -> None:
    rest_of_line = '.bak">out'
    line = press_keys(
        app,
        [
            ('shell cat "sp' + rest_of_line + LEFT * len(rest_of_line) + TAB, menu('shell cat "sp' + rest_of_line, 2)),
            (TAB, shows('shell cat "sp ace.txt' + rest_of_line)),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'shell cat "sp ace.txt.bak">out'


def test_match_chosen_inside_a_quoted_part_of_a_word_stays_inside_its_quotes(app) -> None:
    rest_of_line = ' backup".txt'
    line = press_keys(
        app,
        [
            ('shell cat "sp' + rest_of_line + LEFT * len(rest_of_line) + TAB, menu('shell cat "sp' + rest_of_line, 2)),
            (TAB, shows('shell cat "sp ace.txt' + rest_of_line)),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert shlex.split(line) == ["shell", "cat", "sp ace.txt backup.txt"]


def test_only_match_keeps_a_closing_quote_which_follows_the_cursor(app) -> None:
    line = press_keys(
        app,
        [
            ('edit "my"' + LEFT + TAB, shows('edit "my file.txt"')),
            (ENTER, None),
        ],
    )
    assert line == 'edit "my file.txt"'


def test_directory_chosen_from_the_menu_stays_open(app) -> None:
    line = press_keys(
        app,
        [
            ("edit dd" + TAB, menu('edit "dd ', 2)),
            (TAB, shows('edit "dd one/')),
            (ENTER, no_menu),
            # The quote was left open, so completion carries on inside the directory
            (TAB, shows('edit "dd one/inner.txt" ')),
            (ENTER, None),
        ],
    )
    assert line == 'edit "dd one/inner.txt" '


def test_directory_chosen_after_a_shortcut_stays_open(app) -> None:
    line = press_keys(
        app,
        [
            # @ is the shortcut for run_script. The quote goes after it.
            ("@dd" + TAB, menu('@"dd ', 2)),
            (TAB, shows('@"dd one/')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == '@"dd one/'


def test_directory_chosen_in_front_of_a_separator_stays_open(app) -> None:
    """A directory is offered without a trailing separator when one already follows the cursor."""
    rest_of_path = "/inner.txt"
    line = press_keys(
        app,
        [
            ('edit "dd ' + rest_of_path + LEFT * len(rest_of_path) + TAB, menu('edit "dd /inner.txt', 2)),
            (TAB, shows('edit "dd one/inner.txt')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'edit "dd one/inner.txt'


def test_custom_completion_key_opens_the_menu_for_a_match_which_needs_a_quote(tmp_path, monkeypatch) -> None:
    make_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    app = cmd2.Cmd(completekey="c-t")

    line = press_keys(
        app,
        [
            # A custom key only opens the menu on its first press, whether or not the match needs a quote
            ("edit my" + CTRL_T, menu("edit my", 1)),
            (CTRL_T, shows('edit "my file.txt" ')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'edit "my file.txt" '


@pytest.mark.parametrize(
    ("typed", "ready"),
    [
        ("edit my", shows('edit "my file.txt" ')),
        ("edit lo", menu('edit "long name ', 2)),
    ],
    ids=["one-match", "shared-prefix"],
)
def test_tab_still_completes_when_another_key_is_the_completion_key(tmp_path, monkeypatch, typed, ready) -> None:
    """Tab goes on doing what it does by default, whatever the completion key is set to."""
    make_files(tmp_path)
    monkeypatch.chdir(tmp_path)
    app = cmd2.Cmd(completekey="c-t")
    lines = []

    def record(buffer: Buffer) -> bool:
        lines.append(buffer.text)
        return True

    press_keys(
        app,
        [
            (typed + TAB, ready),
            ("", record),
            # Clear the line, which closes any menu, and submit it
            ("\x15" + ENTER, None),
        ],
    )
    assert len(lines) == 1


def test_request_which_selects_the_last_match_does_so_when_matches_need_a_quote(app) -> None:
    line = press_keys(
        app,
        [
            # Ctrl-P asks for the last match to be selected in Vi insert mode
            ("edit sp" + CTRL_P, shows('edit "spare.txt" ')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
        editing_mode=EditingMode.VI,
    )
    assert line == 'edit "spare.txt" '


def test_one_tab_adds_the_quote_and_the_shared_prefix_in_read_input(app) -> None:
    line = press_keys(
        app,
        [
            ("ha" + TAB, menu('"has space ', 2)),
            (TAB, shows('"has space one" ')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
        read=lambda: app.read_input("> ", choices=["has space one", "has space two"]),
    )
    assert line == '"has space one" '


def test_tab_in_a_history_search_does_not_complete_the_search_text(app, monkeypatch) -> None:
    texts = []
    monkeypatch.setattr(app, "complete", lambda text, *_args, **_kwargs: texts.append(text) or cmd2.Completions())

    line = press_keys(
        app,
        [
            # Enter ends the search and then submits the line, which is empty since nothing was found
            (CTRL_R + "my" + TAB + ENTER + ENTER, None),
        ],
    )
    assert line == ""
    assert texts == []


def test_finished_match_closes_its_quote_when_another_match_has_more_segments() -> None:
    line = press_keys(
        DelimiterApp(),
        [
            ("pick so" + TAB, menu('pick "some ', 2)),
            # This match has another segment after it, so its quote stays open
            (TAB, shows('pick "some dir/')),
            (TAB, shows('pick "some file" ')),
            (ENTER, no_menu),
            (ENTER, None),
        ],
    )
    assert line == 'pick "some file" '


def test_prompt_ending_during_a_completion_leaves_no_listener_on_the_buffer(app, monkeypatch) -> None:
    complete = app.complete
    completing = threading.Event()

    def slow_complete(*args: Any, **kwargs: Any) -> cmd2.Completions:
        # Find the matches, but don't return them until the user has submitted the line
        completions = complete(*args, **kwargs)
        completing.set()
        prompt_app = get_app()
        deadline = time.monotonic() + 5
        while not prompt_app.is_done and time.monotonic() < deadline:
            time.sleep(0.005)
        return completions

    monkeypatch.setattr(app, "complete", slow_complete)

    def completion_started(_: Buffer) -> bool:
        return completing.is_set()

    line = press_keys(
        app,
        [
            ("edit my" + TAB, completion_started),
            (ENTER, None),
        ],
    )
    assert line == "edit my"

    # Nothing of the abandoned request is attached to the buffer which the next prompt will use
    handlers = app.main_session.default_buffer.on_completions_changed._handlers
    assert [handler.__qualname__ for handler in handlers if "Cmd2Completer" in handler.__qualname__] == []


def no_menu_after_a_moment() -> Ready:
    """Wait a moment for a menu to open if one is going to, and fail if it does."""
    waiting_since: list[float] = []

    def ready(buffer: Buffer) -> bool:
        if not waiting_since:
            waiting_since.append(time.monotonic())
        if time.monotonic() - waiting_since[0] < 0.3:
            return False
        if buffer.complete_state is not None:
            raise AssertionError(f"a completion menu opened. The command line was {buffer.text!r}")
        return True

    return ready


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        # Several matches which need no quote are listed above the prompt
        ("h", "h"),
        # The opening quote and the text the matches share are inserted before the rest is listed
        ("edit lo", 'edit "long name '),
        ("edit sp", 'edit "sp'),
        # A single match is completed
        ("edit my", 'edit "my file.txt" '),
        # The quote goes after a shortcut, here the one for run_script
        ("@my", '@"my file.txt" '),
        ("@dd", '@"dd '),
    ],
)
def test_tab_completes_like_readline_when_the_session_is_set_up_to(app, typed, expected) -> None:
    lines = []

    def record(buffer: Buffer) -> bool:
        lines.append(buffer.text)
        return True

    press_keys(
        app,
        [
            (typed + TAB, no_menu_after_a_moment()),
            ("", record),
            # Clear the line and submit it
            ("\x15" + ENTER, None),
        ],
        complete_style=CompleteStyle.READLINE_LIKE,
    )
    assert lines == [expected]


def test_binding_which_inserts_every_match_gets_each_with_its_own_quotes(app) -> None:
    """Meta-* in Emacs mode asks for the completions itself and inserts all of them after the cursor."""
    lines = []

    def record(buffer: Buffer) -> bool:
        lines.append(buffer.text)
        return True

    press_keys(
        app,
        [
            ("shell cat sp" + "\x1b*", shows('shell cat sp"sp ace.txt"  "spare.txt" ')),
            ("", record),
            # Clear the line and submit it
            ("\x15" + ENTER, None),
        ],
    )
    assert len(lines) == 1
