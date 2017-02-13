.. cmd2 documentation master file, created by
   sphinx-quickstart on Wed Feb 10 12:05:28 2010.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

cmd2
====

A python package for building powerful command-line interpreter (CLI)
programs.  Extends the Python Standard Library's cmd_ package.

.. _cmd: https://docs.python.org/3/library/cmd.html
.. _`cmd2 project page`: https://github.com/python-cmd2/cmd2
.. _`project bug tracker`: https://github.com/python-cmd2/cmd2/issues


The basic use of ``cmd2`` is identical to that of cmd_.

.. highlight:: python

1. Create a subclass of ``cmd2.Cmd``.  Define attributes and
   ``do_*`` methods to control its behavior.  Throughout this documentation,
   we will assume that you are naming your subclass ``App``::

     from cmd2 import Cmd
     class App(Cmd):
         # customized attributes and methods here

2. Instantiate ``App`` and start the command loop::

     app = App()
     app.cmdloop()

.. note::

   The tab-completion feature provided by cmd_ relies on underlying capability provided by GNU readline or an
   equivalent library.  Linux distros will almost always come with the required library installed.
   For Mac OS X, we recommend installing the `gnureadline <https://pypi.python.org/pypi/gnureadline>`_ Python module.
   For Windows, we recommend installing the `pyreadline <https://pypi.python.org/pypi/pyreadline>`_ Python module.

Resources
---------

* cmd_
* `cmd2 project page`_
* `project bug tracker`_
* `PyCon 2010 presentation <https://github.com/python-cmd2/cmd2/blob/master/docs/pycon2010/pycon2010.rst>`_,
  *Easy Command-Line Applications with cmd and cmd2*:
  :doc:`slides <pycon2010/pycon2010>`,
  `video <http://pyvideo.org/pycon-us-2010/pycon-2010--easy-command-line-applications-with-c.html>`_

These docs will refer to ``App`` as your ``cmd2.Cmd``
subclass, and ``app`` as an instance of ``App``.  Of
course, in your program, you may name them whatever
you want.

Contents:

.. toctree::
   :maxdepth: 2

   install
   overview
   freefeatures
   settingchanges
   unfreefeatures
   alternatives

Compatibility
=============

Tested and working with Python 2.7 and 3.3+.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

