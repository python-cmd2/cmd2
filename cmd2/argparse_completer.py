# coding=utf-8
# flake8: noqa C901
# NOTE: Ignoreing flake8 cyclomatic complexity in this file because the complexity due to copy-and-paste overrides from
#       argparse
"""
AutoCompleter interprets the argparse.ArgumentParser internals to automatically
generate the completion options for each argument.

How to supply completion options for each argument:
    argparse Choices
    - pass a list of values to the choices parameter of an argparse argument.
      ex: parser.add_argument('-o', '--options', dest='options', choices=['An Option', 'SomeOtherOption'])

    arg_choices dictionary lookup
        arg_choices is a dict() mapping from argument name to one of 3 possible values:
          ex:
            parser = argparse.ArgumentParser()
            parser.add_argument('-o', '--options', dest='options')
            choices = {}
            mycompleter = AutoCompleter(parser, cmd2_app, completer, 1, choices)

        - static list - provide a static list for each argument name
          ex:
            choices['options'] = ['An Option', 'SomeOtherOption']

        - choices function - provide a function that returns a list for each argument name
          ex:
            def generate_choices():
                return ['An Option', 'SomeOtherOption']
            choices['options'] = generate_choices

        - custom completer function - provide a completer function that will return the list
            of completion arguments
          ex 1:
            def my_completer(text: str, line: str, begidx: int, endidx:int):
                my_choices = [...]
                return my_choices
            choices['options'] = (my_completer)
          ex 2:
            def my_completer(text: str, line: str, begidx: int, endidx:int, extra_param: str, another: int):
                my_choices = [...]
                return my_choices
            completer_params = {'extra_param': 'my extra', 'another': 5}
            choices['options'] = (my_completer, completer_params)

How to supply completion choice lists or functions for sub-commands:
    subcmd_args_lookup is used to supply a unique pair of arg_choices and subcmd_args_lookup
    for each sub-command in an argparser subparser group.
    This requires your subparser group to be named with the dest parameter
        ex:
            parser = ArgumentParser()
            subparsers = parser.add_subparsers(title='Actions', dest='action')

    subcmd_args_lookup maps a named subparser group to a subcommand group dictionary
    The subcommand group dictionary maps subcommand names to tuple(arg_choices, subcmd_args_lookup)

    For more details of this more complex approach see tab_autocompletion.py in the examples

Copyright 2018 Eric Lin <anselor@gmail.com>
Released under MIT license, see LICENSE file
"""

import argparse
import os
import re as _re
import sys

# imports copied from argparse to support our customized argparse functions
from argparse import ZERO_OR_MORE, ONE_OR_MORE, ArgumentError, _, _get_action_name, SUPPRESS
from typing import List, Dict, Tuple, Callable, Union

from colorama import Fore

from .rl_utils import rl_force_redisplay
from .utils import ansi_safe_wcswidth

# attribute that can optionally added to an argparse argument (called an Action) to
# define the completion choices for the argument. You may provide a Collection or a Function.
ACTION_ARG_CHOICES = 'arg_choices'
ACTION_SUPPRESS_HINT = 'suppress_hint'
ACTION_DESCRIPTIVE_COMPLETION_HEADER = 'desc_header'


class CompletionItem(str):
    """
    Completion item with descriptive text attached

    Returning this instead of a regular string for completion results will signal the
    autocompleter to output the completions results in a table of completion tokens
    with descriptions instead of just a table of tokens.

    For example, you'd see this:
        TOKEN          Description
        MY_TOKEN       Info about my token
        SOME_TOKEN     Info about some token
        YET_ANOTHER    Yet more info

    Instead of this:
        TOKEN_ID   SOME_TOKEN   YET_ANOTHER

    This is especially useful if you want to complete ID numbers in a more
    user-friendly manner. For example, you can provide this:

        ITEM_ID     Item Name
        1           My item
        2           Another item
        3           Yet another item

    Instead of this:
        1     2     3
    """
    def __new__(cls, o, desc='', *args, **kwargs) -> str:
        return str.__new__(cls, o, *args, **kwargs)

    # noinspection PyMissingConstructor,PyUnusedLocal
    def __init__(self, o, desc='', *args, **kwargs) -> None:
        self.description = desc


class _RangeAction(object):
    def __init__(self, nargs: Union[int, str, Tuple[int, int], None]) -> None:
        self.nargs_min = None
        self.nargs_max = None

        # pre-process special ranged nargs
        if isinstance(nargs, tuple):
            if len(nargs) != 2 or not isinstance(nargs[0], int) or not isinstance(nargs[1], int):
                raise ValueError('Ranged values for nargs must be a tuple of 2 integers')
            if nargs[0] >= nargs[1]:
                raise ValueError('Invalid nargs range. The first value must be less than the second')
            if nargs[0] < 0:
                raise ValueError('Negative numbers are invalid for nargs range.')
            narg_range = nargs
            self.nargs_min = nargs[0]
            self.nargs_max = nargs[1]
            if narg_range[0] == 0:
                if narg_range[1] > 1:
                    self.nargs_adjusted = '*'
                else:
                    # this shouldn't use a range tuple, but yet here we are
                    self.nargs_adjusted = '?'
            else:
                self.nargs_adjusted = '+'
        else:
            self.nargs_adjusted = nargs


# noinspection PyShadowingBuiltins,PyShadowingBuiltins
class _StoreRangeAction(argparse._StoreAction, _RangeAction):
    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None) -> None:

        _RangeAction.__init__(self, nargs)

        argparse._StoreAction.__init__(self,
                                       option_strings=option_strings,
                                       dest=dest,
                                       nargs=self.nargs_adjusted,
                                       const=const,
                                       default=default,
                                       type=type,
                                       choices=choices,
                                       required=required,
                                       help=help,
                                       metavar=metavar)


