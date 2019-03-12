# coding=utf-8
# flake8: noqa E302
"""
Test history functions of cmd2
"""
import tempfile
import os
import sys

import pytest

# Python 3.5 had some regressions in the unitest.mock module, so use 3rd party mock if available
try:
    import mock
except ImportError:
    from unittest import mock

import cmd2
from cmd2 import clipboard
from cmd2 import utils
from .conftest import run_cmd, normalize, HELP_HISTORY


def test_base_help_history(base_app):
    out = run_cmd(base_app, 'help history')
    assert out == normalize(HELP_HISTORY)

def test_exclude_from_history(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the subprocess.Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    # Run edit command
    run_cmd(base_app, 'edit')

    # Run history command
    run_cmd(base_app, 'history')

    # Verify that the history is empty
    out = run_cmd(base_app, 'history')
    assert out == []

    # Now run a command which isn't excluded from the history
    run_cmd(base_app, 'help')

    # And verify we have a history now ...
    out = run_cmd(base_app, 'history')
    expected = normalize("""    1  help""")
    assert out == expected


@pytest.fixture
def hist():
    from cmd2.parsing import Statement
    from cmd2.cmd2 import History, HistoryItem
    h = History([HistoryItem(Statement('', raw='first')),
                 HistoryItem(Statement('', raw='second')),
                 HistoryItem(Statement('', raw='third')),
                 HistoryItem(Statement('', raw='fourth'))])
    return h

def test_history_class_span(hist):
    for tryit in ['*', ':', '-', 'all', 'ALL']:
        assert hist.span(tryit) == hist

    assert hist.span('3') == ['third']
    assert hist.span('-1') == ['fourth']

    assert hist.span('2..') == ['second', 'third', 'fourth']
    assert hist.span('2:') == ['second', 'third', 'fourth']

    assert hist.span('-2..') == ['third', 'fourth']
    assert hist.span('-2:') == ['third', 'fourth']

    assert hist.span('1..3') == ['first', 'second', 'third']
    assert hist.span('1:3') == ['first', 'second', 'third']
    assert hist.span('2:-1') == ['second', 'third', 'fourth']
    assert hist.span('-3:4') == ['second', 'third','fourth']
    assert hist.span('-4:-2') == ['first', 'second', 'third']

    assert hist.span(':-2') == ['first', 'second', 'third']
    assert hist.span('..-2') == ['first', 'second', 'third']

    value_errors = ['fred', 'fred:joe', 'a..b', '2 ..', '1 : 3', '1:0', '0:3']
    for tryit in value_errors:
        with pytest.raises(ValueError):
            hist.span(tryit)

def test_history_class_get(hist):
    assert hist.get('1') == 'first'
    assert hist.get(3) == 'third'
    assert hist.get('-2') == hist[-2]
    assert hist.get(-1) == 'fourth'

    with pytest.raises(IndexError):
        hist.get(0)
    with pytest.raises(IndexError):
        hist.get('0')

    with pytest.raises(IndexError):
        hist.get('5')
    with pytest.raises(ValueError):
        hist.get('2-3')
    with pytest.raises(ValueError):
        hist.get('1..2')
    with pytest.raises(ValueError):
        hist.get('3:4')
    with pytest.raises(ValueError):
        hist.get('fred')
    with pytest.raises(ValueError):
        hist.get('')
    with pytest.raises(TypeError):
        hist.get(None)

def test_history_str_search(hist):
    assert hist.str_search('ir') == ['first', 'third']
    assert hist.str_search('rth') == ['fourth']

def test_history_regex_search(hist):
    assert hist.regex_search('/i.*d/') == ['third']
    assert hist.regex_search('s[a-z]+ond') == ['second']

def test_base_history(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history')
    expected = normalize("""
    1  help
    2  shortcuts
""")
    assert out == expected

    out = run_cmd(base_app, 'history he')
    expected = normalize("""
    1  help
""")
    assert out == expected

    out = run_cmd(base_app, 'history sh')
    expected = normalize("""
    2  shortcuts
""")
    assert out == expected

def test_history_script_format(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history -s')
    expected = normalize("""
help
shortcuts
""")
    assert out == expected

def test_history_with_string_argument(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history help')
    expected = normalize("""
    1  help
    3  help history
""")
    assert out == expected

def test_history_expanded_with_string_argument(base_app):
    run_cmd(base_app, 'alias create sc shortcuts')
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help history')
    run_cmd(base_app, 'sc')
    out = run_cmd(base_app, 'history -v shortcuts')
    expected = normalize("""
    1  alias create sc shortcuts
    4  sc
    4x shortcuts
""")
    assert out == expected

def test_history_expanded_with_regex_argument(base_app):
    run_cmd(base_app, 'alias create sc shortcuts')
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help history')
    run_cmd(base_app, 'sc')
    out = run_cmd(base_app, 'history -v /sh.*cuts/')
    expected = normalize("""
    1  alias create sc shortcuts
    4  sc
    4x shortcuts
""")
    assert out == expected

def test_history_with_integer_argument(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history 1')
    expected = normalize("""
    1  help
""")
    assert out == expected


def test_history_with_integer_span(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history 1..2')
    expected = normalize("""
    1  help
    2  shortcuts
""")
    assert out == expected

def test_history_with_span_start(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history 2:')
    expected = normalize("""
    2  shortcuts
    3  help history
""")
    assert out == expected

def test_history_with_span_end(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out = run_cmd(base_app, 'history :2')
    expected = normalize("""
    1  help
    2  shortcuts
""")
    assert out == expected

def test_history_with_span_index_error(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help history')
    run_cmd(base_app, '!ls -hal :')
    with pytest.raises(ValueError):
        _, err = run_cmd(base_app, 'history "hal :"')
        assert "ValueError" in err

def test_history_output_file(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')

    fd, fname = tempfile.mkstemp(prefix='', suffix='.txt')
    os.close(fd)
    run_cmd(base_app, 'history -o "{}"'.format(fname))
    expected = normalize('\n'.join(['help', 'shortcuts', 'help history']))
    with open(fname) as f:
        content = normalize(f.read())
    assert content == expected

def test_history_edit(base_app, monkeypatch):
    # Set a fake editor just to make sure we have one.  We aren't really
    # going to call it due to the mock
    base_app.editor = 'fooedit'

    # Mock out the Popen call so we don't actually open an editor
    m = mock.MagicMock(name='Popen')
    monkeypatch.setattr("subprocess.Popen", m)

    # Run help command just so we have a command in history
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'history -e 1')

    # We have an editor, so should expect a Popen call
    m.assert_called_once()

def test_history_run_all_commands(base_app):
    # make sure we refuse to run all commands as a default
    run_cmd(base_app, 'shortcuts')
    out = run_cmd(base_app, 'history -r')
    # this should generate an error, but we don't currently have a way to
    # capture stderr in these tests. So we assume that if we got nothing on
    # standard out, that the error occurred because if the command executed
    # then we should have a list of shortcuts in our output
    assert out == []

def test_history_run_one_command(base_app):
    expected = run_cmd(base_app, 'help')
    output = run_cmd(base_app, 'history -r 1')
    assert output == expected

def test_history_clear(base_app):
    # Add commands to history
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'alias')

    # Make sure history has items
    out = run_cmd(base_app, 'history')
    assert out

    # Clear the history
    run_cmd(base_app, 'history --clear')

    # Make sure history is empty
    out = run_cmd(base_app, 'history')
    assert out == []

def test_history_verbose_with_other_options(base_app):
    # make sure -v shows a usage error if any other options are present
    options_to_test = ['-r', '-e', '-o file', '-t file', '-c', '-x']
    for opt in options_to_test:
        output = run_cmd(base_app, 'history -v ' + opt)
        assert len(output) == 3
        assert output[1].startswith('Usage:')

def test_history_verbose(base_app):
    # validate function of -v option
    run_cmd(base_app, 'alias create s shortcuts')
    run_cmd(base_app, 's')
    output = run_cmd(base_app, 'history -v')
    assert len(output) == 3
    # TODO test for basic formatting once we figure it out

def test_history_script_with_invalid_options(base_app):
    # make sure -s shows a usage error if -c, -r, -e, -o, or -t are present
    options_to_test = ['-r', '-e', '-o file', '-t file', '-c']
    for opt in options_to_test:
        output = run_cmd(base_app, 'history -s ' + opt)
        assert len(output) == 3
        assert output[1].startswith('Usage:')

def test_history_script(base_app):
    cmds = ['alias create s shortcuts', 's']
    for cmd in cmds:
        run_cmd(base_app, cmd)
    output = run_cmd(base_app, 'history -s')
    assert output == cmds

def test_history_expanded_with_invalid_options(base_app):
    # make sure -x shows a usage error if -c, -r, -e, -o, or -t are present
    options_to_test = ['-r', '-e', '-o file', '-t file', '-c']
    for opt in options_to_test:
        output = run_cmd(base_app, 'history -x ' + opt)
        assert len(output) == 3
        assert output[1].startswith('Usage:')

def test_history_expanded(base_app):
    # validate function of -x option
    cmds = ['alias create s shortcuts', 's']
    for cmd in cmds:
        run_cmd(base_app, cmd)
    output = run_cmd(base_app, 'history -x')
    expected = ['    1  alias create s shortcuts', '    2  shortcuts']
    assert output == expected

def test_history_script_expanded(base_app):
    # validate function of -s -x options together
    cmds = ['alias create s shortcuts', 's']
    for cmd in cmds:
        run_cmd(base_app, cmd)
    output = run_cmd(base_app, 'history -sx')
    expected = ['alias create s shortcuts', 'shortcuts']
    assert output == expected


#####
#
# readline tests
#
#####
def test_readline_remove_history_item(base_app):
    from cmd2.rl_utils import readline
    assert readline.get_current_history_length() == 0
    readline.add_history('this is a test')
    assert readline.get_current_history_length() == 1
    readline.remove_history_item(0)
    assert readline.get_current_history_length() == 0


@pytest.fixture(scope="session")
def hist_file():
    fd, filename = tempfile.mkstemp(prefix='hist_file', suffix='.txt')
    os.close(fd)
    yield filename
    # teardown code
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass

def test_existing_history_file(hist_file, capsys):
    import atexit
    import readline

    # Create the history file before making cmd2 app
    with open(hist_file, 'w'):
        pass

    # Create a new cmd2 app
    cmd2.Cmd(persistent_history_file=hist_file)
    _, err = capsys.readouterr()

    # Make sure there were no errors
    assert err == ''

    # Unregister the call to write_history_file that cmd2 did
    atexit.unregister(readline.write_history_file)

    # Remove created history file
    os.remove(hist_file)

def test_new_history_file(hist_file, capsys):
    import atexit
    import readline

    # Remove any existing history file
    try:
        os.remove(hist_file)
    except OSError:
        pass

    # Create a new cmd2 app
    cmd2.Cmd(persistent_history_file=hist_file)
    _, err = capsys.readouterr()

    # Make sure there were no errors
    assert err == ''

    # Unregister the call to write_history_file that cmd2 did
    atexit.unregister(readline.write_history_file)

    # Remove created history file
    os.remove(hist_file)

def test_bad_history_file_path(capsys, request):
    # Use a directory path as the history file
    test_dir = os.path.dirname(request.module.__file__)

    # Create a new cmd2 app
    cmd2.Cmd(persistent_history_file=test_dir)
    _, err = capsys.readouterr()

    if sys.platform == 'win32':
        # pyreadline masks the read exception. Therefore the bad path error occurs when trying to write the file.
        assert 'readline cannot write' in err
    else:
        # GNU readline raises an exception upon trying to read the directory as a file
        assert 'readline cannot read' in err

