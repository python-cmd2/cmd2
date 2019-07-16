Minimum Required Changes
========================

``cmd2.Cmd`` subclasses ``Cmd.cmd`` from the standard library, and overrides
most of the methods. Most apps based on the standard library can be migrated to
``cmd2`` in just a couple of minutes.


Import and Inheritance
----------------------

You need to change your import from this::

    import cmd

to this::

    import cmd2

Then you need to change your class definition from::

    class CmdLineApp(cmd.Cmd):

to::

    class CmdLineApp(cmd2.Cmd):


Exiting
-------

Have a look at the commands you created to exit your application. You probably
have one called ``exit`` and maybe a similar one called ``quit``. You also
might have implemented a ``do_EOF()`` method so your program exits like many
operating system shells. If all these commands do is quit the application,
you may be able to remove them. See :ref:`features/misc:Exiting`.


Distribution
------------

If you are distributing your application, you'll also need to ensure
that ``cmd2`` is properly installed. You will need to add this to
your ``setup()`` method in ``setup.py``::

    install_requires=[
        'cmd2>=1,<2`
    ]

See :ref:`overview/integrating:Integrate cmd2 Into Your Project` for more
details.
