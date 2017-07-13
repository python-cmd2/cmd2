# coding=utf-8
"""
Unit/functional testing for helper functions/classes in the cmd2.py module.

These are primarily tests related to parsing.  Moreover, they are mostly a port of the old doctest tests which were
problematic because they worked properly for some versions of pyparsing but not for others.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import sys

import cmd2
import pytest


@pytest.fixture
def hist():
    from cmd2 import HistoryItem
    h = cmd2.History([HistoryItem('first'), HistoryItem('second'), HistoryItem('third'), HistoryItem('fourth')])
    return h

# Case-insensitive parser
@pytest.fixture
def parser():
    c = cmd2.Cmd()
    c.multilineCommands = ['multiline']
    c.case_insensitive = True
    c.parser_manager = cmd2.ParserManager(redirector=c.redirector, terminators=c.terminators, multilineCommands=c.multilineCommands,
                          legalChars=c.legalChars, commentGrammars=c.commentGrammars,
                          commentInProgress=c.commentInProgress, case_insensitive=c.case_insensitive,
                          blankLinesAllowed=c.blankLinesAllowed, prefixParser=c.prefixParser,
                          preparse=c.preparse, postparse=c.postparse, shortcuts=c.shortcuts)
    return c.parser_manager.main_parser

# Case-insensitive ParserManager
@pytest.fixture
def ci_pm():
    c = cmd2.Cmd()
    c.multilineCommands = ['multiline']
    c.case_insensitive = True
    c.parser_manager = cmd2.ParserManager(redirector=c.redirector, terminators=c.terminators, multilineCommands=c.multilineCommands,
                          legalChars=c.legalChars, commentGrammars=c.commentGrammars,
                          commentInProgress=c.commentInProgress, case_insensitive=c.case_insensitive,
                          blankLinesAllowed=c.blankLinesAllowed, prefixParser=c.prefixParser,
                          preparse=c.preparse, postparse=c.postparse, shortcuts=c.shortcuts)
    return c.parser_manager

# Case-sensitive ParserManager
@pytest.fixture
def cs_pm():
    c = cmd2.Cmd()
    c.multilineCommands = ['multiline']
    c.case_insensitive = False
    c.parser_manager = cmd2.ParserManager(redirector=c.redirector, terminators=c.terminators, multilineCommands=c.multilineCommands,
                          legalChars=c.legalChars, commentGrammars=c.commentGrammars,
                          commentInProgress=c.commentInProgress, case_insensitive=c.case_insensitive,
                          blankLinesAllowed=c.blankLinesAllowed, prefixParser=c.prefixParser,
                          preparse=c.preparse, postparse=c.postparse, shortcuts=c.shortcuts)
    return c.parser_manager


@pytest.fixture
def input_parser():
    c = cmd2.Cmd()
    return c.parser_manager.input_source_parser

@pytest.fixture
def option_parser():
    op = cmd2.OptionParser()
    return op


def test_remaining_args():
    assert cmd2.remaining_args('-f bar   bar   cow', ['bar', 'cow']) == 'bar   cow'


def test_history_span(hist):
    h = hist
    assert h == ['first', 'second', 'third', 'fourth']
    assert h.span('-2..') == ['third', 'fourth']
    assert h.span('2..3') == ['second', 'third']    # Inclusive of end
    assert h.span('3') == ['third']
    assert h.span(':') == h
    assert h.span('2..') == ['second', 'third', 'fourth']
    assert h.span('-1') == ['fourth']
    assert h.span('-2..-3') == ['third', 'second']
    assert h.span('*') == h

def test_history_get(hist):
    h = hist
    assert h == ['first', 'second', 'third', 'fourth']
    assert h.get('') == h
    assert h.get('-2') == h[:-2]
    assert h.get('5') == []
    assert h.get('2-3') == ['second']           # Exclusive of end
    assert h.get('ir') == ['first', 'third']    # Normal string search for all elements containing "ir"
    assert h.get('/i.*d/') == ['third']         # Regex string search "i", then anything, then "d"


def test_cast():
    cast = cmd2.cast

    # Boolean
    assert cast(True, True) == True
    assert cast(True, False) == False
    assert cast(True, 0) == False
    assert cast(True, 1) == True
    assert cast(True, 'on') == True
    assert cast(True, 'off') == False
    assert cast(True, 'ON') == True
    assert cast(True, 'OFF') == False
    assert cast(True, 'y') == True
    assert cast(True, 'n') == False
    assert cast(True, 't') == True
    assert cast(True, 'f') == False

    # Non-boolean same type
    assert cast(1, 5) == 5
    assert cast(3.4, 2.7) == 2.7
    assert cast('foo', 'bar') == 'bar'
    assert cast([1,2], [3,4]) == [3,4]


def test_cast_problems(capsys):
    cast = cmd2.cast

    expected = 'Problem setting parameter (now {}) to {}; incorrect type?\n'

    # Boolean current, with new value not convertible to bool
    current = True
    new = [True, True]
    assert cast(current, new) == current
    out, err = capsys.readouterr()
    assert out == expected.format(current, new)

    # Non-boolean current, with new value not convertible to current type
    current = 1
    new = 'octopus'
    assert cast(current, new) == current
    out, err = capsys.readouterr()
    assert out == expected.format(current, new)


def test_parse_empty_string(parser):
    assert parser.parseString('').dump() == '[]'

def test_parse_only_comment(parser):
    assert parser.parseString('/* empty command */').dump() == '[]'

def test_parse_single_word(parser):
    line = 'plainword'
    results = parser.parseString(line)
    assert results.command == line

def test_parse_word_plus_terminator(parser):
    line = 'termbare;'
    results = parser.parseString(line)
    assert results.command == 'termbare'
    assert results.terminator == ';'

def test_parse_suffix_after_terminator(parser):
    line = 'termbare; suffx'
    results = parser.parseString(line)
    assert results.command == 'termbare'
    assert results.terminator == ';'
    assert results.suffix == 'suffx'

def test_parse_command_with_args(parser):
    line = 'COMmand with args'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == 'with args'

def test_parse_command_with_args_terminator_and_suffix(parser):
    line = 'command with args and terminator; and suffix'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == "with args and terminator"
    assert results.terminator == ';'
    assert results.suffix == 'and suffix'

def test_parse_simple_piped(parser):
    line = 'simple | piped'
    results = parser.parseString(line)
    assert results.command == 'simple'
    assert results.pipeTo == " piped"

def test_parse_double_pipe_is_not_a_pipe(parser):
    line = 'double-pipe || is not a pipe'
    results = parser.parseString(line)
    assert results.command == 'double-pipe'
    assert results.args == '|| is not a pipe'
    assert not 'pipeTo' in results

def test_parse_complex_pipe(parser):
    line = 'command with args, terminator;sufx | piped'
    results = parser.parseString(line)
    assert results.command == 'command'
    assert results.args == "with args, terminator"
    assert results.terminator == ';'
    assert results.suffix == 'sufx'
    assert results.pipeTo == ' piped'

def test_parse_output_redirect(parser):
    line = 'output into > afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.output == '>'
    assert results.outputTo == 'afile.txt'

def test_parse_output_redirect_with_dash_in_path(parser):
    line = 'output into > python-cmd2/afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.output == '>'
    assert results.outputTo == 'python-cmd2/afile.txt'


def test_case_insensitive_parsed_single_word(ci_pm):
    line = 'HeLp'
    statement = ci_pm.parsed(line)
    assert statement.parsed.command == line.lower()

def test_case_sensitive_parsed_single_word(cs_pm):
    line = 'HeLp'
    statement = cs_pm.parsed(line)
    assert statement.parsed.command == line


def test_parse_input_redirect(input_parser):
    line = '< afile.txt'
    results = input_parser.parseString(line)
    assert results.inputFrom == line

def test_parse_input_redirect_with_dash_in_path(input_parser):
    line = "< python-cmd2/afile.txt"
    results = input_parser.parseString(line)
    assert results.inputFrom == line

def test_parse_pipe_and_redirect(parser):
    line = 'output into;sufx | pipethrume plz > afile.txt'
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'into'
    assert results.terminator == ';'
    assert results.suffix == 'sufx'
    assert results.pipeTo == ' pipethrume plz'
    assert results.output == '>'
    assert results.outputTo == 'afile.txt'

def test_parse_output_to_paste_buffer(parser):
    line = 'output to paste buffer >> '
    results = parser.parseString(line)
    assert results.command == 'output'
    assert results.args == 'to paste buffer'
    assert results.output == '>>'

def test_parse_ignore_commented_redirectors(parser):
    line = 'ignore the /* commented | > */ stuff;'
    results = parser.parseString(line)
    assert results.command == 'ignore'
    assert results.args == 'the /* commented | > */ stuff'
    assert results.terminator == ';'

def test_parse_has_redirect_inside_terminator(parser):
    """The terminator designates the end of the commmand/arguments portion.  If a redirector
    occurs before a terminator, then it will be treated as part of the arguments and not as a redirector."""
    line = 'has > inside;'
    results = parser.parseString(line)
    assert results.command == 'has'
    assert results.args == '> inside'
    assert results.terminator == ';'

def test_parse_what_if_quoted_strings_seem_to_start_comments(parser):
    line = 'what if "quoted strings /* seem to " start comments?'
    results = parser.parseString(line)
    assert results.command == 'what'
    assert results.args == 'if "quoted strings /* seem to " start comments?'

def test_parse_unfinished_multiliine_command(parser):
    line = 'multiline has > inside an unfinished command'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert not 'args' in results

def test_parse_multiline_command_ignores_redirectors_within_it(parser):
    line = 'multiline has > inside;'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert results.args == 'has > inside'
    assert results.terminator == ';'

def test_parse_multiline_with_incomplete_comment(parser):
    """A terminator within a comment will be ignored and won't terminate a multiline command.
    Un-closed comments effectively comment out everything after the start."""
    line = 'multiline command /* with comment in progress;'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert not 'args' in results

def test_parse_multiline_with_complete_comment(parser):
    line = 'multiline command /* with comment complete */ is done;'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert results.args == 'command /* with comment complete */ is done'
    assert results.terminator == ';'

def test_parse_multiline_termninated_by_empty_line(parser):
    line = 'multiline command ends\n\n'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert results.args == 'command ends'
    assert len(results.terminator) == 2
    assert results.terminator[0] == '\n'
    assert results.terminator[1] == '\n'

def test_parse_multiline_ignores_terminators_in_comments(parser):
    line = 'multiline command "with term; ends" now\n\n'
    results = parser.parseString(line)
    assert results.multilineCommand == 'multiline'
    assert results.args == 'command "with term; ends" now'
    assert len(results.terminator) == 2
    assert results.terminator[0] == '\n'
    assert results.terminator[1] == '\n'

def test_parse_abbreviated_multiline_not_allowed(parser):
    line = 'multilin command\n'
    results = parser.parseString(line)
    assert results.command == 'multilin'
    assert results.multilineCommand == ''

# Unicode support is only present in cmd2 for Python 3
@pytest.mark.skipif(sys.version_info < (3,0), reason="cmd2 unicode support requires python3")
def test_parse_command_with_unicode_args(parser):
    line = 'drink café'
    results = parser.parseString(line)
    assert results.command == 'drink'
    assert results.args == 'café'

@pytest.mark.skipif(sys.version_info < (3, 0), reason="cmd2 unicode support requires python3")
def test_parse_unicode_command(parser):
    line = 'café au lait'
    results = parser.parseString(line)
    assert results.command == 'café'
    assert results.args == 'au lait'

@pytest.mark.skipif(sys.version_info < (3,0), reason="cmd2 unicode support requires python3")
def test_parse_redirect_to_unicode_filename(parser):
    line = 'dir home > café'
    results = parser.parseString(line)
    assert results.command == 'dir'
    assert results.args == 'home'
    assert results.output == '>'
    assert results.outputTo == 'café'

@pytest.mark.skipif(sys.version_info < (3,0), reason="cmd2 unicode support requires python3")
def test_parse_input_redirect_from_unicode_filename(input_parser):
    line = '< café'
    results = input_parser.parseString(line)
    assert results.inputFrom == line


def test_option_parser_exit_with_msg(option_parser, capsys):
    msg = 'foo bar'
    option_parser.exit(msg=msg)
    out, err = capsys.readouterr()
    assert out == msg + '\n'
    assert err == ''


def test_empty_statement_raises_exception():
    app = cmd2.Cmd()
    with pytest.raises(cmd2.EmptyStatement):
        app._complete_statement('')

    with pytest.raises(cmd2.EmptyStatement):
        app._complete_statement(' ')
