Testing
=======

.. toctree::
   :maxdepth: 1

Overview
~~~~~~~~

This covers special considerations when writing unit tests for a cmd2 application.


Testing Commands
~~~~~~~~~~~~~~~~

The :doc:`External Test Plugin <plugins/external_test>` provides a mixin class with an :meth:`` function that
allows external calls to application commands.  The :meth:`~cmd2_ext_test.ExternalTestMixin.app_cmd()` function captures
and returns stdout, stderr, and the command-specific result data.


Mocking
~~~~~~~

.. _python_mock_autospeccing:
   https://docs.python.org/3/library/unittest.mock.html#autospeccing
.. _python_mock_patch:
   https://docs.python.org/3/library/unittest.mock.html#patch

If you need to mock anything in your cmd2 application, and most specifically in sub-classes of :class:`~cmd2.Cmd` or
:class:`~cmd2.command_definition.CommandSet`, you must use `Autospeccing <python_mock_autospeccing_>`_,
`spec=True <python_mock_patch_>`_, or whatever equivalant is provided in the mocking library you're using.

In order to automatically load functions as commands cmd2 performs a number of reflection calls to look up attributes
of classes defined in your cmd2 application. Many mocking libraries will automatically create mock objects to match any
attribute being requested, regardless of whether they're present in the object being mocked. This behavior can
incorrectly instruct cmd2 to treat a function or attribute as something it needs to recognize and process. To prevent
this, you should always mock with `Autospeccing <python_mock_autospeccing_>`_ or `spec=True <python_mock_patch_>`_
enabled.

Example of spec=True
====================
.. code-block:: python

    def test_mocked_methods():
        with mock.patch.object(MockMethodApp, 'foo', spec=True):
            cli = MockMethodApp()
