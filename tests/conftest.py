# coding=utf-8
"""
Cmd2 unit/functional testing

Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
Released under MIT license, see LICENSE file
"""
import sys
from typing import Optional
from unittest import mock

from pytest import fixture

import cmd2
from cmd2.utils import StdSim

# Prefer statically linked gnureadline if available (for macOS compatibility due to issues with libedit)
try:
    import gnureadline as readline
except ImportError:
    # Try to import readline, but allow failure for convenience in Windows unit testing
    # Note: If this actually fails, you should install readline on Linux or Mac or pyreadline on Windows
    try:
        # noinspection PyUnresolvedReferences
        import readline
    except ImportError:
        pass

# Help text for base cmd2.Cmd application
BASE_HELP = """Documented commands (type help <topic>):
========================================
alias  help     load   py        quit  shell    
edit   history  macro  pyscript  set   shortcuts
"""

BASE_HELP_VERBOSE = """
Documented commands (type help <topic>):
================================================================================
alias               Manage aliases
edit                Edit a file in a text editor
help                List available commands or provide detailed help for a specific command
history             View, run, edit, save, or clear previously entered commands
load                Run commands in script file that is encoded as either ASCII or UTF-8 text
macro               Manage macros
py                  Invoke Python command or shell
pyscript            Run a Python script file inside the console
quit                Exit this application
set                 Set a settable parameter or show current settings of parameters
shell               Execute a command as if at the OS prompt
shortcuts           List available shortcuts
"""

# Help text for the history command
HELP_HISTORY = """Usage: history [-h] [-r | -e | -s | -o FILE | -t TRANSCRIPT | -c] [arg]

View, run, edit, save, or clear previously entered commands

positional arguments:
  arg                   empty               all history items
                        a                   one history item by number
                        a..b, a:b, a:, ..b  items by indices (inclusive)
                        [string]            items containing string
                        /regex/             items matching regular expression

optional arguments:
  -h, --help            show this help message and exit
  -r, --run             run selected history items
  -e, --edit            edit and then run selected history items
  -s, --script          output commands in script format
  -o, --output-file FILE
                        output commands to a script file
  -t, --transcript TRANSCRIPT
                        output commands and results to a transcript file
  -c, --clear           clear all history
"""

# Output from the shortcuts command with default built-in shortcuts
SHORTCUTS_TXT = """Shortcuts for other commands:
!: shell
?: help
@: load
@@: _relative_load
"""

# Output from the show command with default settings
SHOW_TXT = """colors: Terminal
continuation_prompt: >
debug: False
echo: False
editor: vim
feedback_to_output: False
locals_in_py: False
prompt: (Cmd)
quiet: False
timing: False
"""

SHOW_LONG = """
colors: Terminal          # Allow colorized output (valid values: Terminal, Always, Never)
continuation_prompt: >    # On 2nd+ line of input
debug: False              # Show full error stack on error
echo: False               # Echo command issued into output
editor: vim               # Program used by ``edit``
feedback_to_output: False # Include nonessentials in `|`, `>` results
locals_in_py: False       # Allow access to your application in py via self
prompt: (Cmd)             # The prompt issued to solicit input
quiet: False              # Don't print nonessential feedback
timing: False             # Report execution times
"""

def normalize(block):
    """ Normalize a block of text to perform comparison.

    Strip newlines from the very beginning and very end  Then split into separate lines and strip trailing whitespace
    from each line.
    """
    assert isinstance(block, str)
    block = block.strip('\n')
    return [line.rstrip() for line in block.splitlines()]


def run_cmd(app, cmd):
    """ Clear StdSim buffer, run the command, extract the buffer contents, """
    app.stdout.clear()
    app.onecmd_plus_hooks(cmd)
    out = app.stdout.getvalue()
    app.stdout.clear()
    return normalize(out)


@fixture
def base_app():
    c = cmd2.Cmd()
    c.stdout = StdSim(c.stdout)
    return c


def complete_tester(text: str, line: str, begidx: int, endidx: int, app) -> Optional[str]:
    """
    This is a convenience function to test cmd2.complete() since
    in a unit test environment there is no actual console readline
    is monitoring. Therefore we use mock to provide readline data
    to complete().

    :param text: the string prefix we are attempting to match
    :param line: the current input line with leading whitespace removed
    :param begidx: the beginning index of the prefix text
    :param endidx: the ending index of the prefix text
    :param app: the cmd2 app that will run completions
    :return: The first matched string or None if there are no matches
             Matches are stored in app.completion_matches
             These matches also have been sorted by complete()
    """
    def get_line():
        return line

    def get_begidx():
        return begidx

    def get_endidx():
        return endidx

    # Run the readline tab-completion function with readline mocks in place
    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                return app.complete(text, 0)
