# coding=utf-8
# flake8: noqa E302
"""
Unit/functional testing for readline tab completion functions in the cmd2.py module.

These are primarily tests related to readline completer functions which handle tab completion of cmd2/cmd commands,
file system paths, and shell commands.
"""
# Python 3.5 had some regressions in the unitest.mock module, so use 3rd party mock if available
try:
    import mock
except ImportError:
    from unittest import mock

import argparse
import enum
import os
import sys

import pytest

import cmd2
from cmd2 import utils
from examples.subcommands import SubcommandsExample

from .conftest import complete_tester, normalize, run_cmd

# List of strings used with completion functions
food_item_strs = ['Pizza', 'Ham', 'Ham Sandwich', 'Potato', 'Cheese "Pizza"']
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
        # Tab complete food items after -f and --food flag in command line
        '-f': food_item_strs,
        '--food': food_item_strs,

        # Tab complete sport items after -s and --sport flag in command line
        '-s': sport_item_strs,
        '--sport': sport_item_strs,
    }

# Dictionary used with index based completion functions
index_dict = \
    {
        1: food_item_strs,            # Tab complete food items at index 1 in command line
        2: sport_item_strs,           # Tab complete sport items at index 2 in command line
    }


class CompletionsExample(cmd2.Cmd):
    """
    Example cmd2 application used to exercise tab completion tests
    """
    def __init__(self):
        cmd2.Cmd.__init__(self, multiline_commands=['test_multiline'])
        self.foo = 'bar'
        self.add_settable(utils.Settable('foo', str, description="a settable param",
                                         completer_method=CompletionsExample.complete_foo_val))

    def do_test_basic(self, args):
        pass

    def complete_test_basic(self, text, line, begidx, endidx):
        return utils.basic_complete(text, line, begidx, endidx, food_item_strs)

    def do_test_delimited(self, args):
        pass

    def complete_test_delimited(self, text, line, begidx, endidx):
        return self.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')

    def do_test_sort_key(self, args):
        pass

    def complete_test_sort_key(self, text, line, begidx, endidx):
        num_strs = ['2', '11', '1']
        return utils.basic_complete(text, line, begidx, endidx, num_strs)

    def do_test_raise_exception(self, args):
        pass

    def complete_test_raise_exception(self, text, line, begidx, endidx):
        raise IndexError("You are out of bounds!!")

    def do_test_multiline(self, args):
        pass

    def complete_test_multiline(self, text, line, begidx, endidx):
        return utils.basic_complete(text, line, begidx, endidx, sport_item_strs)

    def do_test_no_completer(self, args):
        """Completing this should result in completedefault() being called"""
        pass

    def complete_foo_val(self, text, line, begidx, endidx, arg_tokens):
        """Supports unit testing cmd2.Cmd2.complete_set_val to confirm it passes all tokens in the set command"""
        if 'param' in arg_tokens:
            return ["SUCCESS"]
        else:
            return ["FAIL"]

    def completedefault(self, *ignored):
        """Method called to complete an input line when no command-specific
        complete_*() method is available.

        """
        return ['default']


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

    expected = sorted(cmd2_app.get_visible_commands(), key=cmd2_app.default_sort_key)
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)

    assert first_match is not None and cmd2_app.completion_matches == expected

def test_complete_bogus_command(cmd2_app):
    text = ''
    line = 'fizbuzz {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['default ']
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

def test_complete_exception(cmd2_app, capsys):
    text = ''
    line = 'test_raise_exception {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    out, err = capsys.readouterr()

    assert first_match is None
    assert "IndexError" in err

def test_complete_macro(base_app, request):
    # Create the macro
    out, err = run_cmd(base_app, 'macro create fake run_pyscript {1}')
    assert out == normalize("Macro 'fake' created")

    # Macros do path completion
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = 'fake {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'cript.py', text + 'cript.txt', text + 'cripts' + os.path.sep]
    first_match = complete_tester(text, line, begidx, endidx, base_app)
    assert first_match is not None and base_app.completion_matches == expected


def test_default_sort_key(cmd2_app):
    text = ''
    line = 'test_sort_key {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # First do alphabetical sorting
    cmd2_app.default_sort_key = cmd2.Cmd.ALPHABETICAL_SORT_KEY
    expected = ['1', '11', '2']
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

    # Now switch to natural sorting
    cmd2_app.default_sort_key = cmd2.Cmd.NATURAL_SORT_KEY
    expected = ['1', '2', '11']
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected


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

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)

    # It is at end of line, so extra space is present
    assert first_match is not None and cmd2_app.completion_matches == ['help ']

