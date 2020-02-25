History
=======

For Developers
--------------

The ``cmd`` module from the Python standard library includes ``readline``
history.

:class:`cmd2.Cmd` offers the same ``readline`` capabilities, but also maintains
it's own data structures for the history of all commands entered by the user.
When the class is initialized, it creates an instance of the
:class:`cmd2.history.History` class (which is a subclass of ``list``) as
:data:`cmd2.Cmd.history`.

Each time a command is executed (this gets
complex, see :ref:`features/hooks:Command Processing Loop` for exactly when)
the parsed :class:`cmd2.Statement` is appended to :data:`cmd2.Cmd.history`.

``cmd2`` adds the option of making this history persistent via optional
arguments to :meth:`cmd2.Cmd.__init__`. If you pass a filename in the
``persistent_history_file`` argument, the contents of :data:`cmd2.Cmd.history`
will be pickled into that history file. We chose to use pickle instead of plain
text so that we can save the results of parsing all the commands.

.. note::

    ``readline`` saves everything you type, whether it is a valid command or
    not. ``cmd2`` only saves input to internal history if the command parses
    successfully and is a valid command. This design choice was intentional,
    because the contents of history can be saved to a file as a script, or can
    be re-run. Not saving invalid input reduces unintentional errors when doing
    so.

    However, this design choice causes an inconsistency between the
    ``readline`` history and the ``cmd2`` history when you enter an invalid
    command: it is saved to the ``readline`` history, but not to the ``cmd2``
    history.

The :data:`cmd2.Cmd.history` attribute, the :class:`cmd2.history.History`
class, and the :class:`cmd2.history.HistoryItem` class are all part of the
public API for :class:`cmd2.Cmd`. You could use these classes to implement
write your own ``history`` command (see below for documentation on how the
included ``history`` command works). If you don't like pickled history, you
could implement your own mechanism for saving and loading history from a plain
text file.


For Users
---------

You can use the up and down arrow keys to move through the history of
previously entered commands.

If the ``readline`` module is installed, you can press ``Control-p`` to move to
the previously entered command, and ``Control-n`` to move to the next command.
You can also search through the command history using ``Control-r``.

Eric Johnson hosts a nice `readline cheat sheet
<http://readline.kablamo.org/emacs.html>`_, or you can dig into the `GNU
Readline User Manual
<http://man7.org/linux/man-pages/man3/readline.3.html>`_ for all the
details, including instructions for customizing the key bindings.

``cmd2`` makes a third type of history access available with the ``history``
command. Each time the user enters a command, ``cmd2`` saves the input. The
``history`` command lets you do interesting things with that saved input. The
examples to follow all assume that you have entered the following commands::

    (Cmd) alias create one !echo one
    Alias 'one' created
    (Cmd) alias create two !echo two
    Alias 'two' created
    (Cmd) alias create three !echo three
    Alias 'three' created
    (Cmd) alias create four !echo four
    Alias 'four' created

In it's simplest form, the ``history`` command displays previously entered
commands. With no additional arguments, it displays all previously entered
commands::

    (Cmd) history
        1  alias create one !echo one
        2  alias create two !echo two
        3  alias create three !echo three
        4  alias create four !echo four

If you give a positive integer as an argument, then it only displays the
specified command::

    (Cmd) history 4
        4  alias create four !echo four

If you give a negative integer *N* as an argument, then it display the *Nth*
last command. For example, if you give ``-1`` it will display the last command
you entered. If you give ``-2`` it will display the next to last command you
entered, and so forth::

    (Cmd) history -2
        3  alias create three !echo three

You can use a similar mechanism to display a range of commands. Simply give two
command numbers separated by ``..`` or ``:``, and you will see all commands
between, and including, those two numbers::

    (Cmd) history 1:3
        1  alias create one !echo one
        2  alias create two !echo two
        3  alias create three !echo three

If you omit the first number, it will start at the beginning. If you omit the
last number, it will continue to the end::

    (Cmd) history :2
        1  alias create one !echo one
        2  alias create two !echo two
    (Cmd) history 2:
        2  alias create two !echo two
        3  alias create three !echo three
        4  alias create four !echo four

If you want to display the last three commands entered::

    (Cmd) history -- -3:
        2  alias create two !echo two
        3  alias create three !echo three
        4  alias create four !echo four

Notice the double dashes. These are required because the history command uses
``argparse`` to parse the command line arguments. As described in the `argparse
documentation <https://docs.python.org/3/library/argparse.html>`_ , ``-3:`` is
an option, not an argument:

    If you have positional arguments that must begin with - and don’t look
    like negative numbers, you can insert the pseudo-argument '--' which tells
    parse_args() that everything after that is a positional argument:

