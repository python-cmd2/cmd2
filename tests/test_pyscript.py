"""
Unit/functional testing for argparse completer in cmd2

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""
import os
import pytest
from cmd2.cmd2 import Cmd, with_argparser
from cmd2 import argparse_completer
from .conftest import run_cmd, StdOut
from cmd2.utils import namedtuple_with_defaults

class PyscriptExample(Cmd):
    ratings_types = ['G', 'PG', 'PG-13', 'R', 'NC-17']

    def _do_media_movies(self, args) -> None:
        if not args.command:
            self.do_help('media movies')
        else:
            print('media movies ' + str(args.__dict__))

    def _do_media_shows(self, args) -> None:
        if not args.command:
            self.do_help('media shows')

        if not args.command:
            self.do_help('media shows')
        else:
            print('media shows ' + str(args.__dict__))

    media_parser = argparse_completer.ACArgumentParser(prog='media')

    media_types_subparsers = media_parser.add_subparsers(title='Media Types', dest='type')

    movies_parser = media_types_subparsers.add_parser('movies')
    movies_parser.set_defaults(func=_do_media_movies)

    movies_commands_subparsers = movies_parser.add_subparsers(title='Commands', dest='command')

    movies_list_parser = movies_commands_subparsers.add_parser('list')

    movies_list_parser.add_argument('-t', '--title', help='Title Filter')
    movies_list_parser.add_argument('-r', '--rating', help='Rating Filter', nargs='+',
                                    choices=ratings_types)
    movies_list_parser.add_argument('-d', '--director', help='Director Filter')
    movies_list_parser.add_argument('-a', '--actor', help='Actor Filter', action='append')

    movies_add_parser = movies_commands_subparsers.add_parser('add')
    movies_add_parser.add_argument('title', help='Movie Title')
    movies_add_parser.add_argument('rating', help='Movie Rating', choices=ratings_types)
    movies_add_parser.add_argument('-d', '--director', help='Director', nargs=(1, 2), required=True)
    movies_add_parser.add_argument('actor', help='Actors', nargs='*')

    movies_delete_parser = movies_commands_subparsers.add_parser('delete')

    shows_parser = media_types_subparsers.add_parser('shows')
    shows_parser.set_defaults(func=_do_media_shows)

    shows_commands_subparsers = shows_parser.add_subparsers(title='Commands', dest='command')

    shows_list_parser = shows_commands_subparsers.add_parser('list')

    @with_argparser(media_parser)
    def do_media(self, args):
        """Media management command demonstrates multiple layers of subcommands being handled by AutoCompleter"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('media')

    foo_parser = argparse_completer.ACArgumentParser(prog='foo')
    foo_parser.add_argument('-c', dest='counter', action='count')
    foo_parser.add_argument('-t', dest='trueval', action='store_true')
    foo_parser.add_argument('-n', dest='constval', action='store_const', const=42)
    foo_parser.add_argument('variable', nargs=(2, 3))
    foo_parser.add_argument('optional', nargs='?')
    foo_parser.add_argument('zeroormore', nargs='*')

    @with_argparser(foo_parser)
    def do_foo(self, args):
        print('foo ' + str(args.__dict__))
        if self._in_py:
            FooResult = namedtuple_with_defaults('FooResult',
                                                 ['counter', 'trueval', 'constval',
                                                  'variable', 'optional', 'zeroormore'])
            self._last_result = FooResult(**{'counter': args.counter,
                                             'trueval': args.trueval,
                                             'constval': args.constval,
                                             'variable': args.variable,
                                             'optional': args.optional,
                                             'zeroormore': args.zeroormore})

    bar_parser = argparse_completer.ACArgumentParser(prog='bar')
    bar_parser.add_argument('first')
    bar_parser.add_argument('oneormore', nargs='+')
    bar_parser.add_argument('-a', dest='aaa')

    @with_argparser(bar_parser)
    def do_bar(self, args):
        out = 'bar '
        arg_dict = args.__dict__
        keys = list(arg_dict.keys())
        keys.sort()
        out += '{'
        for key in keys:
            out += "'{}':'{}'".format(key, arg_dict[key])
        print(out)


@pytest.fixture
def ps_app():
    c = PyscriptExample()
    c.stdout = StdOut()

    return c


class PyscriptCustomNameExample(Cmd):
    def __init__(self):
        super().__init__()
        self.pyscript_name = 'custom'

    def do_echo(self, out):
        print(out)


