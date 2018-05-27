.. cmd2 documentation for application and command lifecycle and the hooks which are available

cmd2 Application Lifecycle and Hooks
====================================

The typical way of starting a cmd2 application is as follows::

    import cmd2
    class App(cmd2.Cmd):
        # customized attributes and methods here

    if __name__ == '__main__':
        app = App()
        app.cmdloop()

There are several pre-existing methods and attributes which you can tweak to
control the overall behavior of your application before, during,
and after the command processing loop.

Application Lifecycle Hooks
---------------------------

You can register methods to be called at the beginning of the command loop::

    class App(cmd2.Cmd):
        def __init__(self, *args, *kwargs):
            super().__init__(*args, **kwargs)
            self.register_preloop_hook(self.myhookmethod)

        def myhookmethod(self):
            self.poutput("before the loop begins")

And also after the command loop has finished::

    class App(cmd2.Cmd):
        def __init__(self, *args, *kwargs):
            super().__init__(*args, **kwargs)
            self.register_postloop_hook(self.myhookmethod)

        def myhookmethod(self):
            self.poutput("before the loop begins")

As you can see the preloop and postloop hook methods are not passed any
parameters and any return value is ignored.


Application Lifecycle Attributes
--------------------------------

There are numerous attributes (member variables of the ``cmd2.Cmd``) which have a significant effect on the application
behavior upon entering or during the main loop.  A partial list of some of the more important ones is presented here:

- **intro**: *str* - if provided this serves as the intro banner printed once at start of application, after ``preloop`` runs
- **allow_cli_args**: *bool* - if True (default), then searches for -t or --test at command line to invoke transcript testing mode instead of a normal main loop
    and also processes any commands provided as arguments on the command line just prior to entering the main loop
- **echo**: *bool* - if True, then the command line entered is echoed to the screen (most useful when running scripts)
- **prompt**: *str* - sets the prompt which is displayed, can be dynamically changed based on application state and/or
    command results


Command Processing Loop
-----------------------

When you call `.cmdloop()`, the following sequence of events are repeated
until the application exits:

1. Output the prompt
2. Accept user input
3. Parse user input into `Statement` object
4. Call methods registered with `register_postparsing_hook()`
5. Call `postparsing_precmd()` - for backwards compatibility deprecated
6. Redirect output, if user asked for it and it's allowed
7. Start command timer
8. Call methods registered with `register_precmd_hook()`
9. Call `precmd()` - for backwards compatibility deprecated
10. Add statement to history
11. Call `do_command` method
12. Call methods registered with `register_postcmd_hook()`
13. Call `postcmd()` - for backwards compatibility deprecated
14. Stop timer
15. Stop redirecting output, if it was redirected
16. Call methods registered with `register_cmdcompleted_hook()`
17. Call `postparsing_postcmd()` - for backwards compatibility - deprecated

By registering hook methods, steps 4, 8, 12, and 16 allow you to run code
during, and control the flow of the command processing loop. Be aware that
plugins also utilize these hooks, so there may be code running that is not
part of your application. Methods registered for a hook are called in the
order they were registered. You can register a function more than once, and
it will be called each time it was registered.

Postparsing Hooks
^^^^^^^^^^^^^^^^^

You can register one or more methods which are called after the user input
has been parsed, but before output is redirected, the timer is started, and
before the command is run.

To define and register a postparsing hook, do the following::

    class App(cmd2.Cmd):
        def __init__(self, *args, *kwargs):
            super().__init__(*args, **kwargs)
            self.register_postparsing_hook(self.myhookmethod)

        def myhookmethod(self, statement):
            return False, statement

The hook method will be passed one parameter, a `Statement` object containing
the parsed user input. There are many useful attributes in the Statement
object, including `.raw` which contains exactly what the user typed. The hook
method must return a tuple: the first element indicates whether to fatally fail
this command and exit the application, and the second element is a potentially
modified `Statement` object.

To modify the user input, you create and return a new `Statement` object::

        def myhookmethod(self, statement):
            if not '|' in statement.raw:
                newinput = statement.raw + ' | less'
                statement = self.statement_parser.parse(newinput)
            return False, statement

There are several other mechanisms for controlling the flow of command
processing. If you raise an `cmd2.EmptyStatement` exception, no further
postparsing hooks will be run, nor will the command be run. No error will
be displayed for the user either.

If you raise any other exception, no further postprocessing hooks will be run,
nor will the command be executed. The exception message will be displayed for
the user.

Precommand Hooks
^^^^^^^^^^^^^^^^^

Postcommand Hooks
^^^^^^^^^^^^^^^^^^

Command Completed Hooks
^^^^^^^^^^^^^^^^^^^^^^^

Deprecated Application Lifecycle Hook Methods
---------------------------------------------

The ``preloop`` and ``postloop`` methods run before and after the main loop, respectively.

.. automethod:: cmd2.cmd2.Cmd.preloop

.. automethod:: cmd2.cmd2.Cmd.postloop

Deprecated Command Processing Hooks
-----------------------------------

Inside the main loop, every time the user hits <Enter> the line is processed by the ``onecmd_plus_hooks`` method.

.. automethod:: cmd2.cmd2.Cmd.onecmd_plus_hooks

As the ``onecmd_plus_hooks`` name implies, there are a number of *hook* methods that can be defined in order to inject
application-specific behavior at various points during the processing of a line of text entered by the user.  ``cmd2``
increases the 2 hooks provided by ``cmd`` (**precmd** and **postcmd**) to 6 for greater flexibility.  Here are
the various hook methods, presented in chronological order starting with the ones called earliest in the process.

.. automethod:: cmd2.cmd2.Cmd.preparse

.. automethod:: cmd2.cmd2.Cmd.postparse

.. automethod:: cmd2.cmd2.Cmd.postparsing_precmd

.. automethod:: cmd2.cmd2.Cmd.precmd

.. automethod:: cmd2.cmd2.Cmd.postcmd

.. automethod:: cmd2.cmd2.Cmd.postparsing_postcmd