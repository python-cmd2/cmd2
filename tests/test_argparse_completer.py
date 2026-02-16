"""Unit/functional testing for argparse completer in cmd2"""

import argparse
from typing import cast

import pytest
from rich.text import Text

import cmd2
import cmd2.string_utils as su
from cmd2 import (
    Choices,
    Cmd2ArgumentParser,
    CompletionError,
    CompletionItem,
    Completions,
    argparse_completer,
    argparse_custom,
    with_argparser,
)
from cmd2 import rich_utils as ru

from .conftest import (
    normalize,
    run_cmd,
    with_ansi_style,
)

# Data and functions for testing standalone choice_provider and completer
standalone_choices = ['standalone', 'provider']
standalone_completions = ['standalone', 'completer']


def standalone_choice_provider(cli: cmd2.Cmd) -> Choices:
    return Choices.from_values(standalone_choices)


def standalone_completer(cli: cmd2.Cmd, text: str, line: str, begidx: int, endidx: int) -> Completions:
    return cli.basic_complete(text, line, begidx, endidx, standalone_completions)


class ArgparseCompleterTester(cmd2.Cmd):
    """Cmd2 app that exercises ArgparseCompleter class"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    ############################################################################################################
    # Begin code related to help and command name completion
    ############################################################################################################
    # Top level parser for music command
    music_parser = Cmd2ArgumentParser(description='Manage music')

    # Add subcommands to music
    music_subparsers = music_parser.add_subparsers()
    music_create_parser = music_subparsers.add_parser('create', help='create music')

    # Add subcommands to music -> create
    music_create_subparsers = music_create_parser.add_subparsers()
    music_create_jazz_parser = music_create_subparsers.add_parser('jazz', help='create jazz')
    music_create_rock_parser = music_create_subparsers.add_parser('rock', help='create rock')

    @with_argparser(music_parser)
    def do_music(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to flag completion
    ############################################################################################################

    # Uses default flag prefix value (-)
    flag_parser = Cmd2ArgumentParser()
    flag_parser.add_argument('-n', '--normal_flag', help='a normal flag', action='store_true')
    flag_parser.add_argument('-a', '--append_flag', help='append flag', action='append')
    flag_parser.add_argument('-o', '--append_const_flag', help='append const flag', action='append_const', const=True)
    flag_parser.add_argument('-c', '--count_flag', help='count flag', action='count')
    flag_parser.add_argument('-e', '--extend_flag', help='extend flag', action='extend')
    flag_parser.add_argument('-s', '--suppressed_flag', help=argparse.SUPPRESS, action='store_true')
    flag_parser.add_argument('-r', '--remainder_flag', nargs=argparse.REMAINDER, help='a remainder flag')
    flag_parser.add_argument('-q', '--required_flag', required=True, help='a required flag', action='store_true')

    @with_argparser(flag_parser)
    def do_flag(self, args: argparse.Namespace) -> None:
        pass

    # Uses non-default flag prefix value (+)
    plus_flag_parser = Cmd2ArgumentParser(prefix_chars='+')
    plus_flag_parser.add_argument('+n', '++normal_flag', help='a normal flag', action='store_true')
    plus_flag_parser.add_argument('+q', '++required_flag', required=True, help='a required flag', action='store_true')

    @with_argparser(plus_flag_parser)
    def do_plus_flag(self, args: argparse.Namespace) -> None:
        pass

    # A parser with a positional and flags. Used to test that remaining flag names are completed when all positionals are done.
    pos_and_flag_parser = Cmd2ArgumentParser()
    pos_and_flag_parser.add_argument("positional", choices=["a", "choice"])
    pos_and_flag_parser.add_argument("-f", "--flag", action='store_true')

    @with_argparser(pos_and_flag_parser)
    def do_pos_and_flag(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to testing choices and choices_provider parameters
    ############################################################################################################
    STR_METAVAR = "HEADLESS"
    TUPLE_METAVAR = ('arg1', 'others')
    CUSTOM_TABLE_HEADER = ("Custom Header",)

    # tuples (for sake of immutability) used in our tests (there is a mix of sorted and unsorted on purpose)
    non_negative_num_choices = (1, 2, 3, 0.5, 22)
    num_choices = (-1, 1, -2, 2.5, 0, -12)
    static_choices_list = ('static', 'choices', 'stop', 'here')
    choices_from_provider = ('choices', 'provider', 'probably', 'improved')
    completion_item_choices = (
        CompletionItem('choice_1', table_row=['Description 1']),
        # Make this the longest description so we can test display width.
        CompletionItem('choice_2', table_row=[su.stylize("String with style", style=cmd2.Color.BLUE)]),
        CompletionItem('choice_3', table_row=[Text("Text with style", style=cmd2.Color.RED)]),
    )

    # This tests that CompletionItems created with numerical values are sorted as numbers.
    num_completion_items = (
        CompletionItem(5, table_row=["Five"]),
        CompletionItem(1.5, table_row=["One.Five"]),
        CompletionItem(2, table_row=["Five"]),
    )

    def choices_provider(self) -> Choices:
        """Method that provides choices"""
        return Choices.from_values(self.choices_from_provider)

    def completion_item_method(self) -> list[CompletionItem]:
        """Choices method that returns CompletionItems"""
        items = []
        for i in range(10):
            main_str = f'main_str{i}'
            items.append(CompletionItem(main_str, table_row=['blah blah']))
        return items

    choices_parser = Cmd2ArgumentParser()

    # Flag args for choices command. Include string and non-string arg types.
    choices_parser.add_argument("-l", "--list", help="a flag populated with a choices list", choices=static_choices_list)
    choices_parser.add_argument(
        "-p", "--provider", help="a flag populated with a choices provider", choices_provider=choices_provider
    )
    choices_parser.add_argument(
        "--table_header",
        help='this arg has a table header',
        choices_provider=completion_item_method,
        table_header=CUSTOM_TABLE_HEADER,
    )
    choices_parser.add_argument(
        "--no_header",
        help='this arg has no table header',
        choices_provider=completion_item_method,
        metavar=STR_METAVAR,
    )
    choices_parser.add_argument(
        '-t',
        "--tuple_metavar",
        help='this arg has tuple for a metavar',
        choices_provider=completion_item_method,
        metavar=TUPLE_METAVAR,
        nargs=argparse.ONE_OR_MORE,
    )
    choices_parser.add_argument('-n', '--num', type=int, help='a flag with an int type', choices=num_choices)
    choices_parser.add_argument('--completion_items', help='choices are CompletionItems', choices=completion_item_choices)
    choices_parser.add_argument(
        '--num_completion_items', help='choices are numerical CompletionItems', choices=num_completion_items
    )

    # Positional args for choices command
    choices_parser.add_argument("list_pos", help="a positional populated with a choices list", choices=static_choices_list)
    choices_parser.add_argument(
        "method_pos", help="a positional populated with a choices provider", choices_provider=choices_provider
    )
    choices_parser.add_argument(
        'non_negative_num', type=int, help='a positional with non-negative numerical choices', choices=non_negative_num_choices
    )
    choices_parser.add_argument('empty_choices', help='a positional with empty choices', choices=[])

    @with_argparser(choices_parser)
    def do_choices(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to testing completer parameter
    ############################################################################################################
    completions_for_flag = ('completions', 'flag', 'fairly', 'complete')
    completions_for_pos_1 = ('completions', 'positional_1', 'probably', 'missed', 'spot')
    completions_for_pos_2 = ('completions', 'positional_2', 'probably', 'missed', 'me')

    def flag_completer(self, text: str, line: str, begidx: int, endidx: int) -> Completions:
        return self.basic_complete(text, line, begidx, endidx, self.completions_for_flag)

    def pos_1_completer(self, text: str, line: str, begidx: int, endidx: int) -> Completions:
        return self.basic_complete(text, line, begidx, endidx, self.completions_for_pos_1)

    def pos_2_completer(self, text: str, line: str, begidx: int, endidx: int) -> Completions:
        return self.basic_complete(text, line, begidx, endidx, self.completions_for_pos_2)

    completer_parser = Cmd2ArgumentParser()

    # Flag args for completer command
    completer_parser.add_argument("-c", "--completer", help="a flag using a completer", completer=flag_completer)

    # Positional args for completer command
    completer_parser.add_argument("pos_1", help="a positional using a completer method", completer=pos_1_completer)
    completer_parser.add_argument("pos_2", help="a positional using a completer method", completer=pos_2_completer)

    @with_argparser(completer_parser)
    def do_completer(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to nargs
    ############################################################################################################
    set_value_choices = ('set', 'value', 'choices')
    one_or_more_choices = ('one', 'or', 'more', 'choices')
    optional_choices = ('a', 'few', 'optional', 'choices')
    range_choices = ('some', 'range', 'choices')
    remainder_choices = ('remainder', 'choices')
    positional_choices = ('the', 'positional', 'choices')

    nargs_parser = Cmd2ArgumentParser()

    # Flag args for nargs command
    nargs_parser.add_argument("--set_value", help="a flag with a set value for nargs", nargs=2, choices=set_value_choices)
    nargs_parser.add_argument(
        "--one_or_more", help="a flag wanting one or more args", nargs=argparse.ONE_OR_MORE, choices=one_or_more_choices
    )
    nargs_parser.add_argument(
        "--optional", help="a flag with an optional value", nargs=argparse.OPTIONAL, choices=optional_choices
    )
    nargs_parser.add_argument("--range", help="a flag with nargs range", nargs=(1, 2), choices=range_choices)
    nargs_parser.add_argument(
        "--remainder", help="a flag wanting remaining", nargs=argparse.REMAINDER, choices=remainder_choices
    )

    nargs_parser.add_argument("normal_pos", help="a remainder positional", nargs=2, choices=positional_choices)
    nargs_parser.add_argument(
        "remainder_pos", help="a remainder positional", nargs=argparse.REMAINDER, choices=remainder_choices
    )

    @with_argparser(nargs_parser)
    def do_nargs(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to testing tab hints
    ############################################################################################################
    hint_parser = Cmd2ArgumentParser()
    hint_parser.add_argument('-f', '--flag', help='a flag arg')
    hint_parser.add_argument('-s', '--suppressed_help', help=argparse.SUPPRESS)
    hint_parser.add_argument('-t', '--suppressed_hint', help='a flag arg', suppress_tab_hint=True)

    hint_parser.add_argument('hint_pos', help='here is a hint\nwith new lines')
    hint_parser.add_argument('no_help_pos')

    @with_argparser(hint_parser)
    def do_hint(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to CompletionError
    ############################################################################################################
    def completer_raise_error(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """Raises CompletionError"""
        raise CompletionError('completer broke something')

    def choice_raise_error(self) -> list[str]:
        """Raises CompletionError"""
        raise CompletionError('choice broke something')

    comp_error_parser = Cmd2ArgumentParser()
    comp_error_parser.add_argument('completer_pos', help='positional arg', completer=completer_raise_error)
    comp_error_parser.add_argument('--choice', help='flag arg', choices_provider=choice_raise_error)

    @with_argparser(comp_error_parser)
    def do_raise_completion_error(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to receiving arg_tokens
    ############################################################################################################
    def choices_takes_arg_tokens(self, arg_tokens: dict[str, list[str]]) -> Choices:
        """Choices function that receives arg_tokens from ArgparseCompleter"""
        return Choices.from_values([arg_tokens['parent_arg'][0], arg_tokens['subcommand'][0]])

    def completer_takes_arg_tokens(
        self, text: str, line: str, begidx: int, endidx: int, arg_tokens: dict[str, list[str]]
    ) -> Completions:
        """Completer function that receives arg_tokens from ArgparseCompleter"""
        match_against = [arg_tokens['parent_arg'][0], arg_tokens['subcommand'][0]]
        return self.basic_complete(text, line, begidx, endidx, match_against)

    arg_tokens_parser = Cmd2ArgumentParser()
    arg_tokens_parser.add_argument('parent_arg', help='arg from a parent parser')

    # Create a subcommand to exercise receiving parent_tokens and subcommand name in arg_tokens
    arg_tokens_subparser = arg_tokens_parser.add_subparsers(dest='subcommand')
    arg_tokens_subcmd_parser = arg_tokens_subparser.add_parser('subcmd')

    arg_tokens_subcmd_parser.add_argument('choices_pos', choices_provider=choices_takes_arg_tokens)
    arg_tokens_subcmd_parser.add_argument('completer_pos', completer=completer_takes_arg_tokens)

    # Used to override parent_arg in arg_tokens_parser
    arg_tokens_subcmd_parser.add_argument('--parent_arg')

    @with_argparser(arg_tokens_parser)
    def do_arg_tokens(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to mutually exclusive groups
    ############################################################################################################
    mutex_parser = Cmd2ArgumentParser()

    mutex_group = mutex_parser.add_mutually_exclusive_group(required=True)
    mutex_group.add_argument('optional_pos', help='the optional positional', nargs=argparse.OPTIONAL)
    mutex_group.add_argument('-f', '--flag', help='the flag arg')
    mutex_group.add_argument('-o', '--other_flag', help='the other flag arg')

    mutex_parser.add_argument('last_arg', help='the last arg')

    @with_argparser(mutex_parser)
    def do_mutex(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to standalone functions
    ############################################################################################################
    standalone_parser = Cmd2ArgumentParser()
    standalone_parser.add_argument('--provider', help='standalone provider', choices_provider=standalone_choice_provider)
    standalone_parser.add_argument('--completer', help='standalone completer', completer=standalone_completer)

    @with_argparser(standalone_parser)
    def do_standalone(self, args: argparse.Namespace) -> None:
        pass

    ############################################################################################################
    # Begin code related to display_meta data
    ############################################################################################################
    meta_parser = Cmd2ArgumentParser()

    # Add subcommands to meta
    meta_subparsers = meta_parser.add_subparsers()

    # Create subcommands with and without help text
    meta_helpful_parser = meta_subparsers.add_parser('helpful', help='my helpful text')
    meta_helpless_parser = meta_subparsers.add_parser('helpless')

    # Create flags with and without help text
    meta_helpful_parser.add_argument('--helpful_flag', help="a helpful flag")
    meta_helpless_parser.add_argument('--helpless_flag')

    @with_argparser(meta_parser)
    def do_meta(self, args: argparse.Namespace) -> None:
        pass


@pytest.fixture
def ac_app() -> ArgparseCompleterTester:
    return ArgparseCompleterTester()


@pytest.mark.parametrize('command', ['music', 'music create', 'music create rock', 'music create jazz'])
def test_help(ac_app, command) -> None:
    out1, _err1 = run_cmd(ac_app, f'{command} -h')
    out2, _err2 = run_cmd(ac_app, f'help {command}')
    assert out1 == out2


def test_bad_subcommand_help(ac_app) -> None:
    # These should give the same output because the second one isn't using a
    # real subcommand, so help will be called on the music command instead.
    out1, _err1 = run_cmd(ac_app, 'help music')
    out2, _err2 = run_cmd(ac_app, 'help music fake')
    assert out1 == out2


@pytest.mark.parametrize(
    ('command', 'text', 'expected'),
    [
        ('', 'mus', ['music']),
        ('music', 'cre', ['create']),
        ('music', 'creab', []),
        ('music create', '', ['jazz', 'rock']),
        ('music crea', 'jazz', []),
        ('music create', 'foo', []),
        ('fake create', '', []),
        ('music fake', '', []),
    ],
)
def test_complete_help(ac_app, command, text, expected) -> None:
    line = f'help {command} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    ('subcommand', 'text', 'expected'),
    [
        ('create', '', ['jazz', 'rock']),
        ('create', 'ja', ['jazz']),
        ('create', 'foo', []),
        ('creab', 'ja', []),
    ],
)
def test_subcommand_completions(ac_app, subcommand, text, expected) -> None:
    line = f'music {subcommand} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    # expected_data is a list of tuples with completion text and display values
    ('command_and_args', 'text', 'expected_data'),
    [
        # Complete all flags (suppressed will not show)
        (
            'flag',
            '-',
            [
                ("-a", "[-a, --append_flag]"),
                ("-c", "[-c, --count_flag]"),
                ('-e', '[-e, --extend_flag]'),
                ("-h", "[-h, --help]"),
                ("-n", "[-n, --normal_flag]"),
                ("-o", "[-o, --append_const_flag]"),
                ("-q", "-q, --required_flag"),
                ("-r", "[-r, --remainder_flag]"),
            ],
        ),
        (
            'flag',
            '--',
            [
                ('--append_const_flag', '[--append_const_flag]'),
                ('--append_flag', '[--append_flag]'),
                ('--count_flag', '[--count_flag]'),
                ('--extend_flag', '[--extend_flag]'),
                ('--help', '[--help]'),
                ('--normal_flag', '[--normal_flag]'),
                ('--remainder_flag', '[--remainder_flag]'),
                ('--required_flag', '--required_flag'),
            ],
        ),
        # Complete individual flag
        ('flag', '-n', [('-n', '[-n]')]),
        ('flag', '--n', [('--normal_flag', '[--normal_flag]')]),
        # No flags should complete until current flag has its args
        ('flag --append_flag', '-', []),
        # Complete REMAINDER flag name
        ('flag', '-r', [('-r', '[-r]')]),
        ('flag', '--rem', [('--remainder_flag', '[--remainder_flag]')]),
        # No flags after a REMAINDER should complete
        ('flag -r value', '-', []),
        ('flag --remainder_flag value', '--', []),
        # Suppressed flag should not complete
        ('flag', '-s', []),
        ('flag', '--s', []),
        # A used flag should not show in completions
        (
            'flag -n',
            '--',
            [
                ('--append_const_flag', '[--append_const_flag]'),
                ('--append_flag', '[--append_flag]'),
                ('--count_flag', '[--count_flag]'),
                ('--extend_flag', '[--extend_flag]'),
                ('--help', '[--help]'),
                ('--remainder_flag', '[--remainder_flag]'),
                ('--required_flag', '--required_flag'),
            ],
        ),
        # Flags with actions set to append, append_const, extend, and count will always show even if they've been used
        (
            'flag --append_flag value --append_const_flag --count_flag --extend_flag value',
            '--',
            [
                ('--append_const_flag', '[--append_const_flag]'),
                ('--append_flag', '[--append_flag]'),
                ('--count_flag', '[--count_flag]'),
                ('--extend_flag', '[--extend_flag]'),
                ('--help', '[--help]'),
                ('--normal_flag', '[--normal_flag]'),
                ('--remainder_flag', '[--remainder_flag]'),
                ('--required_flag', '--required_flag'),
            ],
        ),
        # Non-default flag prefix character (+)
        (
            'plus_flag',
            '+',
            [
                ('+h', '[+h, ++help]'),
                ('+n', '[+n, ++normal_flag]'),
                ('+q', '+q, ++required_flag'),
            ],
        ),
        (
            'plus_flag',
            '++',
            [
                ('++help', '[++help]'),
                ('++normal_flag', '[++normal_flag]'),
                ('++required_flag', '++required_flag'),
            ],
        ),
        # Flag completion should not occur after '--' since that tells argparse all remaining arguments are non-flags
        ('flag --', '--', []),
        ('flag --help --', '--', []),
        ('plus_flag --', '++', []),
        ('plus_flag ++help --', '++', []),
        # Test remaining flag names complete after all positionals are complete
        ('pos_and_flag', '', [('a', 'a'), ('choice', 'choice')]),
        ('pos_and_flag choice ', '', [('-f', '[-f, --flag]'), ('-h', '[-h, --help]')]),
        ('pos_and_flag choice -f ', '', [('-h', '[-h, --help]')]),
        ('pos_and_flag choice -f -h ', '', []),
    ],
)
def test_autcomp_flag_completion(ac_app, command_and_args, text, expected_data) -> None:
    line = f'{command_and_args} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    expected_completions = Completions(items=[CompletionItem(value=v, display=d) for v, d in expected_data])
    completions = ac_app.complete(text, line, begidx, endidx)

    assert completions.to_strings() == expected_completions.to_strings()
    assert [item.display for item in completions] == [item.display for item in expected_completions]


@pytest.mark.parametrize(
    ('flag', 'text', 'expected'),
    [
        ('-l', '', ArgparseCompleterTester.static_choices_list),
        ('--list', 's', ['static', 'stop']),
        ('-p', '', ArgparseCompleterTester.choices_from_provider),
        ('--provider', 'pr', ['provider', 'probably']),
        ('-n', '', ArgparseCompleterTester.num_choices),
        ('--num', '1', ['1']),
        ('--num', '-', [-1, -2, -12]),
        ('--num', '-1', [-1, -12]),
        ('--num_completion_items', '', ArgparseCompleterTester.num_completion_items),
    ],
)
def test_autocomp_flag_choices_completion(ac_app, flag, text, expected) -> None:
    line = f'choices {flag} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    ('pos', 'text', 'expected'),
    [
        (1, '', ArgparseCompleterTester.static_choices_list),
        (1, 's', ['static', 'stop']),
        (2, '', ArgparseCompleterTester.choices_from_provider),
        (2, 'pr', ['provider', 'probably']),
        (3, '', ArgparseCompleterTester.non_negative_num_choices),
        (3, '2', [2, 22]),
        (4, '', []),
    ],
)
def test_autocomp_positional_choices_completion(ac_app, pos, text, expected) -> None:
    # Generate line where preceding positionals are already filled
    line = 'choices {} {}'.format('foo ' * (pos - 1), text)
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    ('flag', 'text', 'expected'),
    [
        ('-c', '', ArgparseCompleterTester.completions_for_flag),
        ('--completer', 'f', ['flag', 'fairly']),
    ],
)
def test_autocomp_flag_completers(ac_app, flag, text, expected) -> None:
    line = f'completer {flag} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    ('pos', 'text', 'expected'),
    [
        (1, '', ArgparseCompleterTester.completions_for_pos_1),
        (1, 'p', ['positional_1', 'probably']),
        (2, '', ArgparseCompleterTester.completions_for_pos_2),
        (2, 'm', ['missed', 'me']),
    ],
)
def test_autocomp_positional_completers(ac_app, pos, text, expected) -> None:
    # Generate line were preceding positionals are already filled
    line = 'completer {} {}'.format('foo ' * (pos - 1), text)
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


def test_autocomp_blank_token(ac_app) -> None:
    """Force a blank token to make sure ArgparseCompleter consumes them like argparse does"""
    from cmd2.argparse_completer import (
        ArgparseCompleter,
    )

    blank = ''

    # Blank flag arg will be consumed. Therefore we expect to be completing the first positional.
    text = ''
    line = f'completer -c {blank} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completer = ArgparseCompleter(ac_app.completer_parser, ac_app)
    tokens = ['-c', blank, text]
    completions = completer.complete(text, line, begidx, endidx, tokens)
    expected = ArgparseCompleterTester.completions_for_pos_1
    assert completions.to_strings() == Completions.from_values(expected).to_strings()

    # Blank arg for first positional will be consumed. Therefore we expect to be completing the second positional.
    text = ''
    line = f'completer {blank} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completer = ArgparseCompleter(ac_app.completer_parser, ac_app)
    tokens = [blank, text]
    completions = completer.complete(text, line, begidx, endidx, tokens)
    expected = ArgparseCompleterTester.completions_for_pos_2
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@with_ansi_style(ru.AllowStyle.ALWAYS)
def test_completion_tables(ac_app) -> None:
    # First test completion table created from strings
    text = ''
    line = f'choices --completion_items {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert len(completions) == len(ac_app.completion_item_choices)
    lines = completions.completion_table.splitlines()

    # Since the completion table was created from strings, the left-most column is left-aligned.
    # Therefore choice_1 will begin the line (with 1 space for padding).
    assert lines[2].startswith(' choice_1')
    assert lines[2].strip().endswith('Description 1')

    # Verify that the styled string was converted to a Rich Text object so that
    # Rich could correctly calculate its display width. Since it was the longest
    # description in the table, we should only see one space of padding after it.
    assert lines[3].endswith("\x1b[34mString with style\x1b[0m ")

    # Verify that the styled Rich Text also rendered.
    assert lines[4].endswith("\x1b[31mText with style  \x1b[0m ")

    # Now test completion table created from numbers
    text = ''
    line = f'choices --num_completion_items {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert len(completions) == len(ac_app.num_completion_items)
    lines = completions.completion_table.splitlines()

    # Since the completion table was created from numbers, the left-most column is right-aligned.
    # Therefore 1.5 will be right-aligned.
    assert lines[2].startswith("                  1.5")
    assert lines[2].strip().endswith('One.Five')


@pytest.mark.parametrize(
    ('num_aliases', 'show_table'),
    [
        # The number of completion results determines if a completion table is displayed.
        # The count must be greater than 1 and less than ac_app.max_completion_table_items,
        # which defaults to 50.
        (1, False),
        (5, True),
        (100, False),
    ],
)
def test_max_completion_table_items(ac_app, num_aliases, show_table) -> None:
    # Create aliases
    for i in range(num_aliases):
        run_cmd(ac_app, f'alias create fake_alias{i} help')

    assert len(ac_app.aliases) == num_aliases

    text = 'fake_alias'
    line = f'alias list {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert len(completions) == num_aliases
    assert bool(completions.completion_table) == show_table


@pytest.mark.parametrize(
    ('args', 'expected'),
    [
        # Flag with nargs = 2
        ('--set_value', ArgparseCompleterTester.set_value_choices),
        ('--set_value set', ['value', 'choices']),
        # Both args are filled. At positional arg now.
        ('--set_value set value', ArgparseCompleterTester.positional_choices),
        # Using the flag again will reset the choices available
        ('--set_value set value --set_value', ArgparseCompleterTester.set_value_choices),
        # Flag with nargs = ONE_OR_MORE
        ('--one_or_more', ArgparseCompleterTester.one_or_more_choices),
        ('--one_or_more one', ['or', 'more', 'choices']),
        # Flag with nargs = OPTIONAL
        ('--optional', ArgparseCompleterTester.optional_choices),
        # Only one arg allowed for an OPTIONAL. At positional now.
        ('--optional optional', ArgparseCompleterTester.positional_choices),
        # Flag with nargs range (1, 2)
        ('--range', ArgparseCompleterTester.range_choices),
        ('--range some', ['range', 'choices']),
        # Already used 2 args so at positional
        ('--range some range', ArgparseCompleterTester.positional_choices),
        # Flag with nargs = REMAINDER
        ('--remainder', ArgparseCompleterTester.remainder_choices),
        ('--remainder remainder ', ['choices']),
        # No more flags can appear after a REMAINDER flag)
        ('--remainder choices --set_value', ['remainder']),
        # Double dash ends the current flag
        ('--range choice --', ArgparseCompleterTester.positional_choices),
        # Double dash ends a REMAINDER flag
        ('--remainder remainder --', ArgparseCompleterTester.positional_choices),
        # No more flags after a double dash
        ('-- --one_or_more ', ArgparseCompleterTester.positional_choices),
        # Consume positional
        ('', ArgparseCompleterTester.positional_choices),
        ('positional', ['the', 'choices']),
        # Intermixed flag and positional
        ('positional --set_value', ArgparseCompleterTester.set_value_choices),
        ('positional --set_value set', ['choices', 'value']),
        # Intermixed flag and positional with flag finishing
        ('positional --set_value set value', ['the', 'choices']),
        ('positional --range choice --', ['the', 'choices']),
        # REMAINDER positional
        ('the positional', ArgparseCompleterTester.remainder_choices),
        ('the positional remainder', ['choices']),
        ('the positional remainder choices', []),
        # REMAINDER positional. Flags don't work in REMAINDER
        ('the positional --set_value', ArgparseCompleterTester.remainder_choices),
        ('the positional remainder --set_value', ['choices']),
    ],
)
def test_autcomp_nargs(ac_app, args, expected) -> None:
    text = ''
    line = f'nargs {args} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    ('command_and_args', 'text', 'is_error'),
    [
        # Flag is finished before moving on
        ('hint --flag foo --', '', False),
        ('hint --flag foo --help', '', False),
        ('hint --flag foo', '--', False),
        ('nargs --one_or_more one --', '', False),
        ('nargs --one_or_more one or --set_value', '', False),
        ('nargs --one_or_more one or more', '--', False),
        ('nargs --set_value set value --', '', False),
        ('nargs --set_value set value --one_or_more', '', False),
        ('nargs --set_value set value', '--', False),
        ('nargs --set_val set value', '--', False),  # This exercises our abbreviated flag detection
        ('nargs --range choices --', '', False),
        ('nargs --range choices range --set_value', '', False),
        ('nargs --range range', '--', False),
        # Flag is not finished before moving on
        ('hint --flag --', '', True),
        ('hint --flag --help', '', True),
        ('hint --flag', '--', True),
        ('nargs --one_or_more --', '', True),
        ('nargs --one_or_more --set_value', '', True),
        ('nargs --one_or_more', '--', True),
        ('nargs --set_value set --', '', True),
        ('nargs --set_value set --one_or_more', '', True),
        ('nargs --set_value set', '--', True),
        ('nargs --set_val set', '--', True),  # This exercises our abbreviated flag detection
        ('nargs --range --', '', True),
        ('nargs --range --set_value', '', True),
        ('nargs --range', '--', True),
    ],
)
def test_unfinished_flag_error(ac_app, command_and_args, text, is_error) -> None:
    line = f'{command_and_args} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert is_error == all(x in completions.completion_error for x in ["Error: argument", "expected"])


def test_completion_table_arg_header(ac_app) -> None:
    # Test when metavar is None
    text = ''
    line = f'choices --table_header {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert "TABLE_HEADER" in normalize(completions.completion_table)[0]

    # Test when metavar is a string
    text = ''
    line = f'choices --no_header {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert ac_app.STR_METAVAR in normalize(completions.completion_table)[0]

    # Test when metavar is a tuple
    text = ''
    line = f'choices --tuple_metavar {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # We are completing the first argument of this flag. The first element in the tuple should be the column header.
    completions = ac_app.complete(text, line, begidx, endidx)
    assert ac_app.TUPLE_METAVAR[0].upper() in normalize(completions.completion_table)[0]

    text = ''
    line = f'choices --tuple_metavar token_1 {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # We are completing the second argument of this flag. The second element in the tuple should be the column header.
    completions = ac_app.complete(text, line, begidx, endidx)
    assert ac_app.TUPLE_METAVAR[1].upper() in normalize(completions.completion_table)[0]

    text = ''
    line = f'choices --tuple_metavar token_1 token_2 {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # We are completing the third argument of this flag. It should still be the second tuple element
    # in the column header since the tuple only has two strings in it.
    completions = ac_app.complete(text, line, begidx, endidx)
    assert ac_app.TUPLE_METAVAR[1].upper() in normalize(completions.completion_table)[0]


def test_completion_table_header(ac_app) -> None:
    from cmd2.argparse_completer import (
        DEFAULT_TABLE_HEADER,
    )

    # This argument provided a table header
    text = ''
    line = f'choices --table_header {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert ac_app.CUSTOM_TABLE_HEADER[0] in normalize(completions.completion_table)[0]

    # This argument did not provide a table header, so it should be DEFAULT_TABLE_HEADER
    text = ''
    line = f'choices --no_header {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert DEFAULT_TABLE_HEADER[0] in normalize(completions.completion_table)[0]


@pytest.mark.parametrize(
    ('command_and_args', 'text', 'has_hint'),
    [
        # Normal cases
        ('hint', '', True),
        ('hint --flag', '', True),
        ('hint --suppressed_help', '', False),
        ('hint --suppressed_hint', '', False),
        # Hint because flag does not have enough values to be considered finished
        ('nargs --one_or_more', '-', True),
        # This flag has reached its minimum value count and therefore a new flag could start.
        # However the flag can still consume values and the text is not a single prefix character.
        # Therefore a hint will be shown.
        ('nargs --one_or_more choices', 'bad_completion', True),
        # Like the previous case, but this time text is a single prefix character which will cause flag
        # name completion to occur instead of a hint for the current flag.
        ('nargs --one_or_more choices', '-', False),
        # Hint because this is a REMAINDER flag and therefore no more flag name completions occur.
        ('nargs --remainder', '-', True),
        # No hint for the positional because text is a single prefix character which results in flag name completion
        ('hint', '-', False),
        # Hint because this is a REMAINDER positional and therefore no more flag name completions occur.
        ('nargs the choices', '-', True),
        ('nargs the choices remainder', '-', True),
    ],
)
def test_autocomp_no_results_hint(ac_app, command_and_args, text, has_hint) -> None:
    """Test whether _NoResultsErrors include hint text."""
    line = f'{command_and_args} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    if has_hint:
        assert "Hint:\n" in completions.completion_error
    else:
        assert not completions.completion_error


def test_autocomp_hint_no_help_text(ac_app) -> None:
    """Tests that a hint for an arg with no help text only includes the arg's name."""
    text = ''
    line = f'hint foo {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.completion_error.strip() == "Hint:\n  no_help_pos"


