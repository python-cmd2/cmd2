"""Unit/functional testing for prompt-toolkit tab completion functions in the cmd2.py module.

These are primarily tests related to prompt-toolkit completer functions which handle tab completion of cmd2/cmd commands,
file system paths, and shell commands.
"""

import dataclasses
import enum
import os
import sys
from typing import NoReturn
from unittest import mock

import pytest

import cmd2
from cmd2 import (
    CompletionItem,
    Completions,
    utils,
)

from .conftest import (
    normalize,
    run_cmd,
)


class SubcommandsExample(cmd2.Cmd):
    """Example cmd2 application where we a base command which has a couple subcommands
    and the "sport" subcommand has tab completion enabled.
    """

    sport_item_strs = ('Bat', 'Basket', 'Basketball', 'Football', 'Space Ball')

    # create the top-level parser for the base command
    base_parser = cmd2.Cmd2ArgumentParser()
    base_subparsers = base_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" subcommand
    parser_foo = base_subparsers.add_parser('foo', help='foo help')
    parser_foo.add_argument('-x', type=int, default=1, help='integer')
    parser_foo.add_argument('y', type=float, help='float')
    parser_foo.add_argument('input_file', type=str, help='Input File')

    # create the parser for the "bar" subcommand
    parser_bar = base_subparsers.add_parser('bar', help='bar help')

    bar_subparsers = parser_bar.add_subparsers(title='layer3', help='help for 3rd layer of commands')
    parser_bar.add_argument('z', help='string')

    bar_subparsers.add_parser('apple', help='apple help')
    bar_subparsers.add_parser('artichoke', help='artichoke help')
    bar_subparsers.add_parser('cranberries', help='cranberries help')

    # create the parser for the "sport" subcommand
    parser_sport = base_subparsers.add_parser('sport', help='sport help')
    sport_arg = parser_sport.add_argument('sport', help='Enter name of a sport', choices=sport_item_strs)

    # create the top-level parser for the alternate command
    # The alternate command doesn't provide its own help flag
    base2_parser = cmd2.Cmd2ArgumentParser(add_help=False)
    base2_subparsers = base2_parser.add_subparsers(title='subcommands', help='subcommand help')

    # create the parser for the "foo" subcommand
    parser_foo2 = base2_subparsers.add_parser('foo', help='foo help')
    parser_foo2.add_argument('-x', type=int, default=1, help='integer')
    parser_foo2.add_argument('y', type=float, help='float')
    parser_foo2.add_argument('input_file', type=str, help='Input File')

    # create the parser for the "bar" subcommand
    parser_bar2 = base2_subparsers.add_parser('bar', help='bar help')

    bar2_subparsers = parser_bar2.add_subparsers(title='layer3', help='help for 3rd layer of commands')
    parser_bar2.add_argument('z', help='string')

    bar2_subparsers.add_parser('apple', help='apple help')
    bar2_subparsers.add_parser('artichoke', help='artichoke help')
    bar2_subparsers.add_parser('cranberries', help='cranberries help')

    # create the parser for the "sport" subcommand
    parser_sport2 = base2_subparsers.add_parser('sport', help='sport help')
    sport2_arg = parser_sport2.add_argument('sport', help='Enter name of a sport', choices=sport_item_strs)

    def __init__(self) -> None:
        super().__init__()

    # subcommand functions for the base command
    def base_foo(self, args) -> None:
        """Foo subcommand of base command."""
        self.poutput(args.x * args.y)

    def base_bar(self, args) -> None:
        """Bar subcommand of base command."""
        self.poutput(f'(({args.z}))')

    def base_sport(self, args) -> None:
        """Sport subcommand of base command."""
        self.poutput(f'Sport is {args.sport}')

    # Set handler functions for the subcommands
    parser_foo.set_defaults(func=base_foo)
    parser_bar.set_defaults(func=base_bar)
    parser_sport.set_defaults(func=base_sport)

    @cmd2.with_argparser(base_parser)
    def do_base(self, args) -> None:
        """Base command help."""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('base')

    @cmd2.with_argparser(base2_parser)
    def do_alternate(self, args) -> None:
        """Alternate command help."""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('alternate')


