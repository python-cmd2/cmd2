# coding=utf-8
"""
Unit/functional testing for ply based parsing in cmd2

Todo List
- multiline
- case sensitive flag
- checkout Cmd2.parseline() function which parses and expands shortcuts and such
  this code should probably be included in CommandParser

Notes:

- Shortcuts may have to be discarded, or handled in a different way than they
  are with pyparsing.
- valid comment styles:
    - C-style -> /* comment */
    - Python/Shell style -> # comment

Functions in cmd2.py to be modified:
- _complete_statement()

"""

import cmd2
from cmd2.parsing import CommandParser

import pytest

@pytest.fixture
def parser():
    parser = CommandParser(
        quotes=['"', "'"],
        allow_redirection=True,
        redirection_chars=['|', '<', '>'],        
        terminators = [';'],
        multilineCommands = ['multiline']
    )
    return parser

def test_parse_empty_string(parser):
    results = parser.parseString('')
    assert not results.command

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
    results = parser.parseString(line)
    assert results.command == line

def test_word_plus_terminator(parser):
    line = 'termbare;'
    results = parser.parseString(line)
    assert results.command == 'termbare'
    assert results.terminator == ';'

def test_suffix_after_terminator(parser):
    line = 'termbare; suffx'
    results = parser.parseString(line)
    assert results.command == 'termbare'
    assert results.terminator == ';'
    assert results.suffix == 'suffx'

def test_command_with_args(parser):
    line = 'command with args'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == 'with args'
    assert not results.pipeTo

def test_parse_command_with_args_terminator_and_suffix(parser):
    line = 'command with args and terminator; and suffix'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == "with args and terminator"
    assert results.terminator == ';'
    assert results.suffix == 'and suffix'

def test_hashcomment(parser):
    results = parser.parseString('hi # this is all a comment')
    assert results.command == 'hi'
    assert not results.args
    assert not results.pipeTo

def test_c_comment(parser):
    results = parser.parseString('hi /* this is | all a comment */')
    assert results.command == 'hi'
    assert not results.args
    assert not results.pipeTo

def test_c_comment_empty(parser):
    results = parser.parseString('/* this is | all a comment */')
    assert not results.command
    assert not results.args
    assert not results.pipeTo

def test_parse_what_if_quoted_strings_seem_to_start_comments(parser):
    results = parser.parseString('what if "quoted strings /* seem to " start comments?')
    assert results.command == 'what'
    assert results.args == 'if "quoted strings /* seem to " start comments?'
    assert not results.pipeTo

def test_simple_piped(parser):
    results = parser.parseString('simple | piped')
    assert results.command == 'simple'
    assert not results.args
    assert results.pipeTo == 'piped'

def test_double_pipe_is_not_a_pipe(parser):
    line = 'double-pipe || is not a pipe'
    results = parser.parseString(line)
    assert results.command == 'double-pipe'
    assert results.args == '|| is not a pipe'
    assert not results.pipeTo

def test_complex_pipe(parser):
    line = 'command with args, terminator;sufx | piped'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == "with args, terminator"
    assert results.terminator == ';'
    assert results.suffix == 'sufx'
    assert results.pipeTo == 'piped'

def test_output_redirect(parser):
    line = 'output into > afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.output == '>'
    assert results.outputTo == 'afile.txt'

def test_output_redirect_with_dash_in_path(parser):
    line = 'output into > python-cmd2/afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.output == '>'
    assert results.outputTo == 'python-cmd2/afile.txt'

def test_parse_input_redirect(parser):
    line = '< afile.txt'
    results = parser.parseString(line)
    assert results.inputFrom == 'afile.txt'

def test_parse_input_redirect_with_dash_in_path(parser):
    line = '< python-cmd2/afile.txt'
    results = parser.parseString(line)
    assert results.inputFrom == 'python-cmd2/afile.txt'

def test_pipe_and_redirect(parser):
    line = 'output into;sufx | pipethrume plz > afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.terminator == ';'
    assert results.suffix == 'sufx'
    assert results.pipeTo == 'pipethrume plz'
    assert results.output == '>'
    assert results.outputTo == 'afile.txt'

def test_parse_output_to_paste_buffer(parser):
    line = 'output to paste buffer >> '
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'to paste buffer'
    assert results.output == '>>'

def test_has_redirect_inside_terminator(parser):
    """The terminator designates the end of the commmand/arguments portion.  If a redirector
    occurs before a terminator, then it will be treated as part of the arguments and not as a redirector."""
    line = 'has > inside;'
    results = parser.parseString(line)
    assert results.command == 'has'
    assert results.args == '> inside'
    assert results.terminator == ';'

# def test_parse_unfinished_multiliine_command(parser):
#     line = 'multiline has > inside an unfinished command'
#     results = parser.parseString(line)
#     assert results.multilineCommand == 'multiline'
#     assert not 'args' in results

def test_parse_multiline_command_ignores_redirectors_within_it(parser):
    line = 'multiline has > inside;'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert results.args == 'has > inside'
    assert results.terminator == ';'

# def test_parse_multiline_with_incomplete_comment(parser):
#     """A terminator within a comment will be ignored and won't terminate a multiline command.
#     Un-closed comments effectively comment out everything after the start."""
#     line = 'multiline command /* with comment in progress;'
#     results = parser.parseString(line)
#     assert results.multilineCommand == 'multiline'
#     assert not 'args' in results

def test_parse_multiline_with_complete_comment(parser):
    line = 'multiline command /* with comment complete */ is done;'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert results.args == 'command is done'
    assert results.terminator == ';'

# def test_parse_multiline_termninated_by_empty_line(parser):
#     line = 'multiline command ends\n\n'
#     results = parser.parseString(line)
#     assert results.multilineCommand == 'multiline'
#     assert results.args == 'command ends'
#     assert len(results.terminator) == 2
#     assert results.terminator[0] == '\n'
#     assert results.terminator[1] == '\n'

# def test_parse_multiline_ignores_terminators_in_comments(parser):
#     line = 'multiline command "with term; ends" now\n\n'
#     results = parser.parseString(line)
#     assert results.multilineCommand == 'multiline'
#     assert results.args == 'command "with term; ends" now'
#     assert len(results.terminator) == 2
#     assert results.terminator[0] == '\n'
#     assert results.terminator[1] == '\n'

def test_parse_command_with_unicode_args(parser):
    line = 'drink café'
    results = parser.parseString(line)
    assert results.command == 'drink'
    assert results.args == 'café'

def test_parse_unicode_command(parser):
    line = 'café au lait'
    results = parser.parseString(line)
    assert results.command == 'café'
    assert results.args == 'au lait'

def test_parse_redirect_to_unicode_filename(parser):
    line = 'dir home > café'
    results = parser.parseString(line)
    assert results.command == 'dir'
    assert results.args == 'home'
    assert results.output == '>'
    assert results.outputTo == 'café'

def test_parse_input_redirect_from_unicode_filename(parser):
    line = '< café'
    results = parser.parseString(line)
    assert results.inputFrom == 'café'

def test_empty_statement_raises_exception():
    app = cmd2.Cmd()
    with pytest.raises(cmd2.cmd2.EmptyStatement):
        app._complete_statement('')

    with pytest.raises(cmd2.cmd2.EmptyStatement):
        app._complete_statement(' ')