# noinspection PyShadowingBuiltins,PyShadowingBuiltins
class _AppendRangeAction(argparse._AppendAction, _RangeAction):
    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None) -> None:

        _RangeAction.__init__(self, nargs)

        argparse._AppendAction.__init__(self,
                                        option_strings=option_strings,
                                        dest=dest,
                                        nargs=self.nargs_adjusted,
                                        const=const,
                                        default=default,
                                        type=type,
                                        choices=choices,
                                        required=required,
                                        help=help,
                                        metavar=metavar)


def register_custom_actions(parser: argparse.ArgumentParser) -> None:
    """Register custom argument action types"""
    parser.register('action', None, _StoreRangeAction)
    parser.register('action', 'store', _StoreRangeAction)
    parser.register('action', 'append', _AppendRangeAction)


def is_potential_flag(token: str, parser: argparse.ArgumentParser) -> bool:
    """Determine if a token looks like a potential flag. Based on argparse._parse_optional()."""
    # if it's an empty string, it was meant to be a positional
    if not token:
        return False

    # if it doesn't start with a prefix, it was meant to be positional
    if not token[0] in parser.prefix_chars:
        return False

    # if it's just a single character, it was meant to be positional
    if len(token) == 1:
        return False

    # if it looks like a negative number, it was meant to be positional
    # unless there are negative-number-like options
    if parser._negative_number_matcher.match(token):
        if not parser._has_negative_number_optionals:
            return False

    # if it contains a space, it was meant to be a positional
    if ' ' in token:
        return False

    # Looks like a flag
    return True


