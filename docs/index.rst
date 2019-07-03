cmd2
====

.. default-domain:: py

.. _cmd: https://docs.python.org/3/library/cmd.html

A python package for building powerful command-line interpreter (CLI)
programs.  Extends the Python Standard Library's cmd_ package.

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


Getting Started
---------------

.. include:: overview/summary.rst

.. toctree::
   :maxdepth: 2
   :hidden:

   overview/index


Migrating from cmd
------------------

[create links with short descriptions to the various migrating pages here]

.. toctree::
   :maxdepth: 2

   migrating/index


Features
--------

[create links with short descriptions to the various feature pages here]

.. toctree::
   :maxdepth: 2

   features/index


API Reference
-------------

.. toctree::
   :maxdepth: 2

   api/index


Examples
--------------------

[create links with short descriptions to the various examples pages here]

.. toctree::
   :maxdepth: 2

   examples/index


Meta
----

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Meta

   doc_conventions


To Be Integrated
----------------

Files from old documentation to be integrated into new structure

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: To Be Integrated

   freefeatures
   integrating
   settingchanges
   unfreefeatures
