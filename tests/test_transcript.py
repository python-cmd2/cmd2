# coding=utf-8
"""
Cmd2 functional testing based on transcript

Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
Released under MIT license, see LICENSE file
"""
import os
import sys
import random

import mock
import pytest
import six

# Used for sm.input: raw_input() for Python 2 or input() for Python 3
import six.moves as sm

from cmd2 import (Cmd, make_option, options, Cmd2TestCase, set_use_arg_list,
                  set_posix_shlex, set_strip_quotes)
from conftest import run_cmd, StdOut, normalize


class CmdLineApp(Cmd):

    MUMBLES = ['like', '...', 'um', 'er', 'hmmm', 'ahh']
    MUMBLE_FIRST = ['so', 'like', 'well']
    MUMBLE_LAST = ['right?']
    
    def __init__(self, *args, **kwargs):
        self.abbrev = True
        self.multilineCommands = ['orate']
        self.maxrepeats = 3
        self.redirector = '->'

        # Add stuff to settable and/or shortcuts before calling base class initializer
        self.settable['maxrepeats'] = 'Max number of `--repeat`s allowed'

        # Need to use this older form of invoking super class constructor to support Python 2.x and Python 3.x
        Cmd.__init__(self, *args, **kwargs)
        self.intro = 'This is an intro banner ...'

        # Configure how arguments are parsed for @options commands
        set_posix_shlex(False)
        set_strip_quotes(True)
        set_use_arg_list(False)

    opts = [make_option('-p', '--piglatin', action="store_true", help="atinLay"),
            make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE"),
            make_option('-r', '--repeat', type="int", help="output [n] times")]

    @options(opts, arg_desc='(text to say)')
    def do_speak(self, arg, opts=None):
        """Repeats what you tell me to."""
        arg = ''.join(arg)
        if opts.piglatin:
            arg = '%s%say' % (arg[1:], arg[0])
        if opts.shout:
            arg = arg.upper()
        repetitions = opts.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.poutput(arg)
            # recommend using the poutput function instead of
            # self.stdout.write or "print", because Cmd allows the user
            # to redirect output

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input

    @options([ make_option('-r', '--repeat', type="int", help="output [n] times") ])
    def do_mumble(self, arg, opts=None):
        """Mumbles what you tell me to."""
        repetitions = opts.repeat or 1
        arg = arg.split()
        for i in range(min(repetitions, self.maxrepeats)):
            output = []
            if (random.random() < .33):
                output.append(random.choice(self.MUMBLE_FIRST))
            for word in arg:
                if (random.random() < .40):
                    output.append(random.choice(self.MUMBLES))
                output.append(word)
            if (random.random() < .25):
                output.append(random.choice(self.MUMBLE_LAST))
            self.poutput(' '.join(output))


class DemoApp(Cmd):
    @options(make_option('-n', '--name', action="store", help="your name"))
    def do_hello(self, arg, opts):
        """Says hello."""
        if opts.name:
            self.stdout.write('Hello {}\n'.format(opts.name))
        else:
            self.stdout.write('Hello Nobody\n')


@pytest.fixture
def _cmdline_app():
    c = CmdLineApp()
    c.stdout = StdOut()
    return c


@pytest.fixture
def _demo_app():
    c = DemoApp()
    c.stdout = StdOut()
    return c


def _get_transcript_blocks(transcript):
    cmd = None
    expected = ''
    for line in transcript.splitlines():
        if line.startswith('(Cmd) '):
            if cmd is not None:
                yield cmd, normalize(expected)

            cmd = line[6:]
            expected = ''
        else:
            expected += line + '\n'
    yield cmd, normalize(expected)


def test_base_with_transcript(_cmdline_app):
    app = _cmdline_app
    transcript = """
(Cmd) help

Documented commands (type help <topic>):
========================================
_relative_load  help     mumble  pyscript  save  shell      speak
cmdenvironment  history  orate   quit      say   shortcuts
edit            load     py      run       set   show

(Cmd) help say
Repeats what you tell me to.
Usage: speak [options] (text to say)

Options:
  -h, --help            show this help message and exit
  -p, --piglatin        atinLay
  -s, --shout           N00B EMULATION MODE
  -r REPEAT, --repeat=REPEAT
                        output [n] times

(Cmd) say goodnight, Gracie
goodnight, Gracie
(Cmd) say -ps --repeat=5 goodnight, Gracie
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
(Cmd) set maxrepeats 5
maxrepeats - was: 3
now: 5
(Cmd) say -ps --repeat=5 goodnight, Gracie
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
(Cmd) hi
-------------------------[1]
help
-------------------------[2]
help say
-------------------------[3]
say goodnight, Gracie
-------------------------[4]
say -ps --repeat=5 goodnight, Gracie
-------------------------[5]
set maxrepeats 5
-------------------------[6]
say -ps --repeat=5 goodnight, Gracie
(Cmd) run 4
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
(Cmd) set prompt "---> "
prompt - was: (Cmd)
now: --->
"""

    for cmd, expected in _get_transcript_blocks(transcript):
        out = run_cmd(app, cmd)
        assert out == expected


class TestMyAppCase(Cmd2TestCase):
    CmdApp = CmdLineApp
    CmdApp.testfiles = ['tests/transcript.txt']