@pytest.mark.parametrize(
    ('args', 'text'),
    [
        # Exercise a flag arg and choices function that raises a CompletionError
        ('--choice ', 'choice'),
        # Exercise a positional arg and completer that raises a CompletionError
        ('', 'completer'),
    ],
)
def test_completion_error(ac_app, args, text) -> None:
    line = f'raise_completion_error {args} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert f"{text} broke something" in completions.completion_error


@pytest.mark.parametrize(
    ('command_and_args', 'expected'),
    [
        # Exercise a choices function that receives arg_tokens dictionary
        ('arg_tokens choice subcmd', ['choice', 'subcmd']),
        # Exercise a completer that receives arg_tokens dictionary
        ('arg_tokens completer subcmd fake', ['completer', 'subcmd']),
        # Exercise overriding parent_arg from the subcommand
        ('arg_tokens completer subcmd --parent_arg override fake', ['override', 'subcmd']),
    ],
)
def test_arg_tokens(ac_app, command_and_args, expected) -> None:
    text = ''
    line = f'{command_and_args} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    ('command_and_args', 'text', 'output_contains', 'first_match'),
    [
        # Group isn't done. The optional positional's hint will show and flags will not complete.
        ('mutex', '', 'the optional positional', None),
        # Group isn't done. Flag name will still complete.
        ('mutex', '--fl', '', '--flag'),
        # Group isn't done. Flag hint will show.
        ('mutex --flag', '', 'the flag arg', None),
        # Group finished by optional positional. No flag name will complete.
        ('mutex pos_val', '--fl', '', None),
        # Group finished by optional positional. Error will display trying to complete the flag's value.
        ('mutex pos_val --flag', '', 'f/--flag: not allowed with argument optional_pos', None),
        # Group finished by --flag. Optional positional will be skipped and last_arg will show its hint.
        ('mutex --flag flag_val', '', 'the last arg', None),
        # Group finished by --flag. Other flag name won't complete.
        ('mutex --flag flag_val', '--oth', '', None),
        # Group finished by --flag. Error will display trying to complete other flag's value.
        ('mutex --flag flag_val --other', '', '-o/--other_flag: not allowed with argument -f/--flag', None),
        # Group finished by --flag. That same flag can be used again so it's hint will show.
        ('mutex --flag flag_val --flag', '', 'the flag arg', None),
    ],
)
def test_complete_mutex_group(ac_app, command_and_args, text, output_contains, first_match) -> None:
    line = f'{command_and_args} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    if first_match is None:
        assert not completions
    else:
        assert first_match == completions[0].text

    assert output_contains in completions.completion_error


