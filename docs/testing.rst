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

If you need to mock anything in your cmd2 application, and most specifically in
sub-classes of :class:`~cmd2.Cmd` or
:class:`~cmd2.command_definition.CommandSet`, you must use `Autospeccing
<python_mock_autospeccing_>`_, `spec=True <python_mock_patch_>`_, or whatever
equivalant is provided in the mocking library you're using.

In order to automatically load functions as commands cmd2 performs a number of
reflection calls to look up attributes of classes defined in your cmd2
application. Many mocking libraries will automatically create mock objects to
match any attribute being requested, regardless of whether they're present in
the object being mocked. This behavior can incorrectly instruct cmd2 to treat a
function or attribute as something it needs to recognize and process. To
prevent this, you should always mock with `Autospeccing
<python_mock_autospeccing_>`_ or `spec=True <python_mock_patch_>`_ enabled.

If you don't have autospeccing on, your unit tests will failing with an error
message like::

    cmd2.exceptions.CommandSetRegistrationError: Subcommand
    <MagicMock name='cmdloop.subcommand_name' id='4506146416'> is not
    valid: must be a string. Received <class 'unittest.mock.MagicMock'> instead


Examples
~~~~~~~~

.. code-block:: python

    def test_mocked_methods():
        with mock.patch.object(MockMethodApp, 'foo', spec=True):
            cli = MockMethodApp()

Another one using `pytest-mock <https://pypi.org/project/pytest-mock/>`_ to
provide a ``mocker`` fixture:

.. code-block:: python

   def test_mocked_methods2(mocker):
      mock_cmdloop = mocker.patch("cmd2.Cmd.cmdloop", autospec=True)
      cli = cmd2.Cmd()
      cli.cmdloop()
      assert mock_cmdloop.call_count == 1
