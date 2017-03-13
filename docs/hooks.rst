.. cmd2 documentation for application and command lifecycle and the hooks which are available

cmd2 Application Lifecyle and Hooks
===================================

The typical way of starting a cmd2 application is as follows::

    from cmd2 import Cmd
    class App(Cmd):
        # customized attributes and methods here
    app = App()
    app.cmdloop()

There are several pre-existing methods and attributes which you can tweak to control the overall behavior of your
application before, during, and after the main loop.

Application Lifecycle Hook Methods
----------------------------------
The ``preloop`` and ``postloop`` methods run before and after the main loop, respectively.

.. automethod:: cmd2.Cmd.preloop

.. automethod:: cmd2.Cmd.postloop

Application Lifecycle Attributes
--------------------------------

There are numerous attributes (member variables of the ``cmd2.Cmd``) which have a signficiant effect on the applicaiton
behavior upon entering or during the main loop.  A partial list of some of the more important ones is presented here:

- **intro**: *str* - if provided this serves as the intro banner printed once at start of application, after ``preloop`` runs
- **allow_cli_args**: *bool* - if True (default), then searches for -t or --test at command line to invoke transcript testing mode instead of a normal main loop
    and also processes any commands provided as arguments on the command line just prior to entering the main loop
- **echo**: *bool* - if True, then the command line entered is echoed to the screen (most useful when running scripts)
- **prompt**: *str* - sets the prompt which is displayed, can be dynamically changed based on applicatoin state and/or
    command results


Command Processing Hooks
------------------------

Inside the main loop, every time the user hits <Enter> the line is processed by the ``onecmd_plus_hooks`` method.

.. automethod:: cmd2.Cmd.onecmd_plus_hooks

As the ``onecmd_plus_hooks`` name implies, there are a number of *hook* methods that can be defined in order to inject
applicaiton-specific behavior at various points during the processing of a line of text entered by the user.  ``cmd2``
increases the 2 hooks provided by ``cmd`` (**precmd** and **postcmd**) to 6 for greater flexibility.  Here are
the various hook methods, presented in chronological order starting with the ones called earliest in the process.

.. automethod:: cmd2.Cmd.preparse

.. automethod:: cmd2.Cmd.postparse

.. automethod:: cmd2.Cmd.postparsing_precmd

.. automethod:: cmd2.Cmd.precmd

.. automethod:: cmd2.Cmd.postcmd

.. automethod:: cmd2.Cmd.postparsing_postcmd