@pytest.fixture
def ps_echo():
    c = PyscriptCustomNameExample()
    c.stdout = StdOut()

    return c


@pytest.mark.parametrize('command, pyscript_file', [
    ('help', 'help.py'),
    ('help media', 'help_media.py'),
])
def test_pyscript_help(ps_app, capsys, request, command, pyscript_file):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', pyscript_file)
    expected = run_cmd(ps_app, command)

    assert len(expected) > 0
    assert len(expected[0]) > 0
    out = run_cmd(ps_app, 'pyscript {}'.format(python_script))
    assert len(out) > 0
    assert out == expected


@pytest.mark.parametrize('command, pyscript_file', [
    ('media movies list', 'media_movies_list1.py'),
    ('media movies list', 'media_movies_list2.py'),
    ('media movies list', 'media_movies_list3.py'),
    ('media movies list -a "Mark Hamill"', 'media_movies_list4.py'),
    ('media movies list -a "Mark Hamill" -a "Carrie Fisher"', 'media_movies_list5.py'),
    ('media movies list -r PG', 'media_movies_list6.py'),
    ('media movies list -r PG PG-13', 'media_movies_list7.py'),
    ('media movies add "My Movie" PG-13 --director "George Lucas" "J. J. Abrams"',
     'media_movies_add1.py'),
    ('media movies add "My Movie" PG-13 --director "George Lucas" "J. J. Abrams" "Mark Hamill"',
     'media_movies_add2.py'),
    ('foo aaa bbb -ccc -t -n', 'foo1.py'),
    ('foo 11 22 33 44 -ccc -t -n', 'foo2.py'),
    ('foo 11 22 33 44 55 66 -ccc', 'foo3.py'),
    ('bar 11 22', 'bar1.py'),
])
def test_pyscript_out(ps_app, capsys, request, command, pyscript_file):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', pyscript_file)
    run_cmd(ps_app, command)
    expected, _ = capsys.readouterr()

    assert len(expected) > 0
    run_cmd(ps_app, 'pyscript {}'.format(python_script))
    out, _ = capsys.readouterr()
    assert len(out) > 0
    assert out == expected


@pytest.mark.parametrize('command, error', [
    ('app.noncommand', 'AttributeError'),
    ('app.media.noncommand', 'AttributeError'),
    ('app.media.movies.list(artist="Invalid Keyword")', 'TypeError'),
    ('app.foo(counter="a")', 'TypeError'),
    ('app.foo("aaa")', 'ValueError'),
])
def test_pyscript_errors(ps_app, capsys, command, error):
    run_cmd(ps_app, 'py {}'.format(command))
    _, err = capsys.readouterr()

    assert len(err) > 0
    assert 'Traceback' in err
    assert error in err


@pytest.mark.parametrize('pyscript_file, exp_out', [
    ('foo4.py', 'Success'),
])
def test_pyscript_results(ps_app, capsys, request, pyscript_file, exp_out):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', pyscript_file)

    run_cmd(ps_app, 'pyscript {}'.format(python_script))
    expected, _ = capsys.readouterr()
    assert len(expected) > 0
    assert exp_out in expected


@pytest.mark.parametrize('expected, pyscript_file', [
    ("['_relative_load', 'alias', 'bar', 'cmd_echo', 'edit', 'eof', 'eos', 'foo', 'help', 'history', 'load', 'media', 'py', 'pyscript', 'quit', 'set', 'shell', 'shortcuts', 'unalias']",
     'pyscript_dir1.py'),
    ("['movies', 'shows']", 'pyscript_dir2.py')
])
def test_pyscript_dir(ps_app, capsys, request, expected, pyscript_file):
    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', pyscript_file)

    run_cmd(ps_app, 'pyscript {}'.format(python_script))
    out, _ = capsys.readouterr()
    out = out.strip()
    assert len(out) > 0
    assert out == expected


def test_pyscript_custom_name(ps_echo, capsys, request):
    message = 'blah!'

    test_dir = os.path.dirname(request.module.__file__)
    python_script = os.path.join(test_dir, 'pyscript', 'custom_echo.py')

    run_cmd(ps_echo, 'pyscript {}'.format(python_script))
    expected, _ = capsys.readouterr()
    assert len(expected) > 0
    expected = expected.splitlines()
    assert message == expected[0]