def test_cmd2_help_completion_multiple(cmd2_app):
    text = 'h'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == ['help', 'history']


def test_cmd2_help_completion_nomatch(cmd2_app):
    text = 'fakecommand'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None


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

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None

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

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and expected in cmd2_app.completion_matches

def test_shell_command_completion_nomatch(cmd2_app):
    text = 'zzzz'
    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None

def test_shell_command_completion_doesnt_complete_when_just_shell(cmd2_app):
    text = ''
    line = 'shell {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None

def test_shell_command_completion_does_path_completion_when_after_command(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')
    line = 'shell cat {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == [text + '.py ']

def test_shell_commmand_complete_in_path(cmd2_app, request):
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = 'shell {}'.format(text)

    endidx = len(line)
    begidx = endidx - len(text)

    # Since this will look for directories and executables in the given path,
    # we expect to see the scripts dir among the results
    expected = os.path.join(test_dir, 'scripts' + os.path.sep)
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and expected in cmd2_app.completion_matches


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

    matches = cmd2_app.path_complete(text, line, begidx, endidx)
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
    assert command in utils.get_exes_in_path(command)
    line = '{} {}'.format(command, text)

    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == [text + '.py ']


def test_path_completion_no_text(cmd2_app):
    # Run path complete with no search text which should show what's in cwd
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

    # We have to strip off the path from the beginning since the matches are entire paths
    completions_cwd = [match.replace(text, '', 1) for match in cmd2_app.path_complete(text, line, begidx, endidx)]

    # Verify that the first test gave results for entries in the cwd
    assert completions_no_text == completions_cwd
    assert completions_cwd

def test_path_completion_no_path(cmd2_app):
    # Run path complete with search text that isn't preceded by a path. This should use CWD as the path.
    text = 's'
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions_no_text = cmd2_app.path_complete(text, line, begidx, endidx)

    # Run path complete with path set to the CWD
    text = os.getcwd() + os.path.sep + 's'
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # We have to strip off the path from the beginning since the matches are entire paths (Leave the 's')
    completions_cwd = [match.replace(text[:-1], '', 1) for match in cmd2_app.path_complete(text, line, begidx, endidx)]

    # Verify that the first test gave results for entries in the cwd
    assert completions_no_text == completions_cwd
    assert completions_cwd


@pytest.mark.skipif(sys.platform == 'win32', reason="this only applies on systems where the root directory is a slash")
def test_path_completion_cwd_is_root_dir(cmd2_app):
    # Change our CWD to root dir
    cwd = os.getcwd()
    os.chdir(os.path.sep)

    text = ''
    line = 'shell ls {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)
    completions = cmd2_app.path_complete(text, line, begidx, endidx)

    # No match should start with a slash
    assert not any(match.startswith(os.path.sep) for match in completions)

    # Restore CWD
    os.chdir(cwd)

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

    assert cmd2_app.path_complete(text, line, begidx, endidx, path_filter=os.path.isdir) == expected

def test_basic_completion_single(cmd2_app):
    text = 'Pi'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert utils.basic_complete(text, line, begidx, endidx, food_item_strs) == ['Pizza']

def test_basic_completion_multiple(cmd2_app):
    text = ''
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    matches = sorted(utils.basic_complete(text, line, begidx, endidx, food_item_strs))
    assert matches == sorted(food_item_strs)

def test_basic_completion_nomatch(cmd2_app):
    text = 'q'
    line = 'list_food -f {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    assert utils.basic_complete(text, line, begidx, endidx, food_item_strs) == []

def test_delimiter_completion(cmd2_app):
    text = '/home/'
    line = 'run_script {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    cmd2_app.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')

    # Remove duplicates from display_matches and sort it. This is typically done in complete().
    display_list = utils.remove_duplicates(cmd2_app.display_matches)
    display_list = utils.alphabetical_sort(display_list)

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
                                        flag_dict, all_else=cmd2_app.path_complete) == [text + 'onftest.py']

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
                                         index_dict, all_else=cmd2_app.path_complete) == [text + 'onftest.py']

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

