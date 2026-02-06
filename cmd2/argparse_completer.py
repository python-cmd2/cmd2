"""Module defines the ArgparseCompleter class which provides argparse-based completion to cmd2 apps.

See the header of argparse_custom.py for instructions on how to use these features.
"""

import argparse
import inspect
import numbers
from collections import (
    deque,
)
from collections.abc import Sequence
from typing import (
    IO,
    TYPE_CHECKING,
    cast,
)

from .constants import INFINITY
from .rich_utils import Cmd2GeneralConsole

if TYPE_CHECKING:  # pragma: no cover
    from .cmd2 import Cmd

from rich.box import SIMPLE_HEAD
from rich.table import (
    Column,
    Table,
)

from .argparse_custom import (
    ChoicesCallable,
    generate_range_error,
)
from .command_definition import CommandSet
from .completion import (
    ChoicesProviderFuncWithTokens,
    CompletionItem,
    Completions,
)
from .exceptions import CompletionError
from .styles import Cmd2Style

# If no descriptive headers are supplied, then this will be used instead
DEFAULT_DESCRIPTIVE_HEADERS: Sequence[str | Column] = ['Description']

# Name of the choice/completer function argument that, if present, will be passed a dictionary of
# command line tokens up through the token being completed mapped to their argparse destination name.
ARG_TOKENS = 'arg_tokens'


def _build_hint(parser: argparse.ArgumentParser, arg_action: argparse.Action) -> str:
    """Build completion hint for a given argument."""
    # Check if hinting is disabled for this argument
    suppress_hint = arg_action.get_suppress_tab_hint()  # type: ignore[attr-defined]
    if suppress_hint or arg_action.help == argparse.SUPPRESS:
        return ''

    # Use the parser's help formatter to display just this action's help text
    formatter = parser._get_formatter()
    formatter.start_section("Hint")
    formatter.add_argument(arg_action)
    formatter.end_section()
    return formatter.format_help()


def _single_prefix_char(token: str, parser: argparse.ArgumentParser) -> bool:
    """Is a token just a single flag prefix character."""
    return len(token) == 1 and token[0] in parser.prefix_chars


def _looks_like_flag(token: str, parser: argparse.ArgumentParser) -> bool:
    """Determine if a token looks like a flag.

    Unless an argument has nargs set to argparse.REMAINDER, then anything that looks like a flag
    can't be consumed as a value for it.

    Based on argparse._parse_optional().
    """
    # Flags have to be at least characters
    if len(token) < 2:
        return False

    # Flags have to start with a prefix character
    if token[0] not in parser.prefix_chars:
        return False

    # If it looks like a negative number, it is not a flag unless there are negative-number-like flags
    if parser._negative_number_matcher.match(token) and not parser._has_negative_number_optionals:
        return False

    # Flags can't have a space
    return ' ' not in token


class _ArgumentState:
    """Keeps state of an argument being parsed."""

    def __init__(self, arg_action: argparse.Action) -> None:
        self.action = arg_action
        self.min: int | str
        self.max: float | int | str
        self.count = 0
        self.is_remainder = self.action.nargs == argparse.REMAINDER

        # Check if nargs is a range
        nargs_range = self.action.get_nargs_range()  # type: ignore[attr-defined]
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
        elif self.action.nargs in (argparse.ZERO_OR_MORE, argparse.REMAINDER):
            self.min = 0
            self.max = INFINITY
        elif self.action.nargs == argparse.ONE_OR_MORE:
            self.min = 1
            self.max = INFINITY
        else:
            self.min = self.action.nargs
            self.max = self.action.nargs


class _UnfinishedFlagError(CompletionError):
    def __init__(self, flag_arg_state: _ArgumentState) -> None:
        """CompletionError which occurs when the user has not finished the current flag.

        :param flag_arg_state: information about the unfinished flag action.
        """
        arg = f'{argparse._get_action_name(flag_arg_state.action)}'
        err = f'{generate_range_error(cast(int, flag_arg_state.min), cast(int | float, flag_arg_state.max))}'
        error = f"Error: argument {arg}: {err} ({flag_arg_state.count} entered)"
        super().__init__(error)


