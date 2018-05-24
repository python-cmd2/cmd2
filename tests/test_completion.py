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

import pytest
import cmd2
from .conftest import complete_tester, StdOut
from examples.subcommands import SubcommandsExample

# List of strings used with completion functions
food_item_strs = ['Pizza', 'Ham', 'Ham Sandwich', 'Potato']
sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']
delimited_strs = \
    [
        '/home/user/file.txt',
        '/home/user/file space.txt',
        '/home/user/prog.c',
        '/home/other user/maps',
        '/home/other user/tests'
    ]

# Dictionary used with flag based completion functions
flag_dict = \
    {
        # Tab-complete food items after -f and --food flag in command line
        '-f': food_item_strs,
        '--food': food_item_strs,

        # Tab-complete sport items after -s and --sport flag in command line
        '-s': sport_item_strs,
        '--sport': sport_item_strs,
    }

# Dictionary used with index based completion functions
index_dict = \
    {
        1: food_item_strs,            # Tab-complete food items at index 1 in command line
        2: sport_item_strs,           # Tab-complete sport items at index 2 in command line
    }


class CompletionsExample(cmd2.Cmd):
    """
    Example cmd2 application used to exercise tab-completion tests
    """
    def __init__(self):
        cmd2.Cmd.__init__(self)

    def do_test_basic(self, args):
        pass

    def complete_test_basic(self, text, line, begidx, endidx):
        return self.basic_complete(text, line, begidx, endidx, food_item_strs)

    def do_test_delimited(self, args):
        pass

    def complete_test_delimited(self, text, line, begidx, endidx):
        return self.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')


@pytest.fixture
def cmd2_app():
    c = CompletionsExample()
    return c


def test_cmd2_command_completion_single(cmd2_app):
    text = 'he'
    line = text
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help']

def test_complete_command_single(cmd2_app):
    text = 'he'
    line = text
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == ['help ']

def test_complete_empty_arg(cmd2_app):
    text = ''
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = sorted(cmd2_app.complete_help(text, line, begidx, endidx))
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)

    assert first_match is not None and \
        cmd2_app.completion_matches == expected

def test_complete_bogus_command(cmd2_app):
    text = ''
    line = 'fizbuzz {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None


def test_cmd2_command_completion_single(cmd2_app):
    text = 'hel'
    line = text
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help']

def test_cmd2_command_completion_multiple(cmd2_app):
    text = 'h'
    line = text
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == ['help', 'history']

def test_cmd2_command_completion_nomatch(cmd2_app):
    text = 'fakecommand'
    line = text
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.completenames(text, line, begidx, endidx) == []


def test_cmd2_help_completion_single(cmd2_app):
    text = 'he'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_help(text, line, begidx, endidx) == ['help']

def test_cmd2_help_completion_multiple(cmd2_app):
    text = 'h'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(cmd2_app.complete_help(text, line, begidx, endidx))
    assert matches == ['help', 'history']

def test_cmd2_help_completion_nomatch(cmd2_app):
    text = 'fakecommand'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_help(text, line, begidx, endidx) == []


def test_shell_command_completion_shortcut(cmd2_app):
    # Made sure ! runs a shell command and all matches start with ! since there
    # isn't a space between ! and the shell command. Display matches won't
    # begin with the !.
    if sys.platform == "win32":
        text = '!calc'
        expected = ['!calc.exe ']
        expected_display = ['calc.exe']
    else:
        text = '!egr'
        expected = ['!egrep ']
        expected_display = ['egrep']

    line = text
    endidx = len(line)
    begidx = 0

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == expected and \
           cmd2_app.display_matches == expected_display

def test_shell_command_completion_doesnt_match_wildcards(cmd2_app):
    if sys.platform == "win32":
        text = 'c*'
    else:
        text = 'e*'

    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_multiple(cmd2_app):
    if sys.platform == "win32":
        text = 'c'
        expected = 'calc.exe'
    else:
        text = 'l'
        expected = 'ls'

    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert expected in cmd2_app.complete_shell(text, line, begidx, endidx)

def test_shell_command_completion_nomatch(cmd2_app):
    text = 'zzzz'
    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_doesnt_complete_when_just_shell(cmd2_app):
    text = ''
    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.complete_shell(text, line, begidx, endidx) == []