def test_tokens_for_completion_punctuation(cmd2_app):
    """Test that redirectors and terminators are word delimiters"""
    text = 'file'
    line = 'command | < ;>>{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_tokens = ['command', '|', '<', ';', '>>', 'file']
    expected_raw_tokens = ['command', '|', '<', ';', '>>', 'file']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens

def test_tokens_for_completion_quoted_punctuation(cmd2_app):
    """Test that quoted punctuation characters are not word delimiters"""
    text = '>file'
    line = 'command "{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_tokens = ['command', '>file']
    expected_raw_tokens = ['command', '">file']

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
    assert first_match is not None and cmd2_app.completion_matches == sorted(food_item_strs,
                                                                             key=cmd2_app.default_sort_key)

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

    expected = sorted(['"Ham', '"Ham Sandwich'], key=cmd2_app.default_sort_key)
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

def test_add_opening_quote_basic_single_quote_added(cmd2_app):
    text = 'Ch'
    line = 'test_basic {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ["'Cheese \"Pizza\"' "]
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

def test_add_opening_quote_basic_text_is_common_prefix(cmd2_app):
    # This tests when the text entered is the same as the common prefix of the matches
    text = 'Ham'
    line = 'test_basic {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = sorted(['"Ham', '"Ham Sandwich'], key=cmd2_app.default_sort_key)
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

def test_add_opening_quote_delimited_no_text(cmd2_app):
    text = ''
    line = 'test_delimited {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    # The whole list will be returned with no opening quotes added
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == sorted(delimited_strs,
                                                                             key=cmd2_app.default_sort_key)

def test_add_opening_quote_delimited_nothing_added(cmd2_app):
    text = '/ho'
    line = 'test_delimited {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected_matches = sorted(delimited_strs, key=cmd2_app.default_sort_key)
    expected_display = sorted(['other user', 'user'], key=cmd2_app.default_sort_key)

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
    expected_display = sorted(['file.txt', 'file space.txt'], key=cmd2_app.default_sort_key)

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
    expected_display = sorted(['file.txt', 'file space.txt'], key=cmd2_app.default_sort_key)

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

def test_no_completer(cmd2_app):
    text = ''
    line = 'test_no_completer {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['default ']
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is not None and cmd2_app.completion_matches == expected

def test_quote_as_command(cmd2_app):
    text = ''
    line = '" {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None and not cmd2_app.completion_matches


def test_complete_multiline_on_single_line(cmd2_app):
    text = ''
    line = 'test_multiline {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = sorted(sport_item_strs, key=cmd2_app.default_sort_key)
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)

    assert first_match is not None and cmd2_app.completion_matches == expected


def test_complete_multiline_on_multiple_lines(cmd2_app):
    # Set the same variables _complete_statement() sets when a user is entering data at a continuation prompt
    cmd2_app._at_continuation_prompt = True
    cmd2_app._multiline_in_progress = "test_multiline\n"

    text = 'Ba'
    line = '{}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    expected = sorted(['Bat', 'Basket', 'Basketball'], key=cmd2_app.default_sort_key)
    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)

    assert first_match is not None and cmd2_app.completion_matches == expected


# Used by redirect_complete tests
class RedirCompType(enum.Enum):
    SHELL_CMD = 1,
    PATH = 2,
    DEFAULT = 3,
    NONE = 4


