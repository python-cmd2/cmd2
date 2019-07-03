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


Overview
--------

[create links with short descriptions to the various overview pages here]

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Overview

   overview/featuretour
   overview/installation
   overview/alternatives
   overview/resources
   examples/quickstart


Migrating from cmd
------------------

[create links with short descriptions to the various migrating pages here]

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Migrating from cmd

   migrating/why
   migrating/incompatibilities
   migrating/minimum
   migrating/free_features
   migrating/nextsteps


Features
--------

[create links with short descriptions to the various feature pages here]

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Features

   features/generating_output
   features/argument_processing
   features/prompt
   features/help
   features/history
   features/startup_commands
   features/shortcuts_aliases_macros
   features/settings
   features/completion
   features/os
   features/multiline
   features/disable_commands
   features/clipboard
   features/transcript
   features/hooks
   features/plugins
   features/scripting
   features/embedded_python_shells


Examples
--------------------

[create links with short descriptions to the various examples pages here]

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Examples

   examples/quickstart


API Reference
-------------

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: API Reference

   api/cmd
   api/decorators
   api/exceptions
   api/utility_functions
   api/utility_classes


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
