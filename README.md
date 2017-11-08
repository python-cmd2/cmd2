cmd2: a tool for building interactive command line apps
=======================================================
[![Latest Version](https://img.shields.io/pypi/v/cmd2.svg?style=flat-square&label=latest%20stable%20version)](https://pypi.python.org/pypi/cmd2/)
[![Build status](https://img.shields.io/travis/python-cmd2/cmd2.svg?style=flat-square&label=unix%20build)](https://travis-ci.org/python-cmd2/cmd2)
[![Appveyor build status](https://img.shields.io/appveyor/ci/FedericoCeratto/cmd2.svg?style=flat-square&label=windows%20build)](https://ci.appveyor.com/project/FedericoCeratto/cmd2)
[![codecov](https://codecov.io/gh/python-cmd2/cmd2/branch/master/graph/badge.svg)](https://codecov.io/gh/python-cmd2/cmd2)
[![Documentation Status](https://readthedocs.org/projects/cmd2/badge/?version=latest)](http://cmd2.readthedocs.io/en/latest/?badge=latest)

cmd2 is a tool for building interactive command line applications in Python. Its goal is to make it
quick and easy for developers to build feature-rich and user-friendly interactive command line
applications.  It provides a simple API which is an extension of Python's built-in
[cmd](https://docs.python.org/3/library/cmd.html) module.  cmd2 provides a wealth of features on top
of cmd to make your life easier and eliminates much of the boilerplate code which would be necessary
when using cmd.

[![Screenshot](cmd2.png)](https://github.com/python-cmd2/cmd2/blob/master/cmd2.png)


Main Features
-------------
- Searchable command history (`history` command and `<Ctrl>+r`)
- Text file scripting of your application with `load` (`@`) and `_relative_load` (`@@`)
- Python scripting of your application with ``pyscript``
- Run shell commands with ``!``
- Pipe command output to shell commands with `|`
- Redirect command output to file with `>`, `>>`; input from file with `<`
- Bare `>`, `>>` with no filename send output to paste buffer (clipboard)
- `py` enters interactive Python console (opt-in `ipy` for IPython console)
- Multi-line, case-insensitive, and abbreviated commands
- Special-character command shortcuts (beyond cmd's `@` and `!`)
- Settable environment parameters
- Parsing commands with flags
- Unicode character support (*Python 3 only*)
- Good tab-completion of commands, file system paths, and shell commands
- Python 2.7 and 3.3+ support
- Linux, macOS and Windows support
- Trivial to provide built-in help for all commands
- Built-in regression testing framework for your applications (transcript-based testing)


Installation
------------
On all operating systems, the latest stable version of `cmd2` can be installed using pip:

```bash
pip install -U cmd2
```

cmd2 works with Python 2.7 and Python 3.3+ on Windows, macOS, and Linux. It is pure Python code with
the only 3rd-party dependencies being on [six](https://pypi.python.org/pypi/six),
[pyparsing](http://pyparsing.wikispaces.com), and [pyperclip](https://github.com/asweigart/pyperclip).

For information on other installation options, see
[Installation Instructions](https://cmd2.readthedocs.io/en/latest/install.html) in the cmd2
documentation.


Documentation
-------------
The latest documentation for cmd2 can be read online here: https://cmd2.readthedocs.io/en/latest/

It is available in HTML, PDF, and ePub formats.


Feature Overview
----------------
Instructions for implementing each feature follow.

- Searchable command history

    All commands will automatically be tracked in the session's history, unless the command is listed in Cmd's excludeFromHistory attribute.
    The history is accessed through the `history`, `list`, and `run` commands.
    If you wish to exclude some of your custom commands from the history, append their names
    to the list at `Cmd.ExcludeFromHistory`.

- Load commands from file, save to file, edit commands in file

    Type `help load`, `help save`, `help edit` for details.

- Multi-line commands

    Any command accepts multi-line input when its name is listed in `Cmd.multilineCommands`.
    The program will keep expecting input until a line ends with any of the characters
    in `Cmd.terminators` .  The default terminators are `;` and `/n` (empty newline).

- Case-insensitive commands

    All commands are case-insensitive, unless ``Cmd.caseInsensitive`` is set to ``False``.

- Special-character shortcut commands (beyond cmd's "@" and "!")

    To create a single-character shortcut for a command, update `Cmd.shortcuts`.

- Settable environment parameters

    To allow a user to change an environment parameter during program execution,
    append the parameter's name to `Cmd.settable``

- Parsing commands with `optparse` options (flags)

    ```python
    @options([make_option('-m', '--myoption', action="store_true", help="all about my option")])
    def do_myfunc(self, arg, opts):
        if opts.myoption:
            #TODO: Do something useful
            pass
    ```

    See Python standard library's `optparse` documentation: https://docs.python.org/3/library/optparse.html


Tutorials
---------

A few tutorials on using cmd2 exist:

* Florida PyCon 2017 talk: [slides](https://docs.google.com/presentation/d/1LRmpfBt3V-pYQfgQHdczf16F3hcXmhK83tl77R6IJtE)
* PyCon 2010 talk by Catherine Devlin, the original author: [video](http://pyvideo.org/pycon-us-2010/pycon-2010--easy-command-line-applications-with-c.html)
* A nice brief step-by-step tutorial: [blog](https://kushaldas.in/posts/developing-command-line-interpreters-using-python-cmd2.html)


Example Application
-------------------

Example cmd2 application (**examples/example.py**):

```python
'''A sample application for cmd2.'''

from cmd2 import Cmd, make_option, options, set_use_arg_list

class CmdLineApp(Cmd):
    def __init__(self):
        self.multilineCommands = ['orate']
        self.maxrepeats = 3

        # Add stuff to settable and shortcutgs before calling base class initializer
        self.settable['maxrepeats'] = 'max repetitions for speak command'
        self.shortcuts.update({'&': 'speak'})

        # Set use_ipython to True to enable the "ipy" command which embeds and interactive IPython shell
        Cmd.__init__(self, use_ipython=False)

        # For option commands, pass a single argument string instead of a list of argument strings to the do_* methods
        set_use_arg_list(False)

    @options([make_option('-p', '--piglatin', action="store_true", help="atinLay"),
              make_option('-s', '--shout', action="store_true", help="N00B EMULATION MODE"),
              make_option('-r', '--repeat', type="int", help="output [n] times")
             ])
    def do_speak(self, arg, opts=None):
        """Repeats what you tell me to."""
        arg = ''.join(arg)
        if opts.piglatin:
            arg = '%s%say' % (arg[1:], arg[0])
        if opts.shout:
            arg = arg.upper()
        repetitions = opts.repeat or 1
        for i in range(min(repetitions, self.maxrepeats)):
            self.stdout.write(arg)
            self.stdout.write('\n')
            # self.stdout.write is better than "print", because Cmd can be
            # initialized with a non-standard output destination

    do_say = do_speak     # now "say" is a synonym for "speak"
    do_orate = do_speak   # another synonym, but this one takes multi-line input

if __name__ == '__main__':
    c = CmdLineApp()
    c.cmdloop()
```

The following is a sample session running example.py.
Thanks to Cmd2's built-in transcript testing capability, it also serves as a test
suite for example.py when saved as *exampleSession.txt*.
Running

```bash
python example.py -t exampleSession.txt
```
will run all the commands in the transcript against `example.py`, verifying that the output produced
matches the transcript.

example/exampleSession.txt:

```text
(Cmd) help

Documented commands (type help <topic>):
========================================
_relative_load  edit  history  orate  pyscript  run   say  shell      show
cmdenvironment  help  load     py     quit      save  set  shortcuts  speak

(Cmd) help say
Repeats what you tell me to.
Usage: speak [options] arg

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
say -ps --repeat=5 goodnight, Gracie

OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
OODNIGHT, GRACIEGAY
(Cmd) orate Four score and
> seven releases ago
> our BDFL
> blah blah blah
Four score and
seven releases ago
our BDFL
blah blah blah
(Cmd) & look, a shortcut!
look, a shortcut!
(Cmd) show color
colors: /(True|False)/
(Cmd) set prompt "---> "
prompt - was: (Cmd)
now: --->
---> say goodbye
goodbye
```

Note how a regular expression `/(True|False)/` is used near the end for output of the **show color** command since
colored text is currently not available for cmd2 on Windows.  Regular expressions can be used anywhere within a
transcript file simply by embedding them within two forward slashes, `/`.