@pytest.mark.parametrize('line, comp_type', [
    ('fake', RedirCompType.DEFAULT),
    ('fake arg', RedirCompType.DEFAULT),
    ('fake |', RedirCompType.SHELL_CMD),
    ('fake | grep', RedirCompType.PATH),
    ('fake | grep arg', RedirCompType.PATH),
    ('fake | grep >', RedirCompType.PATH),
    ('fake | grep > >', RedirCompType.NONE),
    ('fake | grep > file', RedirCompType.NONE),
    ('fake | grep > file >', RedirCompType.NONE),
    ('fake | grep > file |', RedirCompType.SHELL_CMD),
    ('fake | grep > file | grep', RedirCompType.PATH),
    ('fake | |', RedirCompType.NONE),
    ('fake | >', RedirCompType.NONE),
    ('fake >', RedirCompType.PATH),
    ('fake >>', RedirCompType.PATH),
    ('fake > >', RedirCompType.NONE),
    ('fake > |', RedirCompType.SHELL_CMD),
    ('fake >> file |', RedirCompType.SHELL_CMD),
    ('fake >> file | grep', RedirCompType.PATH),
    ('fake > file', RedirCompType.NONE),
    ('fake > file >', RedirCompType.NONE),
    ('fake > file >>', RedirCompType.NONE),
])
def test_redirect_complete(cmd2_app, monkeypatch, line, comp_type):
    # Test both cases of allow_redirection
    cmd2_app.allow_redirection = True
    for count in range(2):
        shell_cmd_complete_mock = mock.MagicMock(name='shell_cmd_complete')
        monkeypatch.setattr("cmd2.Cmd.shell_cmd_complete", shell_cmd_complete_mock)

        path_complete_mock = mock.MagicMock(name='path_complete')
        monkeypatch.setattr("cmd2.Cmd.path_complete", path_complete_mock)

        default_complete_mock = mock.MagicMock(name='fake_completer')

        text = ''
        line = '{} {}'.format(line, text)
        endidx = len(line)
        begidx = endidx - len(text)

        cmd2_app._redirect_complete(text, line, begidx, endidx, default_complete_mock)

        if comp_type == RedirCompType.SHELL_CMD:
            shell_cmd_complete_mock.assert_called_once()
        elif comp_type == RedirCompType.PATH:
            path_complete_mock.assert_called_once()
        elif comp_type == RedirCompType.DEFAULT:
            default_complete_mock.assert_called_once()
        else:
            shell_cmd_complete_mock.assert_not_called()
            path_complete_mock.assert_not_called()
            default_complete_mock.assert_not_called()

        # Do the next test with allow_redirection as False
        cmd2_app.allow_redirection = False
        if comp_type != RedirCompType.DEFAULT:
            comp_type = RedirCompType.NONE


def test_complete_set_value(cmd2_app):
    text = ''
    line = 'set foo {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match == "SUCCESS "

def test_complete_set_value_invalid_settable(cmd2_app, capsys):
    text = ''
    line = 'set fake {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, cmd2_app)
    assert first_match is None

    out, err = capsys.readouterr()
    assert "fake is not a settable parameter" in out

@pytest.fixture
def sc_app():
    c = SubcommandsExample()
    c.stdout = utils.StdSim(c.stdout)
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


def test_help_subcommand_completion_single(sc_app):
    text = 'base'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)

    # It is at end of line, so extra space is present
    assert first_match is not None and sc_app.completion_matches == ['base ']

def test_help_subcommand_completion_multiple(sc_app):
    text = ''
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)
    assert first_match is not None and sc_app.completion_matches == ['bar', 'foo', 'sport']


def test_help_subcommand_completion_nomatch(sc_app):
    text = 'z'
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, sc_app)
    assert first_match is None

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
    base_parser = argparse.ArgumentParser()
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
    sport_arg = parser_sport.add_argument('sport', help='Enter name of a sport', choices=sport_item_strs)

    @cmd2.with_argparser(base_parser, with_unknown_args=True)
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


def test_subcmd_with_unknown_completion_single_end(scu_app):
    text = 'f'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)

    print('first_match: {}'.format(first_match))

    # It is at end of line, so extra space is present
    assert first_match is not None and scu_app.completion_matches == ['foo ']


def test_subcmd_with_unknown_completion_multiple(scu_app):
    text = ''
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is not None and scu_app.completion_matches == ['bar', 'foo', 'sport']


def test_subcmd_with_unknown_completion_nomatch(scu_app):
    text = 'z'
    line = 'base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is None


def test_help_subcommand_completion_single_scu(scu_app):
    text = 'base'
    line = 'help {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)

    # It is at end of line, so extra space is present
    assert first_match is not None and scu_app.completion_matches == ['base ']


def test_help_subcommand_completion_multiple_scu(scu_app):
    text = ''
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is not None and scu_app.completion_matches == ['bar', 'foo', 'sport']

def test_help_subcommand_completion_with_flags_before_command(scu_app):
    text = ''
    line = 'help -h -v base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is not None and scu_app.completion_matches == ['bar', 'foo', 'sport']

def test_complete_help_subcommands_with_blank_command(scu_app):
    text = ''
    line = 'help "" {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match is None and not scu_app.completion_matches


def test_help_subcommand_completion_nomatch_scu(scu_app):
    text = 'z'
    line = 'help base {}'.format(text)
    endidx = len(line)
    begidx = endidx - len(text)

    first_match = complete_tester(text, line, begidx, endidx, scu_app)
    assert first_match == None


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
