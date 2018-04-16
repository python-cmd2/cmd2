#!/usr/bin/env python
# coding=utf-8
"""A simple example demonstrating how to use flag and index based tab-completion functions
"""
import argparse
import AutoCompleter
from typing import List

import cmd2
from cmd2 import with_argparser, with_category

# List of strings used with flag and index based completion functions
food_item_strs = ['Pizza', 'Hamburger', 'Ham', 'Potato']
sport_item_strs = ['Bat', 'Basket', 'Basketball', 'Football']


class TabCompleteExample(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple subcommands."""

    CAT_AUTOCOMPLETE = 'AutoComplete Examples'

    def __init__(self):
        super().__init__()

    # For mocking a data source for the example commands
    ratings_types = ['G', 'PG', 'PG-13', 'R', 'NC-17']
    static_list_directors = ['J. J. Abrams', 'Irvin Kershner', 'George Lucas', 'Richard Marquand',
                             'Rian Johnson', 'Gareth Edwards']
    actors = ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher', 'Alec Guinness', 'Peter Mayhew',
              'Anthony Daniels', 'Adam Driver', 'Daisy Ridley', 'John Boyega', 'Oscar Isaac',
              'Lupita Nyong\'o', 'Andy Serkis', 'Liam Neeson', 'Ewan McGregor', 'Natalie Portman',
              'Jake Lloyd', 'Hayden Christensen', 'Christopher Lee']
    USER_MOVIE_LIBRARY = ['ROGUE1', 'SW_EP04', 'SW_EP05']
    MOVIE_DATABASE_IDS = ['SW_EP01', 'SW_EP02', 'SW_EP03', 'ROGUE1', 'SW_EP04',
                          'SW_EP05', 'SW_EP06', 'SW_EP07', 'SW_EP08', 'SW_EP09']
    MOVIE_DATABASE = {'SW_EP04': {'title': 'Star Wars: Episode IV - A New Hope',
                                  'rating': 'PG',
                                  'director': ['George Lucas'],
                                  'actor': ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher',
                                            'Alec Guinness', 'Peter Mayhew', 'Anthony Daniels']
                                  },
                      'SW_EP05': {'title': 'Star Wars: Episode V - The Empire Strikes Back',
                                  'rating': 'PG',
                                  'director': ['Irvin Kershner'],
                                  'actor': ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher',
                                            'Alec Guinness', 'Peter Mayhew', 'Anthony Daniels']
                                  },
                      'SW_EP06': {'title': 'Star Wars: Episode IV - A New Hope',
                                  'rating': 'PG',
                                  'director': ['Richard Marquand'],
                                  'actor': ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher',
                                            'Alec Guinness', 'Peter Mayhew', 'Anthony Daniels']
                                  },
                      'SW_EP01': {'title': 'Star Wars: Episode I - The Phantom Menace',
                                  'rating': 'PG',
                                  'director': ['George Lucas'],
                                  'actor': ['Liam Neeson', 'Ewan McGregor', 'Natalie Portman', 'Jake Lloyd']
                                  },
                      'SW_EP02': {'title': 'Star Wars: Episode II - Attack of the Clones',
                                  'rating': 'PG',
                                  'director': ['George Lucas'],
                                  'actor': ['Liam Neeson', 'Ewan McGregor', 'Natalie Portman',
                                            'Hayden Christensen', 'Christopher Lee']
                                  },
                      'SW_EP03': {'title': 'Star Wars: Episode III - Revenge of the Sith',
                                  'rating': 'PG-13',
                                  'director': ['George Lucas'],
                                  'actor': ['Liam Neeson', 'Ewan McGregor', 'Natalie Portman',
                                            'Hayden Christensen']
                                  },

                      }

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

    @with_category(CAT_AUTOCOMPLETE)
    @with_argparser(suggest_parser)
    def do_suggest(self, args) -> None:
        """Suggest command demonstrates argparse customizations

        See hybrid_suggest and orig_suggest to compare the help output.


        """
        if not args.type:
            self.do_help('suggest')

    def complete_suggest(self, text: str, line: str, begidx: int, endidx: int) -> List[str]:
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

    @with_category(CAT_AUTOCOMPLETE)
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
    @with_category(CAT_AUTOCOMPLETE)
    def do_orig_suggest(self, args) -> None:
        if not args.type:
            self.do_help('orig_suggest')

    def complete_orig_suggest(self, text, line, begidx, endidx) -> List[str]:
        """ Adds tab completion to media"""
        completer = AutoCompleter.AutoCompleter(TabCompleteExample.suggest_parser_orig)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        results = completer.complete_command(tokens, text, line, begidx, endidx)

        return results

    ###################################################################################
    # The media command demonstrates a completer with multiple layers of subcommands
    #   - This example uses a flat completion lookup dictionary

    def query_actors(self) -> List[str]:
        """Simulating a function that queries and returns a completion values"""
        return TabCompleteExample.actors

    def _do_media_movies(self, args) -> None:
        if not args.command:
            self.do_help('media movies')
        elif args.command == 'list':
            for movie_id in TabCompleteExample.MOVIE_DATABASE:
                movie = TabCompleteExample.MOVIE_DATABASE[movie_id]
                print('{}\n-----------------------------\n{}   ID: {}\nDirector: {}\nCast:\n    {}\n\n'
                      .format(movie['title'], movie['rating'], movie_id,
                              ', '.join(movie['director']),
                              '\n    '.join(movie['actor'])))

    def _do_media_shows(self, args) -> None:
        if not args.command:
            self.do_help('media shows')

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

    @with_category(CAT_AUTOCOMPLETE)
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
        choices = {'actor': self.query_actors,  # function
                   'director': TabCompleteExample.static_list_directors  # static list
                   }
        completer = AutoCompleter.AutoCompleter(TabCompleteExample.media_parser, arg_choices=choices)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        results = completer.complete_command(tokens, text, line, begidx, endidx)

        return results

    ###################################################################################
    # The library command demonstrates a completer with multiple layers of subcommands
    # with different completion results per sub-command
    #   - This demonstrates how to build a tree of completion lookups to pass down
    #
    # Only use this method if you absolutely need to as it dramatically
    # increases the complexity and decreases readability.

    def _do_library_movie(self, args):
        if not args.type or not args.command:
            self.do_help('library movie')

    def _do_library_show(self, args):
        if not args.type:
            self.do_help('library show')

    def _query_movie_database(self, exclude=[]):
        return list(set(TabCompleteExample.MOVIE_DATABASE_IDS).difference(set(exclude)))

    def _query_movie_user_library(self):
        return TabCompleteExample.USER_MOVIE_LIBRARY

    library_parser = AutoCompleter.ACArgumentParser(prog='library')

    library_subcommands = library_parser.add_subparsers(title='Media Types', dest='type')

    library_movie_parser = library_subcommands.add_parser('movie')
    library_movie_parser.set_defaults(func=_do_library_movie)

    library_movie_subcommands = library_movie_parser.add_subparsers(title='Command', dest='command')

    library_movie_add_parser = library_movie_subcommands.add_parser('add')
    library_movie_add_parser.add_argument('movie_id', help='ID of movie to add', action='append')

    library_movie_remove_parser = library_movie_subcommands.add_parser('remove')
    library_movie_remove_parser.add_argument('movie_id', help='ID of movie to remove', action='append')

    library_show_parser = library_subcommands.add_parser('show')
    library_show_parser.set_defaults(func=_do_library_show)

    @with_category(CAT_AUTOCOMPLETE)
    @with_argparser(library_parser)
    def do_library(self, args):
        """Media management command demonstrates multiple layers of subcommands being handled by AutoCompleter"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('library')

    def complete_library(self, text, line, begidx, endidx):

        # this demonstrates the much more complicated scenario of having
        # unique completion parameters per sub-command that use the same
        # argument name. To do this we build a multi-layer nested tree
        # of lookups far AutoCompleter to traverse. This nested tree must
        # match the structure of the argparse parser
        #

        movie_add_choices = {'movie_id': self._query_movie_database}
        movie_remove_choices = {'movie_id': self._query_movie_user_library}

        # The library movie sub-parser group 'command' has 2 sub-parsers:
        #   'add' and 'remove'
        library_movie_command_params = \
            {'add': (movie_add_choices, None),
             'remove': (movie_remove_choices, None)}

        # The 'library movie' command has a sub-parser group called 'command'
        library_movie_subcommand_groups = {'command': library_movie_command_params}

        # Mapping of a specific sub-parser of the 'type' group to a tuple. Each
        #    tuple has 2 values corresponding what's passed to the constructor
        #    parameters (arg_choices,subcmd_args_lookup) of the nested
        #    instance of AutoCompleter
        library_type_params = {'movie': (None, library_movie_subcommand_groups),
                               'show': (None, None)}

        # maps the a subcommand group to a dictionary mapping a specific
        # sub-command to a tuple of (arg_choices, subcmd_args_lookup)
        #
        # In this example, 'library_parser' has a sub-parser group called 'type'
        #   under the type sub-parser group, there are 2 sub-parsers: 'movie', 'show'
        library_subcommand_groups = {'type': library_type_params}

        completer = AutoCompleter.AutoCompleter(TabCompleteExample.library_parser,
                                                subcmd_args_lookup=library_subcommand_groups)

        tokens, _ = self.tokens_for_completion(line, begidx, endidx)
        results = completer.complete_command(tokens, text, line, begidx, endidx)

        return results


if __name__ == '__main__':
    app = TabCompleteExample()
    app.cmdloop()
