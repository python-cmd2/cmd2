# coding=utf-8
"""
Cmd2 unit/functional testing

Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
Released under MIT license, see LICENSE file
"""
import sys

from pytest import fixture

import cmd2


# Help text for base cmd2.Cmd application
BASE_HELP = """Documented commands (type help <topic>):
========================================
edit  help  history  load  py  pyscript  quit  set  shell  shortcuts
"""

# Help text for the history command
HELP_HISTORY = """usage: history [-h] [-r | -e | -s | -o FILE | -t TRANSCRIPT] [arg]

View, run, edit, and save previously entered commands.

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
  -s, --script          script format; no separation lines
  -o FILE, --output-file FILE
                        output commands to a script file
  -t TRANSCRIPT, --transcript TRANSCRIPT
                        output commands and results to a transcript file
"""

# Output from the shortcuts command with default built-in shortcuts
SHORTCUTS_TXT = """Shortcuts for other commands:
!: shell
?: help
@: load
@@: _relative_load
"""

expect_colors = True
if sys.platform.startswith('win'):
    expect_colors = False
# Output from the show command with default settings
SHOW_TXT = """abbrev: False
colors: {}
continuation_prompt: >
debug: False
echo: False
editor: vim
feedback_to_output: False
locals_in_py: True
prompt: (Cmd)
quiet: False
timing: False
""".format(expect_colors)

if expect_colors:
    color_str = 'True '
else:
    color_str = 'False'
SHOW_LONG = """
abbrev: False             # Accept abbreviated commands
colors: {}             # Colorized output (*nix only)
continuation_prompt: >    # On 2nd+ line of input
debug: False              # Show full error stack on error
echo: False               # Echo command issued into output
editor: vim               # Program used by ``edit``
feedback_to_output: False # Include nonessentials in `|`, `>` results
locals_in_py: True        # Allow access to your application in py via self
prompt: (Cmd)             # The prompt issued to solicit input
quiet: False              # Don't print nonessential feedback
timing: False             # Report execution times
""".format(color_str)


class StdOut(object):
    """ Toy class for replacing self.stdout in cmd2.Cmd instances for unit testing. """
    def __init__(self):
        self.buffer = ''

    def write(self, s):
        self.buffer += s

    def read(self):
        raise NotImplementedError

    def clear(self):
        self.buffer = ''


def normalize(block):
    """ Normalize a block of text to perform comparison.

    Strip newlines from the very beginning and very end  Then split into separate lines and strip trailing whitespace
    from each line.
    """
    assert isinstance(block, str)
    block = block.strip('\n')
    return [line.rstrip() for line in block.splitlines()]


def run_cmd(app, cmd):
    """ Clear StdOut buffer, run the command, extract the buffer contents, """
    app.stdout.clear()
    app.onecmd_plus_hooks(cmd)
    out = app.stdout.buffer
    app.stdout.clear()
    return normalize(out)


@fixture
def base_app():
    c = cmd2.Cmd()
    c.stdout = StdOut()
    return c