# List of strings used with completion functions
food_item_strs = ['Pizza', 'Ham', 'Ham Sandwich', 'Potato', 'Cheese "Pizza"']
sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football', 'Space Ball']
delimited_strs = [
    '/home/user/file.txt',
    '/home/user/file space.txt',
    '/home/user/prog.c',
    '/home/other user/maps',
    '/home/other user/tests',
]

# Dictionary used with flag based completion functions
flag_dict = {
    # Tab complete food items after -f and --food flag in command line
    '-f': food_item_strs,
    '--food': food_item_strs,
    # Tab complete sport items after -s and --sport flag in command line
    '-s': sport_item_strs,
    '--sport': sport_item_strs,
}

# Dictionary used with index based completion functions
index_dict = {
    1: food_item_strs,  # Tab complete food items at index 1 in command line
    2: sport_item_strs,  # Tab complete sport items at index 2 in command line
}


class CompletionsExample(cmd2.Cmd):
    """Example cmd2 application used to exercise tab completion tests"""

    def __init__(self) -> None:
        cmd2.Cmd.__init__(self, multiline_commands=['test_multiline'])
        self.foo = 'bar'
        self.add_settable(
            utils.Settable(
                'foo',
                str,
                description="a test settable param",
                settable_object=self,
                completer=CompletionsExample.complete_foo_val,
            )
        )

    def do_test_basic(self, args) -> None:
        pass

    def complete_test_basic(self, text, line, begidx, endidx) -> Completions:
        return self.basic_complete(text, line, begidx, endidx, food_item_strs)

    def do_test_delimited(self, args) -> None:
        pass

    def complete_test_delimited(self, text, line, begidx, endidx) -> Completions:
        return self.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')

    def do_test_sort_key(self, args) -> None:
        pass

    def complete_test_sort_key(self, text, line, begidx, endidx) -> Completions:
        num_strs = ['file2', 'file11', 'file1']
        return self.basic_complete(text, line, begidx, endidx, num_strs)

    def do_test_raise_exception(self, args) -> None:
        pass

    def complete_test_raise_exception(self, text, line, begidx, endidx) -> NoReturn:
        raise IndexError("You are out of bounds!!")

    def do_test_multiline(self, args) -> None:
        pass

    def complete_test_multiline(self, text, line, begidx, endidx) -> Completions:
        return self.basic_complete(text, line, begidx, endidx, sport_item_strs)

    def do_test_no_completer(self, args) -> None:
        """Completing this should result in completedefault() being called"""

    def complete_foo_val(self, text, line, begidx, endidx, arg_tokens) -> Completions:
        """Supports unit testing cmd2.Cmd2.complete_set_val to confirm it passes all tokens in the set command"""
        value = "SUCCESS" if 'param' in arg_tokens else "FAIL"
        return Completions.from_values([value])

    def completedefault(self, *ignored) -> Completions:
        """Method called to complete an input line when no command-specific
        complete_*() method is available.

        """
        return Completions.from_values(['default'])


@pytest.fixture
def cmd2_app():
    return CompletionsExample()


def test_command_completion(cmd2_app) -> None:
    text = 'run'
    line = text
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['run_pyscript', 'run_script']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_command_completion_nomatch(cmd2_app) -> None:
    text = 'fakecommand'
    line = text
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions

    # ArgparseCompleter raises a _NoResultsError in this case
    assert "Hint" in completions.completion_error


def test_complete_bogus_command(cmd2_app) -> None:
    text = ''
    line = f'fizbuzz {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['default']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_complete_exception(cmd2_app) -> None:
    text = ''
    line = f'test_raise_exception {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)

    assert not completions
    assert "IndexError" in completions.completion_error


def test_complete_macro(base_app, request) -> None:
    # Create the macro
    out, _err = run_cmd(base_app, 'macro create fake run_pyscript {1}')
    assert out == normalize("Macro 'fake' created")

    # Macros do path completion
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = f'fake {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'cript.py', text + 'cript.txt', text + 'cripts' + os.path.sep]
    completions = base_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_default_str_sort_key(cmd2_app) -> None:
    text = ''
    line = f'test_sort_key {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    saved_sort_key = utils.DEFAULT_STR_SORT_KEY

    try:
        # First do alphabetical sorting
        utils.set_default_str_sort_key(utils.ALPHABETICAL_SORT_KEY)
        expected = ['file1', 'file11', 'file2']
        completions = cmd2_app.complete(text, line, begidx, endidx)
        assert completions.to_strings() == Completions.from_values(expected).to_strings()

        # Now switch to natural sorting
        utils.set_default_str_sort_key(utils.NATURAL_SORT_KEY)
        expected = ['file1', 'file2', 'file11']
        completions = cmd2_app.complete(text, line, begidx, endidx)
        assert completions.to_strings() == Completions.from_values(expected).to_strings()
    finally:
        utils.set_default_str_sort_key(saved_sort_key)


