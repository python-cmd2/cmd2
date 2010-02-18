.. cmd2 documentation master file, created by
   sphinx-quickstart on Wed Feb 10 12:05:28 2010.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

cmd2
====

A python package for building powerful command-line interpreter (CLI)
programs.  Extends the Python Standard Library's cmd_ package.


.. _`cmd2 project page`: http://www.assembla.com/wiki/show/python-cmd2
.. _`project bug tracker`: http://trac-hg.assembla.com/python-cmd2/report/1

.. _cmd: http://docs.python.org/library/cmd.html#module-cmd

.. _`PyCon 2010 presentation`: http://catherinedevlin.pythoneers.com/presentations/cmd_cmd2/pycon2010.html

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

Resources
---------

* cmd_
* `project bug tracker`_
* `cmd2 project page`_
* `PyCon 2010 presentation`: Easy Command-Line Applications with cmd and cmd2

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

