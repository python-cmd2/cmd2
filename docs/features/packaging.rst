
Packaging a cmd2 application for distribution
=================================================

As a general-purpose tool for building interactive command-line applications,
``cmd2`` is designed to be used in many ways. How you distribute your ``cmd2``
application to customers or end users is up to you.  See the
`Overview of Packaging for Python`_ from the Python Packaging Authority for a
thorough discussion of the extensive options within the Python ecosystem.

For developers wishing to package a ``cmd2`` application into a single binary
image or compressed file, we can recommend all of the following based on
personal and professional experience:

* Deploy your ``cmd2`` Python app using Docker_
  * Powerful and flexible - allows you to control entire user space and
  setup other applications like databases
  * As long as it isn't problematic for your customers to have Docker
  installed, then this is probably the best option
* PyInstaller_
  * Quick and easy - it "just works" and everything you need is installable
  via ``pip``
  * Packages up all of the dependencies into a single directory which you can
  then zip up
* Nuitka_
  * Converts your Python to C and compiles it to a native binary file
  * This can be particularly convenient if you wish to obfuscate the Python
  source code behind your application
  * Recommend invoking with ``--follow-imports`` flag like:
  ``python3 -m nuitka --follow-imports your_app.py``
* `Conda Constructor`_
  * Allows you to create a custom Python distro based on Miniconda_

.. _`Overview of Packaging for Python`: https://packaging.python.org/overview/
.. _Docker: https://djangostars.com/blog/what-is-docker-and-how-to-use-it-with-python/
.. _PyInstaller: https://www.pyinstaller.org
.. _Nuitka: https://nuitka.net
.. _`Conda Constructor`: https://github.com/conda/constructor
.. _Miniconda: https://docs.conda.io/en/latest/miniconda.html
