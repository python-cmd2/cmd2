
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

.. note::

  Depending on how and where you have installed Python on your system and on what OS you are using, you may need to
  have administrator or root privileges to install Python packages.  If this is the case, take the necessary steps
  required to run the commands in this section as root/admin, e.g.: on most Linux or Mac systems, you can precede them
  with ``sudo``::

    sudo pip install <package_name>


.. warning::

  Versions of ``cmd2`` before 0.7.0 should be considered to be of unstable "beta" quality and should not be relied upon
  for production use.  If you cannot get a version >= 0.7 from either pip or your OS repository, then we recommend
  installing from GitHub - see :ref:`github`.


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

pip_ is the recommended installer. Installing packages from PyPI_ with pip is easy::

    pip install cmd2

This should also install the required 3rd-party dependencies, if necessary.


.. _github:

Install from GitHub using pip
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The latest version of ``cmd2`` can be installed directly from the master branch on GitHub using pip_::

  pip install -U git+git://github.com/python-cmd2/cmd2.git

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

``cmd2`` is contained in only one Python file (**cmd2.py**), so it can be easily copied into your project.  *The
copyright and license notice must be retained*.

This is an option suitable for advanced Python users.  You can simply include this file within your project's hierarchy.
If you want to modify ``cmd2``, this may be a reasonable option.  Though, we encourage you to use stock ``cmd2`` and
either composition or inheritance to achieve the same goal.

This approach will obviously NOT automatically install the required 3rd-party dependencies, so you need to make sure
the following Python packages are installed:

  * six
  * pyparsing


Upgrading cmd2
--------------

Upgrade an already installed ``cmd2`` to the latest version from PyPI_::

    pip install -U cmd2

This will upgrade to the newest stable version of ``cmd2`` and will also upgrade any dependencies if necessary.


Uninstalling cmd2
-----------------
If you wish to permanently uninstall ``cmd2``, this can also easily be done with pip_::

    pip uninstall cmd2
