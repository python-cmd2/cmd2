First Application
=================

.. _cmd: https://docs.python.org/3/library/cmd.html

Here's a quick walkthrough of a simple application which demonstrates 8
features of ``cmd2``:

* :ref:`features/settings:Settings`
* :ref:`features/commands:Commands`
* :ref:`features/argument_processing:Argument Processing`
* :ref:`features/generating_output:Generating Output`
* :ref:`features/help:Help`
* :ref:`features/shortcuts_aliases_macros:Shortcuts`
* :ref:`features/multiline_commands:Multiline Commands`
* :ref:`features/history:History`

If you don't want to type as we go, you can download the complete source for
this example.


Basic Application
-----------------

First we need to create a new ``cmd2`` application. Create a new file
``first_app.py`` with the following contents::

    #!/usr/bin/env python
    """A simple cmd2 application."""
    import cmd2


    class FirstApp(cmd2.Cmd):
        """A simple cmd2 application."""


    if __name__ == '__main__':
        import sys
        c = FirstApp()
        sys.exit(c.cmdloop())

We have a new class ``FirstApp`` which is a subclass of
:class:`cmd2.Cmd`. When we tell python to run our file like this:

.. code-block:: shell

   $ python first_app.py

it creates an instance of our class, and calls the :meth:`~cmd2.Cmd.cmdloop`
method. This method accepts user input and runs commands based on that input.
Because we subclassed :class:`cmd2.Cmd`, our new app already has a bunch of
features built in.

Congratulations, you have a working ``cmd2`` app. You can run it, and then type
``quit`` to exit.


Create a New Setting
--------------------

Before we create our first command, we are going to add a setting to this app.
``cmd2`` includes robust support for :ref:`features/settings:Settings`. You
configure settings during object initialization, so we need to add an
initializer to our class::

    def __init__(self):
        super().__init__()

        # Make maxrepeats settable at runtime
        self.maxrepeats = 3
        self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command', self))

In that initializer, the first thing to do is to make sure we initialize
``cmd2``. That's what the ``super().__init__()`` line does. Next create an
attribute to hold the setting. Finally, call the :meth:`~cmd2.Cmd.add_settable`
method with a new instance of a :meth:`~cmd2.utils.Settable` class. Now if you
run the script, and enter the ``set`` command to see the settings, like this:

.. code-block:: shell

   $ python first_app.py
   (Cmd) set

you will see our ``maxrepeats`` setting show up with it's default value of
``3``.


Create A Command
----------------

Now we will create our first command, called ``speak`` which will echo back
whatever we tell it to say. We are going to use an :ref:`argument processor
<features/argument_processing:Argument Processing>` so the ``speak`` command
can shout and talk piglatin. We will also use some built in methods for
:ref:`generating output <features/generating_output:Generating Output>`. Add
this code to ``first_app.py``, so that the ``speak_parser`` attribute and the
``do_speak()`` method are part of the ``CmdLineApp()`` class::

    speak_parser = cmd2.Cmd2ArgumentParser()
    speak_parser.add_argument('-p', '--piglatin', action='store_true', help='atinLay')
    speak_parser.add_argument('-s', '--shout', action='store_true', help='N00B EMULATION MODE')
    speak_parser.add_argument('-r', '--repeat', type=int, help='output [n] times')
    speak_parser.add_argument('words', nargs='+', help='words to say')

    @cmd2.with_argparser(speak_parser)
    def do_speak(self, args):
        """Repeats what you tell me to."""
        words = []
        for word in args.words:
            if args.piglatin:
                word = '%s%say' % (word[1:], word[0])
            if args.shout:
                word = word.upper()
            words.append(word)
        repetitions = args.repeat or 1
        for _ in range(min(repetitions, self.maxrepeats)):
            # .poutput handles newlines, and accommodates output redirection too
            self.poutput(' '.join(words))

Up at the top of the script, you'll also need to add::

    import argparse

There's a bit to unpack here, so let's walk through it. We created
``speak_parser``, which uses the `argparse
<https://docs.python.org/3/library/argparse.html>`_ module from the Python
standard library to parse command line input from a user. There is nothing thus
far that is specific to ``cmd2``.

There is also a new method called ``do_speak()``. In both cmd_ and ``cmd2``,
methods that start with ``do_`` become new commands, so by defining this method
we have created a command called ``speak``.

Note the :func:`~cmd2.decorators.with_argparser` decorator on the
``do_speak()`` method. This decorator does 3 useful things for us:

1. It tells ``cmd2`` to process all input for the ``speak`` command using the
   argparser we defined. If the user input doesn't meet the requirements
   defined by the argparser, then an error will be displayed for the user.
2. It alters our ``do_speak`` method so that instead of receiving the raw user
   input as a parameter, we receive the namespace from the argparser.
3. It creates a help message for us based on the argparser.

You can see in the body of the method how we use the namespace from the
argparser (passed in as the variable ``args``). We build an array of words
which we will output, honoring both the ``--piglatin`` and ``--shout`` options.

At the end of the method, we use our ``maxrepeats`` setting as an upper limit
to the number of times we will print the output.

The last thing you'll notice is that we used the ``self.poutput()`` method to
display our output. ``poutput()`` is a method provided by ``cmd2``, which I
strongly recommend you use anytime you want to :ref:`generate output
<features/generating_output:Generating Output>`. It provides the following
benefits:

1. Allows the user to redirect output to a text file or pipe it to a shell
   process
