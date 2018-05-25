# coding=utf-8
"""
Test the parsing logic in parsing.py

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
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

def test_parse_empty_string(parser):
    statement = parser.parse('')
    assert not statement.command
    assert not statement.args
    assert statement.raw == ''

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
    ([], None, None),
    (['command'], 'command', None),
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
    assert not statement.args
    assert statement.argv == [utils.strip_quotes(line)]

@pytest.mark.parametrize('line,terminator', [
    ('termbare;', ';'),
    ('termbare ;', ';'),
    ('termbare&', '&'),
    ('termbare &', '&'),
])
def test_parse_word_plus_terminator(parser, line, terminator):
    statement = parser.parse(line)
    assert statement.command == 'termbare'
    assert statement.terminator == terminator
    assert statement.argv == ['termbare']

@pytest.mark.parametrize('line,terminator', [
    ('termbare;  suffx', ';'),
    ('termbare ;suffx', ';'),
    ('termbare&  suffx', '&'),
    ('termbare &suffx', '&'),
])
def test_parse_suffix_after_terminator(parser, line, terminator):
    statement = parser.parse(line)
    assert statement.command == 'termbare'
    assert statement.terminator == terminator
    assert statement.suffix == 'suffx'
    assert statement.argv == ['termbare']

def test_parse_command_with_args(parser):
    line = 'command with args'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement.args == 'with args'
    assert statement.argv == ['command', 'with', 'args']

def test_parse_command_with_quoted_args(parser):
    line = 'command with "quoted args" and "some not"'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement.args == 'with "quoted args" and "some not"'
    assert statement.argv == ['command', 'with', 'quoted args', 'and', 'some not']

def test_parse_command_with_args_terminator_and_suffix(parser):
    line = 'command with args and terminator; and suffix'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement.args == "with args and terminator"
    assert statement.terminator == ';'
    assert statement.suffix == 'and suffix'
    assert statement.argv == ['command', 'with', 'args', 'and', 'terminator']

def test_parse_hashcomment(parser):
    statement = parser.parse('hi # this is all a comment')
    assert statement.command == 'hi'
    assert not statement.args
    assert statement.argv == ['hi']

def test_parse_c_comment(parser):
    statement = parser.parse('hi /* this is | all a comment */')
    assert statement.command == 'hi'
    assert not statement.args
    assert not statement.pipe_to
    assert statement.argv == ['hi']

def test_parse_c_comment_empty(parser):
    statement = parser.parse('/* this is | all a comment */')
    assert not statement.command
    assert not statement.args
    assert not statement.pipe_to
    assert not statement.argv

def test_parse_what_if_quoted_strings_seem_to_start_comments(parser):
    statement = parser.parse('what if "quoted strings /* seem to " start comments?')
    assert statement.command == 'what'
    assert statement.args == 'if "quoted strings /* seem to " start comments?'
    assert not statement.pipe_to
    assert statement.argv == ['what', 'if', 'quoted strings /* seem to ', 'start', 'comments?']

@pytest.mark.parametrize('line',[
    'simple | piped',
    'simple|piped',
])
def test_parse_simple_pipe(parser, line):
    statement = parser.parse(line)
    assert statement.command == 'simple'
    assert not statement.args
    assert statement.argv == ['simple']
    assert statement.pipe_to == ['piped']

def test_parse_double_pipe_is_not_a_pipe(parser):
    line = 'double-pipe || is not a pipe'
    statement = parser.parse(line)
    assert statement.command == 'double-pipe'
    assert statement.args == '|| is not a pipe'
    assert statement.argv == ['double-pipe', '||', 'is', 'not', 'a', 'pipe']
    assert not statement.pipe_to

def test_parse_complex_pipe(parser):
    line = 'command with args, terminator&sufx | piped'
    statement = parser.parse(line)
    assert statement.command == 'command'
    assert statement.args == "with args, terminator"
    assert statement.argv == ['command', 'with', 'args,', 'terminator']
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
    assert not statement.args
    assert statement.output == output
    assert statement.output_to == 'out.txt'

def test_parse_redirect_with_args(parser):
    line = 'output into > afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'into'
    assert statement.argv == ['output', 'into']
    assert statement.output == '>'
    assert statement.output_to == 'afile.txt'

def test_parse_redirect_with_dash_in_path(parser):
    line = 'output into > python-cmd2/afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'into'
    assert statement.argv == ['output', 'into']
    assert statement.output == '>'
    assert statement.output_to == 'python-cmd2/afile.txt'

def test_parse_redirect_append(parser):
    line = 'output appended to >> /tmp/afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'appended to'
    assert statement.argv == ['output', 'appended', 'to']
    assert statement.output == '>>'
    assert statement.output_to == '/tmp/afile.txt'

def test_parse_pipe_and_redirect(parser):
    line = 'output into;sufx | pipethrume plz > afile.txt'
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'into'
    assert statement.argv == ['output', 'into']
    assert statement.terminator == ';'
    assert statement.suffix == 'sufx'
    assert statement.pipe_to == ['pipethrume', 'plz', '>', 'afile.txt']
    assert not statement.output
    assert not statement.output_to

def test_parse_output_to_paste_buffer(parser):
    line = 'output to paste buffer >> '
    statement = parser.parse(line)
    assert statement.command == 'output'
    assert statement.args == 'to paste buffer'
    assert statement.argv == ['output', 'to', 'paste', 'buffer']
    assert statement.output == '>>'

def test_parse_redirect_inside_terminator(parser):
    """The terminator designates the end of the commmand/arguments portion.
    If a redirector occurs before a terminator, then it will be treated as
    part of the arguments and not as a redirector."""
    line = 'has > inside;'
    statement = parser.parse(line)
    assert statement.command == 'has'
    assert statement.args == '> inside'
    assert statement.argv == ['has', '>', 'inside']
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
    assert statement.args == 'with | inside'
    assert statement.argv == ['multiline', 'with', '|', 'inside']
    assert statement.terminator == terminator

def test_parse_unfinished_multiliine_command(parser):
    line = 'multiline has > inside an unfinished command'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'has > inside an unfinished command'
    assert statement.argv == ['multiline', 'has', '>', 'inside', 'an', 'unfinished', 'command']
    assert not statement.terminator

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
    assert statement.args == 'has > inside'
    assert statement.argv == ['multiline', 'has', '>', 'inside']
    assert statement.terminator == terminator

def test_parse_multiline_with_incomplete_comment(parser):
    """A terminator within a comment will be ignored and won't terminate a multiline command.
    Un-closed comments effectively comment out everything after the start."""
    line = 'multiline command /* with comment in progress;'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'command'
    assert statement.argv == ['multiline', 'command']
    assert not statement.terminator

def test_parse_multiline_with_complete_comment(parser):
    line = 'multiline command /* with comment complete */ is done;'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'command is done'
    assert statement.argv == ['multiline', 'command', 'is', 'done']
    assert statement.terminator == ';'

def test_parse_multiline_termninated_by_empty_line(parser):
    line = 'multiline command ends\n\n'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'command ends'
    assert statement.argv == ['multiline', 'command', 'ends']
    assert statement.terminator == '\n'

def test_parse_multiline_ignores_terminators_in_comments(parser):
    line = 'multiline command "with term; ends" now\n\n'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'command "with term; ends" now'
    assert statement.argv == ['multiline', 'command', 'with term; ends', 'now']
    assert statement.terminator == '\n'

def test_parse_command_with_unicode_args(parser):
    line = 'drink café'
    statement = parser.parse(line)
    assert statement.command == 'drink'
    assert statement.args == 'café'
    assert statement.argv == ['drink', 'café']

def test_parse_unicode_command(parser):
    line = 'café au lait'
    statement = parser.parse(line)
    assert statement.command == 'café'
    assert statement.args == 'au lait'
    assert statement.argv == ['café', 'au', 'lait']

def test_parse_redirect_to_unicode_filename(parser):
    line = 'dir home > café'
    statement = parser.parse(line)
    assert statement.command == 'dir'
    assert statement.args == 'home'
    assert statement.argv == ['dir', 'home']
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
    ('helpalias', 'help', None),
    ('helpalias mycommand', 'help', 'mycommand'),
    ('42', 'theanswer', None),
    ('42 arg1 arg2', 'theanswer', 'arg1 arg2'),
    ('!ls', 'shell', 'ls'),
    ('!ls -al /tmp', 'shell', 'ls -al /tmp'),
    ('l', 'shell', 'ls -al')
])
def test_parse_alias_and_shortcut_expansion(parser, line, command, args):
    statement = parser.parse(line)
    assert statement.command == command
    assert statement.args == args

def test_parse_alias_on_multiline_command(parser):
    line = 'anothermultiline has > inside an unfinished command'
    statement = parser.parse(line)
    assert statement.multiline_command == 'multiline'
    assert statement.command == 'multiline'
    assert statement.args == 'has > inside an unfinished command'
    assert not statement.terminator

@pytest.mark.parametrize('line,output', [
    ('helpalias > out.txt', '>'),
    ('helpalias>out.txt', '>'),
    ('helpalias >> out.txt', '>>'),
    ('helpalias>>out.txt', '>>'),
])
def test_parse_alias_redirection(parser, line, output):
    statement = parser.parse(line)
    assert statement.command == 'help'
    assert not statement.args
    assert statement.output == output
    assert statement.output_to == 'out.txt'

@pytest.mark.parametrize('line', [
    'helpalias | less',
    'helpalias|less',
])
def test_parse_alias_pipe(parser, line):
    statement = parser.parse(line)
    assert statement.command == 'help'
    assert not statement.args
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
    assert not statement.args
    assert statement.terminator == ';'

def test_parse_command_only_command_and_args(parser):
    line = 'help history'
    statement = parser.parse_command_only(line)
    assert statement.command == 'help'
    assert statement.args == 'history'
    assert statement.command_and_args == line

def test_parse_command_only_emptyline(parser):
    line = ''
    statement = parser.parse_command_only(line)
    # statement is a subclass of str(), the value of the str
    # should be '', to retain backwards compatibility with
    # the cmd in the standard library
    assert statement == ''
    assert statement.command is None
    assert statement.args is None
    assert not statement.argv
    assert statement.command_and_args == None

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
    assert statement.command_and_args == 'shell cat foobar.txt'

def test_parse_command_only_quoted_args(parser):
    line = 'l "/tmp/directory with spaces/doit.sh"'
    statement = parser.parse_command_only(line)
    assert statement.command == 'shell'
    assert statement.args == 'ls -al "/tmp/directory with spaces/doit.sh"'
    assert statement.command_and_args == line.replace('l', 'shell ls -al')

@pytest.mark.parametrize('line', [
    'helpalias > out.txt',
    'helpalias>out.txt',
    'helpalias >> out.txt',
    'helpalias>>out.txt',
    'help|less',
    'helpalias;',
    'help ;;',
    'help; ;;',
])
def test_parse_command_only_specialchars(parser, line):
    statement = parser.parse_command_only(line)
    assert statement.command == 'help'

@pytest.mark.parametrize('line', [
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
def test_parse_command_only_none(parser, line):
    statement = parser.parse_command_only(line)
    assert statement.command == None
    assert statement.args == None