def test_help_completion(cmd2_app) -> None:
    text = 'h'
    line = f'help {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['help', 'history']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_help_completion_empty_arg(cmd2_app) -> None:
    text = ''
    line = f'help {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = cmd2_app.get_visible_commands()
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_help_completion_nomatch(cmd2_app) -> None:
    text = 'fakecommand'
    line = f'help {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions


def test_set_allow_style_completion(cmd2_app) -> None:
    """Confirm that completing allow_style presents AllowStyle strings"""
    text = ''
    line = 'set allow_style'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = [val.name.lower() for val in cmd2.rich_utils.AllowStyle]
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_set_bool_completion(cmd2_app) -> None:
    """Confirm that completing a boolean Settable presents true and false strings"""
    text = ''
    line = 'set debug'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['false', 'true']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_shell_command_completion_shortcut(cmd2_app) -> None:
    # Made sure ! runs a shell command and all matches start with ! since there
    # isn't a space between ! and the shell command. Display matches won't
    # begin with the !.
    if sys.platform == "win32":
        text = '!calc'
        expected_item = CompletionItem('!calc.exe', display='calc.exe')
    else:
        text = '!egr'
        expected_item = CompletionItem('!egrep', display='egrep')

    expected_completions = Completions([expected_item])

    line = text
    endidx = len(line)
    begidx = 0

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == expected_completions.to_strings()
    assert [item.display for item in completions] == [item.display for item in expected_completions]


def test_shell_command_completion_does_not_match_wildcards(cmd2_app) -> None:
    if sys.platform == "win32":
        text = 'c*'
    else:
        text = 'e*'

    line = f'shell {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions


def test_shell_command_complete(cmd2_app) -> None:
    if sys.platform == "win32":
        text = 'c'
        expected = 'calc.exe'
    else:
        text = 'l'
        expected = 'ls'

    line = f'shell {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert expected in completions.to_strings()


def test_shell_command_completion_nomatch(cmd2_app) -> None:
    text = 'zzzz'
    line = f'shell {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions


def test_shell_command_completion_does_not_complete_when_just_shell(cmd2_app) -> None:
    text = ''
    line = f'shell {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions


def test_shell_command_completion_does_path_completion_when_after_command(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')
    line = f'shell cat {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + '.py']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_shell_command_complete_in_path(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = f'shell {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    # Since this will look for directories and executables in the given path,
    # we expect to see the scripts dir among the results
    expected = os.path.join(test_dir, 'scripts' + os.path.sep)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert expected in completions.to_strings()


def test_path_completion_files_and_directories(cmd2_app, request) -> None:
    """Test that directories include an ending slash and files do not."""
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 's')
    line = f'shell cat {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'cript.py', text + 'cript.txt', text + 'cripts' + os.path.sep]
    completions = cmd2_app.path_complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_path_completion_nomatch(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'fakepath')
    line = f'shell cat {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.path_complete(text, line, begidx, endidx)
    assert not completions


def test_default_to_shell_completion(cmd2_app, request) -> None:
    cmd2_app.default_to_shell = True
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'conftest')

    if sys.platform == "win32":
        command = 'calc.exe'
    else:
        command = 'egrep'

    # Make sure the command is on the testing system
    assert command in utils.get_exes_in_path(command)
    line = f'{command} {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + '.py']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_path_completion_no_text(cmd2_app) -> None:
    # Run path complete with no search text which should show what's in cwd
    text = ''
    line = f'shell ls {text}'
    endidx = len(line)
    begidx = endidx - len(text)
    completions_no_text = cmd2_app.path_complete(text, line, begidx, endidx)

    # Run path complete with path set to the CWD
    text = os.getcwd() + os.path.sep
    line = f'shell ls {text}'
    endidx = len(line)
    begidx = endidx - len(text)
    completions_cwd = cmd2_app.path_complete(text, line, begidx, endidx)

    # To compare matches, strip off the CWD from the front of completions_cwd.
    stripped_paths = [CompletionItem(value=item.text.replace(text, '', 1)) for item in completions_cwd]
    completions_cwd = dataclasses.replace(completions_cwd, items=stripped_paths)

    # Verify that the first test gave results for entries in the cwd
    assert completions_no_text == completions_cwd
    assert completions_cwd