There is no zeroth command, so don't ask for it. If you are a python
programmer, you've probably noticed this looks a lot like the slice syntax for
lists and arrays. It is, with the exception that the first history command is
1, where the first element in a python array is 0.

Besides selecting previous commands by number, you can also search for them.
You can use a simple string search::

    (Cmd) history two
        2  alias create two !echo two

Or a regular expression search by enclosing your regex in slashes::

    (Cmd) history '/te\ +th/'
        3  alias create three !echo three

If your regular expression contains any characters that ``argparse`` finds
interesting, like dash or plus, you also need to enclose your regular
expression in quotation marks.

This all sounds great, but doesn't it seem like a bit of overkill to have all
these ways to select commands if all we can do is display them? Turns out,
displaying history commands is just the beginning. The history command can
perform many other actions:

- running previously entered commands
- saving previously entered commands to a text file
- opening previously entered commands in your favorite text editor
- running previously entered commands, saving the commands and their output
  to a text file
- clearing the history of entered commands

Each of these actions is invoked using a command line option. The ``-r`` or
``--run`` option runs one or more previously entered commands. To run command
number 1::

    (Cmd) history --run 1

To rerun the last two commands (there's that double dash again to make argparse
stop looking for options)::

    (Cmd) history -r -- -2:

Say you want to re-run some previously entered commands, but you would really
like to make a few changes to them before doing so. When you use the ``-e`` or
``--edit`` option, ``history`` will write the selected commands out to a text
file, and open that file with a text editor. You make whatever changes,
additions, or deletions, you want. When you leave the text editor, all the
commands in the file are executed. To edit and then re-run commands 2-4 you
would::

    (Cmd) history --edit 2:4

If you want to save the commands to a text file, but not edit and re-run them,
use the ``-o`` or ``--output-file`` option. This is a great way to create
:ref:`Scripts <features/scripting:Scripting>`, which can be executed using the
``run_script`` command. To save the first 5 commands entered in this session to
a text file::

    (Cmd) history :5 -o history.txt

The ``history`` command can also save both the commands and their output to a
text file. This is called a transcript. See
:ref:`features/transcripts:Transcripts` for more information on how transcripts
work, and what you can use them for. To create a transcript use the ``-t`` or
``--transcription`` option::

    (Cmd) history 2:3 --transcript transcript.txt

The ``--transcript`` option implies ``--run``: the commands must be re-run in
order to capture their output to the transcript file.

The last action the history command can perform is to clear the command history
using ``-c`` or ``--clear``::

    (Cmd) history -c

In addition to these five actions, the ``history`` command also has some
options to control how the output is formatted. With no arguments, the
``history`` command displays the command number before each command. This is
great when displaying history to the screen because it gives you an easy
reference to identify previously entered commands. However, when creating a
script or a transcript, the command numbers would prevent the script from
loading properly. The ``-s`` or ``--script`` option instructs the ``history``
command to suppress the line numbers. This option is automatically set by the
``--output_file``, ``--transcript``, and ``--edit`` options. If you want to
output the history commands with line numbers to a file, you can do it with
output redirection::

    (Cmd) history 1:4 > history.txt

You might use ``-s`` or ``--script`` on it's own if you want to display history
commands to the screen without line numbers, so you can copy them to the
clipboard::

    (Cmd) history -s 1:3

``cmd2`` supports both aliases and macros, which allow you to substitute a
short, more convenient input string with a longer replacement string. Say we
create an alias like this, and then use it::

    (Cmd) alias create ls shell ls -aF
    Alias 'ls' created
    (Cmd) ls -d h*
    history.txt     htmlcov/

By default, the ``history`` command shows exactly what we typed::

    (Cmd) history
        1  alias create ls shell ls -aF
        2  ls -d h*

There are two ways to modify that display so you can see what aliases and
macros were expanded to. The first is to use ``-x`` or ``--expanded``. These
options show the expanded command instead of the entered command::

    (Cmd) history -x
        1  alias create ls shell ls -aF
        2  shell ls -aF -d h*

If you want to see both the entered command and the expanded command, use the
``-v`` or ``--verbose`` option::

    (Cmd) history -v
        1  alias create ls shell ls -aF
        2  ls -d h*
        2x shell ls -aF -d h*

If the entered command had no expansion, it is displayed as usual. However, if
there is some change as the result of expanding macros and aliases, then the
entered command is displayed with the number, and the expanded command is
displayed with the number followed by an ``x``.
