Settings
========

- current settings and what they do
- how a developer can add their own
- how to hide built in settings from a user

Built In Settings
-----------------

``cmd2`` has a number of built in settings, which a developer can set a default
value, and which users can modify to change the behavior of the application.


Timing
~~~~~~

Setting ``App.timing`` to ``True`` outputs timing data after every application
command is executed.  |settable|


Echo
~~~~

If ``True``, each command the user issues will be repeated to the screen before
it is executed.  This is particularly useful when running scripts.


Debug
~~~~~

Setting ``App.debug`` to ``True`` will produce detailed error stacks whenever
the application generates an error.  |settable|

.. |settable| replace:: The user can ``set`` this parameter
                        during application execution.
                        (See :ref:`parameters`)

.. _parameters:

Other user-settable parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A list of all user-settable parameters, with brief
comments, is viewable from within a running application
with::

    (Cmd) set --long
    allow_ansi: Terminal           # Allow ANSI escape sequences in output (valid values: Terminal, Always, Never)
    continuation_prompt: >         # On 2nd+ line of input
    debug: False                   # Show full error stack on error
    echo: False                    # Echo command issued into output
    editor: vim                    # Program used by ``edit``
    feedback_to_output: False      # include nonessentials in `|`, `>` results
    locals_in_py: False            # Allow access to your application in py via self
    prompt: (Cmd)                  # The prompt issued to solicit input
    quiet: False                   # Don't print nonessential feedback
    timing: False                  # Report execution times

Any of these user-settable parameters can be set while running your app with
the ``set`` command like so::

    set allow_ansi Never



Create New Settings
-------------------

Your application can define user-settable parameters which your code can
reference. First create a class attribute with the default value. Then update
the ``settable`` dictionary with your setting name and a short description
before you initialize the superclass. Here's an example, from
``examples/environment.py``:

.. literalinclude:: ../../examples/environment.py

If you want to be notified when a setting changes (as we do above), then define
a method ``_onchange_{setting}()``. This method will be called after the user
changes a setting, and will receive both the old value and the new value.

.. code-block:: text

   (Cmd) set --long | grep sunny
   sunny: False                # Is it sunny outside?
   (Cmd) set --long | grep degrees
   degrees_c: 22               # Temperature in Celsius
   (Cmd) sunbathe
   Too dim.
   (Cmd) set degrees_c 41
   degrees_c - was: 22
   now: 41
   (Cmd) set sunny
   sunny: True
   (Cmd) sunbathe
   UV is bad for your skin.
   (Cmd) set degrees_c 13
   degrees_c - was: 41
   now: 13
   (Cmd) sunbathe
   It's 13 C - are you a penguin?
