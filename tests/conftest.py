# coding=utf-8
#
# Cmd2 unit/functional testing
#
# Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
# Released under MIT license, see LICENSE file
import sys

from pytest import fixture

import cmd2


# Help text for base cmd2.Cmd application
BASE_HELP = """Documented commands (type help <topic>):
========================================
_load           ed    history  list   py   save   shortcuts
_relative_load  edit  l        load   r    set    show
cmdenvironment  hi    li       pause  run  shell

Undocumented commands:
======================
EOF  eof  exit  help  q  quit
"""

# Help text for the history command
HELP_HISTORY = """history [arg]: lists past commands issued

        | no arg:         list all
        | arg is integer: list one history item, by index
        | arg is string:  string search
        | arg is /enclosed in forward-slashes/: regular expression search

Usage: history [options] (limit on which commands to include)

Options:
  -h, --help    show this help message and exit
  -s, --script  Script format; no separation lines
"""

# Output from the shortcuts command with default built-in shortcuts
SHORTCUTS_TXT = """Single-key shortcuts for other commands:
!: shell
?: help
@: load
@@: _relative_load
"""

expect_colors = True
if sys.platform.startswith('win'):
    expect_colors = False
# Output from the show command with default settings
SHOW_TXT = """abbrev: True
case_insensitive: True
colors: {}
continuation_prompt: >
debug: False
default_file_name: command.txt
echo: False
feedback_to_output: False
prompt: (Cmd)
quiet: False
timing: False
""".format(expect_colors)


class StdOut(object):
    """ Toy class for replacing self.stdout in cmd2.Cmd instances fror unit testing. """
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
