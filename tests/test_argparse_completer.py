# coding=utf-8
# flake8: noqa E302
"""
Unit/functional testing for argparse completer in cmd2
"""
import argparse
from typing import List

import pytest

import cmd2
from cmd2 import with_argparser, Cmd2ArgParser, CompletionItem
from cmd2.argparse_completer import is_potential_flag, DEFAULT_DESCRIPTIVE_HEADER
from cmd2.utils import StdSim, basic_complete
from .conftest import run_cmd, complete_tester

# Lists used in our tests
static_choices_list = ['static', 'choices', 'stop', 'here']
choices_from_function = ['choices', 'function', 'chatty', 'smith']
choices_from_method = ['choices', 'method', 'most', 'improved']

completions_from_function = ['completions', 'function', 'fairly', 'complete']
completions_from_method = ['completions', 'method', 'missed', 'spot']


def choices_function() -> List[str]:
    """Function that provides choices"""
    return choices_from_function


def completer_function(text: str, line: str, begidx: int, endidx: int) -> List[str]:
    """Tab completion function"""
    return basic_complete(text, line, begidx, endidx, completions_from_function)


# noinspection PyMethodMayBeStatic,PyUnusedLocal
class AutoCompleteTester(cmd2.Cmd):
    """Cmd2 app that exercises AutoCompleter class"""
    def __init__(self):
        super().__init__()

    ############################################################################################################
    # Begin code related to help and command name completion
    ############################################################################################################
    def _music_create(self, args: argparse.Namespace) -> None:
        """Implements the 'music create' command"""
        self.poutput('music create')

    def _music_create_jazz(self, args: argparse.Namespace) -> None:
        """Implements the 'music create jazz' command"""
        self.poutput('music create jazz')

    def _music_create_rock(self, args: argparse.Namespace) -> None:
        """Implements the 'music create rock' command"""
        self.poutput('music create rock')

    # Top level parser for music command
    music_parser = Cmd2ArgParser(description='Manage music', prog='music')

    # Add sub-commands to music
    music_subparsers = music_parser.add_subparsers()

    # music -> create
    music_create_parser = music_subparsers.add_parser('create', help='Create music')
    music_create_parser.set_defaults(func=_music_create)

    # Add sub-commands to music -> create
    music_create_subparsers = music_create_parser.add_subparsers()

    # music -> create -> jazz
    music_create_jazz_parser = music_create_subparsers.add_parser('jazz', help='Create jazz')
    music_create_jazz_parser.set_defaults(func=_music_create_jazz)

    # music -> create -> rock
    music_create_rock_parser = music_create_subparsers.add_parser('rock', help='Create rocks')
    music_create_rock_parser.set_defaults(func=_music_create_rock)

    @with_argparser(music_parser)
    def do_music(self, args: argparse.Namespace) -> None:
        """Music command"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever sub-command function was selected
            func(self, args)
        else:
            # No sub-command was provided, so call help
            self.do_help('music')

    ############################################################################################################
    # Begin code related to testing choices, choices_function, and choices_method parameters
    ############################################################################################################
    def choices_method(self) -> List[str]:
        """Method that provides choices"""
        return choices_from_method

    def completion_item_method(self) -> List[CompletionItem]:
        """Choices method that returns CompletionItems"""
        items = []
        for i in range(0, 10):
            main_str = 'main_str{}'.format(i)
            items.append(CompletionItem(main_str, desc='blah blah'))
        return items

    choices_parser = Cmd2ArgParser()

    # Flag args for choices command
    choices_parser.add_argument("-l", "--list", help="a flag populated with a choices list",
                                choices=static_choices_list)
    choices_parser.add_argument("-f", "--function", help="a flag populated with a choices function",
                                choices_function=choices_function)
    choices_parser.add_argument("-m", "--method", help="a flag populated with a choices method",
                                choices_method=choices_method)
    choices_parser.add_argument('-n', "--no_header", help='this arg has a no descriptive header',
                                choices_method=completion_item_method)

    # Positional args for choices command
    choices_parser.add_argument("list_pos", help="a positional populated with a choices list",
                                choices=static_choices_list)
    choices_parser.add_argument("function_pos", help="a positional populated with a choices function",
                                choices_function=choices_function)
    choices_parser.add_argument("method_pos", help="a positional populated with a choices method",
                                choices_method=choices_method)

    @with_argparser(choices_parser)
    def do_choices(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to testing completer_function and completer_method parameters
    ############################################################################################################
    def completer_method(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Tab completion method"""
        return basic_complete(text, line, begidx, endidx, completions_from_method)

    completer_parser = Cmd2ArgParser()

    # Flag args for completer command
    completer_parser.add_argument("-f", "--function", help="a flag using a completer function",
                                  completer_function=completer_function)
    completer_parser.add_argument("-m", "--method", help="a flag using a completer method",
                                  completer_method=completer_method)

    # Positional args for completer command
    completer_parser.add_argument("function_pos", help="a positional using a completer function",
                                  completer_function=completer_function)
    completer_parser.add_argument("method_pos", help="a positional using a completer method",
                                  completer_method=completer_method)

    @with_argparser(completer_parser)
    def do_completer(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to testing tab hints
    ############################################################################################################
    hint_parser = Cmd2ArgParser()
    hint_parser.add_argument('-f', '--flag', help='a flag arg')
    hint_parser.add_argument('-s', '--suppressed_help', help=argparse.SUPPRESS)
    hint_parser.add_argument('-t', '--suppressed_hint', help='a flag arg', suppress_tab_hint=True)

    hint_parser.add_argument('hint_pos', help='here is a hint\nwith new lines')
    hint_parser.add_argument('no_help_pos')

    @with_argparser(hint_parser)
    def do_hint(self, args: argparse.Namespace) -> None:
        pass


@pytest.fixture
def ac_app():
    app = AutoCompleteTester()
    app.stdout = StdSim(app.stdout)
    return app


@pytest.mark.parametrize('command', [
    'music',
    'music create',
    'music create rock',
    'music create jazz'
])
def test_help(ac_app, command):
    out1, err1 = run_cmd(ac_app, '{} -h'.format(command))
    out2, err2 = run_cmd(ac_app, 'help {}'.format(command))
    assert out1 == out2


@pytest.mark.parametrize('command, text, completions', [
    ('', 'mu', ['music ']),
    ('music', 'cre', ['create ']),
    ('music create', '', ['jazz', 'rock'])
])
def test_complete_help(ac_app, command, text, completions):
    line = 'help {} {}'.format(command, text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and ac_app.completion_matches == completions


@pytest.mark.parametrize('text, completions', [
    ('-', ['--function', '--help', '--list', '--method', '--no_header', '-f', '-h', '-l', '-m', '-n']),
    ('--', ['--function', '--help', '--list', '--method', '--no_header']),
    ('-f', ['-f ']),
    ('--f', ['--function ']),
])
def test_autcomp_flag_completion(ac_app, text, completions):
    line = 'choices {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and ac_app.completion_matches == completions


@pytest.mark.parametrize('flag, text, completions', [
    ('-l', '', static_choices_list),
    ('--list', 's', ['static', 'stop']),
    ('-f', '', choices_from_function),
    ('--function', 'ch', ['choices', 'chatty']),
    ('-m', '', choices_from_method),
    ('--method', 'm', ['method', 'most']),
])
def test_autocomp_flag_choices_completion(ac_app, flag, text, completions):
    line = 'choices {} {}'.format(flag, text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and ac_app.completion_matches == sorted(completions, key=ac_app.matches_sort_key)


@pytest.mark.parametrize('pos, text, completions', [
    (1, '', static_choices_list),
    (1, 's', ['static', 'stop']),
    (2, '', choices_from_function),
    (2, 'ch', ['choices', 'chatty']),
    (3, '', choices_from_method),
    (3, 'm', ['method', 'most']),
])
def test_autocomp_positional_choices_completion(ac_app, pos, text, completions):
    # Generate line were preceding positionals are already filled
    line = 'choices {} {}'.format('foo ' * (pos - 1), text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and ac_app.completion_matches == sorted(completions, key=ac_app.matches_sort_key)


@pytest.mark.parametrize('flag, text, completions', [
    ('-f', '', completions_from_function),
    ('--function', 'f', ['function', 'fairly']),
    ('-m', '', completions_from_method),
    ('--method', 'm', ['method', 'missed']),
])
def test_autocomp_flag_completers(ac_app, flag, text, completions):
    line = 'completer {} {}'.format(flag, text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and ac_app.completion_matches == sorted(completions, key=ac_app.matches_sort_key)


@pytest.mark.parametrize('pos, text, completions', [
    (1, '', completions_from_function),
    (1, 'c', ['completions', 'complete']),
    (2, '', completions_from_method),
    (2, 'm', ['method', 'missed']),
])
def test_autocomp_positional_completers(ac_app, pos, text, completions):
    # Generate line were preceding positionals are already filled
    line = 'completer {} {}'.format('foo ' * (pos - 1), text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None and ac_app.completion_matches == sorted(completions, key=ac_app.matches_sort_key)


@pytest.mark.parametrize('num_aliases, show_description', [
    # The number of completion results determines if the description field of CompletionItems gets displayed
    # in the tab completions. The count must be greater than 1 and less than ac_app.max_completion_items,
    # which defaults to 50.
    (1, False),
    (5, True),
    (100, False),
])
def test_completion_items(ac_app, num_aliases, show_description):
    # Create aliases
    for i in range(0, num_aliases):
        run_cmd(ac_app, 'alias create fake{} help'.format(i))

    assert len(ac_app.aliases) == num_aliases

    text = 'fake'
    line = 'alias list {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    assert first_match is not None
    assert len(ac_app.completion_matches) == num_aliases
    assert len(ac_app.display_matches) == num_aliases

    # If show_description is True, the alias's value will be in the display text
    assert ('help' in ac_app.display_matches[0]) == show_description


def test_completion_items_default_header(ac_app):
    text = ''
    line = 'choices -n {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # This positional argument did not provide a descriptive header, so it should be DEFAULT_DESCRIPTIVE_HEADER
    complete_tester(text, line, begidx, endidx, ac_app)
    assert DEFAULT_DESCRIPTIVE_HEADER in ac_app.completion_header


def test_autocomp_hint_flag(ac_app, capsys):
    text = ''
    line = 'hint --flag {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    out, err = capsys.readouterr()

    assert first_match is None
    assert out == '''
Hint:
  -f, --flag FLAG         a flag arg

'''


def test_autocomp_hint_suppressed_help(ac_app, capsys):
    text = ''
    line = 'hint --suppressed_help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    out, err = capsys.readouterr()

    assert first_match is None
    assert not out


def test_autocomp_hint_suppressed_hint(ac_app, capsys):
    text = ''
    line = 'hint --suppressed_hint {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    out, err = capsys.readouterr()

    assert first_match is None
    assert not out


def test_autocomp_hint_pos(ac_app, capsys):
    text = ''
    line = 'hint {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    out, err = capsys.readouterr()

    assert first_match is None
    assert out == '''
Hint:
  HINT_POS                here is a hint
                          with new lines

'''


def test_autocomp_hint_no_help(ac_app, capsys):
    text = ''
    line = 'hint foo {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, ac_app)
    out, err = capsys.readouterr()

    assert first_match is None
    assert not out == '''
Hint:
  NO_HELP_POS            

'''

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
