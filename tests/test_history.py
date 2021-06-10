# coding=utf-8
# flake8: noqa E302
"""
Test history functions of cmd2
"""
import os
import tempfile
from unittest import (
    mock,
)

import pytest

import cmd2

from .conftest import (
    HELP_HISTORY,
    normalize,
    run_cmd,
)


#
# readline tests
#
def test_readline_remove_history_item(base_app):
    from cmd2.rl_utils import (
        readline,
    )

    readline.clear_history()
    assert readline.get_current_history_length() == 0
    readline.add_history('this is a test')
    assert readline.get_current_history_length() == 1
    readline.remove_history_item(0)
    assert readline.get_current_history_length() == 0


#
# test History() class
#
@pytest.fixture
def hist():
    from cmd2.cmd2 import (
        History,
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    h = History(
        [
            HistoryItem(Statement('', raw='first')),
            HistoryItem(Statement('', raw='second')),
            HistoryItem(Statement('', raw='third')),
            HistoryItem(Statement('', raw='fourth')),
        ]
    )
    return h


# Represents the hist fixture's JSON
hist_json = (
    '{\n'
    '  "history_version": "1.0.0",\n'
    '  "history_items": [\n'
    '    {\n'
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "first",\n'
    '        "command": "",\n'
    '        "arg_list": [],\n'
    '        "multiline_command": "",\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "pipe_to": "",\n'
    '        "output": "",\n'
    '        "output_to": ""\n'
    '      }\n'
    '    },\n'
    '    {\n'
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "second",\n'
    '        "command": "",\n'
    '        "arg_list": [],\n'
    '        "multiline_command": "",\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "pipe_to": "",\n'
    '        "output": "",\n'
    '        "output_to": ""\n'
    '      }\n'
    '    },\n'
    '    {\n'
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "third",\n'
    '        "command": "",\n'
    '        "arg_list": [],\n'
    '        "multiline_command": "",\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "pipe_to": "",\n'
    '        "output": "",\n'
    '        "output_to": ""\n'
    '      }\n'
    '    },\n'
    '    {\n'
    '      "statement": {\n'
    '        "args": "",\n'
    '        "raw": "fourth",\n'
    '        "command": "",\n'
    '        "arg_list": [],\n'
    '        "multiline_command": "",\n'
    '        "terminator": "",\n'
    '        "suffix": "",\n'
    '        "pipe_to": "",\n'
    '        "output": "",\n'
    '        "output_to": ""\n'
    '      }\n'
    '    }\n'
    '  ]\n'
    '}'
)


@pytest.fixture
def persisted_hist():
    from cmd2.cmd2 import (
        History,
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    h = History(
        [
            HistoryItem(Statement('', raw='first')),
            HistoryItem(Statement('', raw='second')),
            HistoryItem(Statement('', raw='third')),
            HistoryItem(Statement('', raw='fourth')),
        ]
    )
    h.start_session()
    h.append(Statement('', raw='fifth'))
    h.append(Statement('', raw='sixth'))
    return h


def test_history_class_span(hist):
    span = hist.span('2..')
    assert len(span) == 3
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'

    span = hist.span('2:')
    assert len(span) == 3
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'

    span = hist.span('-2..')
    assert len(span) == 2
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'

    span = hist.span('-2:')
    assert len(span) == 2
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'

    span = hist.span('1..3')
    assert len(span) == 3
    assert span[1].statement.raw == 'first'
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'

    span = hist.span('1:3')
    assert len(span) == 3
    assert span[1].statement.raw == 'first'
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'

    span = hist.span('2:-1')
    assert len(span) == 3
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'

    span = hist.span('-3:4')
    assert len(span) == 3
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'

    span = hist.span('-4:-2')
    assert len(span) == 3
    assert span[1].statement.raw == 'first'
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'

    span = hist.span(':-2')
    assert len(span) == 3
    assert span[1].statement.raw == 'first'
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'

    span = hist.span('..-2')
    assert len(span) == 3
    assert span[1].statement.raw == 'first'
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'

    value_errors = ['fred', 'fred:joe', '2', '-2', 'a..b', '2 ..', '1 : 3', '1:0', '0:3']
    for tryit in value_errors:
        with pytest.raises(ValueError):
            hist.span(tryit)


def test_persisted_history_span(persisted_hist):
    span = persisted_hist.span('2..')
    assert len(span) == 5
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'
    assert span[5].statement.raw == 'fifth'
    assert span[6].statement.raw == 'sixth'

    span = persisted_hist.span('-2..')
    assert len(span) == 2
    assert span[5].statement.raw == 'fifth'
    assert span[6].statement.raw == 'sixth'

    span = persisted_hist.span('1..3')
    assert len(span) == 3
    assert span[1].statement.raw == 'first'
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'

    span = persisted_hist.span('2:-1')
    assert len(span) == 5
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'
    assert span[5].statement.raw == 'fifth'
    assert span[6].statement.raw == 'sixth'

    span = persisted_hist.span('-3:4')
    assert len(span) == 1
    assert span[4].statement.raw == 'fourth'

    span = persisted_hist.span(':-2', include_persisted=True)
    assert len(span) == 5
    assert span[1].statement.raw == 'first'
    assert span[2].statement.raw == 'second'
    assert span[3].statement.raw == 'third'
    assert span[4].statement.raw == 'fourth'
    assert span[5].statement.raw == 'fifth'

    span = persisted_hist.span(':-2', include_persisted=False)
    assert len(span) == 1
    assert span[5].statement.raw == 'fifth'

    value_errors = ['fred', 'fred:joe', '2', '-2', 'a..b', '2 ..', '1 : 3', '1:0', '0:3']
    for tryit in value_errors:
        with pytest.raises(ValueError):
            persisted_hist.span(tryit)


def test_history_class_get(hist):
    assert hist.get(1).statement.raw == 'first'
    assert hist.get(3).statement.raw == 'third'
    assert hist.get(-2) == hist[-2]
    assert hist.get(-1).statement.raw == 'fourth'

    with pytest.raises(IndexError):
        hist.get(0)

    with pytest.raises(IndexError):
        hist.get(5)


def test_history_str_search(hist):
    items = hist.str_search('ir')
    assert len(items) == 2
    assert items[1].statement.raw == 'first'
    assert items[3].statement.raw == 'third'

    items = hist.str_search('rth')
    assert len(items) == 1
    assert items[4].statement.raw == 'fourth'


def test_history_regex_search(hist):
    items = hist.regex_search('/i.*d/')
    assert len(items) == 1
    assert items[3].statement.raw == 'third'

    items = hist.regex_search('s[a-z]+ond')
    assert len(items) == 1
    assert items[2].statement.raw == 'second'


def test_history_max_length_zero(hist):
    hist.truncate(0)
    assert len(hist) == 0


def test_history_max_length_negative(hist):
    hist.truncate(-1)
    assert len(hist) == 0


def test_history_max_length(hist):
    hist.truncate(2)
    assert len(hist) == 2
    assert hist.get(1).statement.raw == 'third'
    assert hist.get(2).statement.raw == 'fourth'


def test_history_to_json(hist):
    assert hist_json == hist.to_json()


def test_history_from_json(hist):
    import json

    from cmd2.history import (
        History,
    )

    assert hist.from_json(hist_json) == hist

    # Test invalid JSON
    with pytest.raises(json.JSONDecodeError):
        hist.from_json("")

    # Send JSON with missing required element
    with pytest.raises(KeyError):
        hist.from_json("{}")

    # Create JSON with invalid history version
    backed_up_ver = History._history_version
    History._history_version = "BAD_VERSION"
    invalid_ver_json = hist.to_json()
    History._history_version = backed_up_ver

    with pytest.raises(ValueError):
        hist.from_json(invalid_ver_json)


#
# test HistoryItem()
#
@pytest.fixture
def histitem():
    from cmd2.history import (
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    statement = Statement(
        'history',
        raw='help history',
        command='help',
        arg_list=['history'],
    )
    histitem = HistoryItem(statement)
    return histitem


@pytest.fixture
def parser():
    from cmd2.parsing import (
        StatementParser,
    )

    parser = StatementParser(
        terminators=[';', '&'],
        multiline_commands=['multiline'],
        aliases={
            'helpalias': 'help',
            '42': 'theanswer',
            'l': '!ls -al',
            'anothermultiline': 'multiline',
            'fake': 'run_pyscript',
        },
        shortcuts={'?': 'help', '!': 'shell'},
    )
    return parser


def test_multiline_histitem(parser):
    from cmd2.history import (
        History,
    )

    line = 'multiline foo\nbar\n\n'
    statement = parser.parse(line)
    history = History()
    history.append(statement)
    assert len(history) == 1
    hist_item = history[0]
    assert hist_item.raw == line
    pr_lines = hist_item.pr(1).splitlines()
    assert pr_lines[0].endswith('multiline foo bar')


def test_multiline_histitem_verbose(parser):
    from cmd2.history import (
        History,
    )

    line = 'multiline foo\nbar\n\n'
    statement = parser.parse(line)
    history = History()
    history.append(statement)
    assert len(history) == 1
    hist_item = history[0]
    assert hist_item.raw == line
    pr_lines = hist_item.pr(1, verbose=True).splitlines()
    assert pr_lines[0].endswith('multiline foo')
    assert pr_lines[1] == 'bar'


def test_history_item_instantiate():
    from cmd2.history import (
        HistoryItem,
    )
    from cmd2.parsing import (
        Statement,
    )

    statement = Statement(
        'history',
        raw='help history',
        command='help',
        arg_list=['history'],
    )
    with pytest.raises(TypeError):
        _ = HistoryItem()


def test_history_item_properties(histitem):
    assert histitem.raw == 'help history'
    assert histitem.expanded == 'help history'
    assert str(histitem) == 'help history'


#
# test history command
#
def test_base_history(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out, err = run_cmd(base_app, 'history')
    expected = normalize(
        """
    1  help
    2  shortcuts
"""
    )
    assert out == expected

    out, err = run_cmd(base_app, 'history he')
    expected = normalize(
        """
    1  help
"""
    )
    assert out == expected

    out, err = run_cmd(base_app, 'history sh')
    expected = normalize(
        """
    2  shortcuts
"""
    )
    assert out == expected


def test_history_script_format(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out, err = run_cmd(base_app, 'history -s')
    expected = normalize(
        """
help
shortcuts
"""
    )
    assert out == expected


def test_history_with_string_argument(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out, err = run_cmd(base_app, 'history help')
    expected = normalize(
        """
    1  help
    3  help history
"""
    )
    assert out == expected


def test_history_expanded_with_string_argument(base_app):
    run_cmd(base_app, 'alias create sc shortcuts')
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help history')
    run_cmd(base_app, 'sc')
    out, err = run_cmd(base_app, 'history -v shortcuts')
    expected = normalize(
        """
    1  alias create sc shortcuts
    4  sc
    4x shortcuts
"""
    )
    assert out == expected


def test_history_expanded_with_regex_argument(base_app):
    run_cmd(base_app, 'alias create sc shortcuts')
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help history')
    run_cmd(base_app, 'sc')
    out, err = run_cmd(base_app, 'history -v /sh.*cuts/')
    expected = normalize(
        """
    1  alias create sc shortcuts
    4  sc
    4x shortcuts
"""
    )
    assert out == expected


def test_history_with_integer_argument(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    out, err = run_cmd(base_app, 'history 1')
    expected = normalize(
        """
    1  help
"""
    )
    assert out == expected


def test_history_with_integer_span(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out, err = run_cmd(base_app, 'history 1..2')
    expected = normalize(
        """
    1  help
    2  shortcuts
"""
    )
    assert out == expected


def test_history_with_span_start(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out, err = run_cmd(base_app, 'history 2:')
    expected = normalize(
        """
    2  shortcuts
    3  help history
"""
    )
    assert out == expected


def test_history_with_span_end(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')
    out, err = run_cmd(base_app, 'history :2')
    expected = normalize(
        """
    1  help
    2  shortcuts
"""
    )
    assert out == expected


def test_history_with_span_index_error(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'help history')
    run_cmd(base_app, '!ls -hal :')
    with pytest.raises(ValueError):
        base_app.onecmd('history "hal :"')


def test_history_output_file():
    app = cmd2.Cmd(multiline_commands=['alias'])
    run_cmd(app, 'help')
    run_cmd(app, 'shortcuts')
    run_cmd(app, 'help history')
    run_cmd(app, 'alias create my_alias history;')

    fd, fname = tempfile.mkstemp(prefix='', suffix='.txt')
    os.close(fd)
    run_cmd(app, 'history -o "{}"'.format(fname))
    expected = normalize('\n'.join(['help', 'shortcuts', 'help history', 'alias create my_alias history;']))
    with open(fname) as f:
        content = normalize(f.read())
    assert content == expected


def test_history_bad_output_file(base_app):
    run_cmd(base_app, 'help')
    run_cmd(base_app, 'shortcuts')
    run_cmd(base_app, 'help history')

    fname = os.path.join(os.path.sep, "fake", "fake", "fake")
    out, err = run_cmd(base_app, 'history -o "{}"'.format(fname))

    assert not out
    assert "Error saving" in err[0]


def test_history_edit(monkeypatch):
    app = cmd2.Cmd(multiline_commands=['alias'])

    # Set a fake editor just to make sure we have one.  We aren't really
    # going to call it due to the mock
    app.editor = 'fooedit'

    # Mock out the run_editor call so we don't actually open an editor
    edit_mock = mock.MagicMock(name='run_editor')
    monkeypatch.setattr("cmd2.Cmd.run_editor", edit_mock)

    # Mock out the run_script call since the mocked edit won't produce a file
    run_script_mock = mock.MagicMock(name='do_run_script')
    monkeypatch.setattr("cmd2.Cmd.do_run_script", run_script_mock)

    # Put commands in history
    run_cmd(app, 'help')
    run_cmd(app, 'alias create my_alias history;')

    run_cmd(app, 'history -e 1:2')

    # Make sure both functions were called
    edit_mock.assert_called_once()
    run_script_mock.assert_called_once()


def test_history_run_all_commands(base_app):
    # make sure we refuse to run all commands as a default
    run_cmd(base_app, 'shortcuts')
    out, err = run_cmd(base_app, 'history -r')
    # this should generate an error, but we don't currently have a way to
    # capture stderr in these tests. So we assume that if we got nothing on
    # standard out, that the error occurred because if the command executed
    # then we should have a list of shortcuts in our output
    assert out == []


def test_history_run_one_command(base_app):
    out1, err1 = run_cmd(base_app, 'help')
    out2, err2 = run_cmd(base_app, 'history -r 1')
    assert out1 == out2


def test_history_clear(mocker, hist_file):
    # Add commands to history
    app = cmd2.Cmd(persistent_history_file=hist_file)
    run_cmd(app, 'help')
    run_cmd(app, 'alias')

    # Make sure history has items
    out, err = run_cmd(app, 'history')
    assert out

    # Clear the history
    run_cmd(app, 'history --clear')

    # Make sure history is empty and its file is gone
    out, err = run_cmd(app, 'history')
    assert out == []
    assert not os.path.exists(hist_file)

    # Clear the history again and make sure the FileNotFoundError from trying to delete missing history file is silent
    run_cmd(app, 'history --clear')

    # Cause os.remove to fail and make sure error gets printed
    mock_remove = mocker.patch('os.remove')
    mock_remove.side_effect = OSError

    out, err = run_cmd(app, 'history --clear')
    assert out == []
    assert 'Error removing history file' in err[0]


def test_history_verbose_with_other_options(base_app):
    # make sure -v shows a usage error if any other options are present
    options_to_test = ['-r', '-e', '-o file', '-t file', '-c', '-x']
    for opt in options_to_test:
        out, err = run_cmd(base_app, 'history -v ' + opt)
        assert len(out) == 4
        assert out[0] == '-v cannot be used with any other options'
        assert out[1].startswith('Usage:')


def test_history_verbose(base_app):
    # validate function of -v option
    run_cmd(base_app, 'alias create s shortcuts')
    run_cmd(base_app, 's')
    out, err = run_cmd(base_app, 'history -v')
    assert len(out) == 3
    # TODO test for basic formatting once we figure it out


def test_history_script_with_invalid_options(base_app):
    # make sure -s shows a usage error if -c, -r, -e, -o, or -t are present
    options_to_test = ['-r', '-e', '-o file', '-t file', '-c']
    for opt in options_to_test:
        out, err = run_cmd(base_app, 'history -s ' + opt)
        assert len(out) == 4
        assert out[0] == '-s and -x cannot be used with -c, -r, -e, -o, or -t'
        assert out[1].startswith('Usage:')


def test_history_script(base_app):
    cmds = ['alias create s shortcuts', 's']
    for cmd in cmds:
        run_cmd(base_app, cmd)
    out, err = run_cmd(base_app, 'history -s')
    assert out == cmds


def test_history_expanded_with_invalid_options(base_app):
    # make sure -x shows a usage error if -c, -r, -e, -o, or -t are present
    options_to_test = ['-r', '-e', '-o file', '-t file', '-c']
    for opt in options_to_test:
        out, err = run_cmd(base_app, 'history -x ' + opt)
        assert len(out) == 4
        assert out[0] == '-s and -x cannot be used with -c, -r, -e, -o, or -t'
        assert out[1].startswith('Usage:')


def test_history_expanded(base_app):
    # validate function of -x option
    cmds = ['alias create s shortcuts', 's']
    for cmd in cmds:
        run_cmd(base_app, cmd)
    out, err = run_cmd(base_app, 'history -x')
    expected = ['    1  alias create s shortcuts', '    2  shortcuts']
    assert out == expected


def test_history_script_expanded(base_app):
    # validate function of -s -x options together
    cmds = ['alias create s shortcuts', 's']
    for cmd in cmds:
        run_cmd(base_app, cmd)
    out, err = run_cmd(base_app, 'history -sx')
    expected = ['alias create s shortcuts', 'shortcuts']
    assert out == expected


def test_base_help_history(base_app):
    out, err = run_cmd(base_app, 'help history')
    assert out == normalize(HELP_HISTORY)


def test_exclude_from_history(base_app, monkeypatch):
    # Run history command
    run_cmd(base_app, 'history')

    # Verify that the history is empty
    out, err = run_cmd(base_app, 'history')
    assert out == []

    # Now run a command which isn't excluded from the history
    run_cmd(base_app, 'help')

    # And verify we have a history now ...
    out, err = run_cmd(base_app, 'history')
    expected = normalize("""    1  help""")
    assert out == expected


#
# test history initialization
#
@pytest.fixture(scope="session")
def hist_file():
    fd, filename = tempfile.mkstemp(prefix='hist_file', suffix='.dat')
    os.close(fd)
    yield filename
    # teardown code
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass


def test_history_file_is_directory(capsys):
    with tempfile.TemporaryDirectory() as test_dir:
        # Create a new cmd2 app
        cmd2.Cmd(persistent_history_file=test_dir)
        _, err = capsys.readouterr()
        assert 'is a directory' in err


def test_history_can_create_directory(mocker):
    # Mock out atexit.register so the persistent file doesn't written when this function
    # exists because we will be deleting the directory it needs to go to.
    mock_register = mocker.patch('atexit.register')

    # Create a temp path for us to use and let it get deleted
    with tempfile.TemporaryDirectory() as test_dir:
        pass
    assert not os.path.isdir(test_dir)

    # Add some subdirectories for the complete history file directory
    hist_file_dir = os.path.join(test_dir, 'subdir1', 'subdir2')
    hist_file = os.path.join(hist_file_dir, 'hist_file')

    # Make sure cmd2 creates the history file directory
    cmd2.Cmd(persistent_history_file=hist_file)
    assert os.path.isdir(hist_file_dir)

    # Cleanup
    os.rmdir(hist_file_dir)


def test_history_cannot_create_directory(mocker, capsys):
    mock_open = mocker.patch('os.makedirs')
    mock_open.side_effect = OSError

    hist_file_path = os.path.join('fake_dir', 'file')
    cmd2.Cmd(persistent_history_file=hist_file_path)
    _, err = capsys.readouterr()
    assert 'Error creating persistent history file directory' in err


def test_history_file_permission_error(mocker, capsys):
    mock_open = mocker.patch('builtins.open')
    mock_open.side_effect = PermissionError

    cmd2.Cmd(persistent_history_file='/tmp/doesntmatter')
    out, err = capsys.readouterr()
    assert not out
    assert 'Cannot read' in err


def test_history_populates_readline(hist_file):
    # - create a cmd2 with persistent history
    app = cmd2.Cmd(persistent_history_file=hist_file)
    run_cmd(app, 'help')
    run_cmd(app, 'shortcuts')
    run_cmd(app, 'shortcuts')
    run_cmd(app, 'alias')
    # call the private method which is registered to write history at exit
    app._persist_history()

    # see if history came back
    app = cmd2.Cmd(persistent_history_file=hist_file)
    assert len(app.history) == 4
    assert app.history.get(1).statement.raw == 'help'
    assert app.history.get(2).statement.raw == 'shortcuts'
    assert app.history.get(3).statement.raw == 'shortcuts'
    assert app.history.get(4).statement.raw == 'alias'

    # readline only adds a single entry for multiple sequential identical commands
    # so we check to make sure that cmd2 populated the readline history
    # using the same rules
    from cmd2.rl_utils import (
        readline,
    )

    assert readline.get_current_history_length() == 3
    assert readline.get_history_item(1) == 'help'
    assert readline.get_history_item(2) == 'shortcuts'
    assert readline.get_history_item(3) == 'alias'


#
# test cmd2's ability to write out history on exit
# we are testing the _persist_history() method, and
# we assume that the atexit module will call this method
# properly
#
def test_persist_history_ensure_no_error_if_no_histfile(base_app, capsys):
    # make sure if there is no persistent history file and someone
    # calls the private method call that we don't get an error
    base_app._persist_history()
    out, err = capsys.readouterr()
    assert not out
    assert not err


def test_persist_history_permission_error(hist_file, mocker, capsys):
    app = cmd2.Cmd(persistent_history_file=hist_file)
    run_cmd(app, 'help')
    mock_open = mocker.patch('builtins.open')
    mock_open.side_effect = PermissionError
    app._persist_history()
    out, err = capsys.readouterr()
    assert not out
    assert 'Cannot write' in err
