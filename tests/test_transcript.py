# coding=utf-8
# flake8: noqa E302
"""
Cmd2 functional testing based on transcript
"""
import argparse
import os
import random
import re
import sys
import tempfile
from unittest import mock

import pytest

import cmd2
from cmd2 import transcript
from cmd2.utils import Settable, StdSim

from .conftest import run_cmd, verify_help_text


class CmdLineApp(cmd2.Cmd):

    MUMBLES = ['like', '...', 'um', 'er', 'hmmm', 'ahh']
    MUMBLE_FIRST = ['so', 'like', 'well']
    MUMBLE_LAST = ['right?']

    def __init__(self, *args, **kwargs):
        self.maxrepeats = 3

        super().__init__(*args, multiline_commands=['orate'], **kwargs)

        # Make maxrepeats settable at runtime
        self.add_settable(Settable('maxrepeats', int, 'Max number of `--repeat`s allowed'))

        self.intro = 'This is an intro banner ...'

    speak_parser = argparse.ArgumentParser()
    speak_parser.add_argument('-p', '--piglatin', action="store_true", help="atinLay")
    speak_parser.add_argument('-s', '--shout', action="store_true", help="N00B EMULATION MODE")
    speak_parser.add_argument('-r', '--repeat', type=int, help="output [n] times")

    @cmd2.with_argparser(speak_parser, with_unknown_args=True)
    def do_speak(self, opts, arg):
        """Repeats what you tell me to."""
        arg = ' '.join(arg)
        if opts.piglatin:
            arg = '%s%say' % (arg[1:], arg[0])
        if opts.shout:
            arg = arg.upper()
        repetitions = opts.repeat or 1
        for _ in range(min(repetitions, self.maxrepeats)):
            self.poutput(arg)
            # recommend using the poutput function instead of
            # self.stdout.write or "print", because Cmd allows the user
            # to redirect output

    do_say = do_speak  # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input

    mumble_parser = argparse.ArgumentParser()
    mumble_parser.add_argument('-r', '--repeat', type=int, help="output [n] times")

    @cmd2.with_argparser(mumble_parser, with_unknown_args=True)
    def do_mumble(self, opts, arg):
        """Mumbles what you tell me to."""
        repetitions = opts.repeat or 1
        #arg = arg.split()
        for _ in range(min(repetitions, self.maxrepeats)):
            output = []
            if random.random() < .33:
                output.append(random.choice(self.MUMBLE_FIRST))
            for word in arg:
                if random.random() < .40:
                    output.append(random.choice(self.MUMBLES))
                output.append(word)
            if random.random() < .25:
                output.append(random.choice(self.MUMBLE_LAST))
            self.poutput(' '.join(output))

    def do_nothing(self, statement):
        """Do nothing and output nothing"""
        pass

    def do_keyboard_interrupt(self, _):
        raise KeyboardInterrupt('Interrupting this command')


def test_commands_at_invocation():
    testargs = ["prog", "say hello", "say Gracie", "quit"]
    expected = "This is an intro banner ...\nhello\nGracie\n"
    with mock.patch.object(sys, 'argv', testargs):
        app = CmdLineApp()

    app.stdout = StdSim(app.stdout)
    app.cmdloop()
    out = app.stdout.getvalue()
    assert out == expected

@pytest.mark.parametrize('filename,feedback_to_output', [
    ('bol_eol.txt', False),
    ('characterclass.txt', False),
    ('dotstar.txt', False),
    ('extension_notation.txt', False),
    ('from_cmdloop.txt', True),
    ('multiline_no_regex.txt', False),
    ('multiline_regex.txt', False),
    ('no_output.txt', False),
    ('no_output_last.txt', False),
    ('regex_set.txt', False),
    ('singleslash.txt', False),
    ('slashes_escaped.txt', False),
    ('slashslash.txt', False),
    ('spaces.txt', False),
    ('word_boundaries.txt', False),
    ])
