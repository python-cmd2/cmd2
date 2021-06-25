Initialization
==============

Here is a basic example ``cmd2`` application which demonstrates many
capabilities which you may wish to utilize while initializing the app::

    #!/usr/bin/env python3
    # coding=utf-8
    """A simple example cmd2 application demonstrating the following:
         1) Colorizing/stylizing output
         2) Using multiline commands
         3) Persistent history
         4) How to run an initialization script at startup
         5) How to group and categorize commands when displaying them in help
         6) Opting-in to using the ipy command to run an IPython shell
         7) Allowing access to your application in py and ipy
         8) Displaying an intro banner upon starting your application
         9) Using a custom prompt
        10) How to make custom attributes settable at runtime
    """
    import cmd2
    from cmd2 import style, fg, bg

    class BasicApp(cmd2.Cmd):
        CUSTOM_CATEGORY = 'My Custom Commands'

        def __init__(self):
            super().__init__(multiline_commands=['echo'], persistent_history_file='cmd2_history.dat',
                             startup_script='scripts/startup.txt', include_ipy=True)

            # Prints an intro banner once upon application startup
            self.intro = style('Welcome to cmd2!', fg=fg.red, bg=bg.white, bold=True)

            # Show this as the prompt when asking for input
            self.prompt = 'myapp> '

            # Used as prompt for multiline commands after the first line
            self.continuation_prompt = '... '

            # Allow access to your application in py and ipy via self
            self.self_in_py = True

            # Set the default category name
            self.default_category = 'cmd2 Built-in Commands'

            # Color to output text in with echo command
            self.foreground_color = 'cyan'

            # Make echo_fg settable at runtime
            self.add_settable(cmd2.Settable('foreground_color',
                                            str,
                                            'Foreground color to use with echo command',
                                            self,
                                            choices=fg.colors()))

        @cmd2.with_category(CUSTOM_CATEGORY)
        def do_intro(self, _):
            """Display the intro banner"""
            self.poutput(self.intro)

        @cmd2.with_category(CUSTOM_CATEGORY)
        def do_echo(self, arg):
            """Example of a multiline command"""
            self.poutput(style(arg, fg=self.foreground_color))


    if __name__ == '__main__':
        app = BasicApp()
        app.cmdloop()


Cmd class initializer
---------------------

A ``cmd2.Cmd`` instance or subclass instance is an interactive CLI application
framework. There is no good reason to instantiate ``Cmd`` itself; rather, it’s
useful as a superclass of a class you define yourself in order to inherit
``Cmd``’s methods and encapsulate action methods.

Certain things must be initialized within the ``__init__()`` method of your
class derived from ``cmd2.Cmd``(all arguments to ``__init__()`` are optional):

.. automethod:: cmd2.Cmd.__init__
    :noindex:

Cmd instance attributes
-----------------------

The ``cmd2.Cmd`` class provides a large number of public instance attributes
which allow developers to customize a ``cmd2`` application further beyond the
options provided by the ``__init__()`` method.

Public instance attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~
Here are instance attributes of ``cmd2.Cmd`` which developers might wish
override:

- **broken_pipe_warning**: if non-empty, this string will be displayed if a
  broken pipe error occurs
- **continuation_prompt**: used for multiline commands on 2nd+ line of input
- **debug**: if ``True`` show full stack trace on error (Default: ``False``)
- **default_category**: if any command has been categorized, then all other
  commands that haven't been categorized will display under this section in the
  help output.
- **default_error**: the error that prints when a non-existent command is run
- **default_sort_key**: the default key for sorting string results. Its default
  value performs a case-insensitive alphabetical sort.
- **default_to_shell**: if ``True`` attempt to run unrecognized commands as
  shell commands (Default: ``False``)
- **disabled_commands**: commands that have been disabled from use. This is to
  support commands that are only available during specific states of the
  application. This dictionary's keys are the command names and its values are
  DisabledCommand objects.
- **doc_header**: Set the header used for the help function's listing of
  documented functions
- **echo**: if ``True``, each command the user issues will be repeated to the
  screen before it is executed. This is particularly useful when running
  scripts. This behavior does not occur when running a command at the prompt.
  (Default: ``False``)
- **editor**: text editor program to use with *edit* command (e.g. ``vim``)
- **exclude_from_history**: commands to exclude from the *history* command
- **exit_code**: this determines the value returned by ``cmdloop()`` when
  exiting the application
- **feedback_to_output**: if ``True`` send nonessential output to stdout, if
  ``False`` send them to stderr (Default: ``False``)
- **help_error**: the error that prints when no help information can be found
- **hidden_commands**: commands to exclude from the help menu and tab
  completion
- **last_result**: stores results from the last command run to enable usage
  of results in a Python script or interactive console. Built-in commands don't
  make use of this.  It is purely there for user-defined commands and
  convenience.
- **self_in_py**: if ``True`` allow access to your application in *py*
  command via ``self`` (Default: ``False``)
- **macros**: dictionary of macro names and their values
- **max_completion_items**: max number of CompletionItems to display during
  tab completion (Default: 50)
- **pager**: sets the pager command used by the ``Cmd.ppaged()`` method for
  displaying wrapped output using a pager
- **pager_chop**: sets the pager command used by the ``Cmd.ppaged()`` method
  for displaying chopped/truncated output using a pager
- **py_bridge_name**: name by which embedded Python environments and scripts
  refer to the ``cmd2`` application by in order to call commands (Default:
  ``app``)
- **py_locals**: dictionary that defines specific variables/functions available
  in Python shells and scripts (provides more fine-grained control than making
  everything available with **self_in_py**)
- **quiet**: if ``True`` then completely suppress nonessential output (Default:
  ``False``)
- **settable**: dictionary that controls which of these instance attributes
  are settable at runtime using the *set* command
- **timing**: if ``True`` display execution time for each command (Default:
  ``False``)
