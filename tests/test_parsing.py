# coding=utf-8
"""
Unit/functional testing for helper functions/classes in the cmd2.py module.

These are primarily tests related to parsing.  Moreover, they are mostly a port of the old doctest tests which were 
problematic because they worked properly in Python 2, but not in Python 3.

Copyright 2017 Todd Leonhardt <todd.leonhardt@gmail.com>
Released under MIT license, see LICENSE file
"""
import cmd2
import pyparsing
from pytest import fixture

# NOTE: pyparsing's ParseResults.dump() function behaves differently in versions >= 2.1.10
# In version 2.1.10, changed display of string values to show them in quotes

# Extract pyparsing version and figure out if it has a new or old version of ParseResults.dump() behavior
(major, minor, release) = (int(v) for v in pyparsing.__version__.split('.'))
new_pyparsing = True
if major < 2:
    new_pyparsing = False
elif major == 2:
    if minor < 1:
        new_pyparsing = False
    elif minor == 1:
        if release < 10:
            new_pyparsing = False


@fixture
def hist():
    from cmd2 import HistoryItem
    h = cmd2.History([HistoryItem('first'), HistoryItem('second'), HistoryItem('third'), HistoryItem('fourth')])
    return h


@fixture
def parser():
    c = cmd2.Cmd()
    c.multilineCommands = ['multiline']
    c.case_insensitive = True
    c._init_parser()
    return c.parser


def test_remaining_args():
    assert cmd2.remaining_args('-f bar   bar   cow', ['bar', 'cow']) == 'bar   cow'


def test_stubborn_dict_class():
    d = cmd2.StubbornDict(large='gross', small='klein')
    assert sorted(d.items()) == [('large', 'gross'), ('small', 'klein')]

    d.append(['plain', '  plaid'])
    assert sorted(d.items()) == [('large', 'gross'), ('plaid', ''), ('plain', ''), ('small', 'klein')]

    d += '   girl Frauelein, Maedchen\n\n shoe schuh'
    assert sorted(d.items()) == [('girl', 'Frauelein, Maedchen'), ('large', 'gross'), ('plaid', ''), ('plain', ''),
                                 ('shoe', 'schuh'), ('small', 'klein')]

def test_stubborn_dict_factory():
    assert sorted(cmd2.stubbornDict('cow a bovine\nhorse an equine').items()) == [('cow', 'a bovine'),
                                                                                  ('horse', 'an equine')]
    assert sorted(cmd2.stubbornDict(['badger', 'porcupine a poky creature']).items()) == [('badger', ''),
                                                                                          ('porcupine',
                                                                                           'a poky creature')]
    assert sorted(cmd2.stubbornDict(turtle='has shell', frog='jumpy').items()) == [('frog', 'jumpy'),
                                                                                   ('turtle', 'has shell')]


def test_history_span(hist):
    h = hist
    assert h.span('-2..') == ['third', 'fourth']
    assert h.span('2..3') == ['second', 'third']
    assert h.span('3') == ['third']
    assert h.span(':') == ['first', 'second', 'third', 'fourth']
    assert h.span('2..') == ['second', 'third', 'fourth']
    assert h.span('-1') == ['fourth']
    assert h.span('-2..-3') == ['third', 'second']

def test_history_search(hist):
    assert hist.search('o') == ['second', 'fourth']
    assert hist.search('/IR/') == ['first', 'third']


def test_parse_empty_string(parser):
    assert parser.parseString('').dump() == '[]'

def test_parse_only_comment(parser):
    assert parser.parseString('/* empty command */').dump() == '[]'

def test_parse_single_word(parser):
    command = "plainword"
    if new_pyparsing:
        command = repr(command)
    expected = """['plainword', '']
- command: {0}
- statement: ['plainword', '']
  - command: {0}""".format(command)
    assert parser.parseString('plainword').dump() == expected

def test_parse_word_plus_terminator(parser):
    command = "termbare"
    terminator = ";"
    if new_pyparsing:
        command = repr(command)
        terminator = repr(terminator)
    expected = """['termbare', '', ';', '']
- command: {0}
- statement: ['termbare', '', ';']
  - command: {0}
  - terminator: {1}
- terminator: {1}""".format(command, terminator)
    assert parser.parseString('termbare;').dump() == expected

def test_parse_suffix_after_terminator(parser):
    command = "termbare"
    terminator = ";"
    suffix = "suffx"
    if new_pyparsing:
        command = repr(command)
        terminator = repr(terminator)
        suffix = repr(suffix)
    expected = """['termbare', '', ';', 'suffx']
- command: {0}
- statement: ['termbare', '', ';']
  - command: {0}
  - terminator: {1}
- suffix: {2}
- terminator: {1}""".format(command, terminator, suffix)
    assert parser.parseString('termbare; suffx').dump() == expected