def test_transcript(request, capsys, filename, feedback_to_output):
    # Get location of the transcript
    test_dir = os.path.dirname(request.module.__file__)
    transcript_file = os.path.join(test_dir, 'transcripts', filename)

    # Need to patch sys.argv so cmd2 doesn't think it was called with
    # arguments equal to the py.test args
    testargs = ['prog', '-t', transcript_file]
    with mock.patch.object(sys, 'argv', testargs):
        # Create a cmd2.Cmd() instance and make sure basic settings are
        # like we want for test
        app = CmdLineApp()

    app.feedback_to_output = feedback_to_output

    # Run the command loop
    sys_exit_code = app.cmdloop()
    assert sys_exit_code == 0

    # Check for the unittest "OK" condition for the 1 test which ran
    expected_start = ".\n----------------------------------------------------------------------\nRan 1 test in"
    expected_end = "s\n\nOK\n"
    _, err = capsys.readouterr()
    assert err.startswith(expected_start)
    assert err.endswith(expected_end)

def test_history_transcript():
    app = CmdLineApp()
    app.stdout = StdSim(app.stdout)
    run_cmd(app, 'orate this is\na /multiline/\ncommand;\n')
    run_cmd(app, 'speak /tmp/file.txt is not a regex')

    expected = r"""(Cmd) orate this is
> a /multiline/
> command;
this is a \/multiline\/ command
(Cmd) speak /tmp/file.txt is not a regex
\/tmp\/file.txt is not a regex
"""

    # make a tmp file
    fd, history_fname = tempfile.mkstemp(prefix='', suffix='.txt')
    os.close(fd)

    # tell the history command to create a transcript
    run_cmd(app, 'history -t "{}"'.format(history_fname))

    # read in the transcript created by the history command
    with open(history_fname) as f:
        xscript = f.read()

    assert xscript == expected

def test_history_transcript_bad_filename():
    app = CmdLineApp()
    app.stdout = StdSim(app.stdout)
    run_cmd(app, 'orate this is\na /multiline/\ncommand;\n')
    run_cmd(app, 'speak /tmp/file.txt is not a regex')

    expected = r"""(Cmd) orate this is
> a /multiline/
> command;
this is a \/multiline\/ command
(Cmd) speak /tmp/file.txt is not a regex
\/tmp\/file.txt is not a regex
"""

    # make a tmp file
    history_fname = '~/fakedir/this_does_not_exist.txt'

    # tell the history command to create a transcript
    run_cmd(app, 'history -t "{}"'.format(history_fname))

    # read in the transcript created by the history command
    with pytest.raises(FileNotFoundError):
        with open(history_fname) as f:
            transcript = f.read()
        assert transcript == expected


def test_run_script_record_transcript(base_app, request):
    test_dir = os.path.dirname(request.module.__file__)
    filename = os.path.join(test_dir, 'scripts', 'help.txt')

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # make a tmp file to use as a transcript
    fd, transcript_fname = tempfile.mkstemp(prefix='', suffix='.trn')
    os.close(fd)

    # Execute the run_script command with the -t option to generate a transcript
    run_cmd(base_app, 'run_script {} -t {}'.format(filename, transcript_fname))

    assert base_app._script_dir == []
    assert base_app._current_script_dir is None

    # read in the transcript created by the history command
    with open(transcript_fname) as f:
        xscript = f.read()

    assert xscript.startswith('(Cmd) help -v\n')
    verify_help_text(base_app, xscript)


