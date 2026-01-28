import pytest
from prompt_toolkit.shortcuts import CompleteStyle

import cmd2


class AutoStyleApp(cmd2.Cmd):
    def __init__(self):
        super().__init__()

    def do_foo(self, args):
        pass

    def complete_foo(self, text, line, begidx, endidx):
        # Return 10 items
        return [f'item{i}' for i in range(10) if f'item{i}'.startswith(text)]

    def do_bar(self, args):
        pass

    def complete_bar(self, text, line, begidx, endidx):
        # Return 5 items
        return [f'item{i}' for i in range(5) if f'item{i}'.startswith(text)]


@pytest.fixture
def app():
    return AutoStyleApp()


def test_dynamic_complete_style(app):
    # Default max_column_completion_results is 7
    assert app.max_column_completion_results == 7

    # Complete 'foo' which has 10 items (> 7)
    # text='item', state=0, line='foo item', begidx=4, endidx=8
    app.complete('item', 0, 'foo item', 4, 8)
    assert app.session.complete_style == CompleteStyle.MULTI_COLUMN

    # Complete 'bar' which has 5 items (<= 7)
    app.complete('item', 0, 'bar item', 4, 8)
    assert app.session.complete_style == CompleteStyle.COLUMN


def test_dynamic_complete_style_custom_limit(app):
    # Change limit to 3
    app.max_column_completion_results = 3

    # Complete 'bar' which has 5 items (> 3)
    app.complete('item', 0, 'bar item', 4, 8)
    assert app.session.complete_style == CompleteStyle.MULTI_COLUMN

    # Change limit to 15
    app.max_column_completion_results = 15

    # Complete 'foo' which has 10 items (<= 15)
    app.complete('item', 0, 'foo item', 4, 8)
    assert app.session.complete_style == CompleteStyle.COLUMN