def test_path_completion_no_path(cmd2_app) -> None:
    # Run path complete with search text that isn't preceded by a path. This should use CWD as the path.
    text = 'p'
    line = f'shell ls {text}'
    endidx = len(line)
    begidx = endidx - len(text)
    completions_no_text = cmd2_app.path_complete(text, line, begidx, endidx)

    # Run path complete with path set to the CWD
    text = os.getcwd() + os.path.sep + text
    line = f'shell ls {text}'
    endidx = len(line)
    begidx = endidx - len(text)
    completions_cwd = cmd2_app.path_complete(text, line, begidx, endidx)

    # To compare matches, strip off the CWD from the front of completions_cwd (leave the 's').
    stripped_paths = [CompletionItem(value=item.text.replace(text[:-1], '', 1)) for item in completions_cwd]
    completions_cwd = dataclasses.replace(completions_cwd, items=stripped_paths)

    # Verify that the first test gave results for entries in the cwd
    assert completions_no_text == completions_cwd
    assert completions_cwd


@pytest.mark.skipif(sys.platform == 'win32', reason="this only applies on systems where the root directory is a slash")
def test_path_completion_cwd_is_root_dir(cmd2_app) -> None:
    # Change our CWD to root dir
    cwd = os.getcwd()
    try:
        os.chdir(os.path.sep)

        text = ''
        line = f'shell ls {text}'
        endidx = len(line)
        begidx = endidx - len(text)
        completions = cmd2_app.path_complete(text, line, begidx, endidx)

        # No match should start with a slash
        assert not any(item.text.startswith(os.path.sep) for item in completions)
    finally:
        # Restore CWD
        os.chdir(cwd)


