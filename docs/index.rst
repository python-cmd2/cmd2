.. cmd2 documentation master file, created by
   sphinx-quickstart on Wed Feb 10 12:05:28 2010.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to cmd2's documentation!
================================

The basic use of ``cmd2`` is identical to that of cmd_.

1. Create a subclass of ``cmd2.Cmd``.  Define attributes and
   ``do_*`` methods to control its behavior.  Throughout this documentation,
   we will assume that you are naming your subclass ``App``::
   
     from cmd2 import Cmd
     class App(Cmd):
         # customized attributes and methods here
         
2. Instantiate ``App`` and start the command loop::

     app = App()
     app.cmdloop()

These docs will refer to ``App`` as your ``cmd2.Cmd``
subclass, and ``app`` as an instance of ``App``.  Of
course, in your program, you may name them whatever
you want.
     
Contents:

.. toctree::
   :maxdepth: 2
   
   overview
   example
   freefeatures
   settingchanges
   unfreefeatures

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

