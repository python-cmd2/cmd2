# coding=utf-8
"""
Test the parsing logic in parsing.py

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import cmd2
from cmd2.parsing import StatementParser

import pytest


@pytest.fixture
def parser():
    parser = StatementParser(
        allow_redirection=True,
        terminators = [';'],
        multiline_commands = ['multiline'],
        aliases = {'helpalias': 'help', '42': 'theanswer', 'anothermultiline': 'multiline', 'fake': 'pyscript'},
        shortcuts = [('?', 'help'), ('!', 'shell')]
    )
    return parser

def test_parse_empty_string(parser):
    statement = parser.parse('')
    assert not statement.command
    assert not statement.args
    assert statement.raw == ''

@pytest.mark.parametrize('tokens,command,args', [
    ( [], None, ''),
    ( ['command'], 'command', '' ),
    ( ['command', 'arg1', 'arg2'], 'command', 'arg1 arg2')
])
def test_command_and_args(parser, tokens, command, args):
    (parsed_command, parsed_args) = parser._command_and_args(tokens)
    assert command == parsed_command
    assert args == parsed_args

@pytest.mark.parametrize('line', [
    'plainword',
    '"one word"',
    "'one word'",
])
def test_single_word(parser, line):
    statement = parser.parse(line)
    assert statement.command == line

def test_word_plus_terminator(parser):
    line = 'termbare;'
    statement = parser.parse(line)
    assert statement.command == 'termbare'
    assert statement.terminator == ';'

def test_suffix_after_terminator(parser):
    line = 'termbare; suffx'
    statement = parser.parse(line)
    assert statement.command == 'termbare'
    assert statement.terminator == ';'
    assert statement.suffix == 'suffx'

def test_command_with_args(parser):
    line = 'command with args'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement.args == 'with args'
    assert not statement.pipe_to

def test_parse_command_with_args_terminator_and_suffix(parser):
    line = 'command with args and terminator; and suffix'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement.args == "with args and terminator"
    assert statement.terminator == ';'
    assert statement.suffix == 'and suffix'

def test_hashcomment(parser):
    statement = parser.parse('hi # this is all a comment')
    assert statement.command == 'hi'
    assert not statement.args
    assert not statement.pipe_to

def test_c_comment(parser):
    statement = parser.parse('hi /* this is | all a comment */')
    assert statement.command == 'hi'
    assert not statement.args
    assert not statement.pipe_to

def test_c_comment_empty(parser):
    statement = parser.parse('/* this is | all a comment */')
    assert not statement.command
    assert not statement.args
    assert not statement.pipe_to

def test_parse_what_if_quoted_strings_seem_to_start_comments(parser):
    statement = parser.parse('what if "quoted strings /* seem to " start comments?')
    assert statement.command == 'what'
    assert statement.args == 'if "quoted strings /* seem to " start comments?'
    assert not statement.pipe_to

def test_simple_piped(parser):
    statement = parser.parse('simple | piped')
    assert statement.command == 'simple'
    assert not statement.args
    assert statement.pipe_to == 'piped'

def test_double_pipe_is_not_a_pipe(parser):
    line = 'double-pipe || is not a pipe'
    statement = parser.parse(line)
    assert statement.command == 'double-pipe'
    assert statement.args == '|| is not a pipe'
    assert not statement.pipe_to

def test_complex_pipe(parser):
    line = 'command with args, terminator;sufx | piped'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement.args == "with args, terminator"
    assert statement.terminator == ';'
    assert statement.suffix == 'sufx'
    assert statement.pipe_to == 'piped'

def test_output_redirect(parser):
    line = 'output into > afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'into'
    assert statement.output == '>'
    assert statement.output_to == 'afile.txt'

def test_output_redirect_with_dash_in_path(parser):
    line = 'output into > python-cmd2/afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'into'
    assert statement.output == '>'
    assert statement.output_to == 'python-cmd2/afile.txt'

def test_output_redirect_append(parser):
    line = 'output appended to >> /tmp/afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'appended to'
    assert statement.output == '>>'
    assert statement.output_to == '/tmp/afile.txt'

def test_parse_input_redirect(parser):
    line = '< afile.txt'
    statement = parser.parse(line)
    assert statement.inputFrom == 'afile.txt'

def test_parse_input_redirect_after_command(parser):
    line = 'help < afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'help'
    assert statement.args == ''
    assert statement.inputFrom == 'afile.txt'

def test_parse_input_redirect_with_dash_in_path(parser):
    line = '< python-cmd2/afile.txt'
    statement = parser.parse(line)
    assert statement.inputFrom == 'python-cmd2/afile.txt'

def test_pipe_and_redirect(parser):
    line = 'output into;sufx | pipethrume plz > afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'into'
    assert statement.terminator == ';'
    assert statement.suffix == 'sufx'
    assert statement.pipe_to == 'pipethrume plz'
    assert statement.output == '>'
    assert statement.output_to == 'afile.txt'

def test_parse_output_to_paste_buffer(parser):
    line = 'output to paste buffer >> '
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'to paste buffer'
    assert statement.output == '>>'

def test_has_redirect_inside_terminator(parser):
    """The terminator designates the end of the commmand/arguments portion.  If a redirector
    occurs before a terminator, then it will be treated as part of the arguments and not as a redirector."""
    line = 'has > inside;'
    statement = parser.parse(line)
    assert statement.command == 'has'
    assert statement.args == '> inside'
    assert statement.terminator == ';'

def test_parse_unfinished_multiliine_command(parser):
    line = 'multiline has > inside an unfinished command'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'has > inside an unfinished command'
    assert not statement.terminator

def test_parse_multiline_command_ignores_redirectors_within_it(parser):
    line = 'multiline has > inside;'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.args == 'has > inside'
    assert statement.terminator == ';'

def test_parse_multiline_with_incomplete_comment(parser):
    """A terminator within a comment will be ignored and won't terminate a multiline command.
    Un-closed comments effectively comment out everything after the start."""
    line = 'multiline command /* with comment in progress;'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.args == 'command'
    assert not statement.terminator

def test_parse_multiline_with_complete_comment(parser):
    line = 'multiline command /* with comment complete */ is done;'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.args == 'command is done'
    assert statement.terminator == ';'

def test_parse_multiline_termninated_by_empty_line(parser):
    line = 'multiline command ends\n\n'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.args == 'command ends'
    assert statement.terminator == '\n'

def test_parse_multiline_ignores_terminators_in_comments(parser):
    line = 'multiline command "with term; ends" now\n\n'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.args == 'command "with term; ends" now'
    assert statement.terminator == '\n'

def test_parse_command_with_unicode_args(parser):
    line = 'drink café'
    statement = parser.parse(line)
    assert statement.command == 'drink'
    assert statement.args == 'café'

def test_parse_unicode_command(parser):
    line = 'café au lait'
    statement = parser.parse(line)
    assert statement.command == 'café'
    assert statement.args == 'au lait'

def test_parse_redirect_to_unicode_filename(parser):
    line = 'dir home > café'
    statement = parser.parse(line)
    assert statement.command == 'dir'
    assert statement.args == 'home'
    assert statement.output == '>'
    assert statement.output_to == 'café'

def test_parse_input_redirect_from_unicode_filename(parser):
    line = '< café'
    statement = parser.parse(line)
    assert statement.inputFrom == 'café'

def test_empty_statement_raises_exception():
    app = cmd2.Cmd()
    with pytest.raises(cmd2.cmd2.EmptyStatement):
        app._complete_statement('')

    with pytest.raises(cmd2.cmd2.EmptyStatement):
        app._complete_statement(' ')

@pytest.mark.parametrize('line,command,args', [
    ('helpalias', 'help', ''),
    ('helpalias mycommand', 'help', 'mycommand'),
    ('42', 'theanswer', ''),
    ('42 arg1 arg2', 'theanswer', 'arg1 arg2'),
    ('!ls', 'shell', 'ls'),
    ('!ls -al /tmp', 'shell', 'ls -al /tmp'),
])
def test_alias_and_shortcut_expansion(parser, line, command, args):
    statement = parser.parse(line)
    assert statement.command == command
    assert statement.args == args

def test_alias_on_multiline_command(parser):
    line = 'anothermultiline has > inside an unfinished command'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'has > inside an unfinished command'
    assert not statement.terminator

def test_parse_command_only_command_and_args(parser):
    line = 'help history'
    statement = parser.parse_command_only(line)
    assert statement.command == 'help'
    assert statement.args == 'history'
    assert statement.command_and_args == line

def test_parse_command_only_emptyline(parser):
    line = ''
    statement = parser.parse_command_only(line)
    assert statement.command is None
    assert statement.args is ''
    assert statement.command_and_args is line

def test_parse_command_only_strips_line(parser):
    line = '  help history  '
    statement = parser.parse_command_only(line)
    assert statement.command == 'help'
    assert statement.args == 'history'
    assert statement.command_and_args == line.strip()

def test_parse_command_only_expands_alias(parser):
    line = 'fake foobar.py'
    statement = parser.parse_command_only(line)
    assert statement.command == 'pyscript'
    assert statement.args == 'foobar.py'

def test_parse_command_only_expands_shortcuts(parser):
    line = '!cat foobar.txt'
    statement = parser.parse_command_only(line)
    assert statement.command == 'shell'
    assert statement.args == 'cat foobar.txt'
    assert statement.command_and_args == line.replace('!', 'shell ')
