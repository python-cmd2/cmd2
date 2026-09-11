# Testing

## Overview

This covers special considerations when writing unit or integration tests for a cmd2 application.

## Running cmd2's Test Suite

Run `make test` to execute the suite with coverage and pytest-xdist. The default, `-n auto`, selects
the worker count automatically based on the available CPUs and runs independent tests concurrently.
The same settings apply to `uv run pytest` and CI.

For a focused test or interactive debugging, disable parallel execution:

```sh
uv run pytest -n 0 tests/test_history.py
uv run pytest -n 0 --no-cov --pdb tests/test_history.py
```

Override the worker count with `-n 4`, for example. Coverage is collected for `cmd2` and written to
the terminal, `coverage.xml`, and `htmlcov/`. Each invocation starts fresh; pass `--cov-append`
explicitly when combining separate runs is intentional.

Terminal test doubles should answer cursor-position requests unless missing replies are what the
test exercises. Synchronize concurrent tests with events rather than arbitrary sleeps, and shorten
test-only expiry intervals when the timeout path is the assertion. Keep generous bounds on waits
that depend on another thread making progress.

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
