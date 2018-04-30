"""
Bridges calls made inside of pyscript with the Cmd2 host app while maintaining a reasonable
degree of isolation between the two

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""

import argparse
from typing import List, Tuple


class ArgparseFunctor:
    def __init__(self, cmd2_app, item, parser):
        self._cmd2_app = cmd2_app
        self._item = item
        self._parser = parser

        # Dictionary mapping command argument name to value
        self._args = {}
        # argparse object for the current command layer
        self.__current_subcommand_parser = parser

    def __getattr__(self, item):
        """Search for a subcommand matching this item and update internal state to track the traversal"""
        # look for sub-command under the current command/sub-command layer
        for action in self.__current_subcommand_parser._actions:
            if not action.option_strings and isinstance(action, argparse._SubParsersAction):
                if item in action.choices:
                    # item matches the a sub-command, save our position in argparse,
                    # save the sub-command, return self to allow next level of traversal
                    self.__current_subcommand_parser = action.choices[item]
                    self._args[action.dest] = item
                    return self

        raise AttributeError(item)
        # return super().__getattr__(item)

    def __call__(self, *args, **kwargs):
        """
        Process the arguments at this layer of the argparse command tree. If there are more sub-commands,
        return self to accept the next sub-command name. If there are no more sub-commands, execute the
        sub-command with the given parameters.
        """
        next_pos_index = 0

        has_subcommand = False
        consumed_kw = []

        # Iterate through the current sub-command's arguments in order
        for action in self.__current_subcommand_parser._actions:
            # is this a flag option?
            if action.option_strings:
                # this is a flag argument, search for the argument by name in the parameters
                if action.dest in kwargs:
                    self._args[action.dest] = kwargs[action.dest]
                    consumed_kw.append(action.dest)
            else:
                # This is a positional argument, search the positional arguments passed in.
                if not isinstance(action, argparse._SubParsersAction):
                    if action.dest in kwargs:
                        self._args[action.dest] = kwargs[action.dest]
                    elif next_pos_index < len(args):
                        self._args[action.dest] = args[next_pos_index]
                        next_pos_index += 1
                else:
                    has_subcommand = True

        # Check if there are any extra arguments we don't know how to handle
        for kw in kwargs:
            if kw not in self._args:  # consumed_kw:
                raise TypeError('{}() got an unexpected keyword argument \'{}\''.format(
                    self.__current_subcommand_parser.prog, kw))

        if has_subcommand:
            return self
        else:
            return self._run()

    def _run(self):
        # look up command function
        func = getattr(self._cmd2_app, 'do_' + self._item)

        # reconstruct the cmd2 command from the python call
        cmd_str = ['']

        def process_flag(action, value):
            # was the argument a flag?
            if action.option_strings:
                cmd_str[0] += '{} '.format(action.option_strings[0])

            if isinstance(value, List) or isinstance(value, Tuple):
                for item in value:
                    item = str(item).strip()
                    if ' ' in item:
                        item = '"{}"'.format(item)
                    cmd_str[0] += '{} '.format(item)
            else:
                value = str(value).strip()
                if ' ' in value:
                    value = '"{}"'.format(value)
                cmd_str[0] += '{} '.format(value)

        def traverse_parser(parser):
            for action in parser._actions:
                # was something provided for the argument
                if action.dest in self._args:
                    if isinstance(action, argparse._SubParsersAction):
                        cmd_str[0] += '{} '.format(self._args[action.dest])
                        traverse_parser(action.choices[self._args[action.dest]])
                    elif isinstance(action, argparse._AppendAction):
                        if isinstance(self._args[action.dest], List) or isinstance(self._args[action.dest], Tuple):
                            for values in self._args[action.dest]:
                                process_flag(action, values)
                        else:
                            process_flag(action, self._args[action.dest])
                    else:
                        process_flag(action, self._args[action.dest])

        traverse_parser(self._parser)

        # print('Command: {}'.format(cmd_str[0]))

        func(cmd_str[0])
        return self._cmd2_app._last_result


class PyscriptBridge(object):
    """Preserves the legacy 'cmd' interface for pyscript while also providing a new python API wrapper for
    application commands."""
    def __init__(self, cmd2_app):
        self._cmd2_app = cmd2_app
        self._last_result = None

    def __getattr__(self, item: str):
        """Check if the attribute is a command. If so, return a callable."""
        commands = self._cmd2_app.get_all_commands()
        if item in commands:
            func = getattr(self._cmd2_app, 'do_' + item)

            try:
                # See if the command uses argparse
                parser = getattr(func, 'argparser')
            except AttributeError:
                # Command doesn't, we will accept parameters in the form of a command string
                def wrap_func(args=''):
                    func(args)
                    return self._cmd2_app._last_result
                return wrap_func
            else:
                # Command does use argparse, return an object that can traverse the argparse subcommands and arguments
                return ArgparseFunctor(self._cmd2_app, item, parser)

        raise AttributeError(item)

    def __call__(self, args):
        self._cmd2_app.onecmd_plus_hooks(args + '\n')
        self._last_result = self._cmd2_app._last_result
        return self._cmd2_app._last_result