def test_single_prefix_char() -> None:
    from cmd2.argparse_completer import (
        _single_prefix_char,
    )

    parser = Cmd2ArgumentParser(prefix_chars='-+')

    # Invalid
    assert not _single_prefix_char('', parser)
    assert not _single_prefix_char('--', parser)
    assert not _single_prefix_char('-+', parser)
    assert not _single_prefix_char('++has space', parser)
    assert not _single_prefix_char('foo', parser)

    # Valid
    assert _single_prefix_char('-', parser)
    assert _single_prefix_char('+', parser)


def test_looks_like_flag() -> None:
    from cmd2.argparse_completer import (
        _looks_like_flag,
    )

    parser = Cmd2ArgumentParser()

    # Does not start like a flag
    assert not _looks_like_flag('', parser)
    assert not _looks_like_flag('non-flag', parser)
    assert not _looks_like_flag('-', parser)
    assert not _looks_like_flag('--has space', parser)
    assert not _looks_like_flag('-2', parser)

    # Does start like a flag
    assert _looks_like_flag('--', parser)
    assert _looks_like_flag('-flag', parser)
    assert _looks_like_flag('--flag', parser)


def test_complete_command_no_tokens(ac_app) -> None:
    from cmd2.argparse_completer import (
        ArgparseCompleter,
    )

    parser = Cmd2ArgumentParser()
    ac = ArgparseCompleter(parser, ac_app)

    completions = ac.complete(text='', line='', begidx=0, endidx=0, tokens=[])
    assert not completions


