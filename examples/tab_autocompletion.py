#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating how to use flag and index based tab-completion functions
"""
import argparse
import AutoCompleter

import cmd2
from cmd2 import with_argparser

# List of strings used with flag and index based completion functions
food_item_strs = ['Pizza', 'Hamburger', 'Ham', 'Potato']
sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football']


class TabCompleteExample(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple subcommands."""

    def __init__(self):
        cmd2.Cmd.__init__(self)

    # This demonstrates a number of customizations of the AutoCompleter version of ArgumentParser
    #  - The help output will separately group required vs optional flags
    #  - The help output for arguments with multiple flags or with append=True is more concise
    #  - ACArgumentParser adds the ability to specify ranges of argument counts in 'nargs'

    suggest_parser = AutoCompleter.ACArgumentParser()

    suggest_parser.add_argument('-t', '--type', choices=['movie', 'show'], required=True)
    suggest_parser.add_argument('-d', '--duration', nargs=(1, 2), action='append',
                                help='Duration constraint in minutes.\n'
                                     '\tsingle value - maximum duration\n'
                                     '\t[a, b] - duration range')

    @with_argparser(suggest_parser)
    def do_suggest(self, args):
        """Suggest command demonstrates argparse customizations

        See hybrid_suggest and orig_suggest to compare the help output.


        """
        if not args.type:
            self.do_help('suggest')

    def complete_suggest(self, text, line, begidx, endidx):
        """ Adds tab completion to media"""
        completer = AutoCompleter.AutoCompleter(TabCompleteExample.suggest_parser, 1)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        results = completer.complete_command(tokens, text, line, begidx, endidx)

        return results

    # If you prefer the original argparse help output but would like narg ranges, it's possible
    # to enable narg ranges without the help changes using this method

    suggest_parser_hybrid = argparse.ArgumentParser()
    # This registers the custom narg range handling
    AutoCompleter.register_custom_actions(suggest_parser_hybrid)

    suggest_parser_hybrid.add_argument('-t', '--type', choices=['movie', 'show'], required=True)
    suggest_parser_hybrid.add_argument('-d', '--duration', nargs=(1, 2), action='append',
                                       help='Duration constraint in minutes.\n'
                                            '\tsingle value - maximum duration\n'
                                            '\t[a, b] - duration range')
    @with_argparser(suggest_parser_hybrid)
    def do_hybrid_suggest(self, args):
        if not args.type:
            self.do_help('orig_suggest')

    def complete_hybrid_suggest(self, text, line, begidx, endidx):
        """ Adds tab completion to media"""
        completer = AutoCompleter.AutoCompleter(TabCompleteExample.suggest_parser_hybrid)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        results = completer.complete_command(tokens, text, line, begidx, endidx)

        return results

    # This variant demonstrates the AutoCompleter working with the orginial argparse.
    # Base argparse is unable to specify narg ranges. Autocompleter will keep expecting additional arguments
    # for the -d/--duration flag until you specify a new flaw or end the list it with '--'

    suggest_parser_orig = argparse.ArgumentParser()

    suggest_parser_orig.add_argument('-t', '--type', choices=['movie', 'show'], required=True)
    suggest_parser_orig.add_argument('-d', '--duration', nargs='+', action='append',
                                     help='Duration constraint in minutes.\n'
                                          '\tsingle value - maximum duration\n'
                                          '\t[a, b] - duration range')
    @with_argparser(suggest_parser_orig)
    def do_orig_suggest(self, args):
        if not args.type:
            self.do_help('orig_suggest')

    def complete_orig_suggest(self, text, line, begidx, endidx):
        """ Adds tab completion to media"""
        completer = AutoCompleter.AutoCompleter(TabCompleteExample.suggest_parser_orig)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        results = completer.complete_command(tokens, text, line, begidx, endidx)

        return results


    ###################################################################################
    # The media command demonstrates a completer with multiple layers of subcommands
    #

    def query_actors(self):
        """Simulating a function that queries and returns a completion values"""
        return ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher', 'Alec Guinness', 'Peter Mayhew', 'Anthony Daniels',
                'Adam Driver', 'Daisy Ridley', 'John Boyega', 'Oscar Isaac', 'Lupita Nyong\'o', 'Andy Serkis']

    def _do_media_movies(self, args):
        if not args.command:
            self.do_help('media movies')

    def _do_media_shows(self, args):
        if not args.command:
            self.do_help('media shows')

    # example choices list
    ratings_types = ['G', 'PG', 'PG-13', 'R', 'NC-17']

    media_parser = AutoCompleter.ACArgumentParser()

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
    movies_add_parser.add_argument('-t', '--title', help='Movie Title', required=True)
    movies_add_parser.add_argument('-r', '--rating', help='Movie Rating', choices=ratings_types, required=True)
    movies_add_parser.add_argument('-d', '--director', help='Director', action='append', required=True)
    movies_add_parser.add_argument('-a', '--actor', help='Actors', action='append', required=True)

    movies_delete_parser = movies_commands_subparsers.add_parser('delete')

    shows_parser = media_types_subparsers.add_parser('shows')
    shows_parser.set_defaults(func=_do_media_shows)

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

    # This completer is implemented using a single dictionary to look up completion lists for all layers of
    # subcommands. For each argument, AutoCompleter will search for completion values from the provided
    # arg_choices dict. This requires careful naming of argparse arguments so that there are no unintentional
    # name collisions.
    def complete_media(self, text, line, begidx, endidx):
        """ Adds tab completion to media"""
        static_list_directors = ['J. J. Abrams', 'Irvin Kershner', 'George Lucas', 'Richard Marquand',
                     'Rian Johnson', 'Gareth Edwards']
        choices = {'actor': self.query_actors,
                   'director': static_list_directors}
        completer = AutoCompleter.AutoCompleter(TabCompleteExample.media_parser, arg_choices=choices)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        results = completer.complete_command(tokens, text, line, begidx, endidx)

        return results


if __name__ == '__main__':
    app = TabCompleteExample()
    app.cmdloop()