def test_generate_transcript_stop(capsys):
    # Verify transcript generation stops when a command returns True for stop
    app = CmdLineApp()

    # Make a tmp file to use as a transcript
    fd, transcript_fname = tempfile.mkstemp(prefix='', suffix='.trn')
    os.close(fd)

    # This should run all commands
    commands = ['help', 'set']
    app._generate_transcript(commands, transcript_fname)
    _, err = capsys.readouterr()
    assert err.startswith("2 commands")

    # Since quit returns True for stop, only the first 2 commands will run
    commands = ['help', 'quit', 'set']
    app._generate_transcript(commands, transcript_fname)
    _, err = capsys.readouterr()
    assert err.startswith("Command 2 triggered a stop")

    # keyboard_interrupt command should stop the loop and not run the third command
    commands = ['help', 'keyboard_interrupt', 'set']
    app._generate_transcript(commands, transcript_fname)
    _, err = capsys.readouterr()
    assert err.startswith("Interrupting this command\nCommand 2 triggered a stop")


@pytest.mark.parametrize('expected, transformed', [
    # strings with zero or one slash or with escaped slashes means no regular
    # expression present, so the result should just be what re.escape returns.
    # we don't use static strings in these tests because re.escape behaves
    # differently in python 3.7 than in prior versions
    ( 'text with no slashes', re.escape('text with no slashes') ),
    ( 'specials .*', re.escape('specials .*') ),
    ( 'use 2/3 cup', re.escape('use 2/3 cup') ),
    ( '/tmp is nice', re.escape('/tmp is nice') ),
    ( 'slash at end/', re.escape('slash at end/') ),
    # escaped slashes
    ( r'not this slash\/ or this one\/', re.escape('not this slash/ or this one/' ) ),
    # regexes
    ( '/.*/', '.*' ),
    ( 'specials ^ and + /[0-9]+/', re.escape('specials ^ and + ') + '[0-9]+' ),
    ( r'/a{6}/ but not \/a{6} with /.*?/ more', 'a{6}' + re.escape(' but not /a{6} with ') + '.*?' + re.escape(' more') ),
    ( r'not \/, use /\|?/, not \/', re.escape('not /, use ') + r'\|?' + re.escape(', not /') ),
    # inception: slashes in our regex. backslashed on input, bare on output
    ( r'not \/, use /\/?/, not \/', re.escape('not /, use ') + '/?' + re.escape(', not /') ),
    ( r'lots /\/?/ more /.*/ stuff', re.escape('lots ') + '/?' + re.escape(' more ') + '.*' + re.escape(' stuff') ),
    ])
def test_parse_transcript_expected(expected, transformed):
    app = CmdLineApp()

    class TestMyAppCase(transcript.Cmd2TestCase):
        cmdapp = app

    testcase = TestMyAppCase()
    assert testcase._transform_transcript_expected(expected) == transformed


def test_transcript_failure(request, capsys):
    # Get location of the transcript
    test_dir = os.path.dirname(request.module.__file__)
    transcript_file = os.path.join(test_dir, 'transcripts', 'failure.txt')

    # Need to patch sys.argv so cmd2 doesn't think it was called with
    # arguments equal to the py.test args
    testargs = ['prog', '-t', transcript_file]
    with mock.patch.object(sys, 'argv', testargs):
        # Create a cmd2.Cmd() instance and make sure basic settings are
        # like we want for test
        app = CmdLineApp()

    app.feedback_to_output = False

    # Run the command loop
    sys_exit_code = app.cmdloop()
    assert sys_exit_code != 0

    expected_start = "File "
    expected_end = "s\n\nFAILED (failures=1)\n\n"
    _, err = capsys.readouterr()
    assert err.startswith(expected_start)
    assert err.endswith(expected_end)


def test_transcript_no_file(request, capsys):
    # Need to patch sys.argv so cmd2 doesn't think it was called with
    # arguments equal to the py.test args
    testargs = ['prog', '-t']
    with mock.patch.object(sys, 'argv', testargs):
        app = CmdLineApp()

    app.feedback_to_output = False

    # Run the command loop
    sys_exit_code = app.cmdloop()
    assert sys_exit_code != 0

    # Check for the unittest "OK" condition for the 1 test which ran
    expected = 'No test files found - nothing to test\n'
    _, err = capsys.readouterr()
    assert err == expected
