import sys
from code import InteractiveConsole
from unittest import mock


def test_py_completion_setup_readline(base_app):
    # Mock readline and rlcompleter
    mock_readline = mock.MagicMock()
    mock_readline.__doc__ = 'GNU Readline'
    mock_rlcompleter = mock.MagicMock()

    with mock.patch.dict(sys.modules, {'readline': mock_readline, 'rlcompleter': mock_rlcompleter}):
        interp = InteractiveConsole()
        base_app._set_up_py_shell_env(interp)

        # Verify completion setup for GNU Readline
        mock_readline.parse_and_bind.assert_called_with("tab: complete")
        mock_readline.set_completer.assert_called()


def test_py_completion_setup_libedit(base_app):
    # Mock readline and rlcompleter
    mock_readline = mock.MagicMock()
    mock_readline.__doc__ = 'libedit'
    mock_rlcompleter = mock.MagicMock()

    with mock.patch.dict(sys.modules, {'readline': mock_readline, 'rlcompleter': mock_rlcompleter}):
        interp = InteractiveConsole()
        base_app._set_up_py_shell_env(interp)

        # Verify completion setup for LibEdit
        mock_readline.parse_and_bind.assert_called_with("bind ^I rl_complete")
        mock_readline.set_completer.assert_called()


def test_py_completion_restore(base_app):
    # Mock readline
    mock_readline = mock.MagicMock()
    original_completer = mock.Mock()
    mock_readline.get_completer.return_value = original_completer

    with mock.patch.dict(sys.modules, {'readline': mock_readline, 'rlcompleter': mock.MagicMock()}):
        interp = InteractiveConsole()
        env = base_app._set_up_py_shell_env(interp)

        # Restore and verify
        base_app._restore_cmd2_env(env)

        # set_completer is called twice: once in setup, once in restore
        mock_readline.set_completer.assert_called_with(original_completer)