def test_shell_command_completion_does_path_completion_when_after_command(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.complete_shell(text, line, begidx, endidx) == [text + '.py']


def test_path_completion_single_end(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx) == [text + '.py']

def test_path_completion_multiple(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(cmd2_app.path_complete(text, line, begidx, endidx))
    expected = [text + 'cript.py', text + 'cript.txt', text + 'cripts' + os.path.sep]
    assert matches == expected

def test_path_completion_nomatch(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'fakepath')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.path_complete(text, line, begidx, endidx) == []


def test_default_to_shell_completion(cmd2_app, request):
    cmd2_app.default_to_shell = True
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')

    if sys.platform == "win32":
        command = 'calc.exe'
    else:
        command = 'egrep'

    # Make sure the command is on the testing system
    assert command in cmd2_app.get_exes_in_path(command)
    line = '{} {}'.format(command, text)

    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == [text + '.py ']


def test_path_completion_cwd(cmd2_app):
    # Run path complete with no search text
    text = ''
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_no_text = cmd2_app.path_complete(text, line, begidx, endidx)

    # Run path complete with path set to the CWD
    text = os.getcwd() + os.path.sep
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # We have to strip off the text from the beginning since the matches are entire paths
    completions_cwd = [match.replace(text, '', 1) for match in cmd2_app.path_complete(text, line, begidx, endidx)]

    # Verify that the first test gave results for entries in the cwd
    assert completions_no_text == completions_cwd
    assert completions_cwd

def test_path_completion_doesnt_match_wildcards(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c*')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    # Currently path completion doesn't accept wildcards, so will always return empty results
    assert cmd2_app.path_complete(text, line, begidx, endidx) == []

@pytest.mark.skipif(sys.platform == 'win32', reason="getpass.getuser() does not work on Windows in AppVeyor because "
                                                    "no user name environment variables are set")
def test_path_completion_complete_user(cmd2_app):
    import getpass
    user = getpass.getuser()

    text = '~{}'.format(user)
    line = 'shell fake {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions = cmd2_app.path_complete(text, line, begidx, endidx)

    expected = text + os.path.sep
    assert expected in completions

def test_path_completion_user_path_expansion(cmd2_app):
    # Run path with a tilde and a slash
    if sys.platform.startswith('win'):
        cmd = 'dir'
    else:
        cmd = 'ls'

    # Use a ~ which will be expanded into the user's home directory
    text = '~{}'.format(os.path.sep)
    line = 'shell {} {}'.format(cmd, text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_tilde_slash = [match.replace(text, '', 1) for match in cmd2_app.path_complete(text, line,
                                                                                              begidx, endidx)]

    # Run path complete on the user's home directory
    text = os.path.expanduser('~') + os.path.sep
    line = 'shell {} {}'.format(cmd, text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_home = [match.replace(text, '', 1) for match in cmd2_app.path_complete(text, line, begidx, endidx)]

    assert completions_tilde_slash == completions_home

def test_path_completion_directories_only(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'cripts' + os.path.sep]

    assert cmd2_app.path_complete(text, line, begidx, endidx, dir_only=True) == expected

def test_basic_completion_single(cmd2_app):
    text = 'Pi'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.basic_complete(text, line, begidx, endidx, food_item_strs) == ['Pizza']

def test_basic_completion_multiple(cmd2_app):
    text = ''
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(cmd2_app.basic_complete(text, line, begidx, endidx, food_item_strs))
    assert matches == sorted(food_item_strs)

def test_basic_completion_nomatch(cmd2_app):
    text = 'q'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.basic_complete(text, line, begidx, endidx, food_item_strs) == []

def test_delimiter_completion(cmd2_app):
    text = '/home/'
    line = 'load {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    cmd2_app.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')

    # Remove duplicates from display_matches and sort it. This is typically done in complete().
    display_set = set(cmd2_app.display_matches)
    display_list = list(display_set)
    display_list.sort()

    assert display_list == ['other user', 'user']

def test_flag_based_completion_single(cmd2_app):
    text = 'Pi'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.flag_based_complete(text, line, begidx, endidx, flag_dict) == ['Pizza']

def test_flag_based_completion_multiple(cmd2_app):
    text = ''
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(cmd2_app.flag_based_complete(text, line, begidx, endidx, flag_dict))
    assert matches == sorted(food_item_strs)

def test_flag_based_completion_nomatch(cmd2_app):
    text = 'q'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.flag_based_complete(text, line, begidx, endidx, flag_dict) == []

def test_flag_based_default_completer(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'list_food {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.flag_based_complete(text, line, begidx, endidx,
                                        flag_dict, cmd2_app.path_complete) == [text + 'onftest.py']

def test_flag_based_callable_completer(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'list_food -o {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    flag_dict['-o'] = cmd2_app.path_complete
    assert cmd2_app.flag_based_complete(text, line, begidx, endidx,
                                        flag_dict) == [text + 'onftest.py']


def test_index_based_completion_single(cmd2_app):
    text = 'Foo'
    line = 'command Pizza {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict) == ['Football']

def test_index_based_completion_multiple(cmd2_app):
    text = ''
    line = 'command Pizza {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict))
    assert matches == sorted(sport_item_strs)

def test_index_based_completion_nomatch(cmd2_app):
    text = 'q'
    line = 'command {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict) == []

def test_index_based_default_completer(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'command Pizza Bat Computer {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    assert cmd2_app.index_based_complete(text, line, begidx, endidx,
                                         index_dict, cmd2_app.path_complete) == [text + 'onftest.py']

def test_index_based_callable_completer(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = 'command Pizza Bat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    index_dict[3] = cmd2_app.path_complete
    assert cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict) == [text + 'onftest.py']


def test_tokens_for_completion_quoted(cmd2_app):
    text = 'Pi'
    line = 'list_food "{}"'.format(text)
    endidx = len(line)
    begidx = endidx

    expected_tokens = ['list_food', 'Pi', '']
    expected_raw_tokens = ['list_food', '"Pi"', '']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens

def test_tokens_for_completion_unclosed_quote(cmd2_app):
    text = 'Pi'
    line = 'list_food "{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_tokens = ['list_food', 'Pi']
    expected_raw_tokens = ['list_food', '"Pi']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens

def test_tokens_for_completion_redirect(cmd2_app):
    text = '>>file'
    line = 'command | < {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    cmd2_app.allow_redirection = True
    expected_tokens = ['command', '|', '<', '>>', 'file']
    expected_raw_tokens = ['command', '|', '<', '>>', 'file']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens

def test_tokens_for_completion_quoted_redirect(cmd2_app):
    text = '>file'
    line = 'command "{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    cmd2_app.allow_redirection = True
    expected_tokens = ['command', '>file']
    expected_raw_tokens = ['command', '">file']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens

def test_tokens_for_completion_redirect_off(cmd2_app):
    text = '>file'
    line = 'command {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    cmd2_app.allow_redirection = False
    expected_tokens = ['command', '>file']
    expected_raw_tokens = ['command', '>file']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens

def test_add_opening_quote_basic_no_text(cmd2_app):
    text = ''
    line = 'test_basic {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # The whole list will be returned with no opening quotes added
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == sorted(food_item_strs)

def test_add_opening_quote_basic_nothing_added(cmd2_app):
    text = 'P'
    line = 'test_basic {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == ['Pizza', 'Potato']

def test_add_opening_quote_basic_quote_added(cmd2_app):
    text = 'Ha'
    line = 'test_basic {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = sorted(['"Ham', '"Ham Sandwich'])
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

def test_add_opening_quote_basic_text_is_common_prefix(cmd2_app):
    # This tests when the text entered is the same as the common prefix of the matches
    text = 'Ham'
    line = 'test_basic {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = sorted(['"Ham', '"Ham Sandwich'])
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

def test_add_opening_quote_delimited_no_text(cmd2_app):
    text = ''
    line = 'test_delimited {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # The whole list will be returned with no opening quotes added
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == sorted(delimited_strs)

def test_add_opening_quote_delimited_nothing_added(cmd2_app):
    text = '/ho'
    line = 'test_delimited {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_matches = sorted(delimited_strs)
    expected_display = sorted(['other user', 'user'])

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           cmd2_app.completion_matches == expected_matches and \
           cmd2_app.display_matches == expected_display

def test_add_opening_quote_delimited_quote_added(cmd2_app):
    text = '/home/user/fi'
    line = 'test_delimited {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_common_prefix = '"/home/user/file'
    expected_display = sorted(['file.txt', 'file space.txt'])

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           os.path.commonprefix(cmd2_app.completion_matches) == expected_common_prefix and \
           cmd2_app.display_matches == expected_display

def test_add_opening_quote_delimited_text_is_common_prefix(cmd2_app):
    # This tests when the text entered is the same as the common prefix of the matches
    text = '/home/user/file'
    line = 'test_delimited {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_common_prefix = '"/home/user/file'
    expected_display = sorted(['file.txt', 'file space.txt'])

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           os.path.commonprefix(cmd2_app.completion_matches) == expected_common_prefix and \
           cmd2_app.display_matches == expected_display

def test_add_opening_quote_delimited_space_in_prefix(cmd2_app):
    # This test when a space appears before the part of the string that is the display match
    text = '/home/oth'
    line = 'test_delimited {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_common_prefix = '"/home/other user/'
    expected_display = ['maps', 'tests']

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and \
           os.path.commonprefix(cmd2_app.completion_matches) == expected_common_prefix and \
           cmd2_app.display_matches == expected_display


@pytest.fixture
def sc_app():
    c = SubcommandsExample()
    c.stdout = StdOut()

    return c

def test_cmd2_subcommand_completion_single_end(sc_app):
    text = 'f'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)

    # It is at end of line, so extra space is present
    assert first_match is not None and sc_app.completion_matches == ['foo ']

def test_cmd2_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)
    assert first_match is not None and sc_app.completion_matches == ['bar', 'foo', 'sport']

def test_cmd2_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)
    assert first_match is None


def test_cmd2_help_subcommand_completion_single(sc_app):
    text = 'base'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert sc_app.complete_help(text, line, begidx, endidx) == ['base']

def test_cmd2_help_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(sc_app.complete_help(text, line, begidx, endidx))
    assert matches == ['bar', 'foo', 'sport']


def test_cmd2_help_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert sc_app.complete_help(text, line, begidx, endidx) == []

def test_subcommand_tab_completion(sc_app):
    # This makes sure the correct completer for the sport subcommand is called
    text = 'Foot'
    line = 'base sport {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)

    # It is at end of line, so extra space is present
    assert first_match is not None and sc_app.completion_matches == ['Football ']


def test_subcommand_tab_completion_with_no_completer(sc_app):
    # This tests what happens when a subcommand has no completer
    # In this case, the foo subcommand has no completer defined
    text = 'Foot'
    line = 'base foo {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)
    assert first_match is None


def test_subcommand_tab_completion_space_in_text(sc_app):
    text = 'B'
    line = 'base sport "Space {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)

    assert first_match is not None and \
           sc_app.completion_matches == ['Ball" '] and \
           sc_app.display_matches == ['Space Ball']

####################################################


class SubcommandsWithUnknownExample(cmd2.Cmd):
    """
    Example cmd2 application where we a base command which has a couple subcommands
    and the "sport" subcommand has tab completion enabled.
    """

    def __init__(self):
        cmd2.Cmd.__init__(self)

    # subcommand functions for the base command
    def base_foo(self, args):
        """foo subcommand of base command"""
        self.poutput(args.x * args.y)

    def base_bar(self, args):
        """bar subcommand of base command"""
        self.poutput('((%s))' % args.z)

    def base_sport(self, args):
        """sport subcommand of base command"""
        self.poutput('Sport is {}'.format(args.sport))

    # create the top-level parser for the base command
    base_parser = argparse.ArgumentParser(prog='base')
    base_subparsers = base_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" subcommand
    parser_foo = base_subparsers.add_parser('foo', help='foo help')
    parser_foo.add_argument('-x', type=int, default=1, help='integer')
    parser_foo.add_argument('y', type=float, help='float')
    parser_foo.set_defaults(func=base_foo)

    # create the parser for the "bar" subcommand
    parser_bar = base_subparsers.add_parser('bar', help='bar help')
    parser_bar.add_argument('z', help='string')
    parser_bar.set_defaults(func=base_bar)

    # create the parser for the "sport" subcommand
    parser_sport = base_subparsers.add_parser('sport', help='sport help')
    sport_arg = parser_sport.add_argument('sport', help='Enter name of a sport')
    setattr(sport_arg, 'arg_choices', sport_item_strs)

    @cmd2.with_argparser_and_unknown_args(base_parser)
    def do_base(self, args):
        """Base command help"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('base')


@pytest.fixture
def scu_app():
    """Declare test fixture for with_argparser_and_unknown_args"""
    app = SubcommandsWithUnknownExample()
    return app


def test_cmd2_subcmd_with_unknown_completion_single_end(scu_app):
    text = 'f'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)

    print('first_match: {}'.format(first_match))

    # It is at end of line, so extra space is present
    assert first_match is not None and scu_app.completion_matches == ['foo ']


def test_cmd2_subcmd_with_unknown_completion_multiple(scu_app):
    text = ''
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is not None and scu_app.completion_matches == ['bar', 'foo', 'sport']


def test_cmd2_subcmd_with_unknown_completion_nomatch(scu_app):
    text = 'z'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is None


def test_cmd2_help_subcommand_completion_single_scu(scu_app):
    text = 'base'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert scu_app.complete_help(text, line, begidx, endidx) == ['base']


def test_cmd2_help_subcommand_completion_multiple_scu(scu_app):
    text = ''
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(scu_app.complete_help(text, line, begidx, endidx))
    assert matches == ['bar', 'foo', 'sport']


def test_cmd2_help_subcommand_completion_nomatch_scu(scu_app):
    text = 'z'
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    assert scu_app.complete_help(text, line, begidx, endidx) == []


def test_subcommand_tab_completion_scu(scu_app):
    # This makes sure the correct completer for the sport subcommand is called
    text = 'Foot'
    line = 'base sport {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)

    # It is at end of line, so extra space is present
    assert first_match is not None and scu_app.completion_matches == ['Football ']


def test_subcommand_tab_completion_with_no_completer_scu(scu_app):
    # This tests what happens when a subcommand has no completer
    # In this case, the foo subcommand has no completer defined
    text = 'Foot'
    line = 'base foo {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is None


def test_subcommand_tab_completion_space_in_text_scu(scu_app):
    text = 'B'
    line = 'base sport "Space {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)

    assert first_match is not None and \
           scu_app.completion_matches == ['Ball" '] and \
           scu_app.display_matches == ['Space Ball']
