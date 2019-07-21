# coding=utf-8
# flake8: noqa C901
# NOTE: Ignoring flake8 cyclomatic complexity in this file
"""
This module defines the AutoCompleter class which provides argparse-based tab completion to cmd2 apps.
See the header of argparse_custom.py for instructions on how to use these features.
"""

import argparse
import numbers
import shutil
from typing import List, Union

from . import cmd2
from . import utils
from .ansi import ansi_safe_wcswidth, style_error
from .argparse_custom import ATTR_SUPPRESS_TAB_HINT, ATTR_DESCRIPTIVE_COMPLETION_HEADER, ATTR_NARGS_RANGE
from .argparse_custom import ChoicesCallable, CompletionItem, ATTR_CHOICES_CALLABLE, INFINITY, generate_range_error
from .rl_utils import rl_force_redisplay

# If no descriptive header is supplied, then this will be used instead
DEFAULT_DESCRIPTIVE_HEADER = 'Description'


def _single_prefix_char(token: str, parser: argparse.ArgumentParser) -> bool:
    """Returns if a token is just a single flag prefix character"""
    return len(token) == 1 and token[0] in parser.prefix_chars


# noinspection PyProtectedMember
def _looks_like_flag(token: str, parser: argparse.ArgumentParser) -> bool:
    """
    Determine if a token looks like a flag. Unless an argument has nargs set to argparse.REMAINDER,
    then anything that looks like a flag can't be consumed as a value for it.
    Based on argparse._parse_optional().
    """
    # Flags have to be at least characters
    if len(token) < 2:
        return False

    # Flags have to start with a prefix character
    if not token[0] in parser.prefix_chars:
        return False

    # If it looks like a negative number, it is not a flag unless there are negative-number-like flags
    if parser._negative_number_matcher.match(token):
        if not parser._has_negative_number_optionals:
            return False

    # Flags can't have a space
    if ' ' in token:
        return False

    # Starts like a flag
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
            self.is_remainder = (self.action.nargs == argparse.REMAINDER)

            # Check if nargs is a range
            nargs_range = getattr(self.action, ATTR_NARGS_RANGE, None)
            if nargs_range is not None:
                self.min = nargs_range[0]
                self.max = nargs_range[1]

            # Otherwise check against argparse types
            elif self.action.nargs is None:
                self.min = 1
                self.max = 1
            elif self.action.nargs == argparse.OPTIONAL:
                self.min = 0
                self.max = 1
            elif self.action.nargs == argparse.ZERO_OR_MORE or self.action.nargs == argparse.REMAINDER:
                self.min = 0
                self.max = INFINITY
            elif self.action.nargs == argparse.ONE_OR_MORE:
                self.min = 1
                self.max = INFINITY
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
        self._token_start_index = token_start_index

        self._flags = []  # all flags in this command
        self._flag_to_action = {}  # maps flags to the argparse action object
        self._positional_actions = []  # actions for positional arguments (by position index)

        # maps action to subcommand autocompleter:
        #   action -> dict(sub_command -> completer)
        self._positional_completers = {}

        # Start digging through the argparse structures.
        #   _actions is the top level container of parameter definitions
        for action in self._parser._actions:
            # if the parameter is flag based, it will have option_strings
            if action.option_strings:
                # record each option flag
                for option in action.option_strings:
                    self._flags.append(option)
                    self._flag_to_action[option] = action

            # Otherwise this is a positional parameter
            else:
                self._positional_actions.append(action)

                if isinstance(action, argparse._SubParsersAction):
                    sub_completers = {}

                    # Create an AutoCompleter for each subcommand of this command
                    for subcmd in action.choices:

                        subcmd_start = token_start_index + len(self._positional_actions)
                        sub_completers[subcmd] = AutoCompleter(action.choices[subcmd],
                                                               cmd2_app,
                                                               token_start_index=subcmd_start)

                    self._positional_completers[action] = sub_completers

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
        consumed_arg_values = {}  # dict(arg_name -> [values, ...])

        def consume_argument(arg_state: AutoCompleter._ArgumentState) -> None:
            """Consuming token as an argument"""
            arg_state.count += 1

            # Does this complete an option item for the flag?
            arg_choices = self._resolve_choices_for_arg(arg_state.action)

            # If the current token is in the flag argument's autocomplete list,
            # then track that we've used it already.
            if token in arg_choices:
                consumed_arg_values.setdefault(arg_state.action, [])
                consumed_arg_values[arg_state.action].append(token)

        #############################################################################################
        # Parse all but the last token
        #############################################################################################
        for loop_index, token in enumerate(tokens[self._token_start_index:-1]):

            # If we're in a positional REMAINDER arg, force all future tokens to go to that
            if pos_arg_state is not None and pos_arg_state.is_remainder:
                consume_argument(pos_arg_state)
                continue

            # If we're in a flag REMAINDER arg, force all future tokens to go to that until a double dash is hit
            elif flag_arg_state is not None and flag_arg_state.is_remainder:
                if token == '--':
                    flag_arg_state = None
                else:
                    consume_argument(flag_arg_state)
                continue

            # Handle '--' which tells argparse all remaining arguments are non-flags
            elif token == '--' and not skip_remaining_flags:
                # Check if there is an unfinished flag
                if flag_arg_state is not None and flag_arg_state.count < flag_arg_state.min:
                    self._print_unfinished_flag_error(flag_arg_state)
                    return []

                # Otherwise end the current flag
                else:
                    flag_arg_state = None
                    skip_remaining_flags = True
                    continue

            # Check the format of the current token to see if it can be an argument's value
            if _looks_like_flag(token, self._parser) and not skip_remaining_flags:

                # Check if there is an unfinished flag
                if flag_arg_state is not None and flag_arg_state.count < flag_arg_state.min:
                    self._print_unfinished_flag_error(flag_arg_state)
                    return []

                # Reset flag arg state but not positional tracking because flags can be
                # interspersed anywhere between positionals
                flag_arg_state = None
                action = None

                # Does the token match a known flag?
                if token in self._flag_to_action:
                    action = self._flag_to_action[token]
                elif self._parser.allow_abbrev:
                    candidates_flags = [flag for flag in self._flag_to_action if flag.startswith(token)]
                    if len(candidates_flags) == 1:
                        action = self._flag_to_action[candidates_flags[0]]

                if action is not None:
                    # Keep track of what flags have already been used
                    # Flags with action set to append, append_const, and count can be reused
                    if not isinstance(action, (argparse._AppendAction,
                                               argparse._AppendConstAction,
                                               argparse._CountAction)):
                        matched_flags.extend(action.option_strings)

                    new_arg_state = AutoCompleter._ArgumentState(action)

                    # Keep track of this flag if it can receive arguments
                    if new_arg_state.max > 0:
                        flag_arg_state = new_arg_state
                        skip_remaining_flags = flag_arg_state.is_remainder

                        # It's possible we already have consumed values for this flag if it was used
                        # earlier in the command line. Reset them now for this use of it.
                        consumed_arg_values[flag_arg_state.action] = []

            # Check if we are consuming a flag
            elif flag_arg_state is not None:
                consume_argument(flag_arg_state)

                # Check if we have finished with this flag
                if flag_arg_state.count >= flag_arg_state.max:
                    flag_arg_state = None

            # Otherwise treat as a positional argument
            else:
                # If we aren't current tracking a positional, then get the next positional arg to handle this token
                if pos_arg_state is None:
                    pos_index = next_pos_arg_index
                    next_pos_arg_index += 1

                    # Make sure we are still have positional arguments to fill
                    if pos_index < len(self._positional_actions):
                        action = self._positional_actions[pos_index]

                        # Are we at a subcommand? If so, forward to the matching completer
                        if isinstance(action, argparse._SubParsersAction):
                            sub_completers = self._positional_completers[action]
                            if token in sub_completers:
                                return sub_completers[token].complete_command(tokens, text, line,
                                                                              begidx, endidx)
                            else:
                                # Invalid subcommand entered, so no way to complete remaining tokens
                                return []

                        # Otherwise keep track of the argument
                        else:
                            pos_arg_state = AutoCompleter._ArgumentState(action)

                # Check if we have a positional to consume this token
                if pos_arg_state is not None:
                    consume_argument(pos_arg_state)

                    # No more flags are allowed if this is a REMAINDER argument
                    if pos_arg_state.is_remainder:
                        skip_remaining_flags = True

                    # Check if we have finished with this positional
                    elif pos_arg_state.count >= pos_arg_state.max:
                        pos_arg_state = None

                        # Check if this a case in which we've finished all positionals before one that has nargs
                        # set to argparse.REMAINDER. At this point argparse allows no more flags to be processed.
                        if next_pos_arg_index < len(self._positional_actions) and \
                                self._positional_actions[next_pos_arg_index].nargs == argparse.REMAINDER:
                            skip_remaining_flags = True

        #############################################################################################
        # We have parsed all but the last token and have enough information to complete it
        #############################################################################################

        # Check if we are completing a flag name. This check ignores strings with a length of one, like '-'.
        # This is because that could be the start of a negative number which may be a valid completion for
        # the current argument. We will handle the completion of flags that start with only one prefix
        # character (-f) at the end.
        if _looks_like_flag(text, self._parser) and not skip_remaining_flags:
            if flag_arg_state is not None and flag_arg_state.count < flag_arg_state.min:
                self._print_unfinished_flag_error(flag_arg_state)
                return []

            return self._complete_flags(text, line, begidx, endidx, matched_flags)

        completion_results = []

        # Check if we are completing a flag's argument
        if flag_arg_state is not None:
            consumed = consumed_arg_values.get(flag_arg_state.action, [])
            completion_results = self._complete_for_arg(flag_arg_state.action, text, line,
                                                        begidx, endidx, consumed)

            # If we have results, then return them
            if completion_results:
                return completion_results

            # Otherwise, print a hint if the flag isn't finished or text isn't possibly the start of a flag
            elif flag_arg_state.count < flag_arg_state.min or \
                    not _single_prefix_char(text, self._parser) or skip_remaining_flags:
                self._print_arg_hint(flag_arg_state.action)
                return []

        # Otherwise check if we have a positional to complete
        elif pos_arg_state is not None or next_pos_arg_index < len(self._positional_actions):

            # If we aren't current tracking a positional, then get the next positional arg to handle this token
            if pos_arg_state is None:
                pos_index = next_pos_arg_index
                action = self._positional_actions[pos_index]
                pos_arg_state = AutoCompleter._ArgumentState(action)

            consumed = consumed_arg_values.get(pos_arg_state.action, [])
            completion_results = self._complete_for_arg(pos_arg_state.action, text, line,
                                                        begidx, endidx, consumed)

            # If we have results, then return them
            if completion_results:
                return completion_results

            # Otherwise, print a hint if text isn't possibly the start of a flag
            elif not _single_prefix_char(text, self._parser) or skip_remaining_flags:
                self._print_arg_hint(pos_arg_state.action)
                return []

        # Handle case in which text is a single flag prefix character that
        # didn't complete against any argument values.
        if _single_prefix_char(text, self._parser) and not skip_remaining_flags:
            return self._complete_flags(text, line, begidx, endidx, matched_flags)

        return completion_results

    def _complete_flags(self, text: str, line: str, begidx: int, endidx: int, matched_flags: List[str]) -> List[str]:
        """Tab completion routine for a parsers unused flags"""

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

    def _format_completions(self, action, completions: List[Union[str, CompletionItem]]) -> List[str]:
        # Check if the results are CompletionItems and that there aren't too many to display
        if 1 < len(completions) <= self._cmd2_app.max_completion_items and \
                isinstance(completions[0], CompletionItem):

            # If the user has not already sorted the CompletionItems, then sort them before appending the descriptions
            if not self._cmd2_app.matches_sorted:
                completions.sort(key=self._cmd2_app.default_sort_key)
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
        Supports cmd2's help command in the completion of subcommand names
        :param tokens: command line tokens
        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :return: List of subcommand completions
        """
        for token in tokens[self._token_start_index:]:
            if self._positional_completers:
                # For now argparse only allows 1 subcommand group per level
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
                # For now argparse only allows 1 subcommand group per level
                # so this will only loop once.
                for completers in self._positional_completers.values():
                    if token in completers:
                        return completers[token].format_help(tokens)
        return self._parser.format_help()

    def _complete_for_arg(self, arg: argparse.Action,
                          text: str, line: str, begidx: int, endidx: int, used_values=()) -> List[str]:
        """Tab completion routine for argparse arguments"""

        # Check the arg provides choices to the user
        if arg.choices is not None:
            arg_choices = arg.choices
        else:
            arg_choices = getattr(arg, ATTR_CHOICES_CALLABLE, None)

        if arg_choices is None:
            return []

        # Check if the argument uses a specific tab completion function to provide its choices
        if isinstance(arg_choices, ChoicesCallable) and arg_choices.is_completer:
            if arg_choices.is_method:
                results = arg_choices.to_call(self._cmd2_app, text, line, begidx, endidx)
            else:
                results = arg_choices.to_call(text, line, begidx, endidx)

        # Otherwise use basic_complete on the choices
        else:
            results = utils.basic_complete(text, line, begidx, endidx,
                                           self._resolve_choices_for_arg(arg, used_values))

        return self._format_completions(arg, results)

    def _resolve_choices_for_arg(self, arg: argparse.Action, used_values=()) -> List[str]:
        """Retrieve a list of choices that are available for a particular argument"""

        # Check the arg provides choices to the user
        if arg.choices is not None:
            arg_choices = arg.choices
        else:
            arg_choices = getattr(arg, ATTR_CHOICES_CALLABLE, None)

        if arg_choices is None:
            return []

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

        # If these choices are numbers, and have not yet been sorted, then sort them now
        if not self._cmd2_app.matches_sorted and all(isinstance(x, numbers.Number) for x in arg_choices):
            arg_choices.sort()
            self._cmd2_app.matches_sorted = True

        # Since choices can be various types like int, we must convert them to strings
        for index, choice in enumerate(arg_choices):
            if not isinstance(choice, str):
                arg_choices[index] = str(choice)

        # Filter out arguments we already used
        return [choice for choice in arg_choices if choice not in used_values]

    @staticmethod
    def _print_arg_hint(arg: argparse.Action) -> None:
        """Print argument hint to the terminal when tab completion results in no results"""

        # Check if hinting is disabled
        suppress_hint = getattr(arg, ATTR_SUPPRESS_TAB_HINT, False)
        if suppress_hint or arg.help == argparse.SUPPRESS or arg.dest == argparse.SUPPRESS:
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

    @staticmethod
    def _print_unfinished_flag_error(flag_arg_state: _ArgumentState) -> None:
        """Print an error during tab completion when the user has not finished the current flag"""
        flags = ', '.join(flag_arg_state.action.option_strings)
        param = ' ' + str(flag_arg_state.action.dest).upper()
        prefix = '{}{}'.format(flags, param)

        out_str = "\nError:\n"
        out_str += '  {0: <{width}}    '.format(prefix, width=20)
        out_str += generate_range_error(flag_arg_state.min, flag_arg_state.max)

        out_str += ' ({} entered)'.format(flag_arg_state.count)
        print(style_error('{}\n'.format(out_str)))

        # Redraw prompt and input line
        rl_force_redisplay()