def test_complete_command_help_no_tokens(ac_app) -> None:
    from cmd2.argparse_completer import (
        ArgparseCompleter,
    )

    parser = Cmd2ArgumentParser()
    ac = ArgparseCompleter(parser, ac_app)

    completions = ac.complete_subcommand_help(text='', line='', begidx=0, endidx=0, tokens=[])
    assert not completions


@pytest.mark.parametrize(
    ('flag', 'expected'),
    [
        ('--provider', standalone_choices),
        ('--completer', standalone_completions),
    ],
)
def test_complete_standalone(ac_app, flag, expected) -> None:
    text = ''
    line = f'standalone {flag} {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions.to_strings() == Completions.from_values(expected).to_strings()


@pytest.mark.parametrize(
    ('subcommand', 'flag', 'display_meta'),
    [
        ('helpful', '', 'my helpful text'),
        ('helpful', '--helpful_flag', "a helpful flag"),
        ('helpless', '', ''),
        ('helpless', '--helpless_flag', ''),
    ],
)
def test_display_meta(ac_app, subcommand, flag, display_meta) -> None:
    """Test that subcommands and flags can have display_meta data."""
    if flag:
        text = flag
        line = line = f'meta {subcommand} {text}'
    else:
        text = subcommand
        line = line = f'meta {text}'

    endidx = len(line)
    begidx = endidx - len(text)

    completions = ac_app.complete(text, line, begidx, endidx)
    assert completions[0].display_meta == display_meta


