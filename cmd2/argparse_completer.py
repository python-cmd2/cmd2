# coding=utf-8
# flake8: noqa C901
# NOTE: Ignoring flake8 cyclomatic complexity in this file
"""
This module adds tab completion to argparse parsers within cmd2 apps.

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
"""

import argparse
import shutil
from typing import List, Union

from . import cmd2
from . import utils
from .ansi import ansi_safe_wcswidth
from .argparse_custom import ATTR_SUPPRESS_TAB_HINT, ATTR_DESCRIPTIVE_COMPLETION_HEADER, ATTR_NARGS_RANGE
from .argparse_custom import ChoicesCallable, CompletionItem, ATTR_CHOICES_CALLABLE
from .rl_utils import rl_force_redisplay

# If no descriptive header is supplied, then this will be used instead
DEFAULT_DESCRIPTIVE_HEADER = 'Description'


# noinspection PyProtectedMember
def is_potential_flag(token: str, parser: argparse.ArgumentParser) -> bool:
    """Determine if a token looks like a potential flag. Based on argparse._parse_optional()."""
    # if it's an empty string, it was meant to be a positional
    if not token:
        return False

    # if it doesn't start with a prefix, it was meant to be positional
    if not token[0] in parser.prefix_chars:
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


# noinspection PyProtectedMember
class AutoCompleter(object):
    """Automatic command line tab completion based on argparse parameters"""

    class _ArgumentState(object):
        """Keeps state of an argument being parsed"""

        def __init__(self, arg_action: argparse.Action) -> None:
            self.action = arg_action
            self.min = None
            self.max = None
            self.count = 0
            self.needed = False
            self.variable = False
            self.is_remainder = (self.action.nargs == argparse.REMAINDER)

            # Check if nargs is a range
            nargs_range = getattr(self.action, ATTR_NARGS_RANGE, None)
            if nargs_range is not None:
                self.min = nargs_range[0]
                self.max = nargs_range[1]
                self.variable = True

            # Otherwise check against argparse types
            elif self.action.nargs is None:
                self.min = 1
                self.max = 1
            elif self.action.nargs == argparse.ONE_OR_MORE:
                self.min = 1
                self.max = float('inf')
                self.variable = True
            elif self.action.nargs == argparse.ZERO_OR_MORE or self.action.nargs == argparse.REMAINDER:
                self.min = 0
                self.max = float('inf')
                self.variable = True
            elif self.action.nargs == argparse.OPTIONAL:
                self.min = 0
                self.max = 1
                self.variable = True
            else:
                self.min = self.action.nargs
                self.max = self.action.nargs

    def __init__(self, parser: argparse.ArgumentParser, cmd2_app: cmd2.Cmd, *,
                 token_start_index: int = 1) -> None:
        """
        Create an AutoCompleter

        :param parser: ArgumentParser instance
        :param cmd2_app: reference to the Cmd2 application that owns this AutoCompleter
        :param token_start_index: index of the token to start parsing at
        """
        self._parser = parser
        self._cmd2_app = cmd2_app
        self._arg_choices = {}
        self._token_start_index = token_start_index

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

            # otherwise check if a callable provides the choices for this argument
            elif hasattr(action, ATTR_CHOICES_CALLABLE):
                arg_choice_callable = getattr(action, ATTR_CHOICES_CALLABLE)
                self._arg_choices[action.dest] = arg_choice_callable

            # if the parameter is flag based, it will have option_strings
            if action.option_strings:
                # record each option flag
                for option in action.option_strings:
                    self._flags.append(option)
                    self._flag_to_action[option] = action
                    if action.nargs == 0:
                        self._flags_without_args.append(option)

            # Otherwise this is a positional parameter
            else:
                self._positional_actions.append(action)

                if isinstance(action, argparse._SubParsersAction):
                    sub_completers = {}
                    sub_commands = []

                    # Create an AutoCompleter for each subcommand of this command
                    for subcmd in action.choices:

                        subcmd_start = token_start_index + len(self._positional_actions)
                        sub_completers[subcmd] = AutoCompleter(action.choices[subcmd],
                                                               cmd2_app,
                                                               token_start_index=subcmd_start)
                        sub_commands.append(subcmd)

                    self._positional_completers[action.dest] = sub_completers
                    self._arg_choices[action.dest] = sub_commands

    def complete_command(self, tokens: List[str], text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """Complete the command using the argparse metadata and provided argument dictionary"""
        if len(tokens) <= self._token_start_index:
            return []

        # Count which positional argument index we're at now. Loop through all tokens on the command line so far
        # Skip any flags or flag parameter tokens
        next_pos_arg_index = 0

        # This gets set to True when flags will no longer be processed as argparse flags
        # That can happen when -- is used or an argument with nargs=argparse.REMAINDER is used
        skip_remaining_flags = False

        # _ArgumentState of the current positional
        pos_arg_state = None

        # _ArgumentState of the current flag
        flag_arg_state = None

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
            if flag_arg_state is None:
                return

            # if the token does not look like a new flag, then count towards flag arguments
            if not is_potential_flag(token, self._parser):
                flag_arg_state.count += 1

                # does this complete an option item for the flag
                arg_choices = self._resolve_choices_for_arg(flag_arg_state.action)

                # If the current token isn't the one being completed and it's in the flag
                # argument's autocomplete list, then track that we've used it already.
                if not is_last_token and token in arg_choices:
                    consumed_arg_values.setdefault(flag_arg_state.action.dest, [])
                    consumed_arg_values[flag_arg_state.action.dest].append(token)

        def consume_positional_argument() -> None:
            """Consuming token as positional argument"""
            if pos_arg_state is None:
                return

            pos_arg_state.count += 1

            # does this complete an option item for the positional
            arg_choices = self._resolve_choices_for_arg(pos_arg_state.action)

            # If the current token isn't the one being completed and it's in the positional
            # argument's autocomplete list, then track that we've used it already.
            if not is_last_token and token in arg_choices:
                consumed_arg_values.setdefault(pos_arg_state.action.dest, [])
                consumed_arg_values[pos_arg_state.action.dest].append(token)

        # This next block of processing tries to parse all parameters before the last parameter.
        # We're trying to determine what specific argument the current cursor position should be
        # matched with. When we finish parsing all of the arguments, we can determine whether the
        # last token is a positional or flag argument and which specific argument it is.
        #
        # We're also trying to save every flag that has been used as well as every value that
        # has been used for a positional or flag parameter.  By saving this information we can exclude
        # it from the completion results we generate for the last token. For example, single-use flag
        # arguments will be hidden from the list of available flags. Also, arguments with a
        # defined list of possible values will exclude values that have already been used.

        # Notes when the token being completed has been reached
        is_last_token = False

        # Enumerate over the sliced list
        for loop_index, token in enumerate(tokens[self._token_start_index:]):
            token_index = loop_index + self._token_start_index
            if token_index >= len(tokens) - 1:
                is_last_token = True

            # If we're in a positional REMAINDER arg, force all future tokens to go to that
            if pos_arg_state is not None and pos_arg_state.is_remainder:
                consume_positional_argument()
                continue

            # If we're in a flag REMAINDER arg, force all future tokens to go to that until a double dash is hit
            elif flag_arg_state is not None and flag_arg_state.is_remainder:
                skip_remaining_flags = True
                if token == '--':
                    flag_arg_state = None
                else:
                    consume_flag_argument()
                continue

            # Handle '--' which tells argparse all remaining arguments are non-flags
            elif token == '--' and not skip_remaining_flags:
                if is_last_token:
                    # Exit loop and see if -- can be completed into a flag
                    break
                else:
                    # End the current flag
                    flag_arg_state = None
                    skip_remaining_flags = True
                    continue

            current_is_positional = False

            # Are we consuming flag arguments?
            if flag_arg_state is not None and flag_arg_state.needed:
                consume_flag_argument()
            else:
                if not skip_remaining_flags:
                    # Special case when each of the following is true:
                    #   - We're not in the middle of consuming flag arguments
                    #   - The current positional argument count has hit the max count
                    #   - The next positional argument is a REMAINDER argument
                    # Argparse will now treat all future tokens as arguments to the positional including tokens that
                    # look like flags so the completer should skip any flag related processing once this happens
                    if pos_arg_state is not None and pos_arg_state.count >= pos_arg_state.max and \
                            next_pos_arg_index < len(self._positional_actions) and \
                            self._positional_actions[next_pos_arg_index].nargs == argparse.REMAINDER:
                        skip_remaining_flags = True

                # At this point we're no longer consuming flag arguments. Is the current argument a potential flag?
                if is_potential_flag(token, self._parser) and not skip_remaining_flags:
                    # Reset flag arg state but not positional tracking because flags can be
                    # interspersed anywhere between positionals
                    flag_arg_state = None
                    action = None

                    # does the token fully match a known flag?
                    if token in self._flag_to_action:
                        action = self._flag_to_action[token]
                    elif hasattr(self._parser, 'allow_abbrev') and self._parser.allow_abbrev:
                        candidates_flags = [flag for flag in self._flag_to_action if flag.startswith(token)]
                        if len(candidates_flags) == 1:
                            action = self._flag_to_action[candidates_flags[0]]

                    if action is not None:
                        flag_arg_state = AutoCompleter._ArgumentState(action)

                        # It's possible we already have consumed values for this flag if it was used earlier
                        # in the command line. Reset them now for this use of the flag.
                        consumed_arg_values[flag_arg_state.action.dest] = []

                        # Keep track of what flags have already been used
                        # Flags with action set to append, append_const, and count can be reused
                        if not is_last_token and \
                                not isinstance(flag_arg_state.action, argparse._AppendAction) and \
                                not isinstance(flag_arg_state.action, argparse._AppendConstAction) and \
                                not isinstance(flag_arg_state.action, argparse._CountAction):
                            matched_flags.extend(flag_arg_state.action.option_strings)

                # current token isn't a potential flag
                #   - does the last flag accept variable arguments?
                #   - have we reached the max arg count for the flag?
                elif flag_arg_state is None or \
                        not flag_arg_state.variable or \
                        flag_arg_state.count >= flag_arg_state.max:
                    # previous flag doesn't accept variable arguments, count this as a positional argument

                    # reset flag tracking variables
                    flag_arg_state = None
                    current_is_positional = True

                    if len(token) > 0 and pos_arg_state is not None and pos_arg_state.count < pos_arg_state.max:
                        # we have positional action match and we haven't reached the max arg count, consume
                        # the positional argument and move on.
                        consume_positional_argument()
                    elif pos_arg_state is None or pos_arg_state.count >= pos_arg_state.max:
                        # if we don't have a current positional action or we've reached the max count for the action
                        # close out the current positional argument state and set up for the next one
                        pos_index = next_pos_arg_index
                        next_pos_arg_index += 1
                        pos_arg_state = None

                        # are we at a sub-command? If so, forward to the matching completer
                        if pos_index < len(self._positional_actions):
                            action = self._positional_actions[pos_index]
                            pos_name = action.dest
                            if pos_name in self._positional_completers:
                                sub_completers = self._positional_completers[pos_name]
                                if token in sub_completers:
                                    return sub_completers[token].complete_command(tokens, text, line,
                                                                                  begidx, endidx)

                            pos_arg_state = AutoCompleter._ArgumentState(action)
                            consume_positional_argument()

                    elif not is_last_token and pos_arg_state is not None:
                        pos_arg_state = None

                else:
                    consume_flag_argument()

            # To allow completion of the final token, we only do the following on preceding tokens
            if not is_last_token:
                if flag_arg_state is not None and flag_arg_state.min is not None:
                    flag_arg_state.needed = flag_arg_state.count < flag_arg_state.min

        # Here we're done parsing all of the prior arguments. We know what the next argument is.

        # if we don't have a flag to populate with arguments and the last token starts with
        # a flag prefix then we'll complete the list of flag options
        if (flag_arg_state is None or not flag_arg_state.needed) and \
                is_potential_flag(tokens[-1], self._parser) and not skip_remaining_flags:

            # Build a list of flags that can be tab completed
            match_against = []

            for flag in self._flags:
                # Make sure this flag hasn't already been used
                if flag not in matched_flags:
                    # Make sure this flag isn't considered hidden
                    action = self._flag_to_action[flag]
                    if action.help != argparse.SUPPRESS:
                        match_against.append(flag)

            return utils.basic_complete(text, line, begidx, endidx, match_against)

        completion_results = []

        # we're not at a positional argument, see if we're in a flag argument
        if not current_is_positional:
            if flag_arg_state is not None:
                consumed = consumed_arg_values.get(flag_arg_state.action.dest, [])
                completion_results = self._complete_for_arg(flag_arg_state.action, text, line,
                                                            begidx, endidx, consumed)
                if not completion_results:
                    self._print_arg_hint(flag_arg_state.action)
                elif len(completion_results) > 1:
                    completion_results = self._format_completions(flag_arg_state.action, completion_results)

        # ok, we're not a flag, see if there's a positional argument to complete
        else:
            if pos_arg_state is not None:
                consumed = consumed_arg_values.get(pos_arg_state.action.dest, [])
                completion_results = self._complete_for_arg(pos_arg_state.action, text, line,
                                                            begidx, endidx, consumed)

                if not completion_results:
                    self._print_arg_hint(pos_arg_state.action)
                elif len(completion_results) > 1:
                    completion_results = self._format_completions(pos_arg_state.action, completion_results)

        return completion_results

    def _format_completions(self, action, completions: List[Union[str, CompletionItem]]) -> List[str]:
        # Check if the results are CompletionItems and that there aren't too many to display
        if 1 < len(completions) <= self._cmd2_app.max_completion_items and \
                isinstance(completions[0], CompletionItem):

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

            term_size = shutil.get_terminal_size()
            fill_width = int(term_size.columns * .6) - (token_width + 2)
            for item in completions:
                entry = '{: <{token_width}}{: <{fill_width}}'.format(item, item.description,
                                                                     token_width=token_width + 2,
                                                                     fill_width=fill_width)
                completions_with_desc.append(entry)

            desc_header = getattr(action, ATTR_DESCRIPTIVE_COMPLETION_HEADER, None)
            if desc_header is None:
                desc_header = DEFAULT_DESCRIPTIVE_HEADER
            header = '\n{: <{token_width}}{}'.format(action.dest.upper(), desc_header, token_width=token_width + 2)

            self._cmd2_app.completion_header = header
            self._cmd2_app.display_matches = completions_with_desc

        return completions

    def complete_command_help(self, tokens: List[str], text: str, line: str, begidx: int, endidx: int) -> List[str]:
        """
        Supports the completion of sub-command names
        :param tokens: command line tokens
        :param text: the string prefix we are attempting to match (all returned matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :return: List of subcommand completions
        """
        for token in tokens[self._token_start_index:]:
            if self._positional_completers:
                # For now argparse only allows 1 sub-command group per level
                # so this will only loop once.
                for completers in self._positional_completers.values():
                    if token in completers:
                        return completers[token].complete_command_help(tokens, text, line, begidx, endidx)
                    else:
                        return utils.basic_complete(text, line, begidx, endidx, completers.keys())
        return []

    def format_help(self, tokens: List[str]) -> str:
        """
        Retrieve help text of a subcommand
        :param tokens: command line tokens
        :return: help text of the subcommand being queried
        """
        for token in tokens[self._token_start_index:]:
            if self._positional_completers:
                # For now argparse only allows 1 sub-command group per level
                # so this will only loop once.
                for completers in self._positional_completers.values():
                    if token in completers:
                        return completers[token].format_help(tokens)
        return self._parser.format_help()

    def _complete_for_arg(self, arg: argparse.Action,
                          text: str, line: str, begidx: int, endidx: int, used_values=()) -> List[str]:
        """Tab completion routine for argparse arguments"""

        # Check the arg provides choices to the user
        if arg.dest in self._arg_choices:
            arg_choices = self._arg_choices[arg.dest]

            # Check if the argument uses a specific tab completion function to provide its choices
            if isinstance(arg_choices, ChoicesCallable) and arg_choices.is_completer:
                if arg_choices.is_method:
                    return arg_choices.to_call(self._cmd2_app, text, line, begidx, endidx)
                else:
                    return arg_choices.to_call(text, line, begidx, endidx)

            # Otherwise use basic_complete on the choices
            else:
                return utils.basic_complete(text, line, begidx, endidx,
                                            self._resolve_choices_for_arg(arg, used_values))

        return []

    def _resolve_choices_for_arg(self, arg: argparse.Action, used_values=()) -> List[str]:
        """Retrieve a list of choices that are available for a particular argument"""
        if arg.dest in self._arg_choices:
            arg_choices = self._arg_choices[arg.dest]

            # Check if arg_choices is a ChoicesCallable that generates a choice list
            if isinstance(arg_choices, ChoicesCallable):
                if arg_choices.is_completer:
                    # Tab completion routines are handled in other functions
                    return []
                else:
                    if arg_choices.is_method:
                        arg_choices = arg_choices.to_call(self._cmd2_app)
                    else:
                        arg_choices = arg_choices.to_call()

            # Since arg_choices can be any iterable type, convert to a list
            arg_choices = list(arg_choices)

            # Since choices can be various types like int, we must convert them to strings
            for index, choice in enumerate(arg_choices):
                if not isinstance(choice, str,):
                    arg_choices[index] = str(choice)

            # Filter out arguments we already used
            return [choice for choice in arg_choices if choice not in used_values]

        return []

    @staticmethod
    def _print_arg_hint(arg: argparse.Action) -> None:
        """Print argument hint to the terminal when tab completion results in no results"""

        # Check if hinting is disabled
        suppress_hint = getattr(arg, ATTR_SUPPRESS_TAB_HINT, False)
        if suppress_hint or arg.help == argparse.SUPPRESS:
            return

        # Check if this is a flag
        if arg.option_strings:
            flags = ', '.join(arg.option_strings)
            param = ' ' + str(arg.dest).upper()
            prefix = '{}{}'.format(flags, param)

        # Otherwise this is a positional
        else:
            prefix = '{}'.format(str(arg.dest).upper())

        prefix = '  {0: <{width}}    '.format(prefix, width=20)
        pref_len = len(prefix)

        help_text = '' if arg.help is None else arg.help
        help_lines = help_text.splitlines()

        if len(help_lines) == 1:
            print('\nHint:\n{}{}\n'.format(prefix, help_lines[0]))
        else:
            out_str = '\n{}'.format(prefix)
            out_str += '\n{0: <{width}}'.format('', width=pref_len).join(help_lines)
            print('\nHint:' + out_str + '\n')

        # Redraw prompt and input line
        rl_force_redisplay()
