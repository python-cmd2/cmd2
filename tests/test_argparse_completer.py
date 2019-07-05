# coding=utf-8
# flake8: noqa E302
"""
Unit/functional testing for argparse completer in cmd2
"""
import argparse
from typing import List

import pytest

import cmd2
from cmd2 import with_argparser
from cmd2.argparse_completer import is_potential_flag
from cmd2.argparse_custom import Cmd2ArgParser
from cmd2.utils import StdSim
from .conftest import run_cmd, complete_tester

# Lists used in our tests
static_choices_list = ['static', 'choices']
choices_from_function = ['choices', 'function']
choices_from_method = ['choices', 'method']


def choices_function() -> List[str]:
    """Function that provides choices"""
    return choices_from_function


class AutoCompleteTester(cmd2.Cmd):
    """Cmd2 app that exercises AutoCompleter class"""
    def __init__(self):
        super().__init__()

    ############################################################################################################
    # Begin code related to testing help and subcommand completion
    ############################################################################################################
    basic_parser = Cmd2ArgParser(prog='basic')
    basic_subparsers = basic_parser.add_subparsers()


    ############################################################################################################
    # Begin code related to testing choices, choices_function, and choices_method parameters
    ############################################################################################################
    def choices_method(self) -> List[str]:
        """Method that provides choices"""
        return choices_from_method

    choices_parser = Cmd2ArgParser()

    # Flags args for choices command
    choices_parser.add_argument("-n", "--no_choices", help="a flag with no choices")
    choices_parser.add_argument("-l", "--choices_list", help="a flag populated with a choices list",
                                choices=static_choices_list)
    choices_parser.add_argument("-f", "--choices_function", help="a flag populated with a choices function",
                                choices_function=choices_function)
    choices_parser.add_argument("-m", "--choices_method", help="a flag populated with a choices method",
                                choices_method=choices_method)

    # Positional args for choices command
    choices_parser.add_argument("no_choice_pos", help="a positional with no choices")
    choices_parser.add_argument("choices_list_pos", help="a positional populated with a choices list",
                                choices=static_choices_list)
    choices_parser.add_argument("choices_function_pos", help="a positional populated with a choices function",
                                choices_function=choices_function)
    choices_parser.add_argument("choices_method_pos", help="a positional populated with a choices method",
                                choices_method=choices_method)

    @with_argparser(choices_parser)
    def do_choices(self, args: argparse.Namespace) -> None:
        pass


@pytest.fixture
def ac_app():
    app = AutoCompleteTester()
    app.stdout = StdSim(app.stdout)
    return app


def test_help_basic(ac_app):
    out1, err1 = run_cmd(ac_app, 'choices -h')
    out2, err2 = run_cmd(ac_app, 'help choices')
    assert out1 == out2


def test_autocomp_flags(ac_app):
    text = '-'
    line = 'choices {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and \
           ac_app.completion_matches == ['--choices_function', '--choices_list', '--choices_method', '--help',
                                         '--no_choices', '-f', '-h', '-l', '-m', '-n']


def test_autcomp_flag_hint(ac_app, capsys):
    text = ''
    line = 'choices -n {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    out, err = capsys.readouterr()

    assert first_match is None
    assert 'a flag with no choices' in out


def test_autcomp_flag_completion(ac_app):
    text = '--ch'
    line = 'choices {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and \
           ac_app.completion_matches == ['--choices_function', '--choices_list', '--choices_method']