def test_path_completion_does_not_match_wildcards(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c*')
    line = f'shell cat {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    # Currently path completion doesn't accept wildcards, so will always return empty results
    completions = cmd2_app.path_complete(text, line, begidx, endidx)
    assert not completions


def test_path_completion_complete_user(cmd2_app) -> None:
    import getpass

    user = getpass.getuser()

    text = f'~{user}'
    line = f'shell fake {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = text + os.path.sep
    completions = cmd2_app.path_complete(text, line, begidx, endidx)
    assert expected in completions.to_strings()


def test_path_completion_user_path_expansion(cmd2_app) -> None:
    # Run path with a tilde and a slash
    if sys.platform.startswith('win'):
        cmd = 'dir'
    else:
        cmd = 'ls'

    # Use a ~ which will be expanded into the user's home directory
    text = f'~{os.path.sep}'
    line = f'shell {cmd} {text}'
    endidx = len(line)
    begidx = endidx - len(text)
    completions_tilde_slash = cmd2_app.path_complete(text, line, begidx, endidx)

    # To compare matches, strip off ~/ from the front of completions_tilde_slash.
    stripped_paths = [CompletionItem(value=item.text.replace(text, '', 1)) for item in completions_tilde_slash]
    completions_tilde_slash = dataclasses.replace(completions_tilde_slash, items=stripped_paths)

    # Run path complete on the user's home directory
    text = os.path.expanduser('~') + os.path.sep
    line = f'shell {cmd} {text}'
    endidx = len(line)
    begidx = endidx - len(text)
    completions_home = cmd2_app.path_complete(text, line, begidx, endidx)

    # To compare matches, strip off user's home directory from the front of completions_home.
    stripped_paths = [CompletionItem(value=item.text.replace(text, '', 1)) for item in completions_home]
    completions_home = dataclasses.replace(completions_home, items=stripped_paths)

    assert completions_tilde_slash == completions_home


def test_basic_completion(cmd2_app) -> None:
    text = 'P'
    line = f'list_food -f {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['Pizza', 'Potato']
    completions = cmd2_app.basic_complete(text, line, begidx, endidx, food_item_strs)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_basic_completion_nomatch(cmd2_app) -> None:
    text = 'q'
    line = f'list_food -f {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.basic_complete(text, line, begidx, endidx, food_item_strs)
    assert not completions


def test_delimiter_completion_partial(cmd2_app) -> None:
    """Test that a delimiter is added when an item has not been fully completed"""
    text = '/home/'
    line = f'command {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # All matches end with the delimiter
    expected_items = [
        CompletionItem("/home/other user/", display="other user/"),
        CompletionItem("/home/user/", display="user/"),
    ]
    expected_completions = Completions(expected_items)
    completions = cmd2_app.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')

    assert completions.to_strings() == expected_completions.to_strings()
    assert [item.display for item in completions] == [item.display for item in expected_completions]


def test_delimiter_completion_full(cmd2_app) -> None:
    """Test that no delimiter is added when an item has been fully completed"""
    text = '/home/other user/'
    line = f'command {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # No matches end with the delimiter
    expected_items = [
        CompletionItem("/home/other user/maps", display="maps"),
        CompletionItem("/home/other user/tests", display="tests"),
    ]
    expected_completions = Completions(expected_items)
    completions = cmd2_app.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')

    assert completions.to_strings() == expected_completions.to_strings()
    assert [item.display for item in completions] == [item.display for item in expected_completions]


def test_delimiter_completion_nomatch(cmd2_app) -> None:
    text = '/nothing_to_see'
    line = f'command {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.delimiter_complete(text, line, begidx, endidx, delimited_strs, '/')
    assert not completions


def test_flag_based_completion(cmd2_app) -> None:
    text = 'P'
    line = f'list_food -f {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['Pizza', 'Potato']
    completions = cmd2_app.flag_based_complete(text, line, begidx, endidx, flag_dict)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_flag_based_completion_nomatch(cmd2_app) -> None:
    text = 'q'
    line = f'list_food -f {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.flag_based_complete(text, line, begidx, endidx, flag_dict)
    assert not completions


def test_flag_based_default_completer(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = f'list_food {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'onftest.py']
    completions = cmd2_app.flag_based_complete(text, line, begidx, endidx, flag_dict, all_else=cmd2_app.path_complete)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_flag_based_callable_completer(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = f'list_food -o {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    flag_dict['-o'] = cmd2_app.path_complete

    expected = [text + 'onftest.py']
    completions = cmd2_app.flag_based_complete(text, line, begidx, endidx, flag_dict)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_index_based_completion(cmd2_app) -> None:
    text = ''
    line = f'command Pizza {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = sport_item_strs
    completions = cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_index_based_completion_nomatch(cmd2_app) -> None:
    text = 'q'
    line = f'command {text}'
    endidx = len(line)
    begidx = endidx - len(text)
    completions = cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict)
    assert not completions


def test_index_based_default_completer(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = f'command Pizza Bat Computer {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    expected = [text + 'onftest.py']
    completions = cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict, all_else=cmd2_app.path_complete)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_index_based_callable_completer(cmd2_app, request) -> None:
    test_dir = os.path.dirname(request.module.__file__)

    text = os.path.join(test_dir, 'c')
    line = f'command Pizza Bat {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    index_dict[3] = cmd2_app.path_complete

    expected = [text + 'onftest.py']
    completions = cmd2_app.index_based_complete(text, line, begidx, endidx, index_dict)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_tokens_for_completion_quoted(cmd2_app) -> None:
    text = 'Pi'
    line = f'list_food "{text}"'
    endidx = len(line)
    begidx = endidx

    expected_tokens = ['list_food', 'Pi', '']
    expected_raw_tokens = ['list_food', '"Pi"', '']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens


def test_tokens_for_completion_unclosed_quote(cmd2_app) -> None:
    text = 'Pi'
    line = f'list_food "{text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected_tokens = ['list_food', 'Pi']
    expected_raw_tokens = ['list_food', '"Pi']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens


def test_tokens_for_completion_punctuation(cmd2_app) -> None:
    """Test that redirectors and terminators are word delimiters"""
    text = 'file'
    line = f'command | < ;>>{text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected_tokens = ['command', '|', '<', ';', '>>', 'file']
    expected_raw_tokens = ['command', '|', '<', ';', '>>', 'file']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens


def test_tokens_for_completion_quoted_punctuation(cmd2_app) -> None:
    """Test that quoted punctuation characters are not word delimiters"""
    text = '>file'
    line = f'command "{text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected_tokens = ['command', '>file']
    expected_raw_tokens = ['command', '">file']

    tokens, raw_tokens = cmd2_app.tokens_for_completion(line, begidx, endidx)
    assert expected_tokens == tokens
    assert expected_raw_tokens == raw_tokens


def test_add_opening_quote_double_quote_added(cmd2_app) -> None:
    text = 'Ha'
    line = f'test_basic {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # At least one match has a space, so quote them all
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions._add_opening_quote
    assert completions._quote_char == '"'


def test_add_opening_quote_single_quote_added(cmd2_app) -> None:
    text = 'Ch'
    line = f'test_basic {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # At least one match contains a double quote, so quote them all with a single quote
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions._add_opening_quote
    assert completions._quote_char == "'"


def test_add_opening_quote_nothing_added(cmd2_app) -> None:
    text = 'P'
    line = f'test_basic {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # No matches have a space so don't quote them
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions._add_opening_quote
    assert not completions._quote_char


def test_word_break_in_quote(cmd2_app) -> None:
    """Test case where search text has a space and is in a quote."""

    # Cmd2Completer still performs word breaks after a quote. Since space
    # is word-break character, it says the search text starts at 'S' and
    # passes that to the complete() function.
    text = 'S'
    line = 'test_basic "Ham S'
    endidx = len(line)
    begidx = endidx - len(text)

    # Since the search text is within an opening quote, cmd2 will rebuild
    # the whole search token as 'Ham S' and match it to 'Ham Sandwich'.
    # But before it returns the results back to Cmd2Completer, it removes
    # anything before the original search text since this is what Cmd2Completer
    # expects. Therefore the actual match text is 'Sandwich'.
    expected = ["Sandwich"]
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_no_completer(cmd2_app) -> None:
    text = ''
    line = f'test_no_completer {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['default']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_word_break_in_command(cmd2_app) -> None:
    text = ''
    line = f'"{text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions


def test_complete_multiline_on_single_line(cmd2_app) -> None:
    text = ''
    line = f'test_multiline {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['Basket', 'Basketball', 'Bat', 'Football', 'Space Ball']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_complete_multiline_on_multiple_lines(cmd2_app) -> None:
    # Set the same variables _complete_statement() sets when a user is entering data at a continuation prompt
    cmd2_app._at_continuation_prompt = True
    cmd2_app._multiline_in_progress = "test_multiline\n"

    text = 'Ba'
    line = f'{text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['Bat', 'Basket', 'Basketball']
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_completions_iteration() -> None:
    items = [CompletionItem(1), CompletionItem(2)]
    completions = Completions(items)

    # Test __iter__
    assert list(completions) == items

    # Test __reversed__
    assert list(reversed(completions)) == items[::-1]


# Used by redirect_complete tests
class RedirCompType(enum.Enum):
    SHELL_CMD = (1,)
    PATH = (2,)
    DEFAULT = (3,)
    NONE = 4


@pytest.mark.parametrize(
    ('line', 'comp_type'),
    [
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
    ],
)
def test_redirect_complete(cmd2_app, monkeypatch, line, comp_type) -> None:
    # Test both cases of allow_redirection
    cmd2_app.allow_redirection = True
    for _ in range(2):
        shell_cmd_complete_mock = mock.MagicMock(name='shell_cmd_complete')
        monkeypatch.setattr("cmd2.Cmd.shell_cmd_complete", shell_cmd_complete_mock)

        path_complete_mock = mock.MagicMock(name='path_complete')
        monkeypatch.setattr("cmd2.Cmd.path_complete", path_complete_mock)

        default_complete_mock = mock.MagicMock(name='fake_completer')

        text = ''
        line = f'{line} {text}'
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


def test_complete_set_value(cmd2_app) -> None:
    text = ''
    line = f'set foo {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ["SUCCESS"]
    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()
    assert completions.completion_hint.strip() == "Hint:\n  value  a test settable param"


def test_complete_set_value_invalid_settable(cmd2_app) -> None:
    text = ''
    line = f'set fake {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = cmd2_app.complete(text, line, begidx, endidx)
    assert not completions
    assert "fake is not a settable parameter" in completions.completion_error


@pytest.fixture
def sc_app():
    c = SubcommandsExample()
    c.stdout = utils.StdSim(c.stdout)
    return c


def test_cmd2_subcommand_completion(sc_app) -> None:
    text = ''
    line = f'base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['bar', 'foo', 'sport']
    completions = sc_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_cmd2_subcommand_completion_nomatch(sc_app) -> None:
    text = 'z'
    line = f'base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = sc_app.complete(text, line, begidx, endidx)
    assert not completions


def test_help_subcommand_completion_multiple(sc_app) -> None:
    text = ''
    line = f'help base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['bar', 'foo', 'sport']
    completions = sc_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_help_subcommand_completion_nomatch(sc_app) -> None:
    text = 'z'
    line = f'help base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = sc_app.complete(text, line, begidx, endidx)
    assert not completions


def test_subcommand_tab_completion(sc_app) -> None:
    # This makes sure the correct completer for the sport subcommand is called
    text = 'Foot'
    line = f'base sport {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['Football']
    completions = sc_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_subcommand_tab_completion_with_no_completer(sc_app) -> None:
    # This tests what happens when a subcommand has no completer
    # In this case, the foo subcommand has no completer defined
    text = 'Foot'
    line = f'base foo {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = sc_app.complete(text, line, begidx, endidx)
    assert not completions


####################################################


class SubcommandsWithUnknownExample(cmd2.Cmd):
    """Example cmd2 application where we a base command which has a couple subcommands
    and the "sport" subcommand has tab completion enabled.
    """

    def __init__(self) -> None:
        cmd2.Cmd.__init__(self)

    # subcommand functions for the base command
    def base_foo(self, args) -> None:
        """Foo subcommand of base command"""
        self.poutput(args.x * args.y)

    def base_bar(self, args) -> None:
        """Bar subcommand of base command"""
        self.poutput(f'(({args.z}))')

    def base_sport(self, args) -> None:
        """Sport subcommand of base command"""
        self.poutput(f'Sport is {args.sport}')

    # create the top-level parser for the base command
    base_parser = cmd2.Cmd2ArgumentParser()
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
    def do_base(self, args) -> None:
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
    """Declare test fixture for with_argparser decorator"""
    return SubcommandsWithUnknownExample()


def test_subcmd_with_unknown_completion(scu_app) -> None:
    text = ''
    line = f'base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['bar', 'foo', 'sport']
    completions = scu_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_subcmd_with_unknown_completion_nomatch(scu_app) -> None:
    text = 'z'
    line = f'base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = scu_app.complete(text, line, begidx, endidx)
    assert not completions


def test_help_subcommand_completion_scu(scu_app) -> None:
    text = ''
    line = f'help base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['bar', 'foo', 'sport']
    completions = scu_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_help_subcommand_completion_with_flags_before_command(scu_app) -> None:
    text = ''
    line = f'help -h -v base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['bar', 'foo', 'sport']
    completions = scu_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_complete_help_subcommands_with_blank_command(scu_app) -> None:
    text = ''
    line = f'help "" {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = scu_app.complete(text, line, begidx, endidx)
    assert not completions


def test_help_subcommand_completion_nomatch_scu(scu_app) -> None:
    text = 'z'
    line = f'help base {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = scu_app.complete(text, line, begidx, endidx)
    assert not completions


def test_subcommand_tab_completion_scu(scu_app) -> None:
    # This makes sure the correct completer for the sport subcommand is called
    text = 'Foot'
    line = f'base sport {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected = ['Football']
    completions = scu_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_subcommand_tab_completion_with_no_completer_scu(scu_app) -> None:
    # This tests what happens when a subcommand has no completer
    # In this case, the foo subcommand has no completer defined
    text = 'Foot'
    line = f'base foo {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = scu_app.complete(text, line, begidx, endidx)
    assert not completions