class _NoResultsError(CompletionError):
    def __init__(self, parser: argparse.ArgumentParser, arg_action: argparse.Action) -> None:
        """CompletionError which occurs when there are no results.

        If hinting is allowed on this argument, then its hint text will display.

        :param parser: ArgumentParser instance which owns the action being completed
        :param arg_action: action being completed.
        """
        # Set apply_style to False because we don't want hints to look like errors
        super().__init__(_build_hint(parser, arg_action), apply_style=False)


class ArgparseCompleter:
    """Automatic command line completion based on argparse parameters."""

    def __init__(
        self,
        parser: argparse.ArgumentParser,
        cmd2_app: 'Cmd',
        *,
        parent_tokens: dict[str, list[str]] | None = None,
    ) -> None:
        """Create an ArgparseCompleter.

        :param parser: ArgumentParser instance
        :param cmd2_app: reference to the Cmd2 application that owns this ArgparseCompleter
        :param parent_tokens: optional dictionary mapping parent parsers' arg names to their tokens
                              This is only used by ArgparseCompleter when recursing on subcommand parsers
                              Defaults to None
        """
        self._parser = parser
        self._cmd2_app = cmd2_app

        if parent_tokens is None:
            parent_tokens = {}
        self._parent_tokens = parent_tokens

        self._flags = []  # all flags in this command
        self._flag_to_action = {}  # maps flags to the argparse action object
        self._positional_actions = []  # actions for positional arguments (by position index)
        self._subcommand_action = None  # this will be set if self._parser has subcommands

        # Start digging through the argparse structures.
        # _actions is the top level container of parameter definitions
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
                # Check if this action defines subcommands
                if isinstance(action, argparse._SubParsersAction):
                    self._subcommand_action = action

    def complete(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        tokens: list[str],
        *,
        cmd_set: CommandSet | None = None,
    ) -> Completions:
        """Complete text using argparse metadata.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param tokens: list of argument tokens being passed to the parser
        :param cmd_set: if completing a command, the CommandSet the command's function belongs to, if applicable.
                        Defaults to None.
        :return: a Completions object
        :raises CompletionError: for various types of completion errors
        """
        if not tokens:
            return Completions()

        # Positionals args that are left to parse
        remaining_positionals = deque(self._positional_actions)

        # This gets set to True when flags will no longer be processed as argparse flags
        # That can happen when -- is used or an argument with nargs=argparse.REMAINDER is used
        skip_remaining_flags = False

        # _ArgumentState of the current positional
        pos_arg_state: _ArgumentState | None = None

        # _ArgumentState of the current flag
        flag_arg_state: _ArgumentState | None = None

        # Non-reusable flags that we've parsed
        used_flags: list[str] = []

        # Keeps track of arguments we've seen and any tokens they consumed
        consumed_arg_values: dict[str, list[str]] = {}  # dict(arg_name -> list[tokens])

        # Completed mutually exclusive groups
        completed_mutex_groups: dict[argparse._MutuallyExclusiveGroup, argparse.Action] = {}

        def consume_argument(arg_state: _ArgumentState, token: str) -> None:
            """Consuming token as an argument."""
            arg_state.count += 1
            consumed_arg_values.setdefault(arg_state.action.dest, [])
            consumed_arg_values[arg_state.action.dest].append(token)

        #############################################################################################
        # Parse all but the last token
        #############################################################################################
        for token_index, token in enumerate(tokens[:-1]):
            # Remainder handling: If we're in a positional REMAINDER arg, force all future tokens to go to that
            if pos_arg_state is not None and pos_arg_state.is_remainder:
                consume_argument(pos_arg_state, token)
                continue

            # If we're in a flag REMAINDER arg, force all future tokens to go to that until a double dash is hit
            if flag_arg_state is not None and flag_arg_state.is_remainder:
                if token == '--':  # noqa: S105
                    flag_arg_state = None
                else:
                    consume_argument(flag_arg_state, token)
                continue

            # Handle '--' which tells argparse all remaining arguments are non-flags
            if token == '--' and not skip_remaining_flags:  # noqa: S105
                # Check if there is an unfinished flag
                if flag_arg_state and isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min:
                    raise _UnfinishedFlagError(flag_arg_state)

                # Otherwise end the current flag
                flag_arg_state = None
                skip_remaining_flags = True
                continue

            # Flag handling: Check the format of the current token to see if it can be an argument's value
            if _looks_like_flag(token, self._parser) and not skip_remaining_flags:
                # Check if there is an unfinished flag
                if flag_arg_state and isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min:
                    raise _UnfinishedFlagError(flag_arg_state)

                # Reset flag arg state but not positional tracking because flags can be
                # interspersed anywhere between positionals
                flag_arg_state = None
                action = self._flag_to_action.get(token)

                # Does the token match a known flag?
                if action is None and self._parser.allow_abbrev:
                    candidates = [f for f in self._flag_to_action if f.startswith(token)]
                    if len(candidates) == 1:
                        action = self._flag_to_action[candidates[0]]
                if action:
                    self._update_mutex_groups(action, completed_mutex_groups, used_flags, remaining_positionals)
                    if isinstance(action, (argparse._AppendAction, argparse._AppendConstAction, argparse._CountAction)):
                        # Flags with action set to append, append_const, and count can be reused
                        # Therefore don't erase any tokens already consumed for this flag
                        consumed_arg_values.setdefault(action.dest, [])
                    else:
                        # This flag is not reusable, so mark that we've seen it
                        used_flags.extend(action.option_strings)

                        # It's possible we already have consumed values for this flag if it was used
                        # earlier in the command line. Reset them now for this use of it.
                        consumed_arg_values[action.dest] = []

                    new_arg_state = _ArgumentState(action)

                    # Keep track of this flag if it can receive arguments
                    if cast(float, new_arg_state.max) > 0:
                        flag_arg_state = new_arg_state
                        skip_remaining_flags = flag_arg_state.is_remainder

            # Check if we are consuming a flag
            elif flag_arg_state is not None:
                consume_argument(flag_arg_state, token)

                # Check if we have finished with this flag
                if flag_arg_state.count >= cast(float, flag_arg_state.max):
                    flag_arg_state = None

            # Positional handling: Otherwise treat as a positional argument
            else:
                # If we aren't current tracking a positional, then get the next positional arg to handle this token
                if pos_arg_state is None and remaining_positionals:
                    action = remaining_positionals.popleft()

                    # Are we at a subcommand? If so, forward to the matching completer
                    if action == self._subcommand_action:
                        if token in self._subcommand_action.choices:
                            # Merge self._parent_tokens and consumed_arg_values
                            parent_tokens = {**self._parent_tokens, **consumed_arg_values}

                            # Include the subcommand name if its destination was set
                            if action.dest != argparse.SUPPRESS:
                                parent_tokens[action.dest] = [token]

                            parser = self._subcommand_action.choices[token]
                            completer_type = self._cmd2_app._determine_ap_completer_type(parser)
                            completer = completer_type(parser, self._cmd2_app, parent_tokens=parent_tokens)
                            return completer.complete(text, line, begidx, endidx, tokens[token_index + 1 :], cmd_set=cmd_set)

                        # Invalid subcommand entered, so no way to complete remaining tokens
                        return Completions()

                    # Otherwise keep track of the argument
                    pos_arg_state = _ArgumentState(action)

                # Check if we have a positional to consume this token
                if pos_arg_state is not None:
                    self._update_mutex_groups(pos_arg_state.action, completed_mutex_groups, used_flags, remaining_positionals)
                    consume_argument(pos_arg_state, token)

                    # No more flags are allowed if this is a REMAINDER argument
                    if pos_arg_state.is_remainder:
                        skip_remaining_flags = True

                    # Check if we have finished with this positional
                    elif pos_arg_state.count >= cast(float, pos_arg_state.max):
                        pos_arg_state = None

                        # Check if the next positional has nargs set to argparse.REMAINDER.
                        # At this point argparse allows no more flags to be processed.
                        if remaining_positionals and remaining_positionals[0].nargs == argparse.REMAINDER:
                            skip_remaining_flags = True

        #############################################################################################
        # We have parsed all but the last token and have enough information to complete it
        #############################################################################################
        return self._handle_last_token(
            text,
            line,
            begidx,
            endidx,
            flag_arg_state,
            pos_arg_state,
            remaining_positionals,
            consumed_arg_values,
            used_flags,
            skip_remaining_flags,
            cmd_set,
        )

    def _update_mutex_groups(
        self,
        arg_action: argparse.Action,
        completed_mutex_groups: dict[argparse._MutuallyExclusiveGroup, argparse.Action],
        used_flags: list[str],
        remaining_positionals: deque[argparse.Action],
    ) -> None:
        """Update mutex groups state."""
        for group in self._parser._mutually_exclusive_groups:
            if arg_action in group._group_actions:
                if group in completed_mutex_groups:
                    completer_action = completed_mutex_groups[group]
                    if arg_action != completer_action:
                        arg_str = f'{argparse._get_action_name(arg_action)}'
                        completer_str = f'{argparse._get_action_name(completer_action)}'
                        raise CompletionError(f"Error: argument {arg_str}: not allowed with argument {completer_str}")
                    return
                completed_mutex_groups[group] = arg_action
                for group_action in group._group_actions:
                    if group_action == arg_action:
                        continue
                    if group_action in self._flag_to_action.values():
                        used_flags.extend(group_action.option_strings)
                    elif group_action in remaining_positionals:
                        remaining_positionals.remove(group_action)
                break

    def _handle_last_token(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        flag_arg_state: _ArgumentState | None,
        pos_arg_state: _ArgumentState | None,
        remaining_positionals: deque[argparse.Action],
        consumed_arg_values: dict[str, list[str]],
        used_flags: list[str],
        skip_remaining_flags: bool,
        cmd_set: CommandSet | None,
    ) -> Completions:
        """Perform final completion step handling positionals and flags."""
        # Check if we are completing a flag name. This check ignores strings with a length of one, like '-'.
        # This is because that could be the start of a negative number which may be a valid completion for
        # the current argument. We will handle the completion of flags that start with only one prefix
        # character (-f) at the end.
        if _looks_like_flag(text, self._parser) and not skip_remaining_flags:
            if flag_arg_state and isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min:
                raise _UnfinishedFlagError(flag_arg_state)
            return self._complete_flags(text, line, begidx, endidx, used_flags)

        # Check if we are completing a flag's argument
        if flag_arg_state is not None:
            completions = self._complete_arg(text, line, begidx, endidx, flag_arg_state, consumed_arg_values, cmd_set=cmd_set)

            # If we have results, then return them
            if completions:
                if not completions.completion_hint:
                    completions.completion_hint = _build_hint(self._parser, flag_arg_state.action)
                return completions

            # Otherwise, print a hint if the flag isn't finished or text isn't possibly the start of a flag
            if (
                (isinstance(flag_arg_state.min, int) and flag_arg_state.count < flag_arg_state.min)
                or not _single_prefix_char(text, self._parser)
                or skip_remaining_flags
            ):
                raise _NoResultsError(self._parser, flag_arg_state.action)
            return Completions()

        # Otherwise check if we have a positional to complete
        if pos_arg_state is None and remaining_positionals:
            pos_arg_state = _ArgumentState(remaining_positionals.popleft())

        if pos_arg_state is not None:
            completions = self._complete_arg(text, line, begidx, endidx, pos_arg_state, consumed_arg_values, cmd_set=cmd_set)

            # Fallback to flags if allowed
            if not skip_remaining_flags:
                if _looks_like_flag(text, self._parser) or _single_prefix_char(text, self._parser):
                    flag_completions = self._complete_flags(text, line, begidx, endidx, used_flags)
                    completions.matches.extend(flag_completions.matches)
                    completions.display_matches.extend(flag_completions.display_matches)
                elif (
                    not text
                    and not completions
                    and (isinstance(pos_arg_state.max, int) and pos_arg_state.count >= pos_arg_state.max)
                ):
                    flag_completions = self._complete_flags(text, line, begidx, endidx, used_flags)
                    if flag_completions:
                        return flag_completions

            # If we have results, then return them
            if completions:
                if (
                    not completions.completion_hint
                    and not isinstance(pos_arg_state.action, argparse._SubParsersAction)
                    and not _looks_like_flag(text, self._parser)
                    and not _single_prefix_char(text, self._parser)
                ):
                    completions.completion_hint = _build_hint(self._parser, pos_arg_state.action)
                return completions

            # Otherwise, print a hint if text isn't possibly the start of a flag
            if not _single_prefix_char(text, self._parser) or skip_remaining_flags:
                raise _NoResultsError(self._parser, pos_arg_state.action)

        # If we aren't skipping remaining flags, then complete flag names if either is True:
        #   1. text is a single flag prefix character that didn't complete against any argument values
        #   2. there are no more positionals to complete
        if not skip_remaining_flags and (not text or _single_prefix_char(text, self._parser) or not remaining_positionals):
            # Reset any completion settings that may have been set by functions which actually had no matches.
            # Otherwise, those settings could alter how the flags are displayed.
            return self._complete_flags(text, line, begidx, endidx, used_flags)

        return Completions()

    def _complete_flags(self, text: str, line: str, begidx: int, endidx: int, used_flags: list[str]) -> Completions:
        """Completion routine for a parsers unused flags."""
        # Build a list of flags that can be completed
        match_against: list[str] = []

        for flag in self._flags:
            # Make sure this flag hasn't already been used
            if flag not in used_flags:
                # Make sure this flag isn't considered hidden
                action = self._flag_to_action[flag]
                if action.help != argparse.SUPPRESS:
                    match_against.append(flag)

        matched_flags = self._cmd2_app.basic_complete(text, line, begidx, endidx, match_against).matches

        # Build a dictionary linking actions with their matched flag names
        matched_actions: dict[argparse.Action, list[str]] = {}
        for flag in matched_flags:
            action = self._flag_to_action[flag]
            matched_actions.setdefault(action, []).append(flag)

        # For completion suggestions, group matched flags by action
        completions = Completions()
        for action, option_strings in matched_actions.items():
            flag_text = ', '.join(option_strings)

            # Mark optional flags with brackets
            if not action.required:
                flag_text = '[' + flag_text + ']'

            # Use the first option string as the completion result for this action
            completions.matches.append(CompletionItem(option_strings[0], [action.help or '']))
            completions.display_matches.append(flag_text)

        return completions

    def _prepare_formatted_exceptions(self, arg_state: _ArgumentState, completions: Completions) -> None:
        """Format CompletionItems into hint table.

        This method modifies the completions object in-place.

        :param completions: the object to modify by populating its formatted_exceptions
        """
        # Nothing to do if we don't have at least 2 completions which are all CompletionItems
        if len(completions) < 2 or not all(isinstance(c, CompletionItem) for c in completions.matches):
            return

        completion_items = cast(list[CompletionItem], completions.matches)

        # Check if the data being completed have a numerical type
        all_nums = all(isinstance(c.orig_value, numbers.Number) for c in completion_items)

        # Sort CompletionItems before building the hint table
        if not completions.matches_sorted:
            # If all orig_value types are numbers, then sort by that value
            if all_nums:
                completion_items.sort(key=lambda c: c.orig_value)
            # Otherwise sort as strings
            else:
                completion_items.sort(key=self._cmd2_app.default_sort_key)
            completions.matches_sorted = True

        # Check if there are too many CompletionItems to display as a table
        if len(completions) <= self._cmd2_app.max_completion_items:
            if isinstance(arg_state.action, argparse._SubParsersAction) or (
                arg_state.action.metavar == "COMMAND" and arg_state.action.dest == "command"
            ):
                return

            # If a metavar was defined, use that instead of the dest field
            destination = arg_state.action.metavar or arg_state.action.dest

            # Handle case where metavar was a tuple
            if isinstance(destination, tuple):
                # Figure out what string in the tuple to use based on how many of the arguments have been completed.
                # Use min() to avoid going passed the end of the tuple to support nargs being ZERO_OR_MORE and
                # ONE_OR_MORE. In those cases, argparse limits metavar tuple to 2 elements but we may be completing
                # the 3rd or more argument here.
                destination = destination[min(len(destination) - 1, arg_state.count)]

            # Build all headers for the hint table
            headers: list[Column] = []
            headers.append(Column(destination.upper(), justify="right" if all_nums else "left", no_wrap=True))
            desc_headers = cast(Sequence[str | Column] | None, arg_state.action.get_descriptive_headers())  # type: ignore[attr-defined]
            if desc_headers is None:
                desc_headers = DEFAULT_DESCRIPTIVE_HEADERS
            headers.extend(dh if isinstance(dh, Column) else Column(dh, overflow="fold") for dh in desc_headers)

            # Build the hint table
            hint_table = Table(*headers, box=SIMPLE_HEAD, show_edge=False, border_style=Cmd2Style.TABLE_BORDER)
            for item in completion_items:
                hint_table.add_row(item, *item.descriptive_data)

            # Generate the hint table string
            console = Cmd2GeneralConsole()
            with console.capture() as capture:
                console.print(hint_table, end="", soft_wrap=False)
            completions.formatted_completions = capture.get()

    def complete_subcommand_help(self, text: str, line: str, begidx: int, endidx: int, tokens: list[str]) -> Completions:
        """Supports cmd2's help command in the completion of subcommand names.

        :param text: the string prefix we are attempting to match (all matches must begin with it)
        :param line: the current input line with leading whitespace removed
        :param begidx: the beginning index of the prefix text
        :param endidx: the ending index of the prefix text
        :param tokens: arguments passed to command/subcommand
        :return: a Completions object
        """
        # If our parser has subcommands, we must examine the tokens and check if they are subcommands
        # If so, we will let the subcommand's parser handle the rest of the tokens via another ArgparseCompleter.
        if self._subcommand_action is not None:
            for token_index, token in enumerate(tokens):
                if token in self._subcommand_action.choices:
                    parser = self._subcommand_action.choices[token]
                    completer = self._cmd2_app._determine_ap_completer_type(parser)(parser, self._cmd2_app)
                    return completer.complete_subcommand_help(text, line, begidx, endidx, tokens[token_index + 1 :])

                if token_index == len(tokens) - 1:
                    # Since this is the last token, we will attempt to complete it
                    return self._cmd2_app.basic_complete(text, line, begidx, endidx, self._subcommand_action.choices)
                break
        return Completions()

    def print_help(self, tokens: list[str], file: IO[str] | None = None) -> None:
        """Supports cmd2's help command in the printing of help text.

        :param tokens: arguments passed to help command
        :param file: optional file object where the argparse should write help text
                     If not supplied, argparse will write to sys.stdout.
        """
        # If our parser has subcommands, we must examine the tokens and check if they are subcommands.
        # If so, we will let the subcommand's parser handle the rest of the tokens via another ArgparseCompleter.
        if tokens and self._subcommand_action is not None:
            parser = cast(argparse.ArgumentParser | None, self._subcommand_action.choices.get(tokens[0]))
            if parser:
                completer = self._cmd2_app._determine_ap_completer_type(parser)(parser, self._cmd2_app)
                completer.print_help(tokens[1:])
                return
        self._parser.print_help(file=file)

    def _complete_arg(
        self,
        text: str,
        line: str,
        begidx: int,
        endidx: int,
        arg_state: _ArgumentState,
        consumed_arg_values: dict[str, list[str]],
        *,
        cmd_set: CommandSet | None = None,
    ) -> Completions:
        """Completion routine for an argparse argument.

        :return: a Completions object
        :raises CompletionError: if the completer or choices function this calls raises one
        """
        # Check if the arg provides choices to the user
        choices_sorted = False
        arg_choices: list[str] | list[CompletionItem] | ChoicesCallable
        if arg_state.action.choices is not None:
            if isinstance(arg_state.action, argparse._SubParsersAction):
                items: list[CompletionItem] = []
                parser_help = {}
                for action in arg_state.action._choices_actions:
                    if action.dest in arg_state.action.choices:
                        subparser = arg_state.action.choices[action.dest]
                        parser_help[subparser] = action.help or ''
                for name, subparser in arg_state.action.choices.items():
                    items.append(CompletionItem(name, [parser_help.get(subparser, '')]))
                arg_choices = items
            else:
                arg_choices = list(arg_state.action.choices)

            if not arg_choices:
                return Completions()

            # If these choices are numbers, then sort them now
            if all(isinstance(x, numbers.Number) for x in arg_choices):
                arg_choices.sort()
                choices_sorted = True

            # Since choices can be various types, make sure they are all strings
            for index, choice in enumerate(arg_choices):
                # Prevent converting anything that is already a str (i.e. CompletionItem)
                if not isinstance(choice, str):
                    arg_choices[index] = str(choice)  # type: ignore[unreachable]
        else:
            choices_attr = arg_state.action.get_choices_callable()  # type: ignore[attr-defined]
            if choices_attr is None:
                return Completions()
            arg_choices = choices_attr

        # If we are going to call a completer/choices function, then set up the common arguments
        args = []
        kwargs = {}

        # The completer may or may not be defined in the same class as the command. Since completer
        # functions are registered with the command argparser before anything is instantiated, we
        # need to find an instance at runtime that matches the types during declaration
        if isinstance(arg_choices, ChoicesCallable):
            self_arg = self._cmd2_app._resolve_func_self(arg_choices.to_call, cmd_set)

            if self_arg is None:
                # No cases matched, raise an error
                raise CompletionError('Could not find CommandSet instance matching defining type for completer')

            args.append(self_arg)

            # Check if arg_choices.to_call expects arg_tokens
            to_call_params = inspect.signature(arg_choices.to_call).parameters
            if ARG_TOKENS in to_call_params:
                # Merge self._parent_tokens and consumed_arg_values
                arg_tokens = {**self._parent_tokens, **consumed_arg_values}

                # Include the token being completed
                arg_tokens.setdefault(arg_state.action.dest, []).append(text)

                # Add the namespace to the keyword arguments for the function we are calling
                kwargs[ARG_TOKENS] = arg_tokens

        # Check if the argument uses a specific completion function to provide its choices
        if isinstance(arg_choices, ChoicesCallable) and arg_choices.is_completer:
            args.extend([text, line, begidx, endidx])
            completions = arg_choices.completer(*args, **kwargs)  # type: ignore[arg-type]

        # Otherwise use basic_complete on the choices
        else:
            # Check if the choices come from a function
            completion_items: list[str] | list[CompletionItem] = []
            if isinstance(arg_choices, ChoicesCallable):
                if not arg_choices.is_completer:
                    choices_func = arg_choices.choices_provider
                    if isinstance(choices_func, ChoicesProviderFuncWithTokens):
                        completion_items = choices_func(*args, **kwargs)
                    else:  # pragma: no cover
                        # This won't hit because runtime checking doesn't check function argument types and will always
                        # resolve true above.
                        completion_items = choices_func(*args)
                # else case is already covered above
            else:
                completion_items = arg_choices

            # Filter out arguments we already used
            used_values = consumed_arg_values.get(arg_state.action.dest, [])
            completion_items = [choice for choice in completion_items if choice not in used_values]

            # Do completion on the choices
            completions = self._cmd2_app.basic_complete(text, line, begidx, endidx, completion_items)
            if choices_sorted:
                completions.matches_sorted = choices_sorted

        self._prepare_formatted_exceptions(arg_state, completions)
        return completions


# The default ArgparseCompleter class for a cmd2 app
DEFAULT_AP_COMPLETER: type[ArgparseCompleter] = ArgparseCompleter


def set_default_ap_completer_type(completer_type: type[ArgparseCompleter]) -> None:
    """Set the default ArgparseCompleter class for a cmd2 app.

    :param completer_type: Type that is a subclass of ArgparseCompleter.
    """
    global DEFAULT_AP_COMPLETER  # noqa: PLW0603
    DEFAULT_AP_COMPLETER = completer_type