# Custom ArgparseCompleter-based class
class CustomCompleter(argparse_completer.ArgparseCompleter):
    def _complete_flags(self, text: str, line: str, begidx: int, endidx: int, matched_flags: list[str]) -> list[str]:
        """Override so flags with 'complete_when_ready' set to True will complete only when app is ready"""
        # Find flags which should not be completed and place them in matched_flags
        for flag in self._flags:
            action = self._flag_to_action[flag]
            app: CustomCompleterApp = cast(CustomCompleterApp, self._cmd2_app)
            if action.get_complete_when_ready() is True and not app.is_ready:
                matched_flags.append(flag)

        return super()._complete_flags(text, line, begidx, endidx, matched_flags)


# Add a custom argparse action attribute
argparse_custom.register_argparse_argument_parameter('complete_when_ready', bool)


# App used to test custom ArgparseCompleter types and custom argparse attributes
class CustomCompleterApp(cmd2.Cmd):
    def __init__(self) -> None:
        super().__init__()
        self.is_ready = True

    # Parser that's used to test setting the app-wide default ArgparseCompleter type
    default_completer_parser = Cmd2ArgumentParser(description="Testing app-wide argparse completer")
    default_completer_parser.add_argument('--myflag', complete_when_ready=True)

    @with_argparser(default_completer_parser)
    def do_default_completer(self, args: argparse.Namespace) -> None:
        """Test command"""

    # Parser that's used to test setting a custom completer at the parser level
    custom_completer_parser = Cmd2ArgumentParser(
        description="Testing parser-specific argparse completer", ap_completer_type=CustomCompleter
    )
    custom_completer_parser.add_argument('--myflag', complete_when_ready=True)

    @with_argparser(custom_completer_parser)
    def do_custom_completer(self, args: argparse.Namespace) -> None:
        """Test command"""

    # Test as_subcommand_to decorator with custom completer
    top_parser = Cmd2ArgumentParser(description="Top Command")
    top_parser.add_subparsers(dest='subcommand', metavar='SUBCOMMAND', required=True)

    @with_argparser(top_parser)
    def do_top(self, args: argparse.Namespace) -> None:
        """Top level command"""
        # Call handler for whatever subcommand was selected
        handler = args.cmd2_handler.get()
        handler(args)

    # Parser for a subcommand with no custom completer type
    no_custom_completer_parser = Cmd2ArgumentParser(description="No custom completer")
    no_custom_completer_parser.add_argument('--myflag', complete_when_ready=True)

    @cmd2.as_subcommand_to('top', 'no_custom', no_custom_completer_parser, help="no custom completer")
    def _subcmd_no_custom(self, args: argparse.Namespace) -> None:
        pass

    # Parser for a subcommand with a custom completer type
    custom_completer_parser2 = Cmd2ArgumentParser(description="Custom completer", ap_completer_type=CustomCompleter)
    custom_completer_parser2.add_argument('--myflag', complete_when_ready=True)

    @cmd2.as_subcommand_to('top', 'custom', custom_completer_parser2, help="custom completer")
    def _subcmd_custom(self, args: argparse.Namespace) -> None:
        pass