def test_optparser(_cmdline_app, capsys):
    run_cmd(_cmdline_app, 'say -h')
    out, err = capsys.readouterr()
    expected = normalize("""
Repeats what you tell me to.
Usage: speak [options] (text to say)

Options:
  -h, --help            show this help message and exit
  -p, --piglatin        atinLay
  -s, --shout           N00B EMULATION MODE
  -r REPEAT, --repeat=REPEAT
                        output [n] times""")
    # NOTE: For some reason this extra cast to str is required for Python 2.7 but not 3.x
    assert normalize(str(out)) == expected


def test_optparser_nosuchoption(_cmdline_app, capsys):
    run_cmd(_cmdline_app, 'say -a')
    out, err = capsys.readouterr()
    expected = normalize("""
no such option: -a
Repeats what you tell me to.
Usage: speak [options] (text to say)

Options:
  -h, --help            show this help message and exit
  -p, --piglatin        atinLay
  -s, --shout           N00B EMULATION MODE
  -r REPEAT, --repeat=REPEAT
                        output [n] times""")
    assert normalize(str(out)) == expected


def test_comment_stripping(_cmdline_app):
    out = run_cmd(_cmdline_app, 'speak it was /* not */ delicious! # Yuck!')
    expected = normalize("""it was delicious!""")
    assert out == expected


def test_optarser_correct_args_with_quotes_and_midline_options(_cmdline_app):
    out = run_cmd(_cmdline_app, "speak 'This is a' -s test of the emergency broadcast system!")
    expected = normalize("""THIS IS A TEST OF THE EMERGENCY BROADCAST SYSTEM!""")
    assert out == expected


def test_optarser_options_with_spaces_in_quotes(_demo_app):
    out = run_cmd(_demo_app, "hello foo -n 'Bugs Bunny' bar baz")
    expected = normalize("""Hello Bugs Bunny""")
    assert out == expected


def test_commands_at_invocation():
    testargs = ["prog", "say hello", "say Gracie", "quit"]
    expected = "This is an intro banner ...\nhello\nGracie\n"
    with mock.patch.object(sys, 'argv', testargs):
        app = CmdLineApp()
        app.stdout = StdOut()
        app.cmdloop()
        out = app.stdout.buffer
        assert out == expected

def test_invalid_syntax(_cmdline_app, capsys):
    run_cmd(_cmdline_app, 'speak "')
    out, err = capsys.readouterr()
    expected = normalize("""ERROR: Invalid syntax: No closing quotation""")
    assert normalize(str(err)) == expected


@pytest.mark.parametrize('filename, feedback_to_output', [
    ('bol_eol.txt', False),
    ('characterclass.txt', False),
    ('dotstar.txt', False),
    ('extension_notation.txt', False),
    ('from_cmdloop.txt', True),
    ('multiline_no_regex.txt', False),
    ('multiline_regex.txt', False),
    ('regex_set.txt', False),
    ('singleslash.txt', False),
    ('slashes_escaped.txt', False),
    ('slashslash.txt', False),
    ('spaces.txt', False),
    ('word_boundaries.txt', False),
    ])
def test_transcript(request, capsys, filename, feedback_to_output):
    # Create a cmd2.Cmd() instance and make sure basic settings are
    # like we want for test
    app = CmdLineApp()
    app.feedback_to_output = feedback_to_output

    # Get location of the transcript
    test_dir = os.path.dirname(request.module.__file__)
    transcript_file = os.path.join(test_dir, 'transcripts', filename)

    # Need to patch sys.argv so cmd2 doesn't think it was called with
    # arguments equal to the py.test args
    testargs = ['prog', '-t', transcript_file]
    with mock.patch.object(sys, 'argv', testargs):
        # Run the command loop
        app.cmdloop()

    # Check for the unittest "OK" condition for the 1 test which ran
    expected_start = ".\n----------------------------------------------------------------------\nRan 1 test in"
    expected_end = "s\n\nOK\n"
    out, err = capsys.readouterr()
    if six.PY3:
        assert err.startswith(expected_start)
        assert err.endswith(expected_end)
    else:
        assert err == ''
        assert out == ''


@pytest.mark.parametrize('expected, transformed', [
    ( 'text with no slashes', 'text\ with\ no\ slashes' ),
    # stuff with just one slash
    ( 'use 2/3 cup', 'use\ 2\/3\ cup' ),
    ( '/tmp is nice', '\/tmp\ is\ nice'),
    ( 'slash at end/', 'slash\ at\ end\/'),
    # regexes
    ( 'specials .*', 'specials\ \.\*' ),
    ( '/.*/', '.*' ),
    ( 'specials ^ and + /[0-9]+/', 'specials\ \^\ and\ \+\ [0-9]+' ),
    ( '/a{6}/ but not \/a{6} with /.*?/ more', 'a{6}\ but\ not\ \/a\{6\}\ with\ .*?\ more' ),
    ( 'not this slash\/ or this one\/', 'not\ this\ slash\\/\ or\ this\ one\\/' ),
    ( 'not \/, use /\|?/, not \/', 'not\ \\/\,\ use\ \|?\,\ not\ \\/' ),
    # inception: slashes in our regex. backslashed on input, bare on output
    ( 'not \/, use /\/?/, not \/', 'not\ \\/\,\ use\ /?\,\ not\ \\/' ),
    ( 'the /\/?/ more /.*/ stuff', 'the\ /?\ more\ .*\ stuff' ),
    ])
def test_parse_transcript_expected(expected, transformed):
    app = CmdLineApp()
    
    class TestMyAppCase(Cmd2TestCase):
        cmdapp = app

    testcase = TestMyAppCase()
    assert testcase._transform_transcript_expected(expected) == transformed
