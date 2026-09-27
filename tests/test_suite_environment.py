"""Guards that the suite renders output independently of the developer's environment.

Rich and cmd2 both consult environment variables when deciding whether to emit styling.
Inheriting them makes large numbers of unrelated tests fail depending on who runs them,
which is expensive to diagnose because the failures look like product regressions.
"""

import os
import sys

import pytest

import cmd2

#: Variables that change how output is rendered. Rich reads all of these; cmd2 reads
#: NO_COLOR directly. Tests that exercise them set them explicitly instead.
COLOR_ENVIRONMENT = ("NO_COLOR", "FORCE_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE")


@pytest.mark.parametrize("name", COLOR_ENVIRONMENT)
def test_color_environment_does_not_leak_into_tests(name: str) -> None:
    """A developer exporting any of these must not change the suite's results."""
    assert name not in os.environ, (
        f"{name} leaked into the test environment; output-rendering assertions would depend on who is running the suite"
    )


def test_terminal_dimensions_do_not_leak_into_tests() -> None:
    """Both Rich and argparse must see the geometry used by wrapping assertions."""
    import shutil

    from rich.console import Console

    assert "COLUMNS" not in os.environ
    assert "LINES" not in os.environ
    assert shutil.get_terminal_size() == (80, 24)
    assert Console(force_terminal=False, legacy_windows=False).size == (80, 24)


class EncodingProbe(cmd2.Cmd):
    """Reports the encoding of whatever stream output is currently going to."""

    def do_show_encoding(self, _: str) -> None:
        """Print the current output stream's encoding."""
        self.poutput(f"ENCODING={getattr(self.stdout, 'encoding', None)}")

    def do_say(self, text: str) -> None:
        """Print the argument unchanged."""
        self.poutput(text)


def test_redirection_to_a_file_uses_utf8(tmp_path) -> None:
    """cmd2 renders non-ASCII, so a redirect target must not use the locale encoding.

    Opened with the locale encoding, redirecting styled output raises UnicodeEncodeError
    on any non-UTF-8 system -- which includes a default Windows console -- leaving the
    user an empty file and an error.
    """
    app = EncodingProbe(allow_cli_args=False)
    target = tmp_path / "out.txt"
    app.onecmd_plus_hooks(f'show_encoding > "{target}"')
    assert "ENCODING=utf-8" in target.read_text(encoding="utf-8")


#: A pass-through filter, run with this interpreter so the test does not depend on Unix
#: utilities being installed. `cmd.exe` has no `cat`, and this fix exists for Windows.
PASS_THROUGH = "import sys; sys.stdin.reconfigure(encoding='utf-8'); sys.stdout.write(sys.stdin.read())"


def test_piping_uses_pipe_encoding(tmp_path, running_pipe_process) -> None:
    """The pipe the subprocess reads from uses the encoding its consumer expects, not the locale's.

    That is UTF-8, except on Windows, where console programs such as more decode with the
    console's code page.
    """
    app = EncodingProbe(allow_cli_args=False)
    target = tmp_path / "piped.txt"
    app.onecmd_plus_hooks(f'show_encoding | "{sys.executable}" -c "{PASS_THROUGH}" > "{target}"')
    assert f"ENCODING={cmd2.utils._pipe_encoding()}" in target.read_text(encoding="utf-8")


#: A pass-through filter that copies bytes, so the test sees exactly what cmd2 wrote to the pipe.
BYTES_PASS_THROUGH = "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"


def test_piping_replaces_what_the_pipe_encoding_lacks(tmp_path, monkeypatch, running_pipe_process) -> None:
    """A console code page cannot represent all output, which must not fail the command."""
    monkeypatch.setattr(cmd2.utils, "_pipe_encoding", lambda: "cp437")
    app = EncodingProbe(allow_cli_args=False)
    target = tmp_path / "piped.bin"
    app.onecmd_plus_hooks(f'say ─\U0001f607 | "{sys.executable}" -c "{BYTES_PASS_THROUGH}" > "{target}"')
    # Box drawing exists in cp437, the emoji does not
    assert target.read_bytes().startswith(b"\xc4?")
