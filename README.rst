cmd2
====

.. image:: https://secure.travis-ci.org/python-cmd2/cmd2.png?branch=master
   :target: https://travis-ci.org/python-cmd2/cmd2
   :alt: Build status

.. image:: https://ci.appveyor.com/api/projects/status/github/python-cmd2/cmd2?branch=master
   :target: https://ci.appveyor.com/project/FedericoCeratto/cmd2
   :alt: Appveyor build status

.. image:: https://readthedocs.org/projects/cmd2/badge/?version=latest
    :target: http://cmd2.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/v/cmd2.svg
   :target: https://pypi.python.org/pypi/cmd2/
   :alt: Latest Version

.. image:: https://img.shields.io/pypi/l/cmd2.svg
    :target: https://pypi.python.org/pypi/cmd2/
    :alt: License


cmd2 is a tool for writing command-line interactive applications for Python 2.7 and Python 3.3+.  It is based on the
Python Standard Library's cmd_ module, and can be used any place cmd is used simply by importing cmd2 instead.  It is
pure Python code with the only 3rd-party dependencies being on six_ and pyparsing_

.. _cmd: https://docs.python.org/3/library/cmd.html
.. _six: https://pypi.python.org/pypi/six
.. _pyparsing: http://pyparsing.wikispaces.com

The latest documentation for cmd2 can be read online here: https://cmd2.readthedocs.io/en/latest/

See the `Installation Instructions`_ in the cmd2 documentation for instructions on installing, upgrading, and
uninstalling cmd2.

.. _`Installation Instructions`: https://cmd2.readthedocs.io/en/latest/install.html

The project is `maintained at GitHub`_.  Bug reports may be submitted directly to the `issue tracker`_.  Tested pull
requests, especially ones with pytest_ unit tests are welcome.

.. _`maintained at GitHub`: https://github.com/python-cmd2/cmd2
.. _`issue tracker`: https://github.com/python-cmd2/cmd2/issues
.. _pytest: http://docs.pytest.org


Feature Support
---------------

cmd2 provides the following features, in addition to those already existing in cmd_:

- Searchable command history
- Load commands from file, save to file, edit commands in file
- Multi-line commands
- Case-insensitive commands
- Special-character shortcut commands (beyond cmd's ``@`` and ``!``)
- Settable environment parameters
- Parsing commands with flags
- Redirection to file with ``>``, ``>>``; input from file with ``<``
- Bare ``>``, ``>>`` with no filename send output to paste buffer
- Pipe output to shell commands with ``|``
- Simple transcript-based application testing

Instructions for implementing each feature follow.

- Searchable command history

    All commands will automatically be tracked in the session's history, unless the command is listed in Cmd's excludeFromHistory attribute.
    The history is accessed through the ``history``, ``list``, and ``run`` commands
    (and their abbreviations: `hi`, `li`, `l`, `r`).
    If you wish to exclude some of your custom commands from the history, append their names
    to the list at Cmd.ExcludeFromHistory.

- Load commands from file, save to file, edit commands in file

    Type ``help load``, ``help save``, ``help edit`` for details.

- Multi-line commands

    Any command accepts multi-line input when its name is listed in ``Cmd.multilineCommands``.
    The program will keep expecting input until a line ends with any of the characters
    in ``Cmd.terminators`` .  The default terminators are ``;`` and ``/n`` (empty newline).

- Case-insensitive commands

    All commands are case-insensitive, unless ``Cmd.caseInsensitive`` is set to ``False``.

- Special-character shortcut commands (beyond cmd's "@" and "!")

    To create a single-character shortcut for a command, update ``Cmd.shortcuts``.

- Settable environment parameters

    To allow a user to change an environment parameter during program execution,
    append the parameter's name to ``Cmd.settable``.

- Parsing commands with ``optparse`` options (flags)

    ::

        @options([make_option('-m', '--myoption', action="store_true", help="all about my option")])
        def do_myfunc(self, arg, opts):
            if opts.myoption:
                ...

    See Python standard library's ``optparse`` documentation: http://docs.python.org/lib/optparse-defining-options.html


Tutorials
---------

A couple tutorials on using cmd2 exist:

    * A detailed PyCon 2010 talk by `Catherine Devlin`_, the original author
        * http://pyvideo.org/pycon-us-2010/pycon-2010--easy-command-line-applications-with-c.html
    * A nice brief step-by-step tutorial
        * https://kushaldas.in/posts/developing-command-line-interpreters-using-python-cmd2.html

.. _Catherine Devlin: https://github.com/catherinedevlin


Example Application
-------------------

Example cmd2 application (**example/example.py**) ::

    '''A sample application for cmd2.'''

    from cmd2 import Cmd, make_option, options

    class CmdLineApp(Cmd):
        multilineCommands = ['orate']
        Cmd.shortcuts.update({'&': 'speak'})
        maxrepeats = 3
        Cmd.settable.append('maxrepeats')

        # Setting this true makes it run a shell command if a cmd2/cmd command doesn't exist
        # default_to_shell = True

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

The following is a sample session running example.py.
Thanks to Cmd2's built-in transcript testing capability, it also serves as a test
suite for example.py when saved as *exampleSession.txt*.
Running::

    python example.py -t exampleSession.txt

will run all the commands in the transcript against `example.py`, verifying that the output produced
matches the transcript.

example/exampleSession.txt::

    (Cmd) help

    Documented commands (type help <topic>):
    ========================================
    _relative_load  edit  help     list  orate  py    run   say  shell      show
    cmdenvironment  eof   history  load  pause  quit  save  set  shortcuts  speak

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
    (Cmd) set prompt "---> "
    prompt - was: (Cmd)
    now: --->
    ---> say goodbye
    goodbye
