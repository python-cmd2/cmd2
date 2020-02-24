Integrate cmd2 Into Your Project
====================================

Once installed, you will want to ensure that your project's dependencies
include ``cmd2``. Make sure your ``setup.py`` includes the following::

  install_requires=[
    'cmd2>=1,<2',
  ]

The ``cmd2`` project uses `Semantic Versioning <https://semver.org>`_, which
means that any incompatible API changes will be release with a new major
version number. The public API is documented in the :ref:`api/index:API
Reference`.

We recommend that you follow the advice given by the Python Packaging User
Guide related to `install_requires
<https://packaging.python.org/discussions/install-requires-vs-requirements/>`_.
By setting an upper bound on the allowed version, you can ensure that your
project does not inadvertently get installed with an incompatible future
version of ``cmd2``.


Windows Considerations
----------------------

If you would like to use :ref:`features/completion:Completion`, and you want
your application to run on Windows, you will need to ensure you install the
``pyreadline`` package. Make sure to include the following in your
``setup.py``::

  install_requires=[
    'cmd2>=1,<2',
    ":sys_platform=='win32'": ['pyreadline'],
  ]