@pytest.fixture
def custom_completer_app():
    return CustomCompleterApp()


def test_default_custom_completer_type(custom_completer_app: CustomCompleterApp) -> None:
    """Test altering the app-wide default ArgparseCompleter type"""
    try:
        argparse_completer.set_default_ap_completer_type(CustomCompleter)

        text = '--m'
        line = f'default_completer {text}'
        endidx = len(line)
        begidx = endidx - len(text)

        # The flag should complete because app is ready
        custom_completer_app.is_ready = True
        completions = custom_completer_app.complete(text, line, begidx, endidx)
        assert completions.items[0].text == "--myflag"

        # The flag should not complete because app is not ready
        custom_completer_app.is_ready = False
        completions = custom_completer_app.complete(text, line, begidx, endidx)
        assert not completions

    finally:
        # Restore the default completer
        argparse_completer.set_default_ap_completer_type(argparse_completer.ArgparseCompleter)


def test_custom_completer_type(custom_completer_app: CustomCompleterApp) -> None:
    """Test parser with a specific custom ArgparseCompleter type"""
    text = '--m'
    line = f'custom_completer {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # The flag should complete because app is ready
    custom_completer_app.is_ready = True
    completions = custom_completer_app.complete(text, line, begidx, endidx)
    assert completions.items[0].text == "--myflag"

    # The flag should not complete because app is not ready
    custom_completer_app.is_ready = False
    completions = custom_completer_app.complete(text, line, begidx, endidx)
    assert not completions


