#!/usr/bin/env python3
# coding=utf-8
"""
A example usage of the AutoCompleter
"""
import argparse
import functools
from typing import List

import cmd2
from cmd2 import utils, Cmd2ArgumentParser, CompletionItem

actors = ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher', 'Alec Guinness', 'Peter Mayhew',
          'Anthony Daniels', 'Adam Driver', 'Daisy Ridley', 'John Boyega', 'Oscar Isaac',
          'Lupita Nyong\'o', 'Andy Serkis', 'Liam Neeson', 'Ewan McGregor', 'Natalie Portman',
          'Jake Lloyd', 'Hayden Christensen', 'Christopher Lee']


def query_actors() -> List[str]:
    """Simulating a function that queries and returns a completion values"""
    return actors


class TabCompleteExample(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple subcommands."""

    CAT_AUTOCOMPLETE = 'AutoComplete Examples'

    def __init__(self):
        super().__init__()

    # For mocking a data source for the example commands
    ratings_types = ['G', 'PG', 'PG-13', 'R', 'NC-17']
    show_ratings = ['TV-Y', 'TV-Y7', 'TV-G', 'TV-PG', 'TV-14', 'TV-MA']
    static_list_directors = ['J. J. Abrams', 'Irvin Kershner', 'George Lucas', 'Richard Marquand',
                             'Rian Johnson', 'Gareth Edwards']
    USER_MOVIE_LIBRARY = ['ROGUE1', 'SW_EP04', 'SW_EP05']
    MOVIE_DATABASE_IDS = ['SW_EP1', 'SW_EP02', 'SW_EP03', 'ROGUE1', 'SW_EP04',
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
                      'SW_EP06': {'title': 'Star Wars: Episode VI - Return of the Jedi',
                                  'rating': 'PG',
                                  'director': ['Richard Marquand'],
                                  'actor': ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher',
                                            'Alec Guinness', 'Peter Mayhew', 'Anthony Daniels']
                                  },
                      'SW_EP1': {'title': 'Star Wars: Episode I - The Phantom Menace',
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
    USER_SHOW_LIBRARY = {'SW_REB': ['S01E01', 'S02E02']}
    SHOW_DATABASE_IDS = ['SW_CW', 'SW_TCW', 'SW_REB']
    SHOW_DATABASE = {'SW_CW': {'title': 'Star Wars: Clone Wars',
                               'rating': 'TV-Y7',
                               'seasons': {1: ['S01E01', 'S01E02', 'S01E03'],
                                           2: ['S02E01', 'S02E02', 'S02E03']}
                               },
                     'SW_TCW': {'title': 'Star Wars: The Clone Wars',
                                'rating': 'TV-PG',
                                'seasons': {1: ['S01E01', 'S01E02', 'S01E03'],
                                            2: ['S02E01', 'S02E02', 'S02E03']}
                                },
                     'SW_REB': {'title': 'Star Wars: Rebels',
                                'rating': 'TV-Y7',
                                'seasons': {1: ['S01E01', 'S01E02', 'S01E03'],
                                            2: ['S02E01', 'S02E02', 'S02E03']}
                                },
                     }

    file_list = \
        [
            '/home/user/file.db',
            '/home/user/file space.db',
            '/home/user/another.db',
            '/home/other user/maps.db',
            '/home/other user/tests.db'
        ]

    # noinspection PyMethodMayBeStatic
    def instance_query_actors(self) -> List[str]:
        """Simulating a function that queries and returns a completion values"""
        return actors

    def instance_query_movie_ids(self) -> List[str]:
        """Demonstrates showing tabular hinting of tab completion information"""
        completions_with_desc = []

        # Sort the movie id strings with a natural sort since they contain numbers
        for movie_id in utils.natural_sort(self.MOVIE_DATABASE_IDS):
            if movie_id in self.MOVIE_DATABASE:
                movie_entry = self.MOVIE_DATABASE[movie_id]
                completions_with_desc.append(CompletionItem(movie_id, movie_entry['title']))

        # Mark that we already sorted the matches
        self.matches_sorted = True
        return completions_with_desc

    # This demonstrates a number of customizations of the AutoCompleter version of ArgumentParser
    #  - The help output will separately group required vs optional flags
    #  - The help output for arguments with multiple flags or with append=True is more concise
    #  - cmd2 adds the ability to specify ranges of argument counts in 'nargs'

    suggest_description = "Suggest command demonstrates argparse customizations.\n"
    suggest_description += "See hybrid_suggest and orig_suggest to compare the help output."
    suggest_parser = Cmd2ArgumentParser(description=suggest_description)

    suggest_parser.add_argument('-t', '--type', choices=['movie', 'show'], required=True)
    suggest_parser.add_argument('-d', '--duration', nargs=(1, 2), action='append',
                                help='Duration constraint in minutes.\n'
                                     '\tsingle value - maximum duration\n'
                                     '\t[a, b] - duration range')

    @cmd2.with_category(CAT_AUTOCOMPLETE)
    @cmd2.with_argparser(suggest_parser)
    def do_suggest(self, args) -> None:
        """Suggest command demonstrates argparse customizations"""
        if not args.type:
            self.do_help('suggest')

    # If you prefer the original argparse help output but would like narg ranges, it's possible
    # to enable narg ranges without the help changes using this method

    suggest_parser_hybrid = argparse.ArgumentParser()
    suggest_parser_hybrid.add_argument('-t', '--type', choices=['movie', 'show'], required=True)
    suggest_parser_hybrid.add_argument('-d', '--duration', nargs=(1, 2), action='append',
                                       help='Duration constraint in minutes.\n'
                                            '\tsingle value - maximum duration\n'
                                            '\t[a, b] - duration range')

    @cmd2.with_category(CAT_AUTOCOMPLETE)
    @cmd2.with_argparser(suggest_parser_hybrid)
    def do_hybrid_suggest(self, args):
        if not args.type:
            self.do_help('orig_suggest')

    # This variant demonstrates the AutoCompleter working with the orginial argparse.
    # Base argparse is unable to specify narg ranges. Autocompleter will keep expecting additional arguments
    # for the -d/--duration flag until you specify a new flag or end processing of flags with '--'

    suggest_parser_orig = argparse.ArgumentParser()

    suggest_parser_orig.add_argument('-t', '--type', choices=['movie', 'show'], required=True)
    suggest_parser_orig.add_argument('-d', '--duration', nargs='+', action='append',
                                     help='Duration constraint in minutes.\n'
                                          '\tsingle value - maximum duration\n'
                                          '\t[a, b] - duration range')

    @cmd2.with_argparser(suggest_parser_orig)
    @cmd2.with_category(CAT_AUTOCOMPLETE)
    def do_orig_suggest(self, args) -> None:
        if not args.type:
            self.do_help('orig_suggest')

    def _do_vid_movies(self, args) -> None:
        if not args.command:
            self.do_help('video movies')
        elif args.command == 'list':
            for movie_id in TabCompleteExample.MOVIE_DATABASE:
                movie = TabCompleteExample.MOVIE_DATABASE[movie_id]
                print('{}\n-----------------------------\n{}   ID: {}\nDirector: {}\nCast:\n    {}\n\n'
                      .format(movie['title'], movie['rating'], movie_id,
                              ', '.join(movie['director']),
                              '\n    '.join(movie['actor'])))

    def _do_vid_shows(self, args) -> None:
        if not args.command:
            self.do_help('video shows')

        elif args.command == 'list':
            for show_id in TabCompleteExample.SHOW_DATABASE:
                show = TabCompleteExample.SHOW_DATABASE[show_id]
                print('{}\n-----------------------------\n{}   ID: {}'
                      .format(show['title'], show['rating'], show_id))
                for season in show['seasons']:
                    ep_list = show['seasons'][season]
                    print('  Season {}:\n    {}'
                          .format(season,
                                  '\n    '.join(ep_list)))
                print()

    video_parser = Cmd2ArgumentParser(prog='media')

    video_types_subparsers = video_parser.add_subparsers(title='Media Types', dest='type')

    vid_movies_parser = video_types_subparsers.add_parser('movies')
    vid_movies_parser.set_defaults(func=_do_vid_movies)

    vid_movies_commands_subparsers = vid_movies_parser.add_subparsers(title='Commands', dest='command')

    vid_movies_list_parser = vid_movies_commands_subparsers.add_parser('list')

    vid_movies_list_parser.add_argument('-t', '--title', help='Title Filter')
    vid_movies_list_parser.add_argument('-r', '--rating', help='Rating Filter', nargs='+',
                                        choices=ratings_types)
    vid_movies_list_parser.add_argument('-d', '--director', help='Director Filter', choices=static_list_directors)
    vid_movies_list_parser.add_argument('-a', '--actor', help='Actor Filter', action='append',
                                        choices_function=query_actors)

    vid_movies_add_parser = vid_movies_commands_subparsers.add_parser('add')
    vid_movies_add_parser.add_argument('title', help='Movie Title')
    vid_movies_add_parser.add_argument('rating', help='Movie Rating', choices=ratings_types)

    vid_movies_add_parser.add_argument('-d', '--director', help='Director', nargs=(1, 2), required=True,
                                       choices=static_list_directors)
    vid_movies_add_parser.add_argument('actor', help='Actors', nargs='*', choices_method=instance_query_actors)

    vid_movies_load_parser = vid_movies_commands_subparsers.add_parser('load')
    vid_movies_load_parser.add_argument('movie_file', help='Movie database',
                                        completer_method=functools.partial(cmd2.Cmd.delimiter_complete,
                                                                           delimiter='/', match_against=file_list))

    vid_movies_read_parser = vid_movies_commands_subparsers.add_parser('read')
    vid_movies_read_parser.add_argument('movie_file', help='Movie database', completer_method=cmd2.Cmd.path_complete)

    vid_movies_delete_parser = vid_movies_commands_subparsers.add_parser('delete')
    vid_movies_delete_parser.add_argument('movie_id', help='Movie ID', choices_method=instance_query_movie_ids,
                                          descriptive_header='Title')

    vid_shows_parser = video_types_subparsers.add_parser('shows')
    vid_shows_parser.set_defaults(func=_do_vid_shows)

    vid_shows_commands_subparsers = vid_shows_parser.add_subparsers(title='Commands', dest='command')

    vid_shows_list_parser = vid_shows_commands_subparsers.add_parser('list')

    @cmd2.with_category(CAT_AUTOCOMPLETE)
    @cmd2.with_argparser(video_parser)
    def do_video(self, args):
        """Video management command demonstrates multiple layers of subcommands being handled by AutoCompleter"""
        func = getattr(args, 'func', None)
        if func is not None:
            # Call whatever subcommand function was selected
            func(self, args)
        else:
            # No subcommand was provided, so call help
            self.do_help('video')


if __name__ == '__main__':
    import sys
    app = TabCompleteExample()
    sys.exit(app.cmdloop())