def test_parse_command_with_args(parser):
    command = "command"
    args = "with args"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
    expected = """['command', 'with args']
- args: {1}
- command: {0}
- statement: ['command', 'with args']
  - args: {1}
  - command: {0}""".format(command, args)
    assert parser.parseString('COMmand with args').dump() == expected

def test_parse_command_with_args_terminator_and_suffix(parser):
    command = "command"
    args = "with args and terminator"
    terminator = ";"
    suffix = "and suffix"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
        terminator = repr(terminator)
        suffix = repr(suffix)
    expected = """['command', 'with args and terminator', ';', 'and suffix']
- args: {1}
- command: {0}
- statement: ['command', 'with args and terminator', ';']
  - args: {1}
  - command: {0}
  - terminator: {2}
- suffix: {3}
- terminator: {2}""".format(command, args, terminator, suffix)
    assert parser.parseString('command with args and terminator; and suffix').dump() == expected

def test_parse_simple_piped(parser):
    command = "simple"
    pipe = " piped"
    if new_pyparsing:
        command = repr(command)
        pipe = repr(pipe)
    expected = """['simple', '', '|', ' piped']
- command: {0}
- pipeTo: {1}
- statement: ['simple', '']
  - command: {0}""".format(command, pipe)
    assert parser.parseString('simple | piped').dump() == expected

def test_parse_doulbe_pipe_is_not_a_pipe(parser):
    command = "double"
    args = "-pipe || is not a pipe"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
    expected = """['double', '-pipe || is not a pipe']
- args: {1}
- command: {0}
- statement: ['double', '-pipe || is not a pipe']
  - args: {1}
  - command: {0}""".format(command, args)
    assert parser.parseString('double-pipe || is not a pipe').dump() == expected

def test_parse_complex_pipe(parser):
    command = "command"
    args = "with args, terminator"
    terminator = ";"
    suffix = "sufx"
    pipe = " piped"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
        terminator = repr(terminator)
        suffix = repr(suffix)
        pipe = repr(pipe)
    expected = """['command', 'with args, terminator', ';', 'sufx', '|', ' piped']
- args: {1}
- command: {0}
- pipeTo: {4}
- statement: ['command', 'with args, terminator', ';']
  - args: {1}
  - command: {0}
  - terminator: {2}
- suffix: {3}
- terminator: {2}""".format(command, args, terminator, suffix, pipe)
    assert parser.parseString('command with args, terminator;sufx | piped').dump() == expected

def test_parse_output_redirect(parser):
    command = "output"
    args = "into"
    redirect = ">"
    output = "afile.txt"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
        redirect = repr(redirect)
        output = repr(output)
    expected = """['output', 'into', '>', 'afile.txt']
- args: {1}
- command: {0}
- output: {2}
- outputTo: {3}
- statement: ['output', 'into']
  - args: {1}
  - command: {0}""".format(command, args, redirect, output)
    assert parser.parseString('output into > afile.txt').dump() == expected

def test_parse_pipe_and_redirect(parser):
    command = "output"
    args = "into"
    terminator = ";"
    suffix = "sufx"
    pipe = " pipethrume plz"
    redirect = ">"
    output = "afile.txt"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
        terminator = repr(terminator)
        pipe = repr(pipe)
        suffix = repr(suffix)
        redirect = repr(redirect)
        output = repr(output)
    expected = """['output', 'into', ';', 'sufx', '|', ' pipethrume plz', '>', 'afile.txt']
- args: {1}
- command: {0}
- output: {5}
- outputTo: {6}
- pipeTo: {4}
- statement: ['output', 'into', ';']
  - args: {1}
  - command: {0}
  - terminator: {2}
- suffix: {3}
- terminator: {2}""".format(command, args, terminator, suffix, pipe, redirect, output)
    assert parser.parseString('output into;sufx | pipethrume plz > afile.txt').dump() == expected

def test_parse_output_to_paste_buffer(parser):
    command = "output"
    args = "to paste buffer"
    redirect = ">>"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
        redirect = repr(redirect)
    expected = """['output', 'to paste buffer', '>>', '']
- args: {1}
- command: {0}
- output: {2}
- statement: ['output', 'to paste buffer']
  - args: {1}
  - command: {0}""".format(command, args, redirect)
    assert parser.parseString('output to paste buffer >> ').dump() == expected

def test_parse_ignore_commented_redirectors(parser):
    command = "ignore"
    args = "the /* commented | > */ stuff"
    terminator = ";"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
        terminator = repr(terminator)
    expected = """['ignore', 'the /* commented | > */ stuff', ';', '']
- args: {1}
- command: {0}
- statement: ['ignore', 'the /* commented | > */ stuff', ';']
  - args: {1}
  - command: {0}
  - terminator: {2}
- terminator: {2}""".format(command, args, terminator)
    assert parser.parseString('ignore the /* commented | > */ stuff;').dump() == expected

