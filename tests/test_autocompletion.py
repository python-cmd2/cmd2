"""
Unit/functional testing for argparse completer in cmd2

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""
import pytest
from .conftest import run_cmd, normalize, StdOut, complete_tester

from examples.tab_autocompletion import TabCompleteExample

@pytest.fixture
def cmd2_app():
    c = TabCompleteExample()
    c.stdout = StdOut()

    return c


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
           cmd2_app.completion_matches == ['add', 'delete', 'list', 'load']


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


def test_autocomp_subcmd_flag_comp_func_attr(cmd2_app):
    text = 'A'
    line = 'video movies list -a "{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['Adam Driver', 'Alec Guinness', 'Andy Serkis', 'Anthony Daniels']


def test_autocomp_subcmd_flag_comp_list_attr(cmd2_app):
    text = 'G'
    line = 'video movies list -d {}'.format(text)
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
    line = 'video movies add -d "George Lucas" -- "Han Solo" PG "Emilia Clarke" "{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['John Boyega" ']


def test_autcomp_custom_func_list_arg(cmd2_app):
    text = 'SW_'
    line = 'library show add {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['SW_CW', 'SW_REB', 'SW_TCW']


def test_autcomp_custom_func_list_and_dict_arg(cmd2_app):
    text = ''
    line = 'library show add SW_REB {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == ['S01E02', 'S01E03', 'S02E01', 'S02E03']