class AutoCompleter(object):
    """Automatically command line tab completion based on argparse parameters"""

    class _ArgumentState(object):
        def __init__(self) -> None:
            self.min = None
            self.max = None
            self.count = 0
            self.needed = False
            self.variable = False

        def reset(self) -> None:
            """reset tracking values"""
            self.min = None
            self.max = None
            self.count = 0
            self.needed = False
            self.variable = False

    def __init__(self,
                 parser: argparse.ArgumentParser,
                 cmd2_app,
                 token_start_index: int = 1,
                 arg_choices: Dict[str, Union[List, Tuple, Callable]] = None,
                 subcmd_args_lookup: dict = None,
                 tab_for_arg_help: bool = True) -> None:
        """
        Create an AutoCompleter

        :param parser: ArgumentParser instance
        :param cmd2_app: reference to the Cmd2 application. Enables argparse argument completion with class methods
        :param token_start_index: index of the token to start parsing at
        :param arg_choices: dictionary mapping from argparse argument 'dest' name to list of choices
        :param subcmd_args_lookup: mapping a sub-command group name to a tuple to fill the child\
        AutoCompleter's arg_choices and subcmd_args_lookup parameters
        :param tab_for_arg_help: Enable of disable argument help when there's no completion result
        """
        if not subcmd_args_lookup:
            subcmd_args_lookup = {}
            forward_arg_choices = True
        else:
            forward_arg_choices = False
        self._parser = parser
        self._cmd2_app = cmd2_app
        self._arg_choices = arg_choices.copy() if arg_choices is not None else {}
        self._token_start_index = token_start_index
        self._tab_for_arg_help = tab_for_arg_help

        self._flags = []  # all flags in this command
        self._flags_without_args = []  # all flags that don't take arguments
        self._flag_to_action = {}  # maps flags to the argparse action object
        self._positional_actions = []  # argument names for positional arguments (by position index)
        # maps action name to sub-command autocompleter:
        #   action_name -> dict(sub_command -> completer)
        self._positional_completers = {}

        # Start digging through the argparse structures.
        #   _actions is the top level container of parameter definitions
        for action in self._parser._actions:
            # if there are choices defined, record them in the arguments dictionary
            if action.choices is not None:
                self._arg_choices[action.dest] = action.choices
            # if completion choices are tagged on the action, record them
            elif hasattr(action, ACTION_ARG_CHOICES):
                action_arg_choices = getattr(action, ACTION_ARG_CHOICES)
                self._arg_choices[action.dest] = action_arg_choices

            # if the parameter is flag based, it will have option_strings
            if action.option_strings:
                # record each option flag
                for option in action.option_strings:
                    self._flags.append(option)
                    self._flag_to_action[option] = action
                    if action.nargs == 0:
                        self._flags_without_args.append(option)
            else:
                self._positional_actions.append(action)

                if isinstance(action, argparse._SubParsersAction):
                    sub_completers = {}
                    sub_commands = []
                    args_for_action = subcmd_args_lookup[action.dest]\
                        if action.dest in subcmd_args_lookup else {}
                    for subcmd in action.choices:
                        (subcmd_args, subcmd_lookup) = args_for_action[subcmd] if \
                            subcmd in args_for_action else \
                            (arg_choices, subcmd_args_lookup) if forward_arg_choices else ({}, {})
                        subcmd_start = token_start_index + len(self._positional_actions)
                        sub_completers[subcmd] = AutoCompleter(action.choices[subcmd],
                                                               cmd2_app,
                                                               token_start_index=subcmd_start,
                                                               arg_choices=subcmd_args,
                                                               subcmd_args_lookup=subcmd_lookup,
                                                               tab_for_arg_help=tab_for_arg_help)
                        sub_commands.append(subcmd)
                    self._positional_completers[action.dest] = sub_completers
                    self._arg_choices[action.dest] = sub_commands

    def complete_command(self, tokens: List[str], text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Complete the command using the argparse metadata and provided argument dictionary"""
        # Count which positional argument index we're at now. Loop through all tokens on the command line so far
        # Skip any flags or flag parameter tokens
        next_pos_arg_index = 0

        # This gets set to True when flags will no longer be processed as argparse flags
        # That can happen when -- is used or an argument with nargs=argparse.REMAINDER is used
        skip_remaining_flags = False

        pos_arg = AutoCompleter._ArgumentState()
        pos_action = None

        flag_arg = AutoCompleter._ArgumentState()
        flag_action = None

        # dict is used because object wrapper is necessary to allow inner functions to modify outer variables
        remainder = {'arg': None, 'action': None}

        matched_flags = []
        current_is_positional = False
        consumed_arg_values = {}  # dict(arg_name -> [values, ...])

        # the following are nested functions that have full access to all variables in the parent
        # function including variables declared and updated after this function.  Variable values
        # are current at the point the nested functions are invoked (as in, they do not receive a
        # snapshot of these values, they directly access the current state of variables in the
        # parent function)

        def consume_flag_argument() -> None:
            """Consuming token as a flag argument"""
            # we're consuming flag arguments
            # if the token does not look like a new flag, then count towards flag arguments
            if not is_potential_flag(token, self._parser) and flag_action is not None:
                flag_arg.count += 1

                # does this complete a option item for the flag
                arg_choices = self._resolve_choices_for_arg(flag_action)
                # if the current token matches the current position's autocomplete argument list,
                # track that we've used it already.  Unless this is the current token, then keep it.
                if not is_last_token and token in arg_choices:
                    consumed_arg_values.setdefault(flag_action.dest, [])
                    consumed_arg_values[flag_action.dest].append(token)

        def consume_positional_argument() -> None:
            """Consuming token as positional argument"""
            pos_arg.count += 1

            # does this complete a option item for the flag
            arg_choices = self._resolve_choices_for_arg(pos_action)
            # if the current token matches the current position's autocomplete argument list,
            # track that we've used it already.  Unless this is the current token, then keep it.
            if not is_last_token and token in arg_choices:
                consumed_arg_values.setdefault(pos_action.dest, [])
                consumed_arg_values[pos_action.dest].append(token)

        def process_action_nargs(action: argparse.Action, arg_state: AutoCompleter._ArgumentState) -> None:
            """Process the current argparse Action and initialize the ArgumentState object used
            to track what arguments we have processed for this action"""
            if isinstance(action, _RangeAction):
                arg_state.min = action.nargs_min
                arg_state.max = action.nargs_max
                arg_state.variable = True
            if arg_state.min is None or arg_state.max is None:
                if action.nargs is None:
                    arg_state.min = 1
                    arg_state.max = 1
                elif action.nargs == '+':
                    arg_state.min = 1
                    arg_state.max = float('inf')
                    arg_state.variable = True
                elif action.nargs == '*' or action.nargs == argparse.REMAINDER:
                    arg_state.min = 0
                    arg_state.max = float('inf')
                    arg_state.variable = True
                    if action.nargs == argparse.REMAINDER:
                        remainder['action'] = action
                        remainder['arg'] = arg_state
                elif action.nargs == '?':
                    arg_state.min = 0
                    arg_state.max = 1
                    arg_state.variable = True
                else:
                    arg_state.min = action.nargs
                    arg_state.max = action.nargs

        # This next block of processing tries to parse all parameters before the last parameter.
        # We're trying to determine what specific argument the current cursor positition should be
        # matched with. When we finish parsing all of the arguments, we can determine whether the
        # last token is a positional or flag argument and which specific argument it is.
        #
        # We're also trying to save every flag that has been used as well as every value that
        # has been used for a positional or flag parameter.  By saving this information we can exclude
        # it from the completion results we generate for the last token. For example, single-use flag
        # arguments will be hidden from the list of available flags. Also, arguments with a
        # defined list of possible values will exclude values that have already been used.

        # notes when the last token has been reached
        is_last_token = False

        for idx, token in enumerate(tokens):
            is_last_token = idx >= len(tokens) - 1

            # Only start at the start token index
            if idx >= self._token_start_index:

                # If a remainder action is found, force all future tokens to go to that
                if remainder['arg'] is not None:
                    if remainder['action'] == pos_action:
                        consume_positional_argument()
                        continue
                    elif remainder['action'] == flag_action:
                        consume_flag_argument()
                        continue

                current_is_positional = False
                # Are we consuming flag arguments?
                if not flag_arg.needed:

                    if not skip_remaining_flags:
                        # Special case when each of the following is true:
                        #   - We're not in the middle of consuming flag arguments
                        #   - The current positional argument count has hit the max count
                        #   - The next positional argument is a REMAINDER argument
                        # Argparse will now treat all future tokens as arguments to the positional including tokens that
                        # look like flags so the completer should skip any flag related processing once this happens
                        if (pos_action is not None) and pos_arg.count >= pos_arg.max and \
                                next_pos_arg_index < len(self._positional_actions) and \
                                self._positional_actions[next_pos_arg_index].nargs == argparse.REMAINDER:
                            skip_remaining_flags = True

                    # At this point we're no longer consuming flag arguments. Is the current argument a potential flag?
                    if is_potential_flag(token, self._parser) and not skip_remaining_flags:
                        # reset some tracking values
                        flag_arg.reset()
                        # don't reset positional tracking because flags can be interspersed anywhere between positionals
                        flag_action = None

                        if token == '--':
                            if is_last_token:
                                # Exit loop and see if -- can be completed into a flag
                                break
                            else:
                                # In argparse, all args after -- are non-flags
                                skip_remaining_flags = True

                        # does the token fully match a known flag?
                        if token in self._flag_to_action:
                            flag_action = self._flag_to_action[token]
                        elif hasattr(self._parser, 'allow_abbrev') and self._parser.allow_abbrev:
                            candidates_flags = [flag for flag in self._flag_to_action if flag.startswith(token)]
                            if len(candidates_flags) == 1:
                                flag_action = self._flag_to_action[candidates_flags[0]]

                        if flag_action is not None:
                            # resolve argument counts
                            process_action_nargs(flag_action, flag_arg)
                            if not is_last_token and not isinstance(flag_action, argparse._AppendAction):
                                matched_flags.extend(flag_action.option_strings)

                    # current token isn't a potential flag
                    #   - does the last flag accept variable arguments?
                    #   - have we reached the max arg count for the flag?
                    elif not flag_arg.variable or flag_arg.count >= flag_arg.max:
                        # previous flag doesn't accept variable arguments, count this as a positional argument

                        # reset flag tracking variables
                        flag_arg.reset()
                        flag_action = None
                        current_is_positional = True

                        if len(token) > 0 and pos_action is not None and pos_arg.count < pos_arg.max:
                            # we have positional action match and we haven't reached the max arg count, consume
                            # the positional argument and move on.
                            consume_positional_argument()
                        elif pos_action is None or pos_arg.count >= pos_arg.max:
                            # if we don't have a current positional action or we've reached the max count for the action
                            # close out the current positional argument state and set up for the next one
                            pos_index = next_pos_arg_index
                            next_pos_arg_index += 1
                            pos_arg.reset()
                            pos_action = None

                            # are we at a sub-command? If so, forward to the matching completer
                            if pos_index < len(self._positional_actions):
                                action = self._positional_actions[pos_index]
                                pos_name = action.dest
                                if pos_name in self._positional_completers:
                                    sub_completers = self._positional_completers[pos_name]
                                    if token in sub_completers:
                                        return sub_completers[token].complete_command(tokens, text, line,
                                                                                      begidx, endidx)
                                pos_action = action
                                process_action_nargs(pos_action, pos_arg)
                                consume_positional_argument()

                        elif not is_last_token and pos_arg.max is not None:
                            pos_action = None
                            pos_arg.reset()

                    else:
                        consume_flag_argument()

                else:
                    consume_flag_argument()

                if remainder['arg'] is not None:
                    skip_remaining_flags = True

                # don't reset this if we're on the last token - this allows completion to occur on the current token
                elif not is_last_token and flag_arg.min is not None:
                    flag_arg.needed = flag_arg.count < flag_arg.min

        # Here we're done parsing all of the prior arguments. We know what the next argument is.

        completion_results = []

        # if we don't have a flag to populate with arguments and the last token starts with
        # a flag prefix then we'll complete the list of flag options
        if not flag_arg.needed and len(tokens[-1]) > 0 and tokens[-1][0] in self._parser.prefix_chars and \
                not skip_remaining_flags:
            return self._cmd2_app.basic_complete(text, line, begidx, endidx,
                                                 [flag for flag in self._flags if flag not in matched_flags])
        # we're not at a positional argument, see if we're in a flag argument
        elif not current_is_positional:
            if flag_action is not None:
                consumed = consumed_arg_values[flag_action.dest]\
                    if flag_action.dest in consumed_arg_values else []
                # current_items.extend(self._resolve_choices_for_arg(flag_action, consumed))
                completion_results = self._complete_for_arg(flag_action, text, line, begidx, endidx, consumed)
                if not completion_results:
                    self._print_action_help(flag_action)
                elif len(completion_results) > 1:
                    completion_results = self._format_completions(flag_action, completion_results)

        # ok, we're not a flag, see if there's a positional argument to complete
        else:
            if pos_action is not None:
                pos_name = pos_action.dest
                consumed = consumed_arg_values[pos_name] if pos_name in consumed_arg_values else []
                completion_results = self._complete_for_arg(pos_action, text, line, begidx, endidx, consumed)
                if not completion_results:
                    self._print_action_help(pos_action)
                elif len(completion_results) > 1:
                    completion_results = self._format_completions(pos_action, completion_results)

        return completion_results

    def _format_completions(self, action, completions: List[Union[str, CompletionItem]]) -> List[str]:
        if completions and len(completions) > 1 and isinstance(completions[0], CompletionItem):

            # If the user has not already sorted the CompletionItems, then sort them before appending the descriptions
            if not self._cmd2_app.matches_sorted:
                completions.sort(key=self._cmd2_app.matches_sort_key)
                self._cmd2_app.matches_sorted = True

            token_width = ansi_safe_wcswidth(action.dest)
            completions_with_desc = []

            for item in completions:
                item_width = ansi_safe_wcswidth(item)
                if item_width > token_width:
                    token_width = item_width

            term_size = os.get_terminal_size()
            fill_width = int(term_size.columns * .6) - (token_width + 2)
            for item in completions:
                entry = '{: <{token_width}}{: <{fill_width}}'.format(item, item.description,
                                                                     token_width=token_width + 2,
                                                                     fill_width=fill_width)
                completions_with_desc.append(entry)

            try:
                desc_header = action.desc_header
            except AttributeError:
                desc_header = 'Description'
            header = '\n{: <{token_width}}{}'.format(action.dest.upper(), desc_header, token_width=token_width + 2)

            self._cmd2_app.completion_header = header
            self._cmd2_app.display_matches = completions_with_desc

        return completions

    def complete_command_help(self, tokens: List[str], text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Supports the completion of sub-commands for commands through the cmd2 help command."""
        for idx, token in enumerate(tokens):
            if idx >= self._token_start_index:
                if self._positional_completers:
                    # For now argparse only allows 1 sub-command group per level
                    # so this will only loop once.
                    for completers in self._positional_completers.values():
                        if token in completers:
                            return completers[token].complete_command_help(tokens, text, line, begidx, endidx)
                        else:
                            return self._cmd2_app.basic_complete(text, line, begidx, endidx, completers.keys())
        return []

    def format_help(self, tokens: List[str]) -> str:
        """Supports the completion of sub-commands for commands through the cmd2 help command."""
        for idx, token in enumerate(tokens):
            if idx >= self._token_start_index:
                if self._positional_completers:
                    # For now argparse only allows 1 sub-command group per level
                    # so this will only loop once.
                    for completers in self._positional_completers.values():
                        if token in completers:
                            return completers[token].format_help(tokens)
        return self._parser.format_help()

    def _complete_for_arg(self, action: argparse.Action,
                          text: str,
                          line: str,
                          begidx: int,
                          endidx: int,
                          used_values=()) -> List[str]:
        if action.dest in self._arg_choices:
            arg_choices = self._arg_choices[action.dest]

            # if arg_choices is a tuple
            #   Let's see if it's a custom completion function.  If it is, return what it provides
            # To do this, we make sure the first element is either a callable
            #   or it's the name of a callable in the application
            if isinstance(arg_choices, tuple) and len(arg_choices) > 0 and \
                    (callable(arg_choices[0]) or
                         (isinstance(arg_choices[0], str) and hasattr(self._cmd2_app, arg_choices[0]) and
                          callable(getattr(self._cmd2_app, arg_choices[0]))
                          )
                     ):

                if callable(arg_choices[0]):
                    completer = arg_choices[0]
                elif isinstance(arg_choices[0], str) and callable(getattr(self._cmd2_app, arg_choices[0])):
                    completer = getattr(self._cmd2_app, arg_choices[0])

                # extract the positional and keyword arguments from the tuple
                list_args = None
                kw_args = None
                for index in range(1, len(arg_choices)):
                    if isinstance(arg_choices[index], list) or isinstance(arg_choices[index], tuple):
                        list_args = arg_choices[index]
                    elif isinstance(arg_choices[index], dict):
                        kw_args = arg_choices[index]
                try:
                    # call the provided function differently depending on the provided positional and keyword arguments
                    if list_args is not None and kw_args is not None:
                        return completer(text, line, begidx, endidx, *list_args, **kw_args)
                    elif list_args is not None:
                        return completer(text, line, begidx, endidx, *list_args)
                    elif kw_args is not None:
                        return completer(text, line, begidx, endidx, **kw_args)
                    else:
                        return completer(text, line, begidx, endidx)
                except TypeError:
                    # assume this is due to an incorrect function signature, return nothing.
                    return []
            else:
                return self._cmd2_app.basic_complete(text, line, begidx, endidx,
                                                     self._resolve_choices_for_arg(action, used_values))

        return []

    def _resolve_choices_for_arg(self, action: argparse.Action, used_values=()) -> List[str]:
        if action.dest in self._arg_choices:
            args = self._arg_choices[action.dest]

            # is the argument a string? If so, see if we can find an attribute in the
            # application matching the string.
            if isinstance(args, str):
                try:
                    args = getattr(self._cmd2_app, args)
                except AttributeError:
                    # Couldn't find anything matching the name
                    return []

            # is the provided argument a callable. If so, call it
            if callable(args):
                try:
                    try:
                        args = args(self._cmd2_app)
                    except TypeError:
                        args = args()
                except TypeError:
                    return []

            try:
                iter(args)
            except TypeError:
                pass
            else:
                # filter out arguments we already used
                args = [arg for arg in args if arg not in used_values]

                if len(args) > 0:
                    return args

        return []

    def _print_action_help(self, action: argparse.Action) -> None:
        # is parameter hinting disabled globally?
        if not self._tab_for_arg_help:
            return

        # is parameter hinting disabled for this parameter?
        try:
            suppress_hint = getattr(action, ACTION_SUPPRESS_HINT)
        except AttributeError:
            pass
        else:
            if suppress_hint:
                return

        if action.option_strings:
            flags = ', '.join(action.option_strings)
            param = ''
            if action.nargs is None or action.nargs != 0:
                param += ' ' + str(action.dest).upper()

            prefix = '{}{}'.format(flags, param)
        else:
            if action.dest != SUPPRESS:
                prefix = '{}'.format(str(action.dest).upper())
            else:
                prefix = ''

        if action.help is None:
            help_text = ''
        else:
            help_text = action.help

        # is there anything to print for this parameter?
        if not prefix and not help_text:
            return

        prefix = '  {0: <{width}}    '.format(prefix, width=20)
        pref_len = len(prefix)
        help_lines = help_text.splitlines()

        if len(help_lines) == 1:
            print('\nHint:\n{}{}\n'.format(prefix, help_lines[0]))
        else:
            out_str = '\n{}'.format(prefix)
            out_str += '\n{0: <{width}}'.format('', width=pref_len).join(help_lines)
            print('\nHint:' + out_str + '\n')

        # Redraw prompt and input line
        rl_force_redisplay()


###############################################################################
# Unless otherwise noted, everything below this point are copied from Python's
# argparse implementation with minor tweaks to adjust output.
# Changes are noted if it's buried in a block of copied code. Otherwise the
# function will check for a special case and fall back to the parent function
###############################################################################


# noinspection PyCompatibility,PyShadowingBuiltins,PyShadowingBuiltins
class ACHelpFormatter(argparse.RawTextHelpFormatter):
    """Custom help formatter to configure ordering of help text"""

    def _format_usage(self, usage, actions, groups, prefix) -> str:
        if prefix is None:
            prefix = _('Usage: ')

        # if usage is specified, use that
        if usage is not None:
            usage %= dict(prog=self._prog)

        # if no optionals or positionals are available, usage is just prog
        elif usage is None and not actions:
            usage = '%(prog)s' % dict(prog=self._prog)

        # if optionals and positionals are available, calculate usage
        elif usage is None:
            prog = '%(prog)s' % dict(prog=self._prog)

            # split optionals from positionals
            optionals = []
            positionals = []
            # Begin cmd2 customization (separates required and optional, applies to all changes in this function)
            required_options = []
            for action in actions:
                if action.option_strings:
                    if action.required:
                        required_options.append(action)
                    else:
                        optionals.append(action)
                else:
                    positionals.append(action)
            # End cmd2 customization

            # build full usage string
            format = self._format_actions_usage
            action_usage = format(required_options + optionals + positionals, groups)
            usage = ' '.join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:

                # Begin cmd2 customization

                # break usage into wrappable parts
                part_regexp = r'\(.*?\)+|\[.*?\]+|\S+'
                req_usage = format(required_options, groups)
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
                req_parts = _re.findall(part_regexp, req_usage)
                opt_parts = _re.findall(part_regexp, opt_usage)
                pos_parts = _re.findall(part_regexp, pos_usage)
                assert ' '.join(req_parts) == req_usage
                assert ' '.join(opt_parts) == opt_usage
                assert ' '.join(pos_parts) == pos_usage

                # End cmd2 customization

                # helper for wrapping lines
                # noinspection PyMissingOrEmptyDocstring,PyShadowingNames
                def get_lines(parts, indent, prefix=None):
                    lines = []
                    line = []
                    if prefix is not None:
                        line_len = len(prefix) - 1
                    else:
                        line_len = len(indent) - 1
                    for part in parts:
                        if line_len + 1 + len(part) > text_width and line:
                            lines.append(indent + ' '.join(line))
                            line = []
                            line_len = len(indent) - 1
                        line.append(part)
                        line_len += len(part) + 1
                    if line:
                        lines.append(indent + ' '.join(line))
                    if prefix is not None:
                        lines[0] = lines[0][len(indent):]
                    return lines

                # if prog is short, follow it with optionals or positionals
                if len(prefix) + len(prog) <= 0.75 * text_width:
                    indent = ' ' * (len(prefix) + len(prog) + 1)
                    # Begin cmd2 customization
                    if req_parts:
                        lines = get_lines([prog] + req_parts, indent, prefix)
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    elif opt_parts:
                        lines = get_lines([prog] + opt_parts, indent, prefix)
                        lines.extend(get_lines(pos_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                    else:
                        lines = [prog]
                    # End cmd2 customization

                # if prog is long, put it on its own line
                else:
                    indent = ' ' * len(prefix)
                    # Begin cmd2 customization
                    parts = req_parts + opt_parts + pos_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(req_parts, indent))
                        lines.extend(get_lines(opt_parts, indent))
                        lines.extend(get_lines(pos_parts, indent))
                    # End cmd2 customization
                    lines = [prog] + lines

                # join lines into usage
                usage = '\n'.join(lines)

        # prefix with 'usage:'
        return '%s%s\n\n' % (prefix, usage)

    def _format_action_invocation(self, action) -> str:
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar

        else:
            parts = []

            # if the Optional doesn't take a value, format is:
            #    -s, --long
            if action.nargs == 0:
                parts.extend(action.option_strings)
                return ', '.join(parts)

            # Begin cmd2 customization (less verbose)
            # if the Optional takes a value, format is:
            #    -s, --long ARGS
            else:
                default = self._get_default_metavar_for_optional(action)
                args_string = self._format_args(action, default)

                return ', '.join(action.option_strings) + ' ' + args_string
            # End cmd2 customization

    def _metavar_formatter(self, action, default_metavar) -> Callable:
        if action.metavar is not None:
            result = action.metavar
        elif action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            # Begin cmd2 customization (added space after comma)
            result = '{%s}' % ', '.join(choice_strs)
            # End cmd2 customization
        else:
            result = default_metavar

        # noinspection PyMissingOrEmptyDocstring
        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result, ) * tuple_size
        return format

    def _format_args(self, action, default_metavar) -> str:
        get_metavar = self._metavar_formatter(action, default_metavar)
        # Begin cmd2 customization (less verbose)
        if isinstance(action, _RangeAction) and \
                action.nargs_min is not None and action.nargs_max is not None:
            result = '{}{{{}..{}}}'.format('%s' % get_metavar(1), action.nargs_min, action.nargs_max)
        elif action.nargs == ZERO_OR_MORE:
            result = '[%s [...]]' % get_metavar(1)
        elif action.nargs == ONE_OR_MORE:
            result = '%s [...]' % get_metavar(1)
        # End cmd2 customization
        else:
            result = super()._format_args(action, default_metavar)
        return result

    def format_help(self):
        return super().format_help() + '\n'


# noinspection PyCompatibility
class ACArgumentParser(argparse.ArgumentParser):
    """Custom argparse class to override error method to change default help text."""

    def __init__(self, *args, **kwargs) -> None:
        if 'formatter_class' not in kwargs:
            kwargs['formatter_class'] = ACHelpFormatter

        super().__init__(*args, **kwargs)
        register_custom_actions(self)

        self._custom_error_message = ''

    # Begin cmd2 customization
    def set_custom_message(self, custom_message: str = '') -> None:
        """
        Allows an error message override to the error() function, useful when forcing a
        re-parse of arguments with newly required parameters
        """
        self._custom_error_message = custom_message
    # End cmd2 customization

    def add_subparsers(self, **kwargs):
        """Custom override. Sets a default title if one was not given."""
        if 'title' not in kwargs:
            kwargs['title'] = 'sub-commands'

        return super().add_subparsers(**kwargs)

    def error(self, message: str) -> None:
        """Custom error override. Allows application to control the error being displayed by argparse"""
        if len(self._custom_error_message) > 0:
            message = self._custom_error_message
            self._custom_error_message = ''

        lines = message.split('\n')
        linum = 0
        formatted_message = ''
        for line in lines:
            if linum == 0:
                formatted_message = 'Error: ' + line
            else:
                formatted_message += '\n       ' + line
            linum += 1

        sys.stderr.write(Fore.LIGHTRED_EX + '{}\n\n'.format(formatted_message) + Fore.RESET)
        # sys.stderr.write('{}\n\n'.format(formatted_message))
        self.print_help()
        sys.exit(1)

    def format_help(self) -> str:
        """Copy of format_help() from argparse.ArgumentParser with tweaks to separately display required parameters"""
        formatter = self._get_formatter()

        # usage
        formatter.add_usage(self.usage, self._actions,
                            self._mutually_exclusive_groups)

        # description
        formatter.add_text(self.description)

        # Begin cmd2 customization (separate required and optional arguments)

        # positionals, optionals and user-defined groups
        for action_group in self._action_groups:
            if action_group.title == 'optional arguments':
                # check if the arguments are required, group accordingly
                req_args = []
                opt_args = []
                for action in action_group._group_actions:
                    if action.required:
                        req_args.append(action)
                    else:
                        opt_args.append(action)

                # separately display required arguments
                formatter.start_section('required arguments')
                formatter.add_text(action_group.description)
                formatter.add_arguments(req_args)
                formatter.end_section()

                # now display truly optional arguments
                formatter.start_section(action_group.title)
                formatter.add_text(action_group.description)
                formatter.add_arguments(opt_args)
                formatter.end_section()
            else:
                formatter.start_section(action_group.title)
                formatter.add_text(action_group.description)
                formatter.add_arguments(action_group._group_actions)
                formatter.end_section()

        # End cmd2 customization

        # epilog
        formatter.add_text(self.epilog)

        # determine help from format above
        return formatter.format_help()

    def _get_nargs_pattern(self, action) -> str:
        # Override _get_nargs_pattern behavior to use the nargs ranges provided by AutoCompleter
        if isinstance(action, _RangeAction) and \
                action.nargs_min is not None and action.nargs_max is not None:
            nargs_pattern = '(-*A{{{},{}}}-*)'.format(action.nargs_min, action.nargs_max)

            # if this is an optional action, -- is not allowed
            if action.option_strings:
                nargs_pattern = nargs_pattern.replace('-*', '')
                nargs_pattern = nargs_pattern.replace('-', '')
            return nargs_pattern
        return super(ACArgumentParser, self)._get_nargs_pattern(action)

    def _match_argument(self, action, arg_strings_pattern) -> int:
        # match the pattern for this action to the arg strings
        nargs_pattern = self._get_nargs_pattern(action)
        match = _re.match(nargs_pattern, arg_strings_pattern)

        # raise an exception if we weren't able to find a match
        if match is None:
            if isinstance(action, _RangeAction) and \
                    action.nargs_min is not None and action.nargs_max is not None:
                raise ArgumentError(action,
                                    'Expected between {} and {} arguments'.format(action.nargs_min, action.nargs_max))

        return super(ACArgumentParser, self)._match_argument(action, arg_strings_pattern)

    # This is the official python implementation with a 5 year old patch applied
    # See the comment below describing the patch
    def _parse_known_args(self, arg_strings, namespace) -> Tuple[argparse.Namespace, List[str]]:  # pragma: no cover
        # replace arg strings that are file references
        if self.fromfile_prefix_chars is not None:
            arg_strings = self._read_args_from_files(arg_strings)

        # map all mutually exclusive arguments to the other arguments
        # they can't occur with
        action_conflicts = {}
        for mutex_group in self._mutually_exclusive_groups:
            group_actions = mutex_group._group_actions
            for i, mutex_action in enumerate(mutex_group._group_actions):
                conflicts = action_conflicts.setdefault(mutex_action, [])
                conflicts.extend(group_actions[:i])
                conflicts.extend(group_actions[i + 1:])

        # find all option indices, and determine the arg_string_pattern
        # which has an 'O' if there is an option at an index,
        # an 'A' if there is an argument, or a '-' if there is a '--'
        option_string_indices = {}
        arg_string_pattern_parts = []
        arg_strings_iter = iter(arg_strings)
        for i, arg_string in enumerate(arg_strings_iter):

            # all args after -- are non-options
            if arg_string == '--':
                arg_string_pattern_parts.append('-')
                for cur_string in arg_strings_iter:
                    arg_string_pattern_parts.append('A')

            # otherwise, add the arg to the arg strings
            # and note the index if it was an option
            else:
                option_tuple = self._parse_optional(arg_string)
                if option_tuple is None:
                    pattern = 'A'
                else:
                    option_string_indices[i] = option_tuple
                    pattern = 'O'
                arg_string_pattern_parts.append(pattern)

        # join the pieces together to form the pattern
        arg_strings_pattern = ''.join(arg_string_pattern_parts)

        # converts arg strings to the appropriate and then takes the action
        seen_actions = set()
        seen_non_default_actions = set()

        def take_action(action, argument_strings, option_string=None):
            seen_actions.add(action)
            argument_values = self._get_values(action, argument_strings)

            # error if this argument is not allowed with other previously
            # seen arguments, assuming that actions that use the default
            # value don't really count as "present"
            if argument_values is not action.default:
                seen_non_default_actions.add(action)
                for conflict_action in action_conflicts.get(action, []):
                    if conflict_action in seen_non_default_actions:
                        msg = _('not allowed with argument %s')
                        action_name = _get_action_name(conflict_action)
                        raise ArgumentError(action, msg % action_name)

            # take the action if we didn't receive a SUPPRESS value
            # (e.g. from a default)
            if argument_values is not SUPPRESS:
                action(self, namespace, argument_values, option_string)

        # function to convert arg_strings into an optional action
        def consume_optional(start_index):

            # get the optional identified at this index
            option_tuple = option_string_indices[start_index]
            action, option_string, explicit_arg = option_tuple

            # identify additional optionals in the same arg string
            # (e.g. -xyz is the same as -x -y -z if no args are required)
            match_argument = self._match_argument
            action_tuples = []
            while True:

                # if we found no optional action, skip it
                if action is None:
                    extras.append(arg_strings[start_index])
                    return start_index + 1

                # if there is an explicit argument, try to match the
                # optional's string arguments to only this
                if explicit_arg is not None:
                    arg_count = match_argument(action, 'A')

                    # if the action is a single-dash option and takes no
                    # arguments, try to parse more single-dash options out
                    # of the tail of the option string
                    chars = self.prefix_chars
                    if arg_count == 0 and option_string[1] not in chars:
                        action_tuples.append((action, [], option_string))
                        char = option_string[0]
                        option_string = char + explicit_arg[0]
                        new_explicit_arg = explicit_arg[1:] or None
                        optionals_map = self._option_string_actions
                        if option_string in optionals_map:
                            action = optionals_map[option_string]
                            explicit_arg = new_explicit_arg
                        else:
                            msg = _('ignored explicit argument %r')
                            raise ArgumentError(action, msg % explicit_arg)

                    # if the action expect exactly one argument, we've
                    # successfully matched the option; exit the loop
                    elif arg_count == 1:
                        stop = start_index + 1
                        args = [explicit_arg]
                        action_tuples.append((action, args, option_string))
                        break

                    # error if a double-dash option did not use the
                    # explicit argument
                    else:
                        msg = _('ignored explicit argument %r')
                        raise ArgumentError(action, msg % explicit_arg)

                # if there is no explicit argument, try to match the
                # optional's string arguments with the following strings
                # if successful, exit the loop
                else:
                    start = start_index + 1
                    selected_patterns = arg_strings_pattern[start:]
                    arg_count = match_argument(action, selected_patterns)
                    stop = start + arg_count
                    args = arg_strings[start:stop]
                    action_tuples.append((action, args, option_string))
                    break

            # add the Optional to the list and return the index at which
            # the Optional's string args stopped
            assert action_tuples
            for action, args, option_string in action_tuples:
                take_action(action, args, option_string)
            return stop

        # the list of Positionals left to be parsed; this is modified
        # by consume_positionals()
        positionals = self._get_positional_actions()

        # function to convert arg_strings into positional actions
        def consume_positionals(start_index):
            # match as many Positionals as possible
            match_partial = self._match_arguments_partial
            selected_pattern = arg_strings_pattern[start_index:]
            arg_counts = match_partial(positionals, selected_pattern)

            ####################################################################
            # Applied mixed.patch from https://bugs.python.org/issue15112
            if 'O' in arg_strings_pattern[start_index:]:
                # if there is an optional after this, remove
                # 'empty' positionals from the current match

                while len(arg_counts) > 1 and arg_counts[-1] == 0:
                    arg_counts = arg_counts[:-1]
            ####################################################################

            # slice off the appropriate arg strings for each Positional
            # and add the Positional and its args to the list
            for action, arg_count in zip(positionals, arg_counts):
                args = arg_strings[start_index: start_index + arg_count]
                start_index += arg_count
                take_action(action, args)

            # slice off the Positionals that we just parsed and return the
            # index at which the Positionals' string args stopped
            positionals[:] = positionals[len(arg_counts):]
            return start_index

        # consume Positionals and Optionals alternately, until we have
        # passed the last option string
        extras = []
        start_index = 0
        if option_string_indices:
            max_option_string_index = max(option_string_indices)
        else:
            max_option_string_index = -1
        while start_index <= max_option_string_index:

            # consume any Positionals preceding the next option
            next_option_string_index = min([
                index
                for index in option_string_indices
                if index >= start_index])
            if start_index != next_option_string_index:
                positionals_end_index = consume_positionals(start_index)

                # only try to parse the next optional if we didn't consume
                # the option string during the positionals parsing
                if positionals_end_index > start_index:
                    start_index = positionals_end_index
                    continue
                else:
                    start_index = positionals_end_index

            # if we consumed all the positionals we could and we're not
            # at the index of an option string, there were extra arguments
            if start_index not in option_string_indices:
                strings = arg_strings[start_index:next_option_string_index]
                extras.extend(strings)
                start_index = next_option_string_index

            # consume the next optional and any arguments for it
            start_index = consume_optional(start_index)

        # consume any positionals following the last Optional
        stop_index = consume_positionals(start_index)

        # if we didn't consume all the argument strings, there were extras
        extras.extend(arg_strings[stop_index:])

        # make sure all required actions were present and also convert
        # action defaults which were not given as arguments
        required_actions = []
        for action in self._actions:
            if action not in seen_actions:
                if action.required:
                    required_actions.append(_get_action_name(action))
                else:
                    # Convert action default now instead of doing it before
                    # parsing arguments to avoid calling convert functions
                    # twice (which may fail) if the argument was given, but
                    # only if it was defined already in the namespace
                    if (action.default is not None and
                            isinstance(action.default, str) and
                            hasattr(namespace, action.dest) and
                            action.default is getattr(namespace, action.dest)):
                        setattr(namespace, action.dest,
                                self._get_value(action, action.default))

        if required_actions:
            self.error(_('the following arguments are required: %s') %
                       ', '.join(required_actions))

        # make sure all required groups had one option present
        for group in self._mutually_exclusive_groups:
            if group.required:
                for action in group._group_actions:
                    if action in seen_non_default_actions:
                        break

                # if no actions were used, report the error
                else:
                    names = [_get_action_name(action)
                             for action in group._group_actions
                             if action.help is not SUPPRESS]
                    msg = _('one of the arguments %s is required')
                    self.error(msg % ' '.join(names))

        # return the updated namespace and the extra arguments
        return namespace, extras
