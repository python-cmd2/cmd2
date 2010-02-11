======================================
Features requiring application changes
======================================

Command shortcuts
=================

.. _parameters:

Environment parameters
======================

Your application can define user-settable parameters 
which your code can reference.  Create them as class attributes
with their default values, and add them (with optional
documentation) to ``settable``.

::

    from cmd2 import Cmd
    class App(Cmd):
        degrees_c = 22
        sunny = False
        settable = Cmd.settable + '''degrees_c temperature in Celsius
                                     sunny'''
        def do_sunbathe(self, arg):
            if self.degrees_c < 20:
                result = "It's {temp} C - are you a penguin?".format(temp=self.degrees_c)
            elif not self.sunny:
                result = 'Too dim.'
            else:
                result = 'UV is bad for your skin.'
            self.stdout.write(result + '\n')
    app = App()
    app.cmdloop()
        
::

    (Cmd) set --long
    degrees_c: 22                  # temperature in Celsius
    sunny: False                   # 
    (Cmd) sunbathe
    Too dim.
    (Cmd) set sunny yes
    sunny - was: False
    now: True
    (Cmd) sunbathe
    UV is bad for your skin.
    (Cmd) set degrees_c 13
    degrees_c - was: 22
    now: 13
    (Cmd) sunbathe
    It's 13 C - are you a penguin?


Commands with flags
===================

.. _outputters:

poutput, pfeedback, perror
==========================

Standard ``cmd`` applications produce their output with ``self.stdout.write('output')`` (or with ``print``,
but ``print`` decreases output flexibility).  ``cmd2`` applications can use 
``self.poutput('output')``, ``self.pfeedback('message')``, and ``self.perror('errmsg')``
instead.  These methods have these advantages:

  - More concise
  - ``.pfeedback()`` destination is controlled by :ref:`quiet` parameter.
  