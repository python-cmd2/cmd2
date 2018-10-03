# coding=utf-8
"""
Test the parsing logic in parsing.py

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import attr
import pytest

import cmd2
from cmd2.parsing import StatementParser
from cmd2 import utils

@pytest.fixture
def parser():
    parser = StatementParser(
        allow_redirection=True,
        terminators=[';', '&'],
        multiline_commands=['multiline'],
        aliases={'helpalias': 'help',
                 '42': 'theanswer',
                 'l': '!ls -al',
                 'anothermultiline': 'multiline',
                 'fake': 'pyscript'},
        shortcuts=[('?', 'help'), ('!', 'shell')]
    )
    return parser

@pytest.fixture
def default_parser():
    parser = StatementParser()
    return parser


def test_parse_empty_string(parser):
    line = ''
    statement = parser.parse(line)
    assert statement == ''
    assert statement.args == statement
    assert statement.raw == line
    assert statement.command == ''
    assert statement.arg_list == []
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''
    assert statement.command_and_args == line
    assert statement.argv == statement.arg_list

def test_parse_empty_string_default(default_parser):
    line = ''
    statement = default_parser.parse(line)
    assert statement == ''
    assert statement.args == statement
    assert statement.raw == line
    assert statement.command == ''
    assert statement.arg_list == []
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''
    assert statement.command_and_args == line
    assert statement.argv == statement.arg_list

@pytest.mark.parametrize('line,tokens', [
    ('command', ['command']),
    ('command /* with some comment */ arg', ['command', 'arg']),
    ('command arg1 arg2 # comment at the end', ['command', 'arg1', 'arg2']),
    ('termbare ; > /tmp/output', ['termbare', ';', '>', '/tmp/output']),
    ('termbare; > /tmp/output', ['termbare', ';', '>', '/tmp/output']),
    ('termbare & > /tmp/output', ['termbare', '&', '>', '/tmp/output']),
    ('termbare& > /tmp/output', ['termbare&', '>', '/tmp/output']),
    ('help|less', ['help', '|', 'less']),
])
def test_tokenize_default(default_parser, line, tokens):
    tokens_to_test = default_parser.tokenize(line)
    assert tokens_to_test == tokens

@pytest.mark.parametrize('line,tokens', [
    ('command', ['command']),
    ('command /* with some comment */ arg', ['command', 'arg']),
    ('command arg1 arg2 # comment at the end', ['command', 'arg1', 'arg2']),
    ('42 arg1 arg2', ['theanswer', 'arg1', 'arg2']),
    ('l', ['shell', 'ls', '-al']),
    ('termbare ; > /tmp/output', ['termbare', ';', '>', '/tmp/output']),
    ('termbare; > /tmp/output', ['termbare', ';', '>', '/tmp/output']),
    ('termbare & > /tmp/output', ['termbare', '&', '>', '/tmp/output']),
    ('termbare& > /tmp/output', ['termbare', '&', '>', '/tmp/output']),
    ('help|less', ['help', '|', 'less']),
    ('l|less', ['shell', 'ls', '-al', '|', 'less']),
])
def test_tokenize(parser, line, tokens):
    tokens_to_test = parser.tokenize(line)
    assert tokens_to_test == tokens

def test_tokenize_unclosed_quotes(parser):
    with pytest.raises(ValueError):
        _ = parser.tokenize('command with "unclosed quotes')

@pytest.mark.parametrize('tokens,command,args', [
    ([], '', ''),
    (['command'], 'command', ''),
    (['command', 'arg1', 'arg2'], 'command', 'arg1 arg2')
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
def test_parse_single_word(parser, line):
    statement = parser.parse(line)
    assert statement.command == line
    assert statement == ''
    assert statement.argv == [utils.strip_quotes(line)]
    assert not statement.arg_list
    assert statement.args == statement
    assert statement.raw == line
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''
    assert statement.command_and_args == line

@pytest.mark.parametrize('line,terminator', [
    ('termbare;', ';'),
    ('termbare ;', ';'),
    ('termbare&', '&'),
    ('termbare &', '&'),
])
def test_parse_word_plus_terminator(parser, line, terminator):
    statement = parser.parse(line)
    assert statement.command == 'termbare'
    assert statement == ''
    assert statement.argv == ['termbare']
    assert not statement.arg_list
    assert statement.terminator == terminator

@pytest.mark.parametrize('line,terminator', [
    ('termbare;  suffx', ';'),
    ('termbare ;suffx', ';'),
    ('termbare&  suffx', '&'),
    ('termbare &suffx', '&'),
])
def test_parse_suffix_after_terminator(parser, line, terminator):
    statement = parser.parse(line)
    assert statement.command == 'termbare'
    assert statement == ''
    assert statement.args == statement
    assert statement.argv == ['termbare']
    assert not statement.arg_list
    assert statement.terminator == terminator
    assert statement.suffix == 'suffx'

def test_parse_command_with_args(parser):
    line = 'command with args'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement == 'with args'
    assert statement.args == statement
    assert statement.argv == ['command', 'with', 'args']
    assert statement.arg_list == statement.argv[1:]

def test_parse_command_with_quoted_args(parser):
    line = 'command with "quoted args" and "some not"'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement == 'with "quoted args" and "some not"'
    assert statement.args == statement
    assert statement.argv == ['command', 'with', 'quoted args', 'and', 'some not']
    assert statement.arg_list == ['with', '"quoted args"', 'and', '"some not"']

def test_parse_command_with_args_terminator_and_suffix(parser):
    line = 'command with args and terminator; and suffix'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement == "with args and terminator"
    assert statement.args == statement
    assert statement.argv == ['command', 'with', 'args', 'and', 'terminator']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == ';'
    assert statement.suffix == 'and suffix'

def test_parse_hashcomment(parser):
    statement = parser.parse('hi # this is all a comment')
    assert statement.command == 'hi'
    assert statement == ''
    assert statement.args == statement
    assert statement.argv == ['hi']
    assert not statement.arg_list

def test_parse_c_comment(parser):
    statement = parser.parse('hi /* this is | all a comment */')
    assert statement.command == 'hi'
    assert statement == ''
    assert statement.args == statement
    assert statement.argv == ['hi']
    assert not statement.arg_list
    assert not statement.pipe_to

def test_parse_c_comment_empty(parser):
    statement = parser.parse('/* this is | all a comment */')
    assert statement.command == ''
    assert statement.args == statement
    assert not statement.pipe_to
    assert not statement.argv
    assert not statement.arg_list
    assert statement == ''

def test_parse_c_comment_no_closing(parser):
    statement = parser.parse('cat /tmp/*.txt')
    assert statement.command == 'cat'
    assert statement == '/tmp/*.txt'
    assert statement.args == statement
    assert not statement.pipe_to
    assert statement.argv == ['cat', '/tmp/*.txt']
    assert statement.arg_list == statement.argv[1:]

def test_parse_c_comment_multiple_opening(parser):
    statement = parser.parse('cat /tmp/*.txt /tmp/*.cfg')
    assert statement.command == 'cat'
    assert statement == '/tmp/*.txt /tmp/*.cfg'
    assert statement.args == statement
    assert not statement.pipe_to
    assert statement.argv == ['cat', '/tmp/*.txt', '/tmp/*.cfg']
    assert statement.arg_list == statement.argv[1:]

def test_parse_what_if_quoted_strings_seem_to_start_comments(parser):
    statement = parser.parse('what if "quoted strings /* seem to " start comments?')
    assert statement.command == 'what'
    assert statement == 'if "quoted strings /* seem to " start comments?'
    assert statement.args == statement
    assert statement.argv == ['what', 'if', 'quoted strings /* seem to ', 'start', 'comments?']
    assert statement.arg_list == ['if', '"quoted strings /* seem to "', 'start', 'comments?']
    assert not statement.pipe_to

@pytest.mark.parametrize('line',[
    'simple | piped',
    'simple|piped',
])
def test_parse_simple_pipe(parser, line):
    statement = parser.parse(line)
    assert statement.command == 'simple'
    assert statement == ''
    assert statement.args == statement
    assert statement.argv == ['simple']
    assert not statement.arg_list
    assert statement.pipe_to == ['piped']

def test_parse_double_pipe_is_not_a_pipe(parser):
    line = 'double-pipe || is not a pipe'
    statement = parser.parse(line)
    assert statement.command == 'double-pipe'
    assert statement == '|| is not a pipe'
    assert statement.args == statement
    assert statement.argv == ['double-pipe', '||', 'is', 'not', 'a', 'pipe']
    assert statement.arg_list == statement.argv[1:]
    assert not statement.pipe_to

def test_parse_complex_pipe(parser):
    line = 'command with args, terminator&sufx | piped'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement == "with args, terminator"
    assert statement.args == statement
    assert statement.argv == ['command', 'with', 'args,', 'terminator']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == '&'
    assert statement.suffix == 'sufx'
    assert statement.pipe_to == ['piped']

@pytest.mark.parametrize('line,output', [
    ('help > out.txt', '>'),
    ('help>out.txt', '>'),
    ('help >> out.txt', '>>'),
    ('help>>out.txt', '>>'),
])
def test_parse_redirect(parser,line, output):
    statement = parser.parse(line)
    assert statement.command == 'help'
    assert statement == ''
    assert statement.args == statement
    assert statement.output == output
    assert statement.output_to == 'out.txt'

def test_parse_redirect_with_args(parser):
    line = 'output into > afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement == 'into'
    assert statement.args == statement
    assert statement.argv == ['output', 'into']
    assert statement.arg_list == statement.argv[1:]
    assert statement.output == '>'
    assert statement.output_to == 'afile.txt'

def test_parse_redirect_with_dash_in_path(parser):
    line = 'output into > python-cmd2/afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement == 'into'
    assert statement.args == statement
    assert statement.argv == ['output', 'into']
    assert statement.arg_list == statement.argv[1:]
    assert statement.output == '>'
    assert statement.output_to == 'python-cmd2/afile.txt'

def test_parse_redirect_append(parser):
    line = 'output appended to >> /tmp/afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement == 'appended to'
    assert statement.args == statement
    assert statement.argv == ['output', 'appended', 'to']
    assert statement.arg_list == statement.argv[1:]
    assert statement.output == '>>'
    assert statement.output_to == '/tmp/afile.txt'

def test_parse_pipe_and_redirect(parser):
    line = 'output into;sufx | pipethrume plz > afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement == 'into'
    assert statement.args == statement
    assert statement.argv == ['output', 'into']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == ';'
    assert statement.suffix == 'sufx'
    assert statement.pipe_to == ['pipethrume', 'plz', '>', 'afile.txt']
    assert statement.output == ''
    assert statement.output_to == ''

def test_parse_output_to_paste_buffer(parser):
    line = 'output to paste buffer >> '
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement == 'to paste buffer'
    assert statement.args == statement
    assert statement.argv == ['output', 'to', 'paste', 'buffer']
    assert statement.arg_list == statement.argv[1:]
    assert statement.output == '>>'

def test_parse_redirect_inside_terminator(parser):
    """The terminator designates the end of the commmand/arguments portion.
    If a redirector occurs before a terminator, then it will be treated as
    part of the arguments and not as a redirector."""
    line = 'has > inside;'
    statement = parser.parse(line)
    assert statement.command == 'has'
    assert statement == '> inside'
    assert statement.args == statement
    assert statement.argv == ['has', '>', 'inside']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == ';'

@pytest.mark.parametrize('line,terminator',[
    ('multiline with | inside;', ';'),
    ('multiline with | inside ;', ';'),
    ('multiline with | inside;;;', ';'),
    ('multiline with | inside;; ;;', ';'),
    ('multiline with | inside&', '&'),
    ('multiline with | inside &;', '&'),
    ('multiline with | inside&&;', '&'),
    ('multiline with | inside &; &;', '&'),
])
def test_parse_multiple_terminators(parser, line, terminator):
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement == 'with | inside'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'with', '|', 'inside']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == terminator

def test_parse_unfinished_multiliine_command(parser):
    line = 'multiline has > inside an unfinished command'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement == 'has > inside an unfinished command'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'has', '>', 'inside', 'an', 'unfinished', 'command']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == ''

@pytest.mark.parametrize('line,terminator',[
    ('multiline has > inside;', ';'),
    ('multiline has > inside;;;', ';'),
    ('multiline has > inside;; ;;', ';'),
    ('multiline has > inside &', '&'),
    ('multiline has > inside & &', '&'),
])
def test_parse_multiline_command_ignores_redirectors_within_it(parser, line, terminator):
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement == 'has > inside'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'has', '>', 'inside']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == terminator

def test_parse_multiline_with_incomplete_comment(parser):
    """A terminator within a comment will be ignored and won't terminate a multiline command.
    Un-closed comments effectively comment out everything after the start."""
    line = 'multiline command /* with unclosed comment;'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement == 'command /* with unclosed comment'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'command', '/*', 'with', 'unclosed', 'comment']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == ';'

def test_parse_multiline_with_complete_comment(parser):
    line = 'multiline command /* with comment complete */ is done;'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement == 'command is done'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'command', 'is', 'done']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == ';'

def test_parse_multiline_terminated_by_empty_line(parser):
    line = 'multiline command ends\n\n'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement == 'command ends'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'command', 'ends']
    assert statement.arg_list == statement.argv[1:]
    assert statement.terminator == '\n'

@pytest.mark.parametrize('line,terminator',[
    ('multiline command "with\nembedded newline";', ';'),
    ('multiline command "with\nembedded newline";;;', ';'),
    ('multiline command "with\nembedded newline";; ;;', ';'),
    ('multiline command "with\nembedded newline" &', '&'),
    ('multiline command "with\nembedded newline" & &', '&'),
    ('multiline command "with\nembedded newline"\n\n', '\n'),
])
def test_parse_multiline_with_embedded_newline(parser, line, terminator):
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement == 'command "with\nembedded newline"'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'command', 'with\nembedded newline']
    assert statement.arg_list == ['command', '"with\nembedded newline"']
    assert statement.terminator == terminator

def test_parse_multiline_ignores_terminators_in_comments(parser):
    line = 'multiline command "with term; ends" now\n\n'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement == 'command "with term; ends" now'
    assert statement.args == statement
    assert statement.argv == ['multiline', 'command', 'with term; ends', 'now']
    assert statement.arg_list == ['command', '"with term; ends"', 'now']
    assert statement.terminator == '\n'

def test_parse_command_with_unicode_args(parser):
    line = 'drink café'
    statement = parser.parse(line)
    assert statement.command == 'drink'
    assert statement == 'café'
    assert statement.args == statement
    assert statement.argv == ['drink', 'café']
    assert statement.arg_list == statement.argv[1:]

def test_parse_unicode_command(parser):
    line = 'café au lait'
    statement = parser.parse(line)
    assert statement.command == 'café'
    assert statement == 'au lait'
    assert statement.args == statement
    assert statement.argv == ['café', 'au', 'lait']
    assert statement.arg_list == statement.argv[1:]

def test_parse_redirect_to_unicode_filename(parser):
    line = 'dir home > café'
    statement = parser.parse(line)
    assert statement.command == 'dir'
    assert statement == 'home'
    assert statement.args == statement
    assert statement.argv == ['dir', 'home']
    assert statement.arg_list == statement.argv[1:]
    assert statement.output == '>'
    assert statement.output_to == 'café'

def test_parse_unclosed_quotes(parser):
    with pytest.raises(ValueError):
        _ = parser.tokenize("command with 'unclosed quotes")

def test_empty_statement_raises_exception():
    app = cmd2.Cmd()
    with pytest.raises(cmd2.EmptyStatement):
        app._complete_statement('')

    with pytest.raises(cmd2.EmptyStatement):
        app._complete_statement(' ')

@pytest.mark.parametrize('line,command,args', [
    ('helpalias', 'help', ''),
    ('helpalias mycommand', 'help', 'mycommand'),
    ('42', 'theanswer', ''),
    ('42 arg1 arg2', 'theanswer', 'arg1 arg2'),
    ('!ls', 'shell', 'ls'),
    ('!ls -al /tmp', 'shell', 'ls -al /tmp'),
    ('l', 'shell', 'ls -al')
])
def test_parse_alias_and_shortcut_expansion(parser, line, command, args):
    statement = parser.parse(line)
    assert statement.command == command
    assert statement == args
    assert statement.args == statement

def test_parse_alias_on_multiline_command(parser):
    line = 'anothermultiline has > inside an unfinished command'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == statement
    assert statement == 'has > inside an unfinished command'
    assert statement.terminator == ''

@pytest.mark.parametrize('line,output', [
    ('helpalias > out.txt', '>'),
    ('helpalias>out.txt', '>'),
    ('helpalias >> out.txt', '>>'),
    ('helpalias>>out.txt', '>>'),
])
def test_parse_alias_redirection(parser, line, output):
    statement = parser.parse(line)
    assert statement.command == 'help'
    assert statement == ''
    assert statement.args == statement
    assert statement.output == output
    assert statement.output_to == 'out.txt'

@pytest.mark.parametrize('line', [
    'helpalias | less',
    'helpalias|less',
])
def test_parse_alias_pipe(parser, line):
    statement = parser.parse(line)
    assert statement.command == 'help'
    assert statement == ''
    assert statement.args == statement
    assert statement.pipe_to == ['less']

@pytest.mark.parametrize('line', [
    'helpalias;',
    'helpalias;;',
    'helpalias;; ;',
    'helpalias ;',
    'helpalias ; ;',
    'helpalias ;; ;',
])
def test_parse_alias_terminator_no_whitespace(parser, line):
    statement = parser.parse(line)
    assert statement.command == 'help'
    assert statement == ''
    assert statement.args == statement
    assert statement.terminator == ';'

def test_parse_command_only_command_and_args(parser):
    line = 'help history'
    statement = parser.parse_command_only(line)
    assert statement == 'history'
    assert statement.args == statement
    assert statement.arg_list == []
    assert statement.command == 'help'
    assert statement.command_and_args == line
    assert statement.multiline_command == ''
    assert statement.raw == line
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''

def test_parse_command_only_strips_line(parser):
    line = '  help history  '
    statement = parser.parse_command_only(line)
    assert statement == 'history'
    assert statement.args == statement
    assert statement.arg_list == []
    assert statement.command == 'help'
    assert statement.command_and_args == line.strip()
    assert statement.multiline_command == ''
    assert statement.raw == line
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''

def test_parse_command_only_expands_alias(parser):
    line = 'fake foobar.py "somebody.py'
    statement = parser.parse_command_only(line)
    assert statement == 'foobar.py "somebody.py'
    assert statement.args == statement
    assert statement.arg_list == []
    assert statement.command == 'pyscript'
    assert statement.command_and_args == 'pyscript foobar.py "somebody.py'
    assert statement.multiline_command == ''
    assert statement.raw == line
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''

def test_parse_command_only_expands_shortcuts(parser):
    line = '!cat foobar.txt'
    statement = parser.parse_command_only(line)
    assert statement == 'cat foobar.txt'
    assert statement.args == statement
    assert statement.arg_list == []
    assert statement.command == 'shell'
    assert statement.command_and_args == 'shell cat foobar.txt'
    assert statement.multiline_command == ''
    assert statement.raw == line
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''

def test_parse_command_only_quoted_args(parser):
    line = 'l "/tmp/directory with spaces/doit.sh"'
    statement = parser.parse_command_only(line)
    assert statement == 'ls -al "/tmp/directory with spaces/doit.sh"'
    assert statement.args == statement
    assert statement.arg_list == []
    assert statement.command == 'shell'
    assert statement.command_and_args == line.replace('l', 'shell ls -al')
    assert statement.multiline_command == ''
    assert statement.raw == line
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''

@pytest.mark.parametrize('line,args', [
    ('helpalias > out.txt', '> out.txt'),
    ('helpalias>out.txt', '>out.txt'),
    ('helpalias >> out.txt', '>> out.txt'),
    ('helpalias>>out.txt', '>>out.txt'),
    ('help|less', '|less'),
    ('helpalias;', ';'),
    ('help ;;', ';;'),
    ('help; ;;', '; ;;'),
])
def test_parse_command_only_specialchars(parser, line, args):
    statement = parser.parse_command_only(line)
    assert statement == args
    assert statement.args == args
    assert statement.command == 'help'
    assert statement.multiline_command == ''
    assert statement.raw == line
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''

@pytest.mark.parametrize('line', [
    '',
    ';',
    ';;',
    ';; ;',
    '&',
    '& &',
    ' && &',
    '>',
    "'",
    '"',
    '|',
])
def test_parse_command_only_empty(parser, line):
    statement = parser.parse_command_only(line)
    assert statement == ''
    assert statement.args == statement
    assert statement.arg_list == []
    assert statement.command == ''
    assert statement.command_and_args == ''
    assert statement.multiline_command == ''
    assert statement.raw == line
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert statement.pipe_to == []
    assert statement.output == ''
    assert statement.output_to == ''

def test_parse_command_only_multiline(parser):
    line = 'multiline with partially "open quotes and no terminator'
    statement = parser.parse_command_only(line)
    assert statement.command == 'multiline'
    assert statement.multiline_command == 'multiline'
    assert statement == 'with partially "open quotes and no terminator'
    assert statement.command_and_args == line
    assert statement.args == statement


def test_statement_initialization():
    string = 'alias'
    statement = cmd2.Statement(string)
    assert string == statement
    assert statement.args == statement
    assert statement.raw == ''
    assert statement.command == ''
    assert isinstance(statement.arg_list, list)
    assert not statement.arg_list
    assert isinstance(statement.argv, list)
    assert not statement.argv
    assert statement.multiline_command == ''
    assert statement.terminator == ''
    assert statement.suffix == ''
    assert isinstance(statement.pipe_to, list)
    assert not statement.pipe_to
    assert statement.output == ''
    assert statement.output_to == ''


def test_statement_is_immutable():
    string = 'foo'
    statement = cmd2.Statement(string)
    assert string == statement
    assert statement.args == statement
    assert statement.raw == ''
    with pytest.raises(attr.exceptions.FrozenInstanceError):
        statement.args = 'bar'
    with pytest.raises(attr.exceptions.FrozenInstanceError):
        statement.raw = 'baz'


def test_is_valid_command_invalid(parser):
    # Empty command
    valid, errmsg = parser.is_valid_command('')
    assert not valid and 'cannot be an empty string' in errmsg

    # Starts with shortcut
    valid, errmsg = parser.is_valid_command('!ls')
    assert not valid and 'cannot start with a shortcut' in errmsg

    # Contains whitespace
    valid, errmsg = parser.is_valid_command('shell ls')
    assert not valid and 'cannot contain: whitespace, quotes,' in errmsg

    # Contains a quote
    valid, errmsg = parser.is_valid_command('"shell"')
    assert not valid and 'cannot contain: whitespace, quotes,' in errmsg

    # Contains a redirector
    valid, errmsg = parser.is_valid_command('>shell')
    assert not valid and 'cannot contain: whitespace, quotes,' in errmsg

    # Contains a terminator
    valid, errmsg = parser.is_valid_command(';shell')
    assert not valid and 'cannot contain: whitespace, quotes,' in errmsg

def test_is_valid_command_valid(parser):
    # Empty command
    valid, errmsg = parser.is_valid_command('shell')
    assert valid
    assert not errmsg


def test_macro_normal_arg_pattern():
    # This pattern matches digits surrounded by exactly 1 brace on a side and 1 or more braces on the opposite side
    from cmd2.parsing import MacroArg
    pattern = MacroArg.macro_normal_arg_pattern

    # Valid strings
    matches = pattern.findall('{5}')
    assert matches == ['{5}']

    matches = pattern.findall('{233}')
    assert matches == ['{233}']

    matches = pattern.findall('{{{{{4}')
    assert matches == ['{4}']

    matches = pattern.findall('{2}}}}}')
    assert matches == ['{2}']

    matches = pattern.findall('{3}{4}{5}')
    assert matches == ['{3}', '{4}', '{5}']

    matches = pattern.findall('{3} {4} {5}')
    assert matches == ['{3}', '{4}', '{5}']

    matches = pattern.findall('{3} {{{4} {5}}}}')
    assert matches == ['{3}', '{4}', '{5}']

    matches = pattern.findall('{3} text {4} stuff {5}}}}')
    assert matches == ['{3}', '{4}', '{5}']

    # Unicode digit
    matches = pattern.findall('{\N{ARABIC-INDIC DIGIT ONE}}')
    assert matches == ['{\N{ARABIC-INDIC DIGIT ONE}}']

    # Invalid strings
    matches = pattern.findall('5')
    assert not matches

    matches = pattern.findall('{5')
    assert not matches

    matches = pattern.findall('5}')
    assert not matches

    matches = pattern.findall('{{5}}')
    assert not matches

    matches = pattern.findall('{5text}')
    assert not matches

def test_macro_escaped_arg_pattern():
    # This pattern matches digits surrounded by 2 or more braces on both sides
    from cmd2.parsing import MacroArg
    pattern = MacroArg.macro_escaped_arg_pattern

    # Valid strings
    matches = pattern.findall('{{5}}')
    assert matches == ['{{5}}']

    matches = pattern.findall('{{233}}')
    assert matches == ['{{233}}']

    matches = pattern.findall('{{{{{4}}')
    assert matches == ['{{4}}']

    matches = pattern.findall('{{2}}}}}')
    assert matches == ['{{2}}']

    matches = pattern.findall('{{3}}{{4}}{{5}}')
    assert matches == ['{{3}}', '{{4}}', '{{5}}']

    matches = pattern.findall('{{3}} {{4}} {{5}}')
    assert matches == ['{{3}}', '{{4}}', '{{5}}']

    matches = pattern.findall('{{3}} {{{4}} {{5}}}}')
    assert matches == ['{{3}}', '{{4}}', '{{5}}']

    matches = pattern.findall('{{3}} text {{4}} stuff {{5}}}}')
    assert matches == ['{{3}}', '{{4}}', '{{5}}']

    # Unicode digit
    matches = pattern.findall('{{\N{ARABIC-INDIC DIGIT ONE}}}')
    assert matches == ['{{\N{ARABIC-INDIC DIGIT ONE}}}']

    # Invalid strings
    matches = pattern.findall('5')
    assert not matches

    matches = pattern.findall('{{5')
    assert not matches

    matches = pattern.findall('5}}')
    assert not matches

    matches = pattern.findall('{5}')
    assert not matches

    matches = pattern.findall('{{5text}}')
    assert not matches
