# coding=utf-8
"""
Unit/functional testing for readline tab-completion functions in the cmd2.py module.

These are primarily tests related to readline completer functions which handle tab-completion of cmd2/cmd commands,
file system paths, and shell commands.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import argparse
import os
import sys

import cmd2
from unittest import mock
import pytest
from conftest import run_cmd, normalize, StdOut

MY_PATH = os.path.realpath(__file__)
sys.path.append(os.path.join(MY_PATH, '..', 'examples'))

from examples.tab_autocompletion import TabCompleteExample

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


@pytest.fixture
def cmd2_app():
    c = TabCompleteExample()
    c.stdout = StdOut()

    return c


def complete_tester(text, line, begidx, endidx, app):
    """
    This is a convenience function to test cmd2.complete() since
    in a unit test environment there is no actual console readline
    is monitoring. Therefore we use mock to provide readline data
    to complete().

    :param text: str - the string prefix we are attempting to match
    :param line: str - the current input line with leading whitespace removed
    :param begidx: int - the beginning index of the prefix text
    :param endidx: int - the ending index of the prefix text
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

    first_match = None
    with mock.patch.object(readline, 'get_line_buffer', get_line):
        with mock.patch.object(readline, 'get_begidx', get_begidx):
            with mock.patch.object(readline, 'get_endidx', get_endidx):
                # Run the readline tab-completion function with readline mocks in place
                first_match = app.complete(text, 0)

    return first_match


SUGGEST_HELP = '''Usage: suggest -t {movie, show} [-h] [-d DURATION{1..2}]

Suggest command demonstrates argparse customizations See hybrid_suggest and
orig_suggest to compare the help output.

required arguments:
  -t, --type {movie, show}

optional arguments:
  -h, --help            show this help message and exit
  -d, --duration DURATION{1..2}
                        Duration constraint in minutes.
                        	single value - maximum duration
                        	[a, b] - duration range'''

MEDIA_MOVIES_ADD_HELP = '''Usage: media movies add title {G, PG, PG-13, R, NC-17} [actor [...]]
                        -d DIRECTOR{1..2}
                        [-h]

positional arguments:
  title                 Movie Title
  {G, PG, PG-13, R, NC-17}
                        Movie Rating
  actor                 Actors

required arguments:
  -d, --director DIRECTOR{1..2}
                        Director

optional arguments:
  -h, --help            show this help message and exit'''

def test_help_required_group(cmd2_app, capsys):
    run_cmd(cmd2_app, 'suggest -h')
    out, err = capsys.readouterr()
    out1 = normalize(str(out))

    out2 = run_cmd(cmd2_app, 'help suggest')

    assert out1 == out2
    assert out1[0].startswith('Usage: suggest')
    assert out1[1] == ''
    assert out1[2].startswith('Suggest command demonstrates argparse customizations ')
    assert out1 == normalize(SUGGEST_HELP)


def test_help_required_group_long(cmd2_app, capsys):
    run_cmd(cmd2_app, 'media movies add -h')
    out, err = capsys.readouterr()
    out1 = normalize(str(out))

    out2 = run_cmd(cmd2_app, 'help media movies add')

    assert out1 == out2
    assert out1[0].startswith('Usage: media movies add')
    assert out1 == normalize(MEDIA_MOVIES_ADD_HELP)


def test_autocomp_flags(cmd2_app):
    text = '-'
    line = 'suggest {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['--duration', '--help', '--type', '-d', '-h', '-t']

def test_autcomp_hint(cmd2_app, capsys):
    text = ''
    line = 'suggest -d {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    out, err = capsys.readouterr()

    assert out == '''
Hint:
  -d, --duration DURATION    Duration constraint in minutes.
                             	single value - maximum duration
                             	[a, b] - duration range

'''

def test_autcomp_flag_comp(cmd2_app, capsys):
    text = '--d'
    line = 'suggest {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    out, err = capsys.readouterr()

    assert first_match is not None and \
           cmd2_app.completion_matches == ['--duration ']


def test_autocomp_flags_choices(cmd2_app):
    text = ''
    line = 'suggest -t {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['movie', 'show']


def test_autcomp_hint_in_narg_range(cmd2_app, capsys):
    text = ''
    line = 'suggest -d 2 {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    out, err = capsys.readouterr()

    assert out == '''
Hint:
  -d, --duration DURATION    Duration constraint in minutes.
                             	single value - maximum duration
                             	[a, b] - duration range

'''

def test_autocomp_flags_narg_max(cmd2_app):
    text = ''
    line = 'suggest d 2 3 {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None


def test_autcomp_narg_beyond_max(cmd2_app, capsys):
    run_cmd(cmd2_app, 'suggest -t movie -d 3 4 5')
    out, err = capsys.readouterr()

    assert 'Error: unrecognized arguments: 5' in err


def test_autocomp_subcmd_nested(cmd2_app):
    text = ''
    line = 'media movies {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['add', 'delete', 'list']


def test_autocomp_subcmd_flag_choices_append(cmd2_app):
    text = ''
    line = 'media movies list -r {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['G', 'NC-17', 'PG', 'PG-13', 'R']

def test_autocomp_subcmd_flag_choices_append_exclude(cmd2_app):
    text = ''
    line = 'media movies list -r PG PG-13 {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['G', 'NC-17', 'R']


def test_autocomp_subcmd_flag_comp_func(cmd2_app):
    text = 'A'
    line = 'media movies list -a "{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['Adam Driver', 'Alec Guinness', 'Andy Serkis', 'Anthony Daniels']


def test_autocomp_subcmd_flag_comp_list(cmd2_app):
    text = 'G'
    line = 'media movies list -d {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and first_match == '"Gareth Edwards'


def test_autcomp_pos_consumed(cmd2_app):
    text = ''
    line = 'library movie add SW_EP01 {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None


def test_autcomp_pos_after_flag(cmd2_app):
    text = 'Joh'
    line = 'media movies add -d "George Lucas" -- "Han Solo" PG "Emilia Clarke" "{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['John Boyega" ']