def test_decorated_subcmd_custom_completer(custom_completer_app: CustomCompleterApp) -> None:
    """Tests custom completer type on a subcommand created with @cmd2.as_subcommand_to"""
    # First test the subcommand without the custom completer
    text = '--m'
    line = f'top no_custom {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # The flag should complete regardless of ready state since this subcommand isn't using the custom completer
    custom_completer_app.is_ready = True
    completions = custom_completer_app.complete(text, line, begidx, endidx)
    assert completions.items[0].text == "--myflag"

    custom_completer_app.is_ready = False
    completions = custom_completer_app.complete(text, line, begidx, endidx)
    assert completions.items[0].text == "--myflag"

    # Now test the subcommand with the custom completer
    text = '--m'
    line = f'top custom {text}'
    endidx = len(line)
    begidx = endidx - len(text)

    # The flag should complete because app is ready
    custom_completer_app.is_ready = True
    completions = custom_completer_app.complete(text, line, begidx, endidx)
    assert completions.items[0].text == "--myflag"

    # The flag should not complete because app is not ready
    custom_completer_app.is_ready = False
    completions = custom_completer_app.complete(text, line, begidx, endidx)
    assert not completions


def test_add_parser_custom_completer() -> None:
    """Tests setting a custom completer type on a subcommand using add_parser()"""
    parser = Cmd2ArgumentParser()
    subparsers = parser.add_subparsers()

    no_custom_completer_parser = subparsers.add_parser(name="no_custom_completer")
    assert no_custom_completer_parser.get_ap_completer_type() is None  # type: ignore[attr-defined]

    custom_completer_parser = subparsers.add_parser(name="custom_completer", ap_completer_type=CustomCompleter)
    assert custom_completer_parser.get_ap_completer_type() is CustomCompleter  # type: ignore[attr-defined]
