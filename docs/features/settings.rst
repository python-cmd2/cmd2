Settings
========

- current settings and what they do
- how a developer can add their own
- how to hide built in settings from a user

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
