# coding=utf-8
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
            mycompleter = AutoCompleter(parser, completer, 1, choices)

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
from colorama import Fore
import sys
from typing import List, Dict, Tuple, Callable, Union


# imports copied from argparse to support our customized argparse functions
from argparse import ZERO_OR_MORE, ONE_OR_MORE, ArgumentError, _
import re as _re


from .rl_utils import rl_force_redisplay

ACTION_ARG_CHOICES = 'arg_choices'


class _RangeAction(object):
    def __init__(self, nargs: Union[int, str, Tuple[int, int], None]):
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
                 metavar=None):

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
                 metavar=None):

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


def register_custom_actions(parser: argparse.ArgumentParser):
    """Register custom argument action types"""
    parser.register('action', None, _StoreRangeAction)
    parser.register('action', 'store', _StoreRangeAction)
    parser.register('action', 'append', _AppendRangeAction)


class AutoCompleter(object):
    """Automatically command line tab completion based on argparse parameters"""

    class _ArgumentState(object):
        def __init__(self):
            self.min = None
            self.max = None
            self.count = 0
            self.needed = False
            self.variable = False

        def reset(self):
            """reset tracking values"""
            self.min = None
            self.max = None
            self.count = 0
            self.needed = False
            self.variable = False

    def __init__(self,
                 parser: argparse.ArgumentParser,
                 token_start_index: int = 1,
                 arg_choices: Dict[str, Union[List, Tuple, Callable]] = None,
                 subcmd_args_lookup: dict = None,
                 tab_for_arg_help: bool = True):
        """
        Create an AutoCompleter

        :param parser: ArgumentParser instance
        :param token_start_index: index of the token to start parsing at
        :param arg_choices: dictionary mapping from argparse argument 'dest' name to list of choices
        :param subcmd_args_lookup: mapping a sub-command group name to a tuple to fill the child\
        AutoCompleter's arg_choices and subcmd_args_lookup parameters
        """
        if not subcmd_args_lookup:
            subcmd_args_lookup = {}
            forward_arg_choices = True
        else:
            forward_arg_choices = False
        self._parser = parser
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
                        sub_completers[subcmd] = AutoCompleter(action.choices[subcmd], subcmd_start,
                                                               arg_choices=subcmd_args,
                                                               subcmd_args_lookup=subcmd_lookup)
                        sub_commands.append(subcmd)
                    self._positional_completers[action.dest] = sub_completers
                    self._arg_choices[action.dest] = sub_commands

    def complete_command(self, tokens: List[str], text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Complete the command using the argparse metadata and provided argument dictionary"""
        # Count which positional argument index we're at now. Loop through all tokens on the command line so far
        # Skip any flags or flag parameter tokens
        next_pos_arg_index = 0

        pos_arg = AutoCompleter._ArgumentState()
        pos_action = None

        flag_arg = AutoCompleter._ArgumentState()
        flag_action = None

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
            # if this is not empty and is not another potential flag, count towards flag arguments
            if token and token[0] not in self._parser.prefix_chars and flag_action is not None:
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

        is_last_token = False
        for idx, token in enumerate(tokens):
            is_last_token = idx >= len(tokens) - 1
            # Only start at the start token index
            if idx >= self._token_start_index:
                current_is_positional = False
                # Are we consuming flag arguments?
                if not flag_arg.needed:
                    # we're not consuming flag arguments, is the current argument a potential flag?
                    if len(token) > 0 and token[0] in self._parser.prefix_chars and\
                            (is_last_token or (not is_last_token and token != '-')):
                        # reset some tracking values
                        flag_arg.reset()
                        # don't reset positional tracking because flags can be interspersed anywhere between positionals
                        flag_action = None

                        # does the token fully match a known flag?
                        if token in self._flag_to_action:
                            flag_action = self._flag_to_action[token]
                        elif hasattr(self._parser, 'allow_abbrev') and self._parser.allow_abbrev:
                            candidates_flags = [flag for flag in self._flag_to_action if flag.startswith(token)]
                            if len(candidates_flags) == 1:
                                flag_action = self._flag_to_action[candidates_flags[0]]

                        if flag_action is not None:
                            # resolve argument counts
                            self._process_action_nargs(flag_action, flag_arg)
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
                                self._process_action_nargs(pos_action, pos_arg)
                                consume_positional_argument()

                        elif not is_last_token and pos_arg.max is not None:
                            pos_action = None
                            pos_arg.reset()

                    else:
                        consume_flag_argument()

                else:
                    consume_flag_argument()

                # don't reset this if we're on the last token - this allows completion to occur on the current token
                if not is_last_token and flag_arg.min is not None:
                    flag_arg.needed = flag_arg.count < flag_arg.min

        # if we don't have a flag to populate with arguments and the last token starts with
        # a flag prefix then we'll complete the list of flag options
        completion_results = []
        if not flag_arg.needed and len(tokens[-1]) > 0 and tokens[-1][0] in self._parser.prefix_chars:
            return AutoCompleter.basic_complete(text, line, begidx, endidx,
                                                [flag for flag in self._flags if flag not in matched_flags])
        # we're not at a positional argument, see if we're in a flag argument
        elif not current_is_positional:
            # current_items = []
            if flag_action is not None:
                consumed = consumed_arg_values[flag_action.dest]\
                    if flag_action.dest in consumed_arg_values else []
                # current_items.extend(self._resolve_choices_for_arg(flag_action, consumed))
                completion_results = self._complete_for_arg(flag_action, text, line, begidx, endidx, consumed)
                if not completion_results:
                    self._print_action_help(flag_action)

        # ok, we're not a flag, see if there's a positional argument to complete
        else:
            if pos_action is not None:
                pos_name = pos_action.dest
                consumed = consumed_arg_values[pos_name] if pos_name in consumed_arg_values else []
                completion_results = self._complete_for_arg(pos_action, text, line, begidx, endidx, consumed)
                if not completion_results:
                    self._print_action_help(pos_action)

        return completion_results

    def complete_command_help(self, tokens: List[str], text: str, line: str, begidx: int, endidx: int) -> List[str]:
        for idx, token in enumerate(tokens):
            is_last_token = idx > len(tokens) - 1

            if idx >= self._token_start_index:
                if self._positional_completers:
                    # For now argparse only allows 1 sub-command group per level
                    # so this will only loop once.
                    for completers in self._positional_completers.values():
                        if token in completers:
                            return completers[token].complete_command_help(tokens, text, line, begidx, endidx)
                        else:
                            return self.basic_complete(text, line, begidx, endidx, completers.keys())
        return []


    @staticmethod
    def _process_action_nargs(action: argparse.Action, arg_state: _ArgumentState) -> None:
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
            elif action.nargs == '*':
                arg_state.min = 0
                arg_state.max = float('inf')
                arg_state.variable = True
            elif action.nargs == '?':
                arg_state.min = 0
                arg_state.max = 1
                arg_state.variable = True
            else:
                arg_state.min = action.nargs
                arg_state.max = action.nargs

    def _complete_for_arg(self, action: argparse.Action,
                          text: str,
                          line: str,
                          begidx: int,
                          endidx: int,
                          used_values=()) -> List[str]:
        if action.dest in self._arg_choices:
            arg_choices = self._arg_choices[action.dest]

            if isinstance(arg_choices, tuple) and len(arg_choices) > 0 and callable(arg_choices[0]):
                completer = arg_choices[0]
                list_args = None
                kw_args = None
                for index in range(1, len(arg_choices)):
                    if isinstance(arg_choices[index], list) or isinstance(arg_choices[index], tuple):
                        list_args = arg_choices[index]
                    elif isinstance(arg_choices[index], dict):
                        kw_args = arg_choices[index]
                if list_args is not None and kw_args is not None:
                    return completer(text, line, begidx, endidx, *list_args, **kw_args)
                elif list_args is not None:
                    return completer(text, line, begidx, endidx, *list_args)
                elif kw_args is not None:
                    return completer(text, line, begidx, endidx, **kw_args)
                else:
                    return completer(text, line, begidx, endidx)
            else:
                return AutoCompleter.basic_complete(text, line, begidx, endidx,
                                                    self._resolve_choices_for_arg(action, used_values))

        return []

    def _resolve_choices_for_arg(self, action: argparse.Action, used_values=()) -> List[str]:
        if action.dest in self._arg_choices:
            args = self._arg_choices[action.dest]

            if callable(args):
                args = args()

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
        if not self._tab_for_arg_help:
            return
        if action.option_strings:
            flags = ', '.join(action.option_strings)
            param = ''
            if action.nargs is None or action.nargs != 0:
                param += ' ' + str(action.dest).upper()

            prefix = '{}{}'.format(flags, param)
        else:
            prefix = '{}'.format(str(action.dest).upper())

        prefix = '  {0: <{width}}    '.format(prefix, width=20)
        pref_len = len(prefix)
        help_lines = action.help.splitlines()
        if len(help_lines) == 1:
            print('\nHint:\n{}{}\n'.format(prefix, help_lines[0]))
        else:
            out_str = '\n{}'.format(prefix)
            out_str += '\n{0: <{width}}'.format('', width=pref_len).join(help_lines)
            print('\nHint:' + out_str + '\n')

        # Redraw prompt and input line
        rl_force_redisplay()

    # noinspection PyUnusedLocal
    @staticmethod
    def basic_complete(text: str, line: str, begidx: int, endidx: int, match_against: List[str]) -> List[str]:
        """
        Performs tab completion against a list

        :param text: str - the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: str - the current input line with leading whitespace removed
        :param begidx: int - the beginning index of the prefix text
        :param endidx: int - the ending index of the prefix text
        :param match_against: Collection - the list being matched against
        :return: List[str] - a list of possible tab completions
        """
        return [cur_match for cur_match in match_against if cur_match.startswith(text)]


###############################################################################
# Unless otherwise noted, everything below this point are copied from Python's
# argparse implementation with minor tweaks to adjust output.
# Changes are noted if it's buried in a block of copied code. Otherwise the
# function will check for a special case and fall back to the parent function
###############################################################################


class ACHelpFormatter(argparse.HelpFormatter):
    """Custom help formatter to configure ordering of help text"""

    def _format_usage(self, usage, actions, groups, prefix):
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
            action_usage = format(positionals + required_options + optionals, groups)
            usage = ' '.join([s for s in [prog, action_usage] if s])

            # wrap the usage parts if it's too long
            text_width = self._width - self._current_indent
            if len(prefix) + len(usage) > text_width:

                # Begin cmd2 customization

                # break usage into wrappable parts
                part_regexp = r'\(.*?\)+|\[.*?\]+|\S+'
                opt_usage = format(optionals, groups)
                pos_usage = format(positionals, groups)
                req_usage = format(required_options, groups)
                opt_parts = _re.findall(part_regexp, opt_usage)
                pos_parts = _re.findall(part_regexp, pos_usage)
                req_parts = _re.findall(part_regexp, req_usage)
                assert ' '.join(opt_parts) == opt_usage
                assert ' '.join(pos_parts) == pos_usage
                assert ' '.join(req_parts) == req_usage

                # End cmd2 customization

                # helper for wrapping lines
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
                    if opt_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                        lines.extend(get_lines(req_parts, indent))
                        lines.extend(get_lines(opt_parts, indent))
                    elif pos_parts:
                        lines = get_lines([prog] + pos_parts, indent, prefix)
                        lines.extend(get_lines(req_parts, indent))
                    else:
                        lines = [prog]
                    # End cmd2 customization

                # if prog is long, put it on its own line
                else:
                    indent = ' ' * len(prefix)
                    # Begin cmd2 customization
                    parts = pos_parts + req_parts + opt_parts
                    lines = get_lines(parts, indent)
                    if len(lines) > 1:
                        lines = []
                        lines.extend(get_lines(pos_parts, indent))
                        lines.extend(get_lines(req_parts, indent))
                        lines.extend(get_lines(opt_parts, indent))
                    # End cmd2 customization
                    lines = [prog] + lines

                # join lines into usage
                usage = '\n'.join(lines)

        # prefix with 'usage:'
        return '%s%s\n\n' % (prefix, usage)

    def _format_action_invocation(self, action):
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

    def _metavar_formatter(self, action, default_metavar):
        if action.metavar is not None:
            result = action.metavar
        elif action.choices is not None:
            choice_strs = [str(choice) for choice in action.choices]
            # Begin cmd2 customization (added space after comma)
            result = '{%s}' % ', '.join(choice_strs)
            # End cmd2 customization
        else:
            result = default_metavar

        def format(tuple_size):
            if isinstance(result, tuple):
                return result
            else:
                return (result, ) * tuple_size
        return format

    def _format_args(self, action, default_metavar):
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

    def _split_lines(self, text, width):
        return text.splitlines()


class ACArgumentParser(argparse.ArgumentParser):
    """Custom argparse class to override error method to change default help text."""

    def __init__(self, *args, **kwargs):
        if 'formatter_class' not in kwargs:
            kwargs['formatter_class'] = ACHelpFormatter

        super().__init__(*args, **kwargs)
        register_custom_actions(self)

        self._custom_error_message = ''

    # Begin cmd2 customization
    def set_custom_message(self, custom_message=''):
        """
        Allows an error message override to the error() function, useful when forcing a
        re-parse of arguments with newly required parameters
        """
        self._custom_error_message = custom_message
    # End cmd2 customization

    def error(self, message):
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

    def format_help(self):
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

    def _get_nargs_pattern(self, action):
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

    def _match_argument(self, action, arg_strings_pattern):
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
