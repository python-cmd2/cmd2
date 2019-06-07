#!/usr/bin/env python3
# coding=utf-8
"""
A example usage of AutoCompleter with delayed initialization of the argparse object
"""
from typing import List

import cmd2
from cmd2 import argparse_completer, utils

actors = ['Mark Hamill', 'Harrison Ford', 'Carrie Fisher', 'Alec Guinness', 'Peter Mayhew',
          'Anthony Daniels', 'Adam Driver', 'Daisy Ridley', 'John Boyega', 'Oscar Isaac',
          'Lupita Nyong\'o', 'Andy Serkis', 'Liam Neeson', 'Ewan McGregor', 'Natalie Portman',
          'Jake Lloyd', 'Hayden Christensen', 'Christopher Lee']


def query_actors() -> List[str]:
    """Simulating a function that queries and returns a completion values"""
    return actors


class TabCompleteExample(cmd2.Cmd):
    """ Example cmd2 application where we a base command which has a couple sub-commands."""

    CAT_AUTOCOMPLETE = 'AutoComplete Examples'

    def __init__(self):
        super().__init__()

        video_types_subparsers = TabCompleteExample.video_parser.add_subparsers(title='Media Types', dest='type')

        vid_movies_parser = argparse_completer.ACArgumentParser(prog='movies')
        vid_movies_parser.set_defaults(func=TabCompleteExample._do_vid_media_movies)

        vid_movies_commands_subparsers = vid_movies_parser.add_subparsers(title='Commands', dest='command')

        vid_movies_list_parser = vid_movies_commands_subparsers.add_parser('list')

        vid_movies_list_parser.add_argument('-t', '--title', help='Title Filter')
        vid_movies_list_parser.add_argument('-r', '--rating', help='Rating Filter', nargs='+',
                                            choices=TabCompleteExample.ratings_types)
        # save a reference to the action object
        director_action = vid_movies_list_parser.add_argument('-d', '--director', help='Director Filter')
        actor_action = vid_movies_list_parser.add_argument('-a', '--actor', help='Actor Filter', action='append')

        # tag the action objects with completion providers. This can be a collection or a callable
        setattr(director_action, argparse_completer.ACTION_ARG_CHOICES, TabCompleteExample.static_list_directors)
        setattr(actor_action, argparse_completer.ACTION_ARG_CHOICES, query_actors)

        vid_movies_add_parser = vid_movies_commands_subparsers.add_parser('add')
        vid_movies_add_parser.add_argument('title', help='Movie Title')
        vid_movies_add_parser.add_argument('rating', help='Movie Rating', choices=TabCompleteExample.ratings_types)

        # save a reference to the action object
        director_action = vid_movies_add_parser.add_argument('-d', '--director', help='Director', nargs=(1, 2),
                                                             required=True)
        actor_action = vid_movies_add_parser.add_argument('actor', help='Actors', nargs='*')

        vid_movies_load_parser = vid_movies_commands_subparsers.add_parser('load')
        vid_movie_file_action = vid_movies_load_parser.add_argument('movie_file', help='Movie database')

        vid_movies_read_parser = vid_movies_commands_subparsers.add_parser('read')
        vid_movie_fread_action = vid_movies_read_parser.add_argument('movie_file', help='Movie database')

        # tag the action objects with completion providers. This can be a collection or a callable
        setattr(director_action, argparse_completer.ACTION_ARG_CHOICES, TabCompleteExample.static_list_directors)
        setattr(actor_action, argparse_completer.ACTION_ARG_CHOICES, 'instance_query_actors')

        # tag the file property with a custom completion function 'delimiter_complete' provided by cmd2.
        setattr(vid_movie_file_action, argparse_completer.ACTION_ARG_CHOICES,
                ('delimiter_complete',
                 {'delimiter': '/',
                  'match_against': TabCompleteExample.file_list}))
        setattr(vid_movie_fread_action, argparse_completer.ACTION_ARG_CHOICES,
                ('path_complete',))

        vid_movies_delete_parser = vid_movies_commands_subparsers.add_parser('delete')
        vid_delete_movie_id = vid_movies_delete_parser.add_argument('movie_id', help='Movie ID')
        setattr(vid_delete_movie_id, argparse_completer.ACTION_ARG_CHOICES, TabCompleteExample.instance_query_movie_ids)
        setattr(vid_delete_movie_id, argparse_completer.ACTION_DESCRIPTIVE_COMPLETION_HEADER, 'Title')

        # Add the 'movies' parser as a parent of sub-parser
        video_types_subparsers.add_parser('movies', parents=[vid_movies_parser], add_help=False)

        vid_shows_parser = argparse_completer.ACArgumentParser(prog='shows')
        vid_shows_parser.set_defaults(func=TabCompleteExample._do_vid_media_shows)

        vid_shows_commands_subparsers = vid_shows_parser.add_subparsers(title='Commands', dest='command')

        vid_shows_commands_subparsers.add_parser('list')

        video_types_subparsers.add_parser('shows', parents=[vid_shows_parser], add_help=False)

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
                completions_with_desc.append(argparse_completer.CompletionItem(movie_id, movie_entry['title']))

        # Mark that we already sorted the matches
        self.matches_sorted = True
        return completions_with_desc

    ###################################################################################
    # The media command demonstrates a completer with multiple layers of subcommands
    #   - This example demonstrates how to tag a completion attribute on each action, enabling argument
    #       completion without implementing a complete_COMMAND function
    def _do_vid_media_movies(self, args) -> None:
        if not args.command:
            self.do_help('video movies')
        elif args.command == 'list':
            for movie_id in TabCompleteExample.MOVIE_DATABASE:
                movie = TabCompleteExample.MOVIE_DATABASE[movie_id]
                print('{}\n-----------------------------\n{}   ID: {}\nDirector: {}\nCast:\n    {}\n\n'
                      .format(movie['title'], movie['rating'], movie_id,
                              ', '.join(movie['director']),
                              '\n    '.join(movie['actor'])))

    def _do_vid_media_shows(self, args) -> None:
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

    video_parser = argparse_completer.ACArgumentParser(prog='video')

    @cmd2.with_category(CAT_AUTOCOMPLETE)
    @cmd2.with_argparser(video_parser)
    def do_video(self, args):
        """Video management command demonstrates multiple layers of sub-commands being handled by AutoCompleter"""
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
