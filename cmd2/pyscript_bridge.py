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
from typing import List, Tuple, Callable

# Python 3.4 require contextlib2 for temporarily redirecting stderr and stdout
if sys.version_info < (3, 5):
    from contextlib2 import redirect_stdout, redirect_stderr
else:
    from contextlib import redirect_stdout, redirect_stderr

from .argparse_completer import _RangeAction
from .utils import namedtuple_with_defaults


class CommandResult(namedtuple_with_defaults('CmdResult', ['stdout', 'stderr', 'data'])):
    """Encapsulates the results from a command.

    Named tuple attributes
    ----------------------
    stdout: str - Output captured from stdout while this command is executing
    stderr: str - Output captured from stderr while this command is executing. None if no error captured
    data - Data returned by the command.

    NOTE: Named tuples are immutable.  So the contents are there for access, not for modification.
    """
    def __bool__(self):
        """If stderr is None and data is not None the command is considered a success"""
        return not self.stderr and self.data is not None


class CopyStream(object):
    """Copies all data written to a stream"""
    def __init__(self, inner_stream, echo: bool = False):
        self.buffer = ''
        self.inner_stream = inner_stream
        self.echo = echo

    def write(self, s):
        self.buffer += s
        if self.echo:
            self.inner_stream.write(s)

    def read(self):
        raise NotImplementedError

    def clear(self):
        self.buffer = ''

    def __getattr__(self, item: str):
        if item in self.__dict__:
            return self.__dict__[item]
        else:
            return getattr(self.inner_stream, item)


def _exec_cmd(cmd2_app, func: Callable, echo: bool):
    """Helper to encapsulate executing a command and capturing the results"""
    copy_stdout = CopyStream(sys.stdout, echo)
    copy_stderr = CopyStream(sys.stderr, echo)

    copy_cmd_stdout = CopyStream(cmd2_app.stdout, echo)

    cmd2_app._last_result = None

    try:
        cmd2_app.stdout = copy_cmd_stdout
        with redirect_stdout(copy_stdout):
            with redirect_stderr(copy_stderr):
                func()
    finally:
        cmd2_app.stdout = copy_cmd_stdout.inner_stream

    # if stderr is empty, set it to None
    stderr = copy_stderr.buffer if copy_stderr.buffer else None

    outbuf = copy_cmd_stdout.buffer if copy_cmd_stdout.buffer else copy_stdout.buffer
    result = CommandResult(stdout=outbuf, stderr=stderr, data=cmd2_app._last_result)
    return result


class ArgparseFunctor:
    """
    Encapsulates translating python object traversal
    """
    def __init__(self, echo: bool, cmd2_app, command_name: str, parser: argparse.ArgumentParser):
        self._echo = echo
        self._cmd2_app = cmd2_app
        self._command_name = command_name
        self._parser = parser

        # Dictionary mapping command argument name to value
        self._args = {}
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
            if kw not in self._args:  # consumed_kw:
                raise TypeError('{}() got an unexpected keyword argument \'{}\''.format(
                    self.__current_subcommand_parser.prog, kw))

        if has_subcommand:
            return self
        else:
            return self._run()

    def _run(self):
        # look up command function
        func = getattr(self._cmd2_app, 'do_' + self._command_name)

        # reconstruct the cmd2 command from the python call
        cmd_str = ['']

        def process_flag(action, value):
            if isinstance(action, argparse._CountAction):
                if isinstance(value, int):
                    for c in range(value):
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

            if isinstance(value, List) or isinstance(value, tuple):
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
                        if isinstance(self._args[action.dest], list) or isinstance(self._args[action.dest], tuple):
                            for values in self._args[action.dest]:
                                process_flag(action, values)
                        else:
                            process_flag(action, self._args[action.dest])
                    else:
                        process_flag(action, self._args[action.dest])

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
                    return _exec_cmd(self._cmd2_app, functools.partial(func, args), self.cmd_echo)
                return wrap_func
            else:
                # Command does use argparse, return an object that can traverse the argparse subcommands and arguments
                return ArgparseFunctor(self.cmd_echo, self._cmd2_app, item, parser)

        return super().__getattr__(item)

    def __dir__(self):
        """Return a custom set of attribute names to match the available commands"""
        commands = list(self._cmd2_app.get_all_commands())
        commands.insert(0, 'cmd_echo')
        return commands

    def __call__(self, args: str):
        return _exec_cmd(self._cmd2_app, functools.partial(self._cmd2_app.onecmd_plus_hooks, args + '\n'), self.cmd_echo)
