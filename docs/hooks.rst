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

Preloop and postloop hook methods are not passed any parameters and any return
value is ignored.


Application Lifecycle Attributes
--------------------------------

There are numerous attributes (member variables of the ``cmd2.Cmd``) which have
a significant effect on the application behavior upon entering or during the
main loop.  A partial list of some of the more important ones is presented here:

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
7. Start timer
8. Call methods registered with `register_precmd_hook()`
9. Call `precmd()` - for backwards compatibility with ``cmd.Cmd``
10. Add statement to history
11. Call `do_command` method
12. Call methods registered with `register_postcmd_hook()`
13. Call `postcmd(stop, statement)` - for backwards compatibility with ``cmd.Cmd``
14. Stop timer and display the elapsed time
15. Stop redirecting output if it was redirected
16. Call methods registered with `register_cmdfinalization_hook()`
17. Call `postparsing_postcmd()` - for backwards compatibility - deprecated

By registering hook methods, steps 4, 8, 12, and 16 allow you to run code
during, and control the flow of the command processing loop. Be aware that
plugins also utilize these hooks, so there may be code running that is not
part of your application. Methods registered for a hook are called in the
order they were registered. You can register a function more than once, and
it will be called each time it was registered.

Postparsing, precomamnd, and postcommand hook methods share some common ways to
influence the command processing loop.

If a hook raises a ``cmd2.EmptyStatement`` exception:
- no more hooks (except command finalization hooks) of any kind will be called
- if the command has not yet been executed, it will not be executed
- no error message will be displayed to the user

If a hook raises any other exception:
- no more hooks (except command finalization hooks) of any kind will be called
- if the command has not yet been executed, it will not be executed
- the exception message will be displayed for the user.

Specific types of hook methods have additional options as described below.

Postparsing Hooks
^^^^^^^^^^^^^^^^^

Postparsing hooks are called after the user input has been parsed but before
execution of the comamnd. These hooks can be used to:
- modify the user input
- cancel execution of the current command
- exit the application

When postparsing hooks are called, output has not been redirected, nor has the
timer for command execution been started.

To define and register a postparsing hook, do the following::

    class App(cmd2.Cmd):
        def __init__(self, *args, *kwargs):
            super().__init__(*args, **kwargs)
            self.register_postparsing_hook(self.myhookmethod)

        def myhookmethod(self, statement):
            return False, statement

The hook method will be passed one parameter, a ``Statement`` object containing
the parsed user input. There are many useful attributes in the ``Statement``
object, including ``.raw`` which contains exactly what the user typed. The hook
method must return a tuple: the first element indicates whether to fatally fail
this command prior to execution and exit the application, and the second element
is a potentially modified ``Statement`` object.

To modify the user input, you create and return a new ``Statement`` object.
Don't try and directly modify the contents of a ``Statement`` object, there be
dragons. Instead, use the various attributes in a ``Statement`` object to
construct a new string, and then parse that string to create a new ``Statement``
object.

``cmd2.Cmd()`` uses an instance of ``cmd2.StatementParser`` to parse user input.
This instance has been configured with the proper command terminators, multiline
commands, and other parsing related settings. This instance is available as the
``self.statement_parser`` attribute. Here's a simple example which shows the
proper technique::

    def myhookmethod(self, statement):
        stop = False
        if not '|' in statement.raw:
            newinput = statement.raw + ' | less'
            statement = self.statement_parser.parse(newinput)
        return stop, statement

If a postparsing hook returns ``True`` as the first value in the tuple:
- no more hooks of any kind (except command finalization hooks) will be called
- the command will not be executed
- no error message will be displayed to the user
- the application will exit


Precommand Hooks
^^^^^^^^^^^^^^^^^

Once output is redirected and the timer started, all the hooks registered with
``register_precmd_hook()`` are called. Here's how you do it::

    class App(cmd2.Cmd):
        def __init__(self, *args, *kwargs):
            super().__init__(*args, **kwargs)
            self.register_precmd_hook(self.myhookmethod)

        def myhookmethod(self, statement):
            return statement

You may choose to create a new ``Statement`` with different properties (see
above) or leave it alone, but you must return a ``Statement`` object.

After all registered precommand hooks have been called, ``self.precmd(statement)``
will be called. This retains full backwards compatibility with ``cmd.Cmd``.

Postcommand Hooks
^^^^^^^^^^^^^^^^^^

Once the command method has returned (i.e. the ``do_command(self, statement) method``
has been called and returns, all postcommand hooks are called. If output was redirected
by the user, it is still redirected, and the command timer is still running.

Here's how to define a register a postcommand hook::

    class App(cmd2.Cmd):
        def __init__(self, *args, *kwargs):
            super().__init__(*args, **kwargs)
            self.register_postcmd_hook(self.myhookmethod)

        def myhookmethod(self, statement):
            stop = False
            return stop

Your hook will be passed the statement object, which describes the command which
was executed. If your postcommand hook method gets called, you are guaranteed that
the command method was called, and that it didn't raise an exception.

If any postcommand hook raises an exception, no further postcommand hook methods
will be called.

After all registered precommand hooks have been called,
``self.postcmd(statement)`` will be called. This retains full backwards
compatibility with ``cmd.Cmd``.

If any postcommand hook (registered or ``self.postcmd()``) returns ``True``,
subsequent postcommand hooks will still be called, as will the command
finalization hooks, but once those hooks have all been called, the application
will terminate.

Command Finalization Hooks
^^^^^^^^^^^^^^^^^^^^^^^^^^

Command finalization hooks are called even if one of the other types of hooks or
the command method raise an exception. Here's how to create and register a
command finalization hook::

    class App(cmd2.Cmd):
        def __init__(self, *args, *kwargs):
            super().__init__(*args, **kwargs)
            self.register_cmdfinalization_hook(self.myhookmethod)

        def myhookmethod(self, stop, statement):
            return stop

If any prior postparsing or precommand hook has requested the application to
terminate, the value of the ``stop`` parameter passed to the first command
finalization hook will be ``True``. Any command finalization hook can change the
value of the ``stop`` parameter before returning it, and the modified value will
be passed to the next command finalization hook. The value returned by the final
command finalization hook will determin whether the application terminates or
not.

This approach to command finalization hooks can be powerful, but it can also
cause problems. If your hook blindly returns ``False``, a prior hook's requst to
exit the application will not be honored. It's best to return the value you were
passed unless you have a compelling reason to do otherwise.

If any command finalization hook raises an exception, no more command
finalization hooks will be called. If the last hook to return a value returned
``True``, then the exception will be rendered, and the application will
terminate.

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