def test_parse_has_redirect_inside_terminator(parser):
    """The terminator designates the end of the commmand/arguments portion.  If a redirector
    occurs before a terminator, then it will be treated as part of the arguments and not as a redirector."""
    command = "has"
    args = "> inside"
    terminator = ";"
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
        terminator = repr(terminator)
    expected = """['has', '> inside', ';', '']
- args: {1}
- command: {0}
- statement: ['has', '> inside', ';']
  - args: {1}
  - command: {0}
  - terminator: {2}
- terminator: {2}""".format(command, args, terminator)
    assert parser.parseString('has > inside;').dump() == expected

def test_parse_what_if_quoted_strings_seem_to_start_comments(parser):
    command = "what"
    args = 'if "quoted strings /* seem to " start comments?'
    if new_pyparsing:
        command = repr(command)
        args = repr(args)
    expected = """['what', 'if "quoted strings /* seem to " start comments?']
- args: {1}
- command: {0}
- statement: ['what', 'if "quoted strings /* seem to " start comments?']
  - args: {1}
  - command: {0}""".format(command, args)
    assert parser.parseString('what if "quoted strings /* seem to " start comments?').dump() == expected

def test_parse_unfinished_multiliine_command(parser):
    multiline = 'multiline'
    if new_pyparsing:
        multiline = repr(multiline)
    expected = """['multiline', ' has > inside an unfinished command']
- multilineCommand: {0}""".format(multiline)
    assert parser.parseString('multiline has > inside an unfinished command').dump() == expected

def test_parse_multiline_command_ignores_redirectors_within_it(parser):
    multiline = "multiline"
    args = "has > inside"
    terminator = ";"
    if new_pyparsing:
        multiline = repr(multiline)
        args = repr(args)
        terminator = repr(terminator)
    expected = """['multiline', 'has > inside', ';', '']
- args: {1}
- multilineCommand: {0}
- statement: ['multiline', 'has > inside', ';']
  - args: {1}
  - multilineCommand: {0}
  - terminator: {2}
- terminator: {2}""".format(multiline, args, terminator)
    assert parser.parseString('multiline has > inside;').dump() == expected

def test_parse_multiline_with_incomplete_comment(parser):
    """A terminator within a comment will be ignored and won't terminate a multiline command.
    Un-closed comments effectively comment out everything after the start."""
    multiline = 'multiline'
    if new_pyparsing:
        multiline = repr(multiline)
    expected = """['multiline', ' command /* with comment in progress;']
- multilineCommand: {0}""".format(multiline)
    assert parser.parseString('multiline command /* with comment in progress;').dump() == expected

def test_parse_multiline_with_complete_comment(parser):
    multiline = "multiline"
    args = "command /* with comment complete */ is done"
    terminator = ";"
    if new_pyparsing:
        multiline = repr(multiline)
        args = repr(args)
        terminator = repr(terminator)
    expected = """['multiline', 'command /* with comment complete */ is done', ';', '']
- args: {1}
- multilineCommand: {0}
- statement: ['multiline', 'command /* with comment complete */ is done', ';']
  - args: {1}
  - multilineCommand: {0}
  - terminator: {2}
- terminator: {2}""".format(multiline, args, terminator)
    assert parser.parseString('multiline command /* with comment complete */ is done;').dump() == expected

def test_parse_multiline_termninated_by_empty_line(parser):
    multiline = "multiline"
    args = "command ends"
    terminator = r"['\n', '\n']"
    if new_pyparsing:
        multiline = repr(multiline)
        args = repr(args)
    expected = r"""['multiline', 'command ends', '\n', '\n']
- args: {1}
- multilineCommand: {0}
- statement: ['multiline', 'command ends', '\n', '\n']
  - args: {1}
  - multilineCommand: {0}
  - terminator: {2}
- terminator: {2}""".format(multiline, args, terminator)
    assert parser.parseString('multiline command ends\n\n').dump() == expected

def test_parse_multiline_ignores_terminators_in_comments(parser):
    multiline = "multiline"
    args = 'command "with term; ends" now'
    terminator = r"['\n', '\n']"
    if new_pyparsing:
        multiline = repr(multiline)
        args = repr(args)
    expected = r"""['multiline', 'command "with term; ends" now', '\n', '\n']
- args: {1}
- multilineCommand: {0}
- statement: ['multiline', 'command "with term; ends" now', '\n', '\n']
  - args: {1}
  - multilineCommand: {0}
  - terminator: {2}
- terminator: {2}""".format(multiline, args, terminator)
    assert parser.parseString('multiline command "with term; ends" now\n\n').dump() == expected
