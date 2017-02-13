
=========================
Installation Instructions
=========================

This section covers the basics of how to install, upgrade, and uninstall ``cmd2``.

Installing
----------
First you need to make sure you have Python 2.7 or Python 3.3+, pip_, and setuptools_.  Then you can just use pip to
install from PyPI_.

.. _pip: https://pypi.python.org/pypi/pip
.. _setuptools: https://pypi.python.org/pypi/setuptools
.. _PyPI: https://pypi.python.org/pypi

Requirements for Installing
~~~~~~~~~~~~~~~~~~~~~~~~~~~
* If you have Python 2 >=2.7.9 or Python 3 >=3.4 installed from `python.org
  <https://www.python.org>`_, you will already have pip_ and
  setuptools_, but may need to upgrade to the latest versions:

  On Linux or OS X:

  ::

    pip install -U pip setuptools


  On Windows:

  ::

    python -m pip install -U pip setuptools


Use pip for Installing
~~~~~~~~~~~~~~~~~~~~~~

pip_ is the recommended installer. Installing with pip is easy::

    pip install cmd2

This should also install the required 3rd-party dependencies, if necessary.


Install from Debian or Ubuntu repos
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
We recommend installing from pip_, but if you wish to install from Debian or Ubuntu repos this can be done with
apt-get.

For Python 2::

    sudo apt-get install python-cmd2

For Python 3::

    sudo apt-get install python3-cmd2

This will also install the required 3rd-party dependencies.


Deploy cmd2.py with your project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is an option suitable for advanced Python users.  The ``cmd2`` module is a single file, **cmd2.py**.  You can
simply include this file within your project's hierarchy.  If you want to modify ``cmd2``, this may be a reasonable
option.  Though, we would encourage you to use stock ``cmd2`` and inheritance to achieve the same goal.


Upgrading cmd2
--------------

Upgrade an already installed ``cmd2`` to the latest version from PyPI_::

    pip install -U cmd2

This will upgrade to the newest stable version of ``cmd2`` and will also upgrade any dependencies if necessary.


Uninstalling cmd2
-----------------
If you wish to permanently uninstall ``cmd2``, this can also easily be done with pip_::

    pip uninstall cmd2