2. Gracefully handles ``BrokenPipeWarning`` exceptions for redirected output
3. Makes the output show up in a :ref:`transcript
   <features/transcripts:Transcripts>`
4. Honors the setting to :ref:`strip embedded ansi sequences
   <features/settings:allow_style>` (typically used for background and
   foreground colors)

Go run the script again, and try out the ``speak`` command. Try typing ``help
speak``, and you will see a lovely usage message describing the various options
for the command.

With those few lines of code, we created a :ref:`command
<features/commands:Commands>`, used an :ref:`Argument Processor
<features/argument_processing:Argument Processing>`, added a nice :ref:`help
message <features/help:Help>` for our users, and :ref:`generated some output
<features/generating_output:Generating Output>`.


Shortcuts
---------

``cmd2`` has several capabilities to simplify repetitive user input:
:ref:`Shortcuts, Aliases, and Macros
<features/shortcuts_aliases_macros:Shortcuts, Aliases, and Macros>`. Let's add
a shortcut to our application. Shortcuts are character strings that can be used
instead of a command name. For example, ``cmd2`` has support for a shortcut
``!`` which runs the ``shell`` command. So instead of typing this:

.. code-block:: shell

   (Cmd) shell ls -al

you can type this:

.. code-block:: shell

   (Cmd) !ls -al

Let's add a shortcut for our ``speak`` command. Change the ``__init__()``
method so it looks like this::

    def __init__(self):
        shortcuts = cmd2.DEFAULT_SHORTCUTS
        shortcuts.update({'&': 'speak'})
        super().__init__(shortcuts=shortcuts)

        # Make maxrepeats settable at runtime
        self.maxrepeats = 3
        self.add_settable(cmd2.Settable('maxrepeats', int, 'max repetitions for speak command', self))

Shortcuts are passed to the ``cmd2`` initializer, and if you want the built-in
shortcuts of ``cmd2`` you have to pass them. These shortcuts are defined as a
dictionary, with the key being the shortcut, and the value containing the
command. When using the default shortcuts and also adding your own, it's a good
idea to use the ``.update()`` method to modify the dictionary. This way if you
add a shortcut that happens to already be in the default set, yours will
override, and you won't get any errors at runtime.

Run your app again, and type:

.. code-block:: shell

   (Cmd) shortcuts

to see the list of all of the shortcuts, including the one for speak that we
just created.


Multiline Commands
------------------

Some use cases benefit from the ability to have commands that span more than
one line. For example, you might want the ability for your user to type in a
SQL command, which can often span lines and which are terminated with a
semicolon. Let's add a :ref:`multiline command
<features/multiline_commands:Multiline Commands>` to our application. First
we'll create a new command called ``orate``. This code shows both the
definition of our ``speak`` command, and the ``orate`` command::

    @cmd2.with_argparser(speak_parser)
    def do_speak(self, args):
        """Repeats what you tell me to."""
        words = []
        for word in args.words:
            if args.piglatin:
                word = '%s%say' % (word[1:], word[0])
            if args.shout:
                word = word.upper()
            words.append(word)
        repetitions = args.repeat or 1
        for _ in range(min(repetitions, self.maxrepeats)):
            # .poutput handles newlines, and accommodates output redirection too
            self.poutput(' '.join(words))

    # orate is a synonym for speak which takes multiline input
    do_orate = do_speak

With the new command created, we need to tell ``cmd2`` to treat that command as
a multi-line command. Modify the super initialization line to look like this::

    super().__init__(multiline_commands=['orate'], shortcuts=shortcuts)

Now when you run the example, you can type something like this:

.. code-block:: shell

    (Cmd) orate O for a Muse of fire, that would ascend
    > The brightest heaven of invention,
    > A kingdom for a stage, princes to act
    > And monarchs to behold the swelling scene! ;

Notice the prompt changes to indicate that input is still ongoing. ``cmd2``
will continue prompting for input until it sees an unquoted semicolon (the
default multi-line command termination character).


History
-------

``cmd2`` tracks the history of the commands that users enter. As a developer,
you don't need to do anything to enable this functionality, you get it for
free. If you want the history of commands to persist between invocations of
your application, you'll need to do a little work. The
:ref:`features/history:History` page has all the details.

Users can access command history using two methods:

- the `readline <https://docs.python.org/3/library/readline.html>`_ library
  which provides a python interface to the `GNU readline library
  <https://en.wikipedia.org/wiki/GNU_Readline>`_
- the ``history`` command which is built-in to ``cmd2``

From the prompt in a ``cmd2``-based application, you can press ``Control-p`` to
move to the previously entered command, and ``Control-n`` to move to the next
command. You can also search through the command history using ``Control-r``.
The `GNU Readline User Manual
<http://man7.org/linux/man-pages/man3/readline.3.html>`_ has all the
details, including all the available commands, and instructions for customizing
the key bindings.

The ``history`` command allows a user to view the command history, and select
commands from history by number, range, string search, or regular expression.
With the selected commands, users can:

- re-run the commands
- edit the selected commands in a text editor, and run them after the text
  editor exits
- save the commands to a file
- run the commands, saving both the commands and their output to a file

Learn more about the ``history`` command by typing ``history -h`` at any
``cmd2`` input prompt, or by exploring :ref:`Command History For Users
<features/history:For Users>`.


Conclusion
----------

You've just created a simple, but functional command line application. With
minimal work on your part, the application leverages many robust features of
``cmd2``. To learn more you can:

- Dive into all of the :doc:`../features/index` that ``cmd2`` provides
- Look at more :doc:`../examples/index`
- Browse the :doc:`../api/index`