@pytest.mark.parametrize('flag, completions', [
    ('-l', static_choices_list),
    ('--choices_list', static_choices_list),
    ('-f', choices_from_function),
    ('--choices_function', choices_from_function),
    ('-m', choices_from_method),
    ('--choices_method', choices_from_method),
])
def test_autocomp_flag_choices_completion(ac_app, flag, completions):
    text = ''
    line = 'choices {} {}'.format(flag, text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and \
           ac_app.completion_matches == sorted(completions, key=ac_app.matches_sort_key)


@pytest.mark.parametrize('pos, completions', [
    (2, static_choices_list),    # choices_list_pos
    (3, choices_from_function),  # choices_function_pos
    (4, choices_from_method),    # choices_method_pos
])
def test_autocomp_positional_choices_completion(ac_app, pos, completions):
    # Test completions of positional arguments by generating a line were preceding positionals are already filled
    text = ''
    line = 'choices {} {}'.format('foo ' * (pos - 1), text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and \
           ac_app.completion_matches == sorted(completions, key=ac_app.matches_sort_key)


# def test_autcomp_hint_in_narg_range(cmd2_app, capsys):
#     text = ''
#     line = 'suggest -d 2 {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     out, err = capsys.readouterr()
#
#     assert out == '''
# Hint:
#   -d, --duration DURATION    Duration constraint in minutes.
#                              	single value - maximum duration
#                              	[a, b] - duration range
#
# '''
#
# def test_autocomp_flags_narg_max(cmd2_app):
#     text = ''
#     line = 'suggest d 2 3 {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     assert first_match is None
#
#
# def test_autcomp_narg_beyond_max(cmd2_app):
#     out, err = run_cmd(cmd2_app, 'suggest -t movie -d 3 4 5')
#     assert 'Error: unrecognized arguments: 5' in err[1]
#
#
# def test_autocomp_subcmd_flag_comp_func_attr(cmd2_app):
#     text = 'A'
#     line = 'video movies list -a "{}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     assert first_match is not None and \
#            cmd2_app.completion_matches == ['Adam Driver', 'Alec Guinness', 'Andy Serkis', 'Anthony Daniels']
#
#
# def test_autocomp_subcmd_flag_comp_list_attr(cmd2_app):
#     text = 'G'
#     line = 'video movies list -d {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     assert first_match is not None and first_match == '"Gareth Edwards'
#
#
# def test_autocomp_pos_consumed(cmd2_app):
#     text = ''
#     line = 'library movie add SW_EP01 {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     assert first_match is None
#
#
# def test_autocomp_pos_after_flag(cmd2_app):
#     text = 'Joh'
#     line = 'video movies add -d "George Lucas" -- "Han Solo" PG "Emilia Clarke" "{}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     assert first_match is not None and \
#            cmd2_app.completion_matches == ['John Boyega" ']
#
#
# def test_autocomp_custom_func_dict_arg(cmd2_app):
#     text = '/home/user/'
#     line = 'video movies load {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     assert first_match is not None and \
#            cmd2_app.completion_matches == ['/home/user/another.db', '/home/user/file space.db', '/home/user/file.db']
#
#
# def test_argparse_remainder_flag_completion(cmd2_app):
#     import cmd2
#     import argparse
#
#     # Test flag completion as first arg of positional with nargs=argparse.REMAINDER
#     text = '--h'
#     line = 'help command {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     # --h should not complete into --help because we are in the argparse.REMAINDER section
#     assert complete_tester(text, line, begidx, endidx, cmd2_app) is None
#
#     # Test flag completion within an already started positional with nargs=argparse.REMAINDER
#     text = '--h'
#     line = 'help command subcommand {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     # --h should not complete into --help because we are in the argparse.REMAINDER section
#     assert complete_tester(text, line, begidx, endidx, cmd2_app) is None
#
#     # Test a flag with nargs=argparse.REMAINDER
#     parser = argparse.ArgumentParser()
#     parser.add_argument('-f', nargs=argparse.REMAINDER)
#
#     # Overwrite eof's parser for this test
#     cmd2.Cmd.do_eof.argparser = parser
#
#     text = '--h'
#     line = 'eof -f {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     # --h should not complete into --help because we are in the argparse.REMAINDER section
#     assert complete_tester(text, line, begidx, endidx, cmd2_app) is None
#
#
# def test_completion_after_double_dash(cmd2_app):
#     """
#     Test completion after --, which argparse says (all args after -- are non-options)
#     All of these tests occur outside of an argparse.REMAINDER section since those tests
#     are handled in test_argparse_remainder_flag_completion
#     """
#
#     # Test -- as the last token
#     text = '--'
#     line = 'help {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     # Since -- is the last token, then it should show flag choices
#     first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
#     assert first_match is not None and '--help' in cmd2_app.completion_matches
#
#     # Test -- to end all flag completion
#     text = '--'
#     line = 'help -- {}'.format(text)
#     endidx = len(line)
#     begidx = endidx - len(text)
#
#     # Since -- appeared before the -- being completed, nothing should be completed
#     assert complete_tester(text, line, begidx, endidx, cmd2_app) is None

def test_is_potential_flag():
    parser = Cmd2ArgParser()

    # Not valid flags
    assert not is_potential_flag('', parser)
    assert not is_potential_flag('non-flag', parser)
    assert not is_potential_flag('-', parser)
    assert not is_potential_flag('--has space', parser)
    assert not is_potential_flag('-2', parser)

    # Valid flags
    assert is_potential_flag('-flag', parser)
    assert is_potential_flag('--flag', parser)