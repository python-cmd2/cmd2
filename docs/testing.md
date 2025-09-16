# Testing

## Overview

This covers special considerations when writing unit or integration tests for a cmd2 application.

## Testing Commands

We encourage `cmd2` application developers to look at the
[cmd2 tests](https://github.com/python-cmd2/cmd2/tree/main/tests) for examples of how to perform
unit and integration testing of `cmd2` commands. There are various helpers that will do things like
capture and return stdout, stderr, and command-specific result data.

## Mocking

If you need to mock anything in your cmd2 application, and most specifically in sub-classes of
[cmd2.Cmd][] or [cmd2.CommandSet][], you must use
[Autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing),
[spec=True](https://docs.python.org/3/library/unittest.mock.html#patch), or whatever equivalent is
provided in the mocking library you're using.

In order to automatically load functions as commands, `cmd2` performs a number of reflection calls
to look up attributes of classes defined in your cmd2 application. Many mocking libraries will
automatically create mock objects to match any attribute being requested, regardless of whether
they're present in the object being mocked. This behavior can incorrectly instruct cmd2 to treat a
function or attribute as something it needs to recognize and process. To prevent this, you should
always mock with [Autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing)
or [spec=True](https://docs.python.org/3/library/unittest.mock.html#patch) enabled. If you don't
have autospeccing on, your unit tests will fail with an error message like:

```sh
cmd2.exceptions.CommandSetRegistrationError: Subcommand
<MagicMock name='cmdloop.subcommand_name' id='4506146416'> is not valid: must be a string.
Received <class 'unittest.mock.MagicMock'> instead
```

## Examples

```py
def test*mocked_methods():
   with mock.patch.object(MockMethodApp, 'foo', spec=True):
      cli = MockMethodApp()
```

Another one using [pytest-mock](https://pypi.org/project/pytest-mock) to provide a `mocker` fixture:

```py
def test_mocked_methods2(mocker):
   mock_cmdloop = mocker.patch("cmd2.Cmd.cmdloop", autospec=True)
   cli = cmd2.Cmd()
   cli.cmdloop()
   assert mock_cmdloop.call_count == 1
```
