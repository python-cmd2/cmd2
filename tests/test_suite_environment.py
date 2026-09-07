"""Guards that the suite renders output independently of the developer's environment.

Rich and cmd2 both consult environment variables when deciding whether to emit styling.
Inheriting them makes large numbers of unrelated tests fail depending on who runs them,
which is expensive to diagnose because the failures look like product regressions.
"""

import os

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


class EncodingProbe(cmd2.Cmd):
    """Reports the encoding of whatever stream output is currently going to."""

    def do_show_encoding(self, _: str) -> None:
        """Print the current output stream's encoding."""
        self.poutput(f"ENCODING={getattr(self.stdout, 'encoding', None)}")


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


def test_piping_uses_utf8(tmp_path) -> None:
    """The same applies to the pipe the subprocess reads from."""
    app = EncodingProbe(allow_cli_args=False)
    target = tmp_path / "piped.txt"
    app.onecmd_plus_hooks(f'show_encoding | cat > "{target}"')
    assert "ENCODING=utf-8" in target.read_text(encoding="utf-8")
