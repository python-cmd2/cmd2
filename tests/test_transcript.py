#
# Cmd2 functional testing based on transcript
#
# Copyright 2016 Federico Ceratto <federico.ceratto@gmail.com>
# Released under MIT license, see LICENSE file

import pytest

from cmd2 import Cmd, make_option, options
from conftest import run_cmd, StdOut, _normalize


class CmdLineApp(Cmd):
    multilineCommands = ['orate']
    maxrepeats = 3
    redirector = '->'

    opts = [
        make_option('-p', '--piglatin', action="store_true", help="atinLay"),
        make_option('-s', '--shout', action="store_true",
                    help="N00B EMULATION MODE"),
        make_option('-r', '--repeat', type="int", help="output [n] times")
    ]

    @options(opts, arg_desc='(text to say)')
    def do_speak(self, arg, opts=None):
        """Repeats what you tell me to."""
        arg = ''.join(arg)
        if opts.piglatin:
            arg = '%s%say' % (arg[1:].rstrip(), arg[0])
        if opts.shout:
            arg = arg.upper()
        repetitions = opts.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(arg)
            self.stdout.write('\n')
            # self.stdout.write is better than "print", because Cmd can be
            # initialized with a non-standard output destination

    do_say = do_speak    # now "say" is a synonym for "speak"
    do_orate = do_speak  # another synonym, but this one takes multi-line input


@pytest.fixture
def _cmdline_app():
    c = CmdLineApp()
    c.stdout = StdOut()
    #c.shortcuts.update({'&': 'speak', 'h': 'hello'})
    c.settable.append('maxrepeats   Max number of `--repeat`s allowed')
    return c


def _get_transcript_blocks(transcript):
    cmd = None
    expected = ''
    for line in transcript.splitlines():
        if line.startswith('(Cmd) '):
            if cmd is not None:
                yield cmd, _normalize(expected)

            cmd = line[6:]
            expected = ''
        else:
            expected += line + '\n'
    yield cmd, _normalize(expected)


@pytest.mark.xfail
def test_base_with_transcript(_cmdline_app):
    app = _cmdline_app
    transcript = """
(Cmd) help

Documented commands (type help <topic>):
========================================
_load           ed    history  list   pause  run   set        show
_relative_load  edit  l        load   py     save  shell      speak
cmdenvironment  hi    li       orate  r      say   shortcuts

Undocumented commands:
======================
EOF  eof  exit  help  q  quit

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
(Cmd) set
abbrev: True
case_insensitive: True
colors: True
continuation_prompt: >
debug: False
default_file_name: command.txt
echo: False
editor: /\w*/
feedback_to_output: False
maxrepeats: 3
prompt: (Cmd)
quiet: False
timing: False
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
set
-------------------------[6]
set maxrepeats 5
-------------------------[7]
say -ps --repeat=5 goodnight, Gracie
(Cmd) run 4
say -ps --repeat=5 goodnight, Gracie
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
(Cmd) orate Four score and
> seven releases ago
> our BDFL
>
Four score and
seven releases ago
our BDFL
(Cmd) & look, a shortcut!
look, a shortcut!
(Cmd) say put this in a file > myfile.txt
(Cmd) say < myfile.txt
put this in a file
(Cmd) set prompt "---> "
prompt - was: (Cmd)
now: --->
---> say goodbye
goodbye
"""

    for cmd, expected in _get_transcript_blocks(transcript):
        out = run_cmd(app, 'help')
        assert out == expected
