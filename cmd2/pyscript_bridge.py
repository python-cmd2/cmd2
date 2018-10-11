# coding=utf-8
"""
Bridges calls made inside of pyscript with the Cmd2 host app while maintaining a reasonable
degree of isolation between the two

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""

import argparse
import functools
import sys
from typing import List, Callable, Optional

from .argparse_completer import _RangeAction, is_potential_flag
from .utils import namedtuple_with_defaults, StdSim, quote_string_if_needed

# Python 3.4 require contextlib2 for temporarily redirecting stderr and stdout
if sys.version_info < (3, 5):
    from contextlib2 import redirect_stdout, redirect_stderr
else:
    from contextlib import redirect_stdout, redirect_stderr


class CommandResult(namedtuple_with_defaults('CommandResult', ['stdout', 'stderr', 'data'])):
    """Encapsulates the results from a command.

    Named tuple attributes
    ----------------------
    stdout: str - Output captured from stdout while this command is executing
    stderr: str - Output captured from stderr while this command is executing. None if no error captured
    data - Data returned by the command.

    NOTE: Named tuples are immutable.  So the contents are there for access, not for modification.
    """
    def __bool__(self) -> bool:
        """Returns True if the command succeeded, otherwise False"""

        # If data has a __bool__ method, then call it to determine success of command
        if self.data is not None and callable(getattr(self.data, '__bool__', None)):
            return bool(self.data)

        # Otherwise check if stderr was filled out
        else:
            return not self.stderr


def _exec_cmd(cmd2_app, func: Callable, echo: bool) -> CommandResult:
    """Helper to encapsulate executing a command and capturing the results"""
    copy_stdout = StdSim(sys.stdout, echo)
    copy_stderr = StdSim(sys.stderr, echo)

    copy_cmd_stdout = StdSim(cmd2_app.stdout, echo)

    cmd2_app._last_result = None

    try:
        cmd2_app.stdout = copy_cmd_stdout
        with redirect_stdout(copy_stdout):
            with redirect_stderr(copy_stderr):
                func()
    finally:
        cmd2_app.stdout = copy_cmd_stdout.inner_stream

    # if stderr is empty, set it to None
    stderr = copy_stderr.getvalue() if copy_stderr.getvalue() else None

    outbuf = copy_cmd_stdout.getvalue() if copy_cmd_stdout.getvalue() else copy_stdout.getvalue()
    result = CommandResult(stdout=outbuf, stderr=stderr, data=cmd2_app._last_result)
    return result


class ArgparseFunctor:
    """
    Encapsulates translating Python object traversal
    """
    def __init__(self, echo: bool, cmd2_app, command_name: str, parser: argparse.ArgumentParser):
        self._echo = echo
        self._cmd2_app = cmd2_app
        self._command_name = command_name
        self._parser = parser

        # Dictionary mapping command argument name to value
        self._args = {}
        # tag the argument that's a remainder type
        self._remainder_arg = None
        # separately track flag arguments so they will be printed before positionals
        self._flag_args = []
        # argparse object for the current command layer
        self.__current_subcommand_parser = parser

    def __dir__(self):
        """Returns a custom list of attribute names to match the sub-commands"""
        commands = []
        for action in self.__current_subcommand_parser._actions:
            if not action.option_strings and isinstance(action, argparse._SubParsersAction):
                commands.extend(action.choices)
        return commands

    def __getattr__(self, item: str):
        """Search for a sub-command matching this item and update internal state to track the traversal"""
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

    def __call__(self, *args, **kwargs):
        """
        Process the arguments at this layer of the argparse command tree. If there are more sub-commands,
        return self to accept the next sub-command name. If there are no more sub-commands, execute the
        sub-command with the given parameters.
        """
        next_pos_index = 0

        has_subcommand = False

        # Iterate through the current sub-command's arguments in order
        for action in self.__current_subcommand_parser._actions:
            # is this a flag option?
            if action.option_strings:
                # this is a flag argument, search for the argument by name in the parameters
                if action.dest in kwargs:
                    self._args[action.dest] = kwargs[action.dest]
                    self._flag_args.append(action.dest)
            else:
                # This is a positional argument, search the positional arguments passed in.
                if not isinstance(action, argparse._SubParsersAction):
                    if action.dest in kwargs:
                        # if this positional argument happens to be passed in as a keyword argument
                        # go ahead and consume the matching keyword argument
                        self._args[action.dest] = kwargs[action.dest]
                    elif next_pos_index < len(args):
                        # Make sure we actually have positional arguments to consume
                        pos_remain = len(args) - next_pos_index

                        # Check if this argument consumes a range of values
                        if isinstance(action, _RangeAction) and action.nargs_min is not None \
                                and action.nargs_max is not None:
                            # this is a cmd2 ranged action.

                            if pos_remain >= action.nargs_min:
                                # Do we meet the minimum count?
                                if pos_remain > action.nargs_max:
                                    # Do we exceed the maximum count?
                                    self._args[action.dest] = args[next_pos_index:next_pos_index + action.nargs_max]
                                    next_pos_index += action.nargs_max
                                else:
                                    self._args[action.dest] = args[next_pos_index:next_pos_index + pos_remain]
                                    next_pos_index += pos_remain
                            else:
                                raise ValueError('Expected at least {} values for {}'.format(action.nargs_min,
                                                                                             action.dest))
                        elif action.nargs is not None:
                            if action.nargs == '+':
                                if pos_remain > 0:
                                    self._args[action.dest] = args[next_pos_index:next_pos_index + pos_remain]
                                    next_pos_index += pos_remain
                                else:
                                    raise ValueError('Expected at least 1 value for {}'.format(action.dest))
                            elif action.nargs == '*':
                                self._args[action.dest] = args[next_pos_index:next_pos_index + pos_remain]
                                next_pos_index += pos_remain
                            elif action.nargs == argparse.REMAINDER:
                                self._args[action.dest] = args[next_pos_index:next_pos_index + pos_remain]
                                next_pos_index += pos_remain
                                self._remainder_arg = action.dest
                            elif action.nargs == '?':
                                self._args[action.dest] = args[next_pos_index]
                                next_pos_index += 1
                        else:
                            self._args[action.dest] = args[next_pos_index]
                            next_pos_index += 1
                else:
                    has_subcommand = True

        # Check if there are any extra arguments we don't know how to handle
        for kw in kwargs:
            if kw not in self._args:
                raise TypeError("{}() got an unexpected keyword argument '{}'".format(
                    self.__current_subcommand_parser.prog, kw))

        if has_subcommand:
            return self
        else:
            return self._run()

    def _run(self):
        # look up command function
        func = self._cmd2_app.cmd_func(self._command_name)
        if func is None:
            raise AttributeError("'{}' object has no command called '{}'".format(self._cmd2_app.__class__.__name__,
                                                                                 self._command_name))

        # reconstruct the cmd2 command from the python call
        cmd_str = ['']

        def process_argument(action, value):
            if isinstance(action, argparse._CountAction):
                if isinstance(value, int):
                    for _ in range(value):
                        cmd_str[0] += '{} '.format(action.option_strings[0])
                    return
                else:
                    raise TypeError('Expected int for ' + action.dest)
            if isinstance(action, argparse._StoreConstAction) or isinstance(action, argparse._AppendConstAction):
                if value:
                    # Nothing else to append to the command string, just the flag is enough.
                    cmd_str[0] += '{} '.format(action.option_strings[0])
                    return
                else:
                    # value is not True so we default to false, which means don't include the flag
                    return

            # was the argument a flag?
            if action.option_strings:
                cmd_str[0] += '{} '.format(action.option_strings[0])

            is_remainder_arg = action.dest == self._remainder_arg

            if isinstance(value, List) or isinstance(value, tuple):
                for item in value:
                    item = str(item).strip()
                    if not is_remainder_arg and is_potential_flag(item, self._parser):
                        raise ValueError('{} appears to be a flag and should be supplied as a keyword argument '
                                         'to the function.'.format(item))
                    item = quote_string_if_needed(item)
                    cmd_str[0] += '{} '.format(item)

                # If this is a flag parameter that can accept a variable number of arguments and we have not
                # reached the max number, add a list completion suffix to tell argparse to move to the next
                # parameter
                if action.option_strings and isinstance(action, _RangeAction) and action.nargs_max is not None and \
                        action.nargs_max > len(value):
                    cmd_str[0] += '{0}{0} '.format(self._parser.prefix_chars[0])

            else:
                value = str(value).strip()
                if not is_remainder_arg and is_potential_flag(value, self._parser):
                    raise ValueError('{} appears to be a flag and should be supplied as a keyword argument '
                                     'to the function.'.format(value))
                value = quote_string_if_needed(value)
                cmd_str[0] += '{} '.format(value)

                # If this is a flag parameter that can accept a variable number of arguments and we have not
                # reached the max number, add a list completion suffix to tell argparse to move to the next
                # parameter
                if action.option_strings and isinstance(action, _RangeAction) and action.nargs_max is not None and \
                        action.nargs_max > 1:
                    cmd_str[0] += '{0}{0} '.format(self._parser.prefix_chars[0])

        def process_action(action):
            if isinstance(action, argparse._SubParsersAction):
                cmd_str[0] += '{} '.format(self._args[action.dest])
                traverse_parser(action.choices[self._args[action.dest]])
            elif isinstance(action, argparse._AppendAction):
                if isinstance(self._args[action.dest], list) or isinstance(self._args[action.dest], tuple):
                    for values in self._args[action.dest]:
                        process_argument(action, values)
                else:
                    process_argument(action, self._args[action.dest])
            else:
                process_argument(action, self._args[action.dest])

        def traverse_parser(parser):
            # first process optional flag arguments
            for action in parser._actions:
                if action.dest in self._args and action.dest in self._flag_args and action.dest != self._remainder_arg:
                    process_action(action)
            # next process positional arguments
            for action in parser._actions:
                if action.dest in self._args and action.dest not in self._flag_args and \
                        action.dest != self._remainder_arg:
                    process_action(action)
            # Keep remainder argument last
            for action in parser._actions:
                if action.dest in self._args and action.dest == self._remainder_arg:
                    process_action(action)

        traverse_parser(self._parser)

        return _exec_cmd(self._cmd2_app, functools.partial(func, cmd_str[0]), self._echo)


class PyscriptBridge(object):
    """Preserves the legacy 'cmd' interface for pyscript while also providing a new python API wrapper for
    application commands."""
    def __init__(self, cmd2_app):
        self._cmd2_app = cmd2_app
        self._last_result = None
        self.cmd_echo = False

    def __getattr__(self, item: str):
        """
        Provide functionality to call application commands as a method of PyscriptBridge
        ex: app.help()
        """
        func = self._cmd2_app.cmd_func(item)

        if func:
            if hasattr(func, 'argparser'):
                # Command uses argparse, return an object that can traverse the argparse subcommands and arguments
                return ArgparseFunctor(self.cmd_echo, self._cmd2_app, item, getattr(func, 'argparser'))
            else:
                # Command doesn't use argparse, we will accept parameters in the form of a command string
                def wrap_func(args=''):
                    return _exec_cmd(self._cmd2_app, functools.partial(func, args), self.cmd_echo)

                return wrap_func
        else:
            # item does not refer to a command
            raise AttributeError("'{}' object has no attribute '{}'".format(self._cmd2_app.pyscript_name, item))

    def __dir__(self):
        """Return a custom set of attribute names"""
        attributes = self._cmd2_app.get_all_commands()
        attributes.insert(0, 'cmd_echo')
        return attributes

    def __call__(self, args: str, echo: Optional[bool]=None) -> CommandResult:
        """
        Provide functionality to call application commands by calling PyscriptBridge
        ex: app('help')
        :param args: The string being passed to the command
        :param echo: If True, output will be echoed while the command runs
                     This temporarily overrides the value of self.cmd_echo
        """
        if echo is None:
            echo = self.cmd_echo

        return _exec_cmd(self._cmd2_app,
                         functools.partial(self._cmd2_app.onecmd_plus_hooks, args + '\n'),
                         echo)
