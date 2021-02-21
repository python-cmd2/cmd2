
Installation Instructions
=========================


.. _pip: https://pypi.org/project/pip
.. _setuptools: https://pypi.org/project/setuptools
.. _PyPI: https://pypi.org

``cmd2`` works on Linux, macOS, and Windows. It requires Python 3.6 or
higher, pip_, and setuptools_. If you've got all that, then you can just:

.. code-block:: shell

   $ pip install cmd2

.. note::

  Depending on how and where you have installed Python on your system and on
  what OS you are using, you may need to have administrator or root privileges
  to install Python packages.  If this is the case, take the necessary steps
  required to run the commands in this section as root/admin, e.g.: on most
  Linux or Mac systems, you can precede them with ``sudo``:

  .. code-block:: shell

    $ sudo pip install <package_name>


Prerequisites
-------------

If you have Python 3 >=3.6 installed from `python.org
<https://www.python.org>`_, you will already have pip_ and setuptools_, but may
need to upgrade to the latest versions:

  On Linux or OS X:

  .. code-block:: shell

    $ pip install -U pip setuptools


  On Windows:

  .. code-block:: shell

    > python -m pip install -U pip setuptools


.. _`pip_install`:

Install from PyPI
-----------------

pip_ is the recommended installer. Installing packages from PyPI_ with pip is
easy:

.. code-block:: shell

    $ pip install cmd2

This will install the required 3rd-party dependencies, if necessary.


.. _github:

Install from GitHub
-------------------

The latest version of ``cmd2`` can be installed directly from the master branch
on GitHub using pip_:

.. code-block:: shell

  $ pip install -U git+git://github.com/python-cmd2/cmd2.git


Install from Debian or Ubuntu repos
-----------------------------------

We recommend installing from pip_, but if you wish to install from Debian or
Ubuntu repos this can be done with apt-get.

For Python 3::

    $ sudo apt-get install python3-cmd2

This will also install the required 3rd-party dependencies.

.. warning::

  Versions of ``cmd2`` before 0.8.9 should be considered to be of unstable
  "beta" quality and should not be relied upon for production use.  If you
  cannot get a version >= 0.8.9 from your OS repository, then we recommend
  installing from either pip or GitHub - see :ref:`pip_install` or
  :ref:`github`.


Upgrading cmd2
--------------

Upgrade an already installed ``cmd2`` to the latest version from PyPI_::

    pip install -U cmd2

This will upgrade to the newest stable version of ``cmd2`` and will also
upgrade any dependencies if necessary.


Uninstalling cmd2
-----------------
If you wish to permanently uninstall ``cmd2``, this can also easily be done with pip_::

    $ pip uninstall cmd2


macOS Considerations
--------------------

macOS comes with the `libedit <http://thrysoee.dk/editline/>`_ library which is
similar, but not identical, to GNU Readline. Tab completion for ``cmd2``
applications is only tested against GNU Readline.

There are several ways GNU Readline can be installed within a Python
environment on a Mac, detailed in the following subsections.


gnureadline Python module
~~~~~~~~~~~~~~~~~~~~~~~~~

Install the `gnureadline <https://pypi.org/project/gnureadline>`_ Python module which is statically linked against a specific compatible version of GNU Readline:

.. code-block:: shell

  $ pip install -U gnureadline


readline via conda
~~~~~~~~~~~~~~~~~~

Install the **readline** package using the ``conda`` package manager included
with the Anaconda Python distribution:

.. code-block:: shell

  $ conda install readline


readline via brew
~~~~~~~~~~~~~~~~~

Install the **readline** package using the Homebrew package manager (compiles
from source):

.. code-block:: shell

  $ brew install openssl
  $ brew install pyenv
  $ brew install readline

Then use pyenv to compile Python and link against the installed readline
