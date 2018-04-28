"""
Unit/functional testing for argparse completer in cmd2

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""
import os
import pytest
from cmd2.cmd2 import Cmd, with_argparser
from cmd2 import argparse_completer
from .conftest import run_cmd, normalize, StdOut, complete_tester

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


@pytest.fixture
def ps_app():
    c = PyscriptExample()
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